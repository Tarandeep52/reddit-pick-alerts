"""Load non-secret settings from YAML and secrets from the environment.

Credentials (the Telegram bot token and chat id) are read ONLY from
environment variables, never from the config file or the code, so nothing
sensitive lands in the repo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

import yaml

DEFAULT_USER_AGENT = "reddit-pick-alerts/1.0 (alert-only; set your contact here)"


# A comment is treated as a pick if ANY of these regexes match (case-insensitive).
# Covers labelled stakes ("Stake: 5 units") and inline unit stakes ("3u", "5u",
# "3.5u"), since these tipsters switch between the two styles.
DEFAULT_TRIGGER_PATTERNS = [
    r"stake\s*[:=]",
    r"(?<![\w.])\d+(?:\.\d+)?\s*u(?:nits?)?\b",
]


@dataclass
class Config:
    usernames: List[str] = field(default_factory=list)
    poll_interval_seconds: int = 60
    trigger_patterns: List[str] = field(
        default_factory=lambda: list(DEFAULT_TRIGGER_PATTERNS))
    state_file: str = "state.json"
    timezone: str = "Asia/Kolkata"
    user_agent: str = DEFAULT_USER_AGENT
    request_timeout_seconds: float = 20
    max_backoff_seconds: float = 900
    no_poll_warning_minutes: int = 15


@dataclass
class Credentials:
    bot_token: str
    chat_id: str


def load_config(path: str) -> Config:
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    health = raw.get("health", {}) or {}
    # Prefer trigger_patterns; fall back to the default set. (Older configs that
    # only had trigger_keywords still work — the defaults cover their picks.)
    patterns = raw.get("trigger_patterns")
    if not patterns:
        patterns = list(DEFAULT_TRIGGER_PATTERNS)
    cfg = Config(
        usernames=list(raw.get("usernames", []) or []),
        poll_interval_seconds=int(raw.get("poll_interval_seconds", 60)),
        trigger_patterns=list(patterns),
        state_file=str(raw.get("state_file", "state.json")),
        timezone=str(raw.get("timezone", "Asia/Kolkata")),
        user_agent=str(raw.get("user_agent", DEFAULT_USER_AGENT)),
        request_timeout_seconds=float(raw.get("request_timeout_seconds", 20)),
        max_backoff_seconds=float(raw.get("max_backoff_seconds", 900)),
        no_poll_warning_minutes=int(health.get("no_poll_warning_minutes", 15)),
    )
    if not cfg.usernames:
        raise ValueError("config: 'usernames' must list at least one Reddit user")
    return cfg


def load_dotenv(path: str = ".env") -> None:
    """Load KEY=VALUE pairs from a .env file into the environment if present.

    Lightweight on purpose (no extra dependency). Existing environment
    variables are never overwritten, so real env/systemd values win.
    """
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass


def load_credentials() -> Credentials:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    missing = [n for n, v in (("TELEGRAM_BOT_TOKEN", token),
                              ("TELEGRAM_CHAT_ID", chat_id)) if not v]
    if missing:
        raise ValueError("missing environment variables: " + ", ".join(missing))
    return Credentials(bot_token=token, chat_id=chat_id)
