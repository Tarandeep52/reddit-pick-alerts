"""Alert-only tool that watches public Reddit comment RSS feeds and sends
Telegram notifications when a followed user posts a betting pick.

This package never places bets or talks to any sportsbook. It only reads a
public Atom feed and sends messages via the Telegram Bot API.
"""

__version__ = "1.0.0"
