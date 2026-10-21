from __future__ import annotations

import pytest

from conftest import FakeClock
from pyrometer.core import COLLECTOR_DURATION, COLLECTOR_ERRORS, Sample, Sampler
from pyrometer.storage import MemoryStorage


class Counter:
    name = "counter"

    def __init__(self, clock: FakeClock | None = None, cost: float = 0.0) -> None:
        self.calls = 0
        self.clock = clock
        self.cost = cost

    def collect(self, timestamp: float) -> list[Sample]:
        self.calls += 1
        if self.clock is not None:
            self.clock.t += self.cost
        return [Sample(timestamp, "calls", float(self.calls))]


class Broken:
    name = "broken"

    def collect(self, timestamp: float) -> list[Sample]:
        raise RuntimeError("boom")


def test_tick_writes_to_sinks_with_shared_timestamp() -> None:
    clock = FakeClock()
    store = MemoryStorage()
    sampler = Sampler([Counter(), Counter()], [store], clock=clock)
    samples = sampler.tick()
    assert samples == store.query()
    assert {s.timestamp for s in samples} == {clock.t}


def test_records_collector_cost() -> None:
    clock = FakeClock()
    sampler = Sampler([Counter(clock, cost=0.25)], clock=clock)
    durations = [s for s in sampler.tick() if s.name == COLLECTOR_DURATION]
    assert len(durations) == 1
    assert durations[0].value == pytest.approx(0.25)
    assert durations[0].tags == {"collector": "counter"}


def test_self_metrics_can_be_disabled() -> None:
    sampler = Sampler([Counter()], clock=FakeClock(), self_metrics=False)
    assert [s.name for s in sampler.tick()] == ["calls"]


def test_failing_collector_does_not_stop_others() -> None:
    good = Counter()
    sampler = Sampler([Broken(), good], clock=FakeClock())
    samples = sampler.tick()
    assert good.calls == 1
    errors = [s for s in samples if s.name == COLLECTOR_ERRORS]
    assert [e.tags["collector"] for e in errors] == ["broken"]


def test_run_iterations_and_interval() -> None:
    clock = FakeClock()
    c = Counter(clock, cost=0.1)
    ticks: list[list[Sample]] = []
    Sampler([c], interval=1.0, clock=clock).run(iterations=3, on_tick=ticks.append)
    assert c.calls == 3
    # Sleep compensates for the 0.1s spent collecting, so ticks stay 1s apart.
    assert clock.sleeps == [pytest.approx(0.9), pytest.approx(0.9)]
    stamps = [t[0].timestamp for t in ticks]
    assert [b - a for a, b in zip(stamps, stamps[1:])] == [pytest.approx(1.0)] * 2


def test_overrun_skips_missed_slots() -> None:
    clock = FakeClock()
    c = Counter(clock, cost=2.5)
    Sampler([c], interval=1.0, clock=clock).run(iterations=2)
    # Tick took 2.5s; slots at +1 and +2 are skipped, next tick waits for +3.
    assert clock.sleeps == [pytest.approx(0.5)]


def test_stop_from_callback() -> None:
    clock = FakeClock()
    sampler = Sampler([Counter()], clock=clock)
    seen: list[int] = []

    def on_tick(samples: list[Sample]) -> None:
        seen.append(1)
        if len(seen) == 2:
            sampler.stop()

    sampler.run(on_tick=on_tick)
    assert len(seen) == 2


def test_interval_must_be_positive() -> None:
    with pytest.raises(ValueError):
        Sampler([], interval=0)
