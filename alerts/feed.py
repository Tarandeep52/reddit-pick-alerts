"""Fetch and parse a user's public Reddit comment Atom feed.

RSS only, no HTML scraping and no Reddit login. A descriptive User-Agent is
required because Reddit blocks default/empty ones.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

import feedparser
import requests


class RateLimited(Exception):
    """Raised on HTTP 429 so the caller can back off (honouring Retry-After)."""

    def __init__(self, retry_after: Optional[float] = None):
        super().__init__("rate limited (HTTP 429)")
        self.retry_after = retry_after


@dataclass
class Comment:
    id: str
    link: str
    title: str
    updated: Optional[datetime]
    content_html: str


def feed_url(username: str) -> str:
    return f"https://www.reddit.com/user/{username}/comments.rss"


def _parse_retry_after(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_comments(username: str, user_agent: str, timeout: float = 20) -> List[Comment]:
    """Return the user's recent comments, newest first.

    Raises ``RateLimited`` on 429 and lets other network/HTTP errors propagate
    so the main loop can log them and back off. Never returns partial garbage:
    a feed that fails to parse yields an empty list.
    """
    resp = requests.get(
        feed_url(username),
        headers={
            "User-Agent": user_agent,
            "Accept": "application/atom+xml, application/xml, text/xml, */*",
        },
        timeout=timeout,
    )
    if resp.status_code == 429:
        raise RateLimited(_parse_retry_after(resp.headers.get("Retry-After")))
    resp.raise_for_status()

    parsed = feedparser.parse(resp.content)
    comments: List[Comment] = []
    for entry in parsed.entries:
        cid = entry.get("id") or entry.get("guid") or ""
        if not cid:
            continue

        link = entry.get("link", "")
        if not link and entry.get("links"):
            link = entry.links[0].get("href", "")

        updated = None
        tm = entry.get("updated_parsed") or entry.get("published_parsed")
        if tm:
            try:
                updated = datetime(*tm[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                updated = None

        content_html = ""
        if entry.get("content"):
            content_html = entry.content[0].get("value", "") or ""
        if not content_html:
            content_html = entry.get("summary", "") or ""

        comments.append(
            Comment(
                id=cid,
                link=link,
                title=entry.get("title", "") or "",
                updated=updated,
                content_html=content_html,
            )
        )
    return comments
