"""Clock abstraction so the sampler loop can be tested without real time."""

from __future__ import annotations

import time
from typing import Protocol


class Clock(Protocol):
    def now(self) -> float:
        """Wall-clock time in seconds since the epoch (used for sample timestamps)."""
        ...

    def monotonic(self) -> float:
        """Monotonic seconds (used for scheduling and durations)."""
        ...

    def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def now(self) -> float:
        return time.time()

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)
