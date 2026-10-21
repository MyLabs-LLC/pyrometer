"""Network throughput and errors per interface."""

from __future__ import annotations

import psutil

from pyrometer.core.collector import registry
from pyrometer.core.sample import Sample
from pyrometer.host._rates import RateTracker

_FIELDS = {
    "bytes_sent": "net.sent_bytes_per_sec",
    "bytes_recv": "net.recv_bytes_per_sec",
    "packets_sent": "net.sent_packets_per_sec",
    "packets_recv": "net.recv_packets_per_sec",
    "errin": "net.errors_in_per_sec",
    "errout": "net.errors_out_per_sec",
    "dropin": "net.drops_in_per_sec",
    "dropout": "net.drops_out_per_sec",
}


@registry.register("network")
class NetworkCollector:
    """Per-interface rates (tag ``interface``); see ``_FIELDS`` for metric names.

    Rates appear from the second collection onward. Loopback is skipped
    unless ``include_loopback`` is set.
    """

    name = "network"

    def __init__(self, include_loopback: bool = False) -> None:
        self.include_loopback = include_loopback
        self._rates = RateTracker()

    def collect(self, timestamp: float) -> list[Sample]:
        samples: list[Sample] = []
        for nic, counters in psutil.net_io_counters(pernic=True).items():
            if not self.include_loopback and _is_loopback(nic):
                continue
            for field, metric in _FIELDS.items():
                rate = self._rates.rate((nic, field), float(getattr(counters, field)), timestamp)
                if rate is not None:
                    samples.append(Sample(timestamp, metric, rate, {"interface": nic}))
        return samples


def _is_loopback(nic: str) -> bool:
    return nic == "lo" or nic.startswith("lo0") or "loopback" in nic.lower()
