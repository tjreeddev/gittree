"""Polling-based change detection (R7). Uses only gitdata's read-only reader."""

from __future__ import annotations

from pathlib import Path

from gittree.gitdata import fingerprint

POLL_INTERVAL = 0.5  # seconds


class RepoWatcher:
    """Remembers the last fingerprint of HEAD and refs; reports when it changes."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self._last: str | None = None

    def has_changed(self) -> bool:
        """True if HEAD or any ref changed since the previous call.

        The first call only records a baseline and returns False.
        """
        current = fingerprint(self.root)
        if self._last is None:
            self._last = current
            return False
        changed = current != self._last
        self._last = current
        return changed
