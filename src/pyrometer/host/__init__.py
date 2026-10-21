"""Host layer: CPU, memory, disk, network and GPU collectors.

Importing this package registers the collectors under the names
``cpu``, ``memory``, ``disk``, ``network`` and ``gpu``. The GPU collector
imports ``pynvml`` only when it is built, so the base install never needs it.
"""

from __future__ import annotations

from pyrometer.host.cpu import CpuCollector
from pyrometer.host.disk import DiskCollector
from pyrometer.host.gpu import GpuCollector
from pyrometer.host.memory import MemoryCollector
from pyrometer.host.network import NetworkCollector

__all__ = ["CpuCollector", "DiskCollector", "GpuCollector", "MemoryCollector", "NetworkCollector"]
