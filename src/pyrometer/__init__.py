"""Pyrometer: performance monitoring for hosts and SQL Server.

Anvil forges it, Pyrometer tells you how hot it's running.
"""

from __future__ import annotations

__version__ = "0.1.0"

from pyrometer.core import Collector, Sample, Sampler, registry

__all__ = ["Collector", "Sample", "Sampler", "__version__", "registry"]
