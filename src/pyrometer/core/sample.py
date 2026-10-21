"""The single data model shared by every layer."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True)
class Sample:
    """One measurement: a metric name and value at a point in time, with tags.

    Host metrics and SQL Server metrics use this same shape so they can be
    stored together and shown on one timeline. Tags carry the dimensions
    (host, device, instance, database, session, query hash, wait type...).
    """

    timestamp: float
    name: str
    value: float
    tags: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Freeze tags so a Sample is safe to share between sinks.
        object.__setattr__(self, "tags", MappingProxyType(dict(self.tags)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "name": self.name,
            "value": self.value,
            "tags": dict(self.tags),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Sample:
        return cls(
            timestamp=float(data["timestamp"]),
            name=str(data["name"]),
            value=float(data["value"]),
            tags={str(k): str(v) for k, v in dict(data.get("tags") or {}).items()},
        )
