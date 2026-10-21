"""Disk space per mount and I/O throughput per device."""

from __future__ import annotations

import psutil

from pyrometer.core.collector import registry
from pyrometer.core.sample import Sample
from pyrometer.gauge._rates import RateTracker

_IO_FIELDS = ("read_bytes", "write_bytes", "read_count", "write_count")

#: Read-only image filesystems that are always "100% full"; skipped by default.
IMAGE_FSTYPES = frozenset({"squashfs", "iso9660", "udf", "erofs", "cramfs"})


@registry.register("disk")
class DiskCollector:
    """Metrics:

    - ``disk.used_bytes``, ``disk.free_bytes``, ``disk.percent`` per mount
      (tags ``mount``, ``device``, ``fstype``). Mounts whose fstype is in
      ``skip_fstypes`` (read-only images by default) are left out.
    - ``disk.read_bytes_per_sec``, ``disk.write_bytes_per_sec``,
      ``disk.read_ops_per_sec``, ``disk.write_ops_per_sec`` per device
      (tag ``device``). Rates appear from the second collection onward.
    """

    name = "disk"

    def __init__(self, skip_fstypes: frozenset[str] = IMAGE_FSTYPES) -> None:
        self.skip_fstypes = skip_fstypes
        self._rates = RateTracker()

    def collect(self, timestamp: float) -> list[Sample]:
        samples: list[Sample] = []
        for part in psutil.disk_partitions(all=False):
            if part.fstype in self.skip_fstypes:
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (PermissionError, OSError):
                continue
            tags = {"mount": part.mountpoint, "device": part.device, "fstype": part.fstype}
            samples += [
                Sample(timestamp, "disk.used_bytes", float(usage.used), tags),
                Sample(timestamp, "disk.free_bytes", float(usage.free), tags),
                Sample(timestamp, "disk.percent", float(usage.percent), tags),
            ]

        counters = psutil.disk_io_counters(perdisk=True) or {}
        for device, io in counters.items():
            for field in _IO_FIELDS:
                rate = self._rates.rate((device, field), float(getattr(io, field)), timestamp)
                if rate is None:
                    continue
                metric = field.replace("_count", "_ops")
                samples.append(
                    Sample(timestamp, f"disk.{metric}_per_sec", rate, {"device": device})
                )
        return samples
