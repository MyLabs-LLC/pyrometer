from __future__ import annotations

import json
from pathlib import Path

import pytest

from pyrometer import __version__
from pyrometer.cli import main, render_summary
from pyrometer.core import Sample
from pyrometer.storage import SQLiteStorage


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["--version"])
    assert __version__ in capsys.readouterr().out


def test_collectors(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["collectors"]) == 0
    out = capsys.readouterr().out
    assert "cpu" in out and "available" in out


def test_watch_summary(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["watch", "-n", "1", "-c", "cpu,memory"]) == 0
    out = capsys.readouterr().out
    assert "CPU" in out and "Memory" in out


def test_watch_json_and_db(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    db = tmp_path / "w.db"
    assert main(["watch", "-n", "2", "-i", "0.05", "-c", "memory", "--json", "--db", str(db)]) == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert any(d["name"] == "memory.percent" for d in lines)
    store = SQLiteStorage(db)
    assert len(store.query(name="memory.percent")) == 2
    store.close()


def test_watch_unknown_collector(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["watch", "-n", "1", "-c", "nope"]) == 2
    assert "unknown collector" in capsys.readouterr().err


def test_bench(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["bench", "-n", "3", "-i", "0.01", "-c", "cpu,memory"]) == 0
    out = capsys.readouterr().out
    assert "mean ms" in out and "memory" in out


def test_render_summary() -> None:
    text = render_summary(
        [
            Sample(1, "cpu.percent", 50.0, {"cpu": "total"}),
            Sample(1, "memory.percent", 25.0),
            Sample(1, "memory.used_bytes", 1024.0**3),
            Sample(1, "memory.total_bytes", 4 * 1024.0**3),
            Sample(1, "net.recv_bytes_per_sec", 2048.0, {"interface": "eth0"}),
            Sample(1, "gpu.utilization_percent", 80.0, {"gpu": "0", "model": "X"}),
        ]
    )
    assert "50.0%" in text
    assert "1.0 GiB / 4.0 GiB" in text
    assert "recv 2.0 KiB/s" in text
    assert "GPU 0" in text
