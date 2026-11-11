"""Compose and send the Telegram alert messages.

Field extraction is best-effort; whatever can't be parsed is shown as a dash,
and the full plain-text body is always included, so an alert is never dropped
because of a parsing failure.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python < 3.9
    ZoneInfo = None  # type: ignore

from . import telegram
from .feed import Comment
from .parse import Pick, extract_fields

log = logging.getLogger(__name__)

BODY_LIMIT = 800


def _fmt_num(value: Optional[float]) -> str:
    if value is None:
        return "—"
    # Show 1.9 not 1.90, and 5 not 5.0.
    if value == int(value):
        return str(int(value))
    return ("%.4f" % value).rstrip("0").rstrip(".")


def _local_time(comment: Comment, tz_name: str) -> str:
    dt = comment.updated
    if dt is None:
        dt = datetime.now(tz=dt.tzinfo if dt else None)
    try:
        if ZoneInfo is not None:
            dt = dt.astimezone(ZoneInfo(tz_name))
    except Exception:
        pass
    return dt.strftime("%Y-%m-%d %H:%M %Z") if dt else "unknown time"


def build_message(username: str, comment: Comment, plain_text: str,
                  tz_name: str, updated: bool = False) -> str:
    fields: Pick = extract_fields(plain_text)
    header = "✏️ UPDATED pick" if updated else "🔔 New pick"
    body = plain_text.strip()
    if len(body) > BODY_LIMIT:
        body = body[:BODY_LIMIT].rstrip() + " …"

    lines = [
        f"{header} from u/{username}",
        f"🕒 {_local_time(comment, tz_name)}",
        f"🎯 Pick: {fields.pick or '—'}",
        f"📊 Odds: {_fmt_num(fields.odds)}   "
        f"(min: {_fmt_num(fields.min_odds)})",
        f"💰 Stake: {_fmt_num(fields.stake)} units",
        "",
        body,
        "",
        comment.link or "",
    ]
    return "\n".join(line for line in lines if line is not None).strip()


def send_alert(creds, username: str, comment: Comment, plain_text: str,
               tz_name: str, updated: bool = False) -> bool:
    text = build_message(username, comment, plain_text, tz_name, updated=updated)
    ok = telegram.send_message(creds.bot_token, creds.chat_id, text)
    if ok:
        log.info("Sent %s alert for %s (%s)",
                 "UPDATED" if updated else "new", username, comment.id)
    return ok


def send_plain(creds, text: str) -> bool:
    """Send an arbitrary short message (health warnings, test alerts)."""
    return telegram.send_message(creds.bot_token, creds.chat_id, text)
