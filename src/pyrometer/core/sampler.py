"""The sampler loop: call every collector on an interval and fan samples out to sinks."""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterable, Sequence
from typing import Callable, Protocol

from pyrometer.core.clock import Clock, SystemClock
from pyrometer.core.collector import Collector
from pyrometer.core.sample import Sample

log = logging.getLogger(__name__)

#: Metric emitted for each collector on every tick: how long ``collect()`` took.
COLLECTOR_DURATION = "pyrometer.collector.duration_seconds"
#: Metric emitted when a collector raises; value is always 1.
COLLECTOR_ERRORS = "pyrometer.collector.errors"


class Sink(Protocol):
    def write(self, samples: Sequence[Sample]) -> None: ...


class Sampler:
    """Runs collectors on a fixed interval.

    The sampler knows nothing about what a collector measures. It also
    measures its own cost: each tick records how long every collector took,
    as ``pyrometer.collector.duration_seconds`` tagged with the collector
    name, so the monitor's overhead is visible next to the load it measures.

    A collector that raises is logged and counted, and does not stop the loop.
    """

    def __init__(
        self,
        collectors: Iterable[Collector],
        sinks: Iterable[Sink] = (),
        interval: float = 1.0,
        clock: Clock | None = None,
        self_metrics: bool = True,
    ) -> None:
        if interval <= 0:
            raise ValueError("interval must be positive")
        self.collectors = list(collectors)
        self.sinks = list(sinks)
        self.interval = interval
        self.clock: Clock = clock or SystemClock()
        self.self_metrics = self_metrics
        self._stop = threading.Event()

    def tick(self) -> list[Sample]:
        """Collect once from every collector, write to sinks, return the samples."""
        timestamp = self.clock.now()
        samples: list[Sample] = []
        for collector in self.collectors:
            started = self.clock.monotonic()
            try:
                samples.extend(collector.collect(timestamp))
            except Exception:
                log.exception("collector %s failed", collector.name)
                if self.self_metrics:
                    samples.append(
                        Sample(timestamp, COLLECTOR_ERRORS, 1.0, {"collector": collector.name})
                    )
            if self.self_metrics:
                elapsed = self.clock.monotonic() - started
                samples.append(
                    Sample(timestamp, COLLECTOR_DURATION, elapsed, {"collector": collector.name})
                )
        for sink in self.sinks:
            sink.write(samples)
        return samples

    def run(
        self,
        iterations: int | None = None,
        on_tick: Callable[[list[Sample]], None] | None = None,
    ) -> None:
        """Tick every ``interval`` seconds until ``stop()`` or ``iterations`` ticks.

        Ticks are scheduled against a monotonic clock so collector time does
        not cause drift. If a tick overruns, the missed slots are skipped
        rather than run back to back.
        """
        self._stop.clear()
        next_at = self.clock.monotonic()
        done = 0
        while not self._stop.is_set():
            samples = self.tick()
            if on_tick is not None:
                on_tick(samples)
            done += 1
            if iterations is not None and done >= iterations:
                break
            next_at += self.interval
            now = self.clock.monotonic()
            if next_at < now:
                missed = int((now - next_at) // self.interval) + 1
                next_at += missed * self.interval
            self._wait(next_at - now)

    def _wait(self, seconds: float) -> None:
        if isinstance(self.clock, SystemClock):
            self._stop.wait(seconds)
        else:
            self.clock.sleep(seconds)

    def stop(self) -> None:
        self._stop.set()
