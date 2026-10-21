from __future__ import annotations

import sys
import time
from collections import namedtuple

import pytest

from pyrometer.core import CollectorUnavailable
from pyrometer.host import (
    CpuCollector,
    DiskCollector,
    GpuCollector,
    MemoryCollector,
    NetworkCollector,
)
from pyrometer.host._rates import RateTracker


def names(samples: list) -> set[str]:
    return {s.name for s in samples}


def test_rate_tracker() -> None:
    r = RateTracker()
    assert r.rate("k", 100.0, 10.0) is None
    assert r.rate("k", 300.0, 12.0) == pytest.approx(100.0)
    assert r.rate("k", 50.0, 13.0) is None  # counter reset
    assert r.rate("k", 60.0, 14.0) == pytest.approx(10.0)
    assert r.rate("k", 70.0, 14.0) is None  # no elapsed time


def test_cpu() -> None:
    samples = CpuCollector().collect(time.time())
    total = [s for s in samples if s.name == "cpu.percent" and s.tags["cpu"] == "total"]
    assert len(total) == 1
    assert 0.0 <= total[0].value <= 100.0
    assert "cpu.count" in names(samples)


def test_cpu_without_per_core() -> None:
    samples = CpuCollector(per_cpu=False).collect(time.time())
    assert {s.tags.get("cpu") for s in samples if s.name == "cpu.percent"} == {"total"}


def test_memory() -> None:
    samples = {s.name: s.value for s in MemoryCollector().collect(time.time())}
    assert samples["memory.total_bytes"] > 0
    assert 0.0 <= samples["memory.percent"] <= 100.0


def test_disk_rates_start_on_second_call(monkeypatch: pytest.MonkeyPatch) -> None:
    import pyrometer.host.disk as disk

    IO = namedtuple("IO", "read_bytes write_bytes read_count write_count")
    readings = iter([{"sda": IO(0, 0, 0, 0)}, {"sda": IO(4096, 8192, 1, 2)}])
    monkeypatch.setattr(disk.psutil, "disk_partitions", lambda all=False: [])
    monkeypatch.setattr(disk.psutil, "disk_io_counters", lambda perdisk=True: next(readings))

    c = DiskCollector()
    assert c.collect(0.0) == []
    rates = {s.name: s.value for s in c.collect(2.0)}
    assert rates == {
        "disk.read_bytes_per_sec": 2048.0,
        "disk.write_bytes_per_sec": 4096.0,
        "disk.read_ops_per_sec": 0.5,
        "disk.write_ops_per_sec": 1.0,
    }


def test_disk_skips_image_filesystems(monkeypatch: pytest.MonkeyPatch) -> None:
    import pyrometer.host.disk as disk

    Part = namedtuple("Part", "device mountpoint fstype opts")
    Usage = namedtuple("Usage", "total used free percent")
    parts = [Part("/dev/sda1", "/", "ext4", "rw"), Part("/dev/loop0", "/snap/x", "squashfs", "ro")]
    monkeypatch.setattr(disk.psutil, "disk_partitions", lambda all=False: parts)
    monkeypatch.setattr(disk.psutil, "disk_usage", lambda m: Usage(100, 40, 60, 40.0))
    monkeypatch.setattr(disk.psutil, "disk_io_counters", lambda perdisk=True: {})

    mounts = {s.tags["mount"] for s in DiskCollector().collect(0.0)}
    assert mounts == {"/"}
    everything = {s.tags["mount"] for s in DiskCollector(skip_fstypes=frozenset()).collect(0.0)}
    assert everything == {"/", "/snap/x"}


def test_disk_real() -> None:
    c = DiskCollector()
    first = c.collect(time.time())
    if not any(s.name == "disk.percent" for s in first):
        pytest.skip("no mounted partitions visible")
    assert all(0.0 <= s.value <= 100.0 for s in first if s.name == "disk.percent")


def test_network_rates_and_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    import pyrometer.host.network as net

    fields = "bytes_sent bytes_recv packets_sent packets_recv errin errout dropin dropout"
    Nic = namedtuple("Nic", fields)
    readings = iter(
        [
            {"eth0": Nic(0, 0, 0, 0, 0, 0, 0, 0), "lo": Nic(0, 0, 0, 0, 0, 0, 0, 0)},
            {"eth0": Nic(1000, 2000, 10, 20, 0, 0, 0, 1), "lo": Nic(5, 5, 5, 5, 0, 0, 0, 0)},
        ]
    )
    monkeypatch.setattr(net.psutil, "net_io_counters", lambda pernic=True: next(readings))

    c = NetworkCollector()
    assert c.collect(0.0) == []
    samples = c.collect(1.0)
    assert {s.tags["interface"] for s in samples} == {"eth0"}
    values = {s.name: s.value for s in samples}
    assert values["net.sent_bytes_per_sec"] == 1000.0
    assert values["net.recv_bytes_per_sec"] == 2000.0
    assert values["net.drops_out_per_sec"] == 1.0


def test_network_real() -> None:
    c = NetworkCollector(include_loopback=True)
    c.collect(time.time())
    time.sleep(0.05)
    assert all(s.value >= 0 for s in c.collect(time.time()))


def test_gpu_unavailable_without_pynvml(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pynvml", None)
    with pytest.raises(CollectorUnavailable, match="nvidia-ml-py"):
        GpuCollector()


def test_gpu_with_fake_nvml(monkeypatch: pytest.MonkeyPatch) -> None:
    import types

    class NVMLError(Exception):
        pass

    Util = namedtuple("Util", "gpu memory")
    Mem = namedtuple("Mem", "used total")
    fake = types.SimpleNamespace(
        NVMLError=NVMLError,
        NVML_TEMPERATURE_GPU=0,
        nvmlInit=lambda: None,
        nvmlDeviceGetCount=lambda: 1,
        nvmlDeviceGetHandleByIndex=lambda i: f"h{i}",
        nvmlDeviceGetName=lambda h: b"Fake GPU",
        nvmlDeviceGetUtilizationRates=lambda h: Util(75, 30),
        nvmlDeviceGetMemoryInfo=lambda h: Mem(1024, 4096),
        nvmlDeviceGetTemperature=lambda h, sensor: 61,
    )

    def no_power(h: str) -> int:
        raise NVMLError("not supported")

    fake.nvmlDeviceGetPowerUsage = no_power
    monkeypatch.setitem(sys.modules, "pynvml", fake)

    samples = GpuCollector().collect(1.0)
    values = {s.name: s.value for s in samples}
    assert values["gpu.utilization_percent"] == 75.0
    assert values["gpu.temperature_celsius"] == 61.0
    assert "gpu.power_watts" not in values
    assert samples[0].tags == {"gpu": "0", "model": "Fake GPU"}
