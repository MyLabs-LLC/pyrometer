"""Shared pieces: the Sample data model, collector registry, clock and sampler loop."""

from __future__ import annotations

from pyrometer.core.clock import Clock, SystemClock
from pyrometer.core.collector import Collector, CollectorUnavailable, Registry, registry
from pyrometer.core.sample import Sample
from pyrometer.core.sampler import COLLECTOR_DURATION, COLLECTOR_ERRORS, Sampler, Sink

__all__ = [
    "COLLECTOR_DURATION",
    "COLLECTOR_ERRORS",
    "Clock",
    "Collector",
    "CollectorUnavailable",
    "Registry",
    "Sample",
    "Sampler",
    "Sink",
    "SystemClock",
    "registry",
]
