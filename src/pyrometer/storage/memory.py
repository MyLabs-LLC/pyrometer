"""Bounded in-memory sample store."""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Mapping, Sequence

from pyrometer.core.sample import Sample


class MemoryStorage:
    """Keeps the most recent ``max_samples`` samples in a ring buffer."""

    def __init__(self, max_samples: int = 100_000) -> None:
        self._samples: deque[Sample] = deque(maxlen=max_samples)
        self._lock = threading.Lock()

    def write(self, samples: Sequence[Sample]) -> None:
        with self._lock:
            self._samples.extend(samples)

    def query(
        self,
        name: str | None = None,
        since: float | None = None,
        until: float | None = None,
        tags: Mapping[str, str] | None = None,
    ) -> list[Sample]:
        with self._lock:
            snapshot = list(self._samples)
        return [s for s in snapshot if _matches(s, name, since, until, tags)]

    def __len__(self) -> int:
        return len(self._samples)

    def close(self) -> None:
        pass


def _matches(
    sample: Sample,
    name: str | None,
    since: float | None,
    until: float | None,
    tags: Mapping[str, str] | None,
) -> bool:
    if name is not None and sample.name != name:
        return False
    if since is not None and sample.timestamp < since:
        return False
    if until is not None and sample.timestamp > until:
        return False
    return not tags or all(sample.tags.get(k) == v for k, v in tags.items())
