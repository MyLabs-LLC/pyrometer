# Pyrometer: agent brief

You are building **Pyrometer**, a Python performance-monitoring tool from **MyLabs LLC**. Read this file fully before writing code, and keep it up to date as decisions get made.

## What Pyrometer is

Pyrometer is the sibling project to **Anvil**, the workbench where Gaia's models are forged, tested, and proven. The story is: *Anvil forges it, Pyrometer tells you how hot it's running.* A pyrometer is the instrument a blacksmith uses to read the heat of the forge and the metal, so the product is about measuring heat and load.

It has two layers, kept clearly separate (the same split DPA and New Relic use between system-level and app-level views):

1. **Host layer** (module `pyrometer.host`)
   PyFormance-style system metrics: CPU, memory, disk, network, and GPU. Low overhead, sampled on an interval, usable as a library and from the CLI.

2. **Database layer** (one module per engine: `pyrometer.sqlserver` first, later e.g. `pyrometer.mysql`, `pyrometer.oracle`)
   No separate product name: it is all just Pyrometer. DPA-style deep analysis of SQL Server: look past CPU/memory/disk to what is happening inside the engine. Which queries are running and costing the most, which wait types dominate, which sessions are blocking which, and what the query plans look like.

## Current state

- **Milestone 1 (core + host layer) is built**, version `0.1.0`, not yet tagged or published.
  - `core/`: `Sample` data model, `Collector` protocol + name registry (`CollectorUnavailable` for collectors that can't run here), `Clock`, and the `Sampler` loop (drift-free scheduling, skips missed slots, isolates failing collectors, records its own per-collector cost as `pyrometer.collector.duration_seconds`).
  - `host/`: `cpu`, `memory`, `disk`, `network`, `gpu` collectors. GPU imports `pynvml` lazily.
  - `storage/`: `MemoryStorage` (ring buffer) and `SQLiteStorage`, both with `query(name, since, until, tags)`.
  - `cli.py`: `pyrometer watch` (summary / `--raw` / `--json`, optional `--db`), `pyrometer collectors`, `pyrometer bench`.
  - `sqlserver/`: empty placeholder for milestone 2.
- `pyproject.toml` uses hatchling with a `src/` layout; version is read from `src/pyrometer/__init__.py`. Keep that.
- `.github/workflows/ci.yml` runs ruff, mypy (strict) and pytest on Python 3.9–3.13 (plus Windows/macOS on 3.13).
- `.github/workflows/publish.yml` publishes to PyPI through trusted publishing when a `v*` tag is pushed, and fails if the tag doesn't match `__version__`. Do not add API tokens to the repo. The trusted publisher (environment `pypi`) must be configured on PyPI.

### Decisions made

- `psutil` is a **base** dependency, not an extra: the host layer is what the base install does. GPU (`[gpu]`) and SQL Server (`[sqlserver]`) are extras.
- Collectors take the tick timestamp: `collect(timestamp) -> list[Sample]`, so every sample in a tick shares one time.
- Counter metrics (disk/network I/O) are reported as per-second rates, starting from the second sample; counter resets yield no sample rather than a negative rate.
- Disk usage skips read-only image filesystems (squashfs, iso9660, udf, erofs, cramfs) by default.
- Copyright holder is **MyLabs LLC** (in `LICENSE` and package metadata).
- **No sub-brand names.** The product is just Pyrometer. Database support is one module per engine (`pyrometer.sqlserver`, `pyrometer.mysql`, `pyrometer.oracle`...), each with its own extra (`pyrometer[sqlserver]`, `pyrometer[mysql]`...). Names like Gauge (the host module is `pyrometer.host`), Assay, Temper, Quench are not used.

## Suggested architecture

Treat these as a starting point. Propose changes before making big ones.

```
src/pyrometer/
  __init__.py
  core/          # shared pieces: Metric/Sample types, sampler loop, registry, clock
  host/          # host metrics collectors (cpu, memory, disk, network, gpu)
  sqlserver/     # SQL Server collectors and analysis
  mysql/, oracle/ ...  # later: one package per database engine, same pattern as sqlserver/
  storage/       # where samples go (start with in-memory + SQLite; JSON/Prometheus export later)
  cli.py         # `pyrometer` command
tests/
```

Design principles:

- **Collectors are small and pluggable.** Each collector exposes the same interface (e.g. `collect() -> list[Sample]`) and is registered by name. The sampler loop doesn't know what it is collecting.
- **One data model for both layers.** A sample has a timestamp, a metric name, a value, and tags (host, instance, database, session, query hash, wait type...). Both layers write the same shape so they can be shown on one timeline.
- **Optional dependencies per layer.** Host layer: `psutil`; GPU via `nvidia-ml-py` (pynvml) only if installed. SQL Server: `pyodbc` (or `mssql-python`). Use extras: `pip install pyrometer[sqlserver]`, `pyrometer[gpu]`. The base install must work with no extras.
- **Low overhead first.** The monitor must not become the load it is measuring. Measure the cost of each collector and document it.
- **Read-only against SQL Server.** Never run anything that changes server state. Use DMVs and Query Store; require only `VIEW SERVER STATE` (and `VIEW DATABASE STATE` where needed). Document the exact permissions.

## SQL Server layer: what to collect

- **Wait-time sampling** (the core of the DPA approach): poll `sys.dm_exec_requests` joined to `sys.dm_exec_sessions` every second or so, record what each active request is waiting on, and attribute wait time to query + wait type. Aggregate over time windows.
- **Server-wide waits:** deltas of `sys.dm_os_wait_stats`, filtering out benign idle waits.
- **Top queries:** `sys.dm_exec_query_stats` plus `sys.dm_exec_sql_text`; group by `query_hash`. Use Query Store when it is enabled.
- **Plans:** `sys.dm_exec_query_plan` / `sys.dm_exec_text_query_plan`; store by `plan_hash`, flag plan changes for the same query.
- **Blocking chains:** build the tree from `blocking_session_id`, identify head blockers, record duration.
- Also worth adding later: file I/O latency (`sys.dm_io_virtual_file_stats`), tempdb usage, memory grants.

## Milestones

1. **Core + host layer.** Data model, sampler loop, psutil collectors, SQLite storage, `pyrometer watch` CLI that prints live host metrics. Tests for each collector.
2. **SQL Server basics.** Connection config, wait sampling, top queries, blocking chains. `pyrometer sql watch` CLI. Test against SQL Server in Docker (`mcr.microsoft.com/mssql/server`).
3. **Analysis.** Time-window aggregation, "top waits / top queries in the last N minutes" reports, plan-change detection.
4. **Output.** JSON export, Prometheus endpoint, and a simple report view. Decide on a UI later.

Ship a release to PyPI at the end of each milestone (bump the version, push a `vX.Y.Z` tag).

## Conventions

- Python 3.9+ (match `requires-python`). Type hints everywhere.
- `ruff` for lint and format, `pytest` for tests, `mypy` on `src/`.
- Keep the README current with install and quickstart for whatever works today.
- Small, focused commits. Don't break the base install by importing optional dependencies at module top level.

## Open questions (ask the owner, don't decide silently)

- Which databases after SQL Server, and in what order? (MySQL and Oracle are named as examples; build SQL Server first.)
- Agent/collector deployment model: run on the DB host, or remotely over the network? (Assume remote over ODBC to start.)
- How Pyrometer integrates with Anvil (shared data store? Anvil runs Pyrometer during model tests?).
- License: placeholder is MIT; confirm.
- Milestone 1 release: tag `v0.1.0` once the PyPI trusted publisher is configured?
