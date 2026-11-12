#!/usr/bin/env python3
"""Watch Reddit comment feeds and send Telegram alerts on new betting picks.

Alert-only. This program never places a bet or contacts a sportsbook.

Usage:
    python main.py                 # run forever (default config.yaml)
    python main.py --once          # run a single poll cycle and exit
    python main.py --config my.yaml
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from alerts import feed, notifier
from alerts.config import load_config, load_credentials, load_dotenv
from alerts.feed import RateLimited
from alerts.parse import matches_any_pattern, text_hash, to_plain_text
from alerts.state import Store

log = logging.getLogger("reddit-pick-alerts")


def process_user(username, comments, store, cfg, creds):
    """Handle one user's comments. Returns the number of alerts sent."""
    # First time we see this user: record everything as seen, alert nothing.
    if not store.is_baselined(username):
        for c in comments:
            store.put(c.id, text_hash(to_plain_text(c.content_html)), False)
        store.mark_baselined(username)
        store.save()
        log.info("Baselined u/%s with %d existing comments (no alerts).",
                 username, len(comments))
        return 0

    alerts_sent = 0
    # Feed is newest-first; process oldest-first so alerts arrive in order.
    for c in reversed(comments):
        try:
            plain = to_plain_text(c.content_html)
            h = text_hash(plain)
            is_pick = matches_any_pattern(plain, cfg.trigger_patterns)
            rec = store.get(c.id)

            if rec is None:
                # Brand-new comment.
                if is_pick:
                    notifier.send_alert(creds, username, c, plain, cfg.timezone)
                    store.put(c.id, h, True)
                    alerts_sent += 1
                else:
                    store.put(c.id, h, False)
            elif rec.get("alerted"):
                # We alerted this one before; a text change is an edit.
                if h != rec.get("hash"):
                    notifier.send_alert(creds, username, c, plain, cfg.timezone,
                                        updated=True)
                    store.put(c.id, h, True)
                    alerts_sent += 1
            else:
                # Seen before but never alerted (was not a pick then).
                if h != rec.get("hash"):
                    if is_pick:
                        notifier.send_alert(creds, username, c, plain, cfg.timezone)
                        store.put(c.id, h, True)
                        alerts_sent += 1
                    else:
                        store.put(c.id, h, False)
        except Exception:  # one bad comment must not stop the rest
            log.exception("Failed to process comment %s from u/%s", c.id, username)

    store.save()
    return alerts_sent


def poll_once(cfg, creds, store):
    """One cycle across all users. Returns True if at least one fetch worked."""
    any_success = False
    retry_after = None
    for username in cfg.usernames:
        try:
            comments = feed.fetch_comments(
                username, cfg.user_agent, timeout=cfg.request_timeout_seconds)
            process_user(username, comments, store, cfg, creds)
            any_success = True
        except RateLimited as exc:
            log.warning("Rate limited on u/%s (retry after %s).",
                        username, exc.retry_after)
            if exc.retry_after:
                retry_after = max(retry_after or 0, exc.retry_after)
        except Exception:
            log.exception("Poll failed for u/%s", username)
    return any_success, retry_after


def run(cfg, creds):
    store = Store(cfg.state_file)
    health_threshold = cfg.no_poll_warning_minutes * 60
    last_success = time.monotonic()
    consecutive_failures = 0
    health_warned = False

    log.info("Watching %s every %ds. Alert-only; no bets are ever placed.",
             ", ".join("u/" + u for u in cfg.usernames), cfg.poll_interval_seconds)

    while True:
        any_success, retry_after = poll_once(cfg, creds, store)
        now = time.monotonic()

        if any_success:
            last_success = now
            consecutive_failures = 0
            if health_warned:
                notifier.send_plain(creds, "✅ Reddit pick alerts: polling recovered.")
                health_warned = False
        else:
            consecutive_failures += 1
            if now - last_success >= health_threshold and not health_warned:
                mins = int((now - last_success) // 60)
                notifier.send_plain(
                    creds,
                    f"⚠️ Reddit pick alerts: no successful poll for ~{mins} min. "
                    "You may be missing picks.")
                health_warned = True

        if any_success and not retry_after:
            sleep_for = cfg.poll_interval_seconds
        else:
            backoff = cfg.poll_interval_seconds * (2 ** min(consecutive_failures, 8))
            sleep_for = min(retry_after or backoff, cfg.max_backoff_seconds)
            log.info("Backing off for %.0fs.", sleep_for)

        time.sleep(sleep_for)


def main():
    ap = argparse.ArgumentParser(description="Alert-only Reddit betting-pick watcher.")
    ap.add_argument("--config", default="config.yaml", help="path to config YAML")
    ap.add_argument("--env", default=".env", help="path to .env file (optional)")
    ap.add_argument("--once", action="store_true", help="run one poll cycle and exit")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    load_dotenv(args.env)
    cfg = load_config(args.config)
    creds = load_credentials()

    if args.once:
        store = Store(cfg.state_file)
        ok, _ = poll_once(cfg, creds, store)
        # Non-zero on a fully failed cycle so GitHub Actions shows a red run.
        sys.exit(0 if ok else 1)

    try:
        run(cfg, creds)
    except KeyboardInterrupt:
        log.info("Stopped.")


if __name__ == "__main__":
    main()
