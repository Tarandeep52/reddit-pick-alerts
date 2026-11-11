"""Minimal Telegram Bot API client: sendMessage only.

Credentials are passed in from the environment by the caller; nothing here
reads or stores them. A send failure is logged and reported as ``False``; it
never raises, so one bad send cannot crash the poll loop.
"""

from __future__ import annotations

import logging

import requests

log = logging.getLogger(__name__)

# Telegram hard-caps a message at 4096 characters.
MAX_LEN = 4096


def send_message(token: str, chat_id: str, text: str,
                 disable_preview: bool = False, timeout: float = 20) -> bool:
    if not token or not chat_id:
        log.error("Telegram token or chat id missing; cannot send.")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text[:MAX_LEN],
                "disable_web_page_preview": disable_preview,
            },
            timeout=timeout,
        )
    except requests.RequestException as exc:
        log.error("Telegram send failed (network): %s", exc)
        return False

    if resp.status_code == 200:
        try:
            if resp.json().get("ok"):
                return True
        except ValueError:
            pass
    log.error("Telegram send failed: HTTP %s %s", resp.status_code, resp.text[:300])
    return False
