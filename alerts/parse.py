"""Turn a comment's HTML-escaped body into plain text and pull out the
pick / odds / stake / minimum-odds fields.

Everything here is best-effort: extraction returns ``None`` for a field it
cannot find rather than raising, so a parsing miss never costs an alert.
"""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass
from typing import Optional

# A decimal or integer number, e.g. 1.95 or 5
_NUM = r"(\d+(?:\.\d+)?)"


def to_plain_text(raw: Optional[str]) -> str:
    """Unescape HTML entities, drop tags, and normalise whitespace.

    Reddit's Atom ``<content>`` is HTML-escaped (``&lt;strong&gt;`` ...), and
    sometimes double-escaped, so we unescape, convert block/break tags to
    newlines, strip the remaining tags, then unescape once more.
    """
    if not raw:
        return ""
    text = html.unescape(raw)
    # Some feeds double-escape; a second pass is safe and idempotent.
    if "&lt;" in text or "&gt;" in text or "&amp;" in text:
        text = html.unescape(text)
    # Line breaks and block closers become newlines so structure survives.
    text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", text)
    text = re.sub(r"(?i)</\s*(?:p|div|h[1-6]|li|tr)\s*>", "\n", text)
    # Strip every remaining tag.
    text = re.sub(r"<[^>]+>", "", text)
    # Entities that were hidden inside tags before stripping.
    text = html.unescape(text)
    # Collapse runs of spaces/tabs and blank lines.
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def text_hash(plain_text: str) -> str:
    """Stable hash of the normalised comment text, for edit detection."""
    return hashlib.sha256(plain_text.strip().encode("utf-8")).hexdigest()


def contains_all_keywords(plain_text: str, keywords) -> bool:
    """True when every trigger keyword is present (case-insensitive)."""
    low = plain_text.lower()
    return all(str(k).lower() in low for k in keywords)


@dataclass
class Pick:
    pick: Optional[str] = None
    odds: Optional[float] = None
    stake: Optional[float] = None
    min_odds: Optional[float] = None


def extract_odds(text: str) -> Optional[float]:
    """Posted odds. Prefers a labelled ``Odds:`` value, else a loose decimal
    that is not part of an over/under total (``u4.5``) or a unit count."""
    m = re.search(r"odds\s*[:=]?\s*\[?\s*" + _NUM, text, re.I)
    if m:
        return float(m.group(1))
    # Fallback: a decimal in a plausible odds range, not glued to a letter
    # (so "u4.5 goals" / "o2.5" totals are skipped by the look-behind).
    for mm in re.finditer(r"(?<![\w.])" + _NUM, text):
        token = mm.group(1)
        if "." not in token:
            continue
        val = float(token)
        if 1.1 <= val <= 50:
            return val
    return None


def extract_stake(text: str) -> Optional[float]:
    """Stake in units. Labelled ``Stake:`` first, else ``5 units`` / ``5U``."""
    m = re.search(r"stake\s*[:=]?\s*" + _NUM, text, re.I)
    if m:
        return float(m.group(1))
    m = re.search(_NUM + r"\s*u(?:nits?)?\b", text, re.I)
    if m:
        return float(m.group(1))
    return None


def extract_min_odds(text: str) -> Optional[float]:
    """Minimum acceptable odds from phrases the tipster uses."""
    m = re.search(r"(?:take\s+it\s+at|take\s+at|get\s+it\s+at|at)\s*" + _NUM +
                  r"\s*or\s+better", text, re.I)
    if m:
        return float(m.group(1))
    m = re.search(r"(?:don'?t\s+take\s+(?:it\s+)?below|not\s+below|no\s+lower\s+than|below)\s*"
                  + _NUM, text, re.I)
    if m:
        return float(m.group(1))
    return None


def extract_pick(text: str) -> Optional[str]:
    """The selection line. Prefers a ``PICK:`` line, else the first line."""
    m = re.search(r"(?im)^\s*pick\s*[:\-]\s*(.+?)\s*$", text)
    if m:
        return m.group(1).strip()
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return None


def extract_fields(text: str) -> Pick:
    """Best-effort extraction of all fields; never raises on bad input."""
    pick = odds = stake = min_odds = None
    try:
        pick = extract_pick(text)
    except Exception:
        pass
    try:
        odds = extract_odds(text)
    except Exception:
        pass
    try:
        stake = extract_stake(text)
    except Exception:
        pass
    try:
        min_odds = extract_min_odds(text)
    except Exception:
        pass
    return Pick(pick=pick, odds=odds, stake=stake, min_odds=min_odds)
