# Pyrometer

Performance monitoring for hosts and SQL Server, from MyLabs LLC.

*Anvil forges it, Pyrometer tells you how hot it's running.*

Pyrometer has two layers that write the same data model, so they can share one timeline:

- **Host** (`pyrometer.host`): CPU, memory, disk, network, GPU. **Works today.**
- **Databases**, one module per engine: `pyrometer.sqlserver` first (DPA-style wait sampling,
  top queries, plans and blocking chains; *planned, milestone 2*), with `pyrometer.mysql`,
  `pyrometer.oracle` and others to follow.

## Install

```bash
pip install pyrometer            # host metrics (CPU, memory, disk, network)
pip install "pyrometer[gpu]"     # + NVIDIA GPU metrics via nvidia-ml-py
```

Python 3.9+. The base install depends only on `psutil`.

## Quickstart: CLI

```bash
pyrometer watch                     # live host summary, refreshed every second
pyrometer watch -i 5 -n 12          # every 5 s, stop after 12 samples
pyrometer watch -c cpu,memory --raw # every sample, one per line
pyrometer watch --json --db run.db  # JSON lines on stdout, and keep them in SQLite
pyrometer collectors                # which collectors can run on this machine
pyrometer bench                     # what each collector costs per tick
```

## Quickstart: library

```python
import pyrometer.host  # registers the host collectors
from pyrometer import Sampler, registry
from pyrometer.storage import SQLiteStorage

collectors, skipped = registry.create_available(["cpu", "memory", "disk"])
store = SQLiteStorage("samples.db")
sampler = Sampler(collectors, sinks=[store], interval=1.0)
sampler.run(iterations=10)

for s in store.query(name="cpu.percent", tags={"cpu": "total"}):
    print(s.timestamp, s.value)
```

Run it in the background with `threading.Thread(target=sampler.run, daemon=True).start()`
and call `sampler.stop()` to end it.

### Data model

Every collector returns `Sample(timestamp, name, value, tags)`. All samples from one tick
share a timestamp. Tags carry the dimensions (`cpu`, `mount`, `device`, `interface`, `gpu`...).

### Writing a collector

```python
from pyrometer import Sample, registry

@registry.register("uptime")
class UptimeCollector:
    name = "uptime"

    def collect(self, timestamp: float) -> list[Sample]:
        import time, psutil
        return [Sample(timestamp, "host.uptime_seconds", time.time() - psutil.boot_time())]
```

A factory that can't run on this machine raises `CollectorUnavailable`; it is then skipped.

## Host metrics

| Collector | Metrics | Tags |
|-----------|---------|------|
| `cpu` | `cpu.percent`, `cpu.count`, `cpu.load1/5/15` (Unix) | `cpu` = `total` or core index |
| `memory` | `memory.{total,available,used}_bytes`, `memory.percent`, `swap.used_bytes`, `swap.percent` | |
| `disk` | `disk.{used,free}_bytes`, `disk.percent`; `disk.{read,write}_{bytes,ops}_per_sec` | `mount`, `device`, `fstype` / `device` |
| `network` | `net.{sent,recv}_{bytes,packets}_per_sec`, `net.errors_{in,out}_per_sec`, `net.drops_{in,out}_per_sec` | `interface` |
| `gpu` | `gpu.utilization_percent`, `gpu.memory_utilization_percent`, `gpu.memory_{used,total}_bytes`, `gpu.temperature_celsius`, `gpu.power_watts` | `gpu`, `model` |

Rates (`*_per_sec`) appear from the second sample onward. Loopback interfaces and read-only
image filesystems (squashfs, iso9660...) are skipped by default.

## Overhead

The sampler records its own cost on every tick as `pyrometer.collector.duration_seconds`
(tag `collector`), and failures as `pyrometer.collector.errors`. `pyrometer bench` summarises it.
Measured on a 4-vCPU Linux VM (Python 3.13, psutil 7):

| Collector | Mean per tick |
|-----------|---------------|
| cpu | ~0.17 ms |
| memory | ~0.15 ms |
| network | ~0.13 ms |
| disk | ~0.5 ms |

At the default 1 s interval the whole host layer costs well under 0.1% of one core.

## Development

```bash
pip install -e ".[dev]"
ruff check src tests && ruff format --check src tests
mypy
pytest
```

Releases: bump `__version__` in `src/pyrometer/__init__.py` and push a matching `vX.Y.Z` tag;
`.github/workflows/publish.yml` publishes to PyPI with trusted publishing.

## License

MIT
