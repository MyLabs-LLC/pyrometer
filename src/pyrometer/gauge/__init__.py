"""Host layer (Gauge): CPU, memory, disk, network and GPU collectors.

Importing this package registers the collectors under the names
``cpu``, ``memory``, ``disk``, ``network`` and ``gpu``. The GPU collector
imports ``pynvml`` only when it is built, so the base install never needs it.
"""

from __future__ import annotations

from pyrometer.gauge.cpu import CpuCollector
from pyrometer.gauge.disk import DiskCollector
from pyrometer.gauge.gpu import GpuCollector
from pyrometer.gauge.memory import MemoryCollector
from pyrometer.gauge.network import NetworkCollector

__all__ = ["CpuCollector", "DiskCollector", "GpuCollector", "MemoryCollector", "NetworkCollector"]
