from __future__ import annotations

import pytest

from pyrometer.core import CollectorUnavailable, Registry, Sample


class Ok:
    name = "ok"

    def collect(self, timestamp: float) -> list[Sample]:
        return [Sample(timestamp, "ok", 1.0)]


def test_register_and_create() -> None:
    reg = Registry()
    reg.register("ok")(Ok)
    assert reg.names() == ["ok"]
    assert isinstance(reg.create("ok"), Ok)


def test_duplicate_name_rejected() -> None:
    reg = Registry()
    reg.register("ok")(Ok)
    with pytest.raises(ValueError):
        reg.register("ok")(Ok)


def test_unknown_name() -> None:
    with pytest.raises(KeyError, match="unknown collector"):
        Registry().create("nope")


def test_create_available_skips_unavailable() -> None:
    reg = Registry()
    reg.register("ok")(Ok)

    @reg.register("missing")
    def missing() -> Ok:
        raise CollectorUnavailable("not installed")

    built, skipped = reg.create_available()
    assert [c.name for c in built] == ["ok"]
    assert skipped == {"missing": "not installed"}


def test_host_collectors_registered() -> None:
    import pyrometer.host  # noqa: F401
    from pyrometer.core import registry

    assert {"cpu", "memory", "disk", "network", "gpu"} <= set(registry.names())
