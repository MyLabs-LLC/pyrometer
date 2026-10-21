"""Virtual memory and swap."""

from __future__ import annotations

import psutil

from pyrometer.core.collector import registry
from pyrometer.core.sample import Sample


@registry.register("memory")
class MemoryCollector:
    """Metrics: ``memory.total_bytes``, ``memory.available_bytes``,
    ``memory.used_bytes``, ``memory.percent``, ``swap.used_bytes``, ``swap.percent``.
    """

    name = "memory"

    def collect(self, timestamp: float) -> list[Sample]:
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return [
            Sample(timestamp, "memory.total_bytes", float(vm.total)),
            Sample(timestamp, "memory.available_bytes", float(vm.available)),
            Sample(timestamp, "memory.used_bytes", float(vm.used)),
            Sample(timestamp, "memory.percent", float(vm.percent)),
            Sample(timestamp, "swap.used_bytes", float(swap.used)),
            Sample(timestamp, "swap.percent", float(swap.percent)),
        ]
