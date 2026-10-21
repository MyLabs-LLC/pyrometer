"""Turn cumulative OS counters into per-second rates."""

from __future__ import annotations

from collections.abc import Hashable


class RateTracker:
    """Remembers the previous value of each counter and returns its rate.

    The first observation of a counter has no rate (returns ``None``). A
    counter that goes backwards (wrap or reset, e.g. a NIC re-attached) is
    treated as a fresh start rather than reported as a negative rate.
    """

    def __init__(self) -> None:
        self._last: dict[Hashable, tuple[float, float]] = {}

    def rate(self, key: Hashable, value: float, timestamp: float) -> float | None:
        previous = self._last.get(key)
        self._last[key] = (timestamp, value)
        if previous is None:
            return None
        last_ts, last_value = previous
        elapsed = timestamp - last_ts
        if elapsed <= 0 or value < last_value:
            return None
        return (value - last_value) / elapsed
