from __future__ import annotations

import pytest

from pyrometer.core import Sample


def test_round_trip() -> None:
    s = Sample(1.5, "cpu.percent", 42.0, {"cpu": "total"})
    assert Sample.from_dict(s.to_dict()) == s


def test_tags_are_frozen_and_copied() -> None:
    tags = {"host": "a"}
    s = Sample(1.0, "x", 1.0, tags)
    tags["host"] = "b"
    assert s.tags["host"] == "a"
    with pytest.raises(TypeError):
        s.tags["host"] = "c"  # type: ignore[index]
