#!/usr/bin/env python3
"""Send one fake alert so you can confirm Telegram is wired up correctly.

Usage (from the project root):
    python -m tools.send_test_alert
    python tools/send_test_alert.py --config config.yaml

It builds a realistic sample pick and sends it through the same code path the
watcher uses. It never touches Reddit or any sportsbook.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

# Allow running as a plain script (python tools/send_test_alert.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alerts import notifier  # noqa: E402
from alerts.config import load_config, load_credentials, load_dotenv  # noqa: E402
from alerts.feed import Comment  # noqa: E402

SAMPLE_BODY = (
    "PICK: Atlético Madrid Double Chance\n"
    "Odds: [1.95] (only take it at 1.85 or better)\n"
    "Stake: 5 units\n"
    "(This is a TEST alert from send_test_alert.py — not a real pick.)"
)


def main():
    ap = argparse.ArgumentParser(description="Send a fake Telegram alert.")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--env", default=".env")
    args = ap.parse_args()

    load_dotenv(args.env)
    cfg = load_config(args.config)
    creds = load_credentials()

    comment = Comment(
        id="t1_testalert",
        link="https://www.reddit.com/r/sportsbook/comments/example/",
        title="[TEST] Pick of the Day thread",
        updated=datetime.now(timezone.utc),
        content_html=SAMPLE_BODY,
    )
    username = cfg.usernames[0] if cfg.usernames else "test-user"
    ok = notifier.send_alert(creds, username, comment, SAMPLE_BODY, cfg.timezone)
    print("Test alert sent ✅" if ok else "Test alert FAILED ❌ — check token/chat id.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
