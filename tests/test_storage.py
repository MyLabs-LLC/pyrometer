from __future__ import annotations

from pathlib import Path
from typing import Union

import pytest

from pyrometer.core import Sample
from pyrometer.storage import MemoryStorage, SQLiteStorage

Store = Union[MemoryStorage, SQLiteStorage]

SAMPLES = [
    Sample(1.0, "cpu.percent", 10.0, {"cpu": "total"}),
    Sample(1.0, "cpu.percent", 20.0, {"cpu": "0"}),
    Sample(2.0, "cpu.percent", 30.0, {"cpu": "total"}),
    Sample(2.0, "memory.percent", 50.0),
]


@pytest.fixture(params=["memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> Store:
    if request.param == "memory":
        return MemoryStorage()
    return SQLiteStorage(tmp_path / "samples.db")


def test_query_all(store: Store) -> None:
    store.write(SAMPLES)
    assert store.query() == SAMPLES


def test_query_filters(store: Store) -> None:
    store.write(SAMPLES)
    assert store.query(name="memory.percent") == [SAMPLES[3]]
    assert store.query(since=2.0) == SAMPLES[2:]
    assert store.query(until=1.0) == SAMPLES[:2]
    assert store.query(name="cpu.percent", tags={"cpu": "total"}) == [SAMPLES[0], SAMPLES[2]]


def test_empty_write(store: Store) -> None:
    store.write([])
    assert store.query() == []


def test_memory_is_bounded() -> None:
    store = MemoryStorage(max_samples=2)
    store.write(SAMPLES)
    assert store.query() == SAMPLES[2:]


def test_sqlite_persists(tmp_path: Path) -> None:
    path = tmp_path / "p.db"
    first = SQLiteStorage(path)
    first.write(SAMPLES)
    first.close()
    second = SQLiteStorage(path)
    assert second.query() == SAMPLES
    second.close()
