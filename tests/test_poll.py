"""Tests for the polling cycle's rate-limit handling.

These guard the bug where the second user fetched in a cycle hit a 429 and was
silently skipped forever (so that user never got baselined or alerted).
"""

import main
from alerts.config import Config
from alerts.feed import Comment, RateLimited


def _cfg(**over):
    c = Config(
        usernames=["userA", "userB"],
        per_user_delay_seconds=0,     # no real sleeping in tests
        fetch_attempts=3,
        retry_429_wait_seconds=0,
        max_429_wait_seconds=0,
    )
    for k, v in over.items():
        setattr(c, k, v)
    return c


def test_retry_recovers_from_a_transient_429(monkeypatch):
    """A user that 429s once then succeeds must still be processed."""
    calls = {"userA": 0, "userB": 0}

    def fake_fetch(username, user_agent, timeout=20):
        calls[username] += 1
        if username == "userB" and calls[username] == 1:
            raise RateLimited(retry_after=0)      # first attempt fails
        return [Comment(id=f"{username}1", link="", title="", updated=None,
                        content_html="Stake: 1u")]

    processed = []
    monkeypatch.setattr(main.feed, "fetch_comments", fake_fetch)
    monkeypatch.setattr(main, "process_user",
                        lambda u, c, s, cfg, cr: processed.append(u))
    monkeypatch.setattr(main.time, "sleep", lambda *_: None)
    monkeypatch.setattr(main.random, "shuffle", lambda seq: None)  # deterministic

    ok, _ = main.poll_once(_cfg(), creds=None, store=None)

    assert ok is True
    assert set(processed) == {"userA", "userB"}   # BOTH users handled
    assert calls["userB"] == 2                     # retried after the 429


def test_one_user_failing_does_not_block_the_other(monkeypatch):
    """If a user 429s on every attempt, the other user is still processed."""
    def fake_fetch(username, user_agent, timeout=20):
        if username == "userB":
            raise RateLimited(retry_after=0)
        return [Comment(id="a1", link="", title="", updated=None,
                        content_html="Stake: 1u")]

    processed = []
    monkeypatch.setattr(main.feed, "fetch_comments", fake_fetch)
    monkeypatch.setattr(main, "process_user",
                        lambda u, c, s, cfg, cr: processed.append(u))
    monkeypatch.setattr(main.time, "sleep", lambda *_: None)
    monkeypatch.setattr(main.random, "shuffle", lambda seq: None)

    ok, _ = main.poll_once(_cfg(), creds=None, store=None)

    assert ok is True
    assert processed == ["userA"]
