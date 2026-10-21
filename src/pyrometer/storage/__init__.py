"""Where samples go. Every store is a ``Sink`` (has ``write``) and can be queried."""

from __future__ import annotations

from pyrometer.storage.memory import MemoryStorage
from pyrometer.storage.sqlite import SQLiteStorage

__all__ = ["MemoryStorage", "SQLiteStorage"]
