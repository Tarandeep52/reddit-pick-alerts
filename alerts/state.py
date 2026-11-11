"""Durable dedupe/edit state in a JSON file.

Shape::

    {
      "baselined": ["Suspicious-Cow-1909"],   # users whose existing comments
                                               # were recorded without alerting
      "ids": {                                 # every comment id we've seen
        "t1_abc": {"hash": "...", "alerted": true}
      }
    }

A user is "baselined" on its first poll: all current comments are marked seen
without alerting, so restarts and newly-added tipsters never spam old picks.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from typing import Optional

log = logging.getLogger(__name__)


class Store:
    def __init__(self, path: str):
        self.path = path
        self.data = {"baselined": [], "ids": {}}
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                self.data["baselined"] = list(loaded.get("baselined", []))
                self.data["ids"] = dict(loaded.get("ids", {}))
        except FileNotFoundError:
            pass
        except (json.JSONDecodeError, OSError) as exc:
            # Corrupt or unreadable state: start fresh rather than crash, but
            # keep the bad file aside so nothing is silently lost.
            log.error("Could not read state file %s (%s); starting fresh.", self.path, exc)
            try:
                os.replace(self.path, self.path + ".corrupt")
            except OSError:
                pass

    def save(self) -> None:
        """Atomic write: temp file in the same dir, then rename."""
        directory = os.path.dirname(os.path.abspath(self.path)) or "."
        try:
            os.makedirs(directory, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=directory, prefix=".state-", suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except OSError as exc:
            log.error("Could not write state file %s: %s", self.path, exc)

    # --- baseline tracking ------------------------------------------------
    def is_baselined(self, username: str) -> bool:
        return username in self.data["baselined"]

    def mark_baselined(self, username: str) -> None:
        if username not in self.data["baselined"]:
            self.data["baselined"].append(username)

    # --- per-comment records ---------------------------------------------
    def get(self, comment_id: str) -> Optional[dict]:
        return self.data["ids"].get(comment_id)

    def put(self, comment_id: str, text_hash: str, alerted: bool) -> None:
        self.data["ids"][comment_id] = {"hash": text_hash, "alerted": alerted}
