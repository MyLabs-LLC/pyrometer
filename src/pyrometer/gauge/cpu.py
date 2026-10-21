"""CPU utilisation and load."""

from __future__ import annotations

import os

import psutil

from pyrometer.core.collector import registry
from pyrometer.core.sample import Sample


@registry.register("cpu")
class CpuCollector:
    """Total and per-core CPU percent, plus load average where the OS has one.

    Metrics: ``cpu.percent`` (tag ``cpu=total`` or ``cpu=<n>``), ``cpu.count``,
    ``cpu.load1``/``cpu.load5``/``cpu.load15``.

    Percentages are measured between successive calls (non-blocking), so the
    collector primes psutil when it is built.
    """

    name = "cpu"

    def __init__(self, per_cpu: bool = True) -> None:
        self.per_cpu = per_cpu
        psutil.cpu_percent(interval=None, percpu=True)
        self._count = psutil.cpu_count(logical=True) or 0

    def collect(self, timestamp: float) -> list[Sample]:
        per_core = psutil.cpu_percent(interval=None, percpu=True)
        total = sum(per_core) / len(per_core) if per_core else 0.0
        samples = [
            Sample(timestamp, "cpu.percent", total, {"cpu": "total"}),
            Sample(timestamp, "cpu.count", float(self._count)),
        ]
        if self.per_cpu:
            samples.extend(
                Sample(timestamp, "cpu.percent", pct, {"cpu": str(i)})
                for i, pct in enumerate(per_core)
            )
        if hasattr(os, "getloadavg"):
            load1, load5, load15 = os.getloadavg()
            samples += [
                Sample(timestamp, "cpu.load1", load1),
                Sample(timestamp, "cpu.load5", load5),
                Sample(timestamp, "cpu.load15", load15),
            ]
        return samples
