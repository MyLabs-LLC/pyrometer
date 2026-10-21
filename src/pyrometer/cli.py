"""The ``pyrometer`` command."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from collections.abc import Sequence
from typing import TextIO

import pyrometer.gauge  # noqa: F401  (registers host collectors)
from pyrometer import __version__
from pyrometer.core import COLLECTOR_DURATION, COLLECTOR_ERRORS, Sample, Sampler, Sink, registry
from pyrometer.storage import SQLiteStorage

CLEAR = "\033[H\033[2J"


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        return 130


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyrometer", description="Tells you how hot it's running."
    )
    parser.add_argument("--version", action="version", version=f"pyrometer {__version__}")
    sub = parser.add_subparsers(title="commands")

    watch = sub.add_parser("watch", help="print live host metrics")
    _add_sampling_args(watch)
    watch.add_argument("--db", metavar="PATH", help="also store samples in this SQLite file")
    out = watch.add_mutually_exclusive_group()
    out.add_argument("--raw", action="store_true", help="print every sample, one per line")
    out.add_argument("--json", action="store_true", help="print every sample as JSON lines")
    watch.add_argument(
        "--no-clear", action="store_true", help="don't redraw the screen between ticks"
    )
    watch.set_defaults(func=cmd_watch)

    lst = sub.add_parser("collectors", help="list collectors and whether they can run here")
    lst.set_defaults(func=cmd_collectors)

    bench = sub.add_parser("bench", help="measure how much each collector costs per tick")
    _add_sampling_args(bench, default_interval=0.2, default_count=25)
    bench.set_defaults(func=cmd_bench)
    return parser


def _add_sampling_args(
    p: argparse.ArgumentParser, default_interval: float = 1.0, default_count: int | None = None
) -> None:
    p.add_argument(
        "-i", "--interval", type=float, default=default_interval, help="seconds between samples"
    )
    p.add_argument(
        "-n", "--count", type=int, default=default_count, help="stop after this many samples"
    )
    p.add_argument(
        "-c",
        "--collectors",
        type=lambda s: [x.strip() for x in s.split(",") if x.strip()],
        help="comma-separated collector names (default: all available)",
    )


def _build_collectors(names: list[str] | None, err: TextIO) -> Sampler | None:
    try:
        collectors, skipped = registry.create_available(names)
    except KeyError as exc:
        print(f"pyrometer: {exc.args[0]}", file=err)
        return None
    for name, reason in skipped.items():
        if names is not None:
            print(f"pyrometer: skipping {name}: {reason}", file=err)
    if not collectors:
        print("pyrometer: no collectors available", file=err)
        return None
    return Sampler(collectors)


def cmd_watch(
    args: argparse.Namespace, out: TextIO | None = None, err: TextIO | None = None
) -> int:
    out, err = out or sys.stdout, err or sys.stderr
    sampler = _build_collectors(args.collectors, err)
    if sampler is None:
        return 2
    sampler.interval = args.interval
    store: SQLiteStorage | None = None
    if args.db:
        store = SQLiteStorage(args.db)
        sinks: list[Sink] = [store]
        sampler.sinks = sinks
    clear = not args.no_clear and not args.raw and not args.json and out.isatty()

    def show(samples: list[Sample]) -> None:
        if args.json:
            for s in samples:
                out.write(json.dumps(s.to_dict()) + "\n")
        elif args.raw:
            for s in samples:
                out.write(format_sample(s) + "\n")
        else:
            out.write((CLEAR if clear else "") + render_summary(samples) + "\n")
        out.flush()

    try:
        sampler.run(iterations=args.count, on_tick=show)
    finally:
        if store is not None:
            store.close()
    return 0


def cmd_collectors(args: argparse.Namespace, out: TextIO | None = None) -> int:
    out = out or sys.stdout
    for name in registry.names():
        _, skipped = registry.create_available([name])
        status = f"unavailable ({skipped[name]})" if name in skipped else "available"
        out.write(f"{name:<10} {status}\n")
    return 0


def cmd_bench(
    args: argparse.Namespace, out: TextIO | None = None, err: TextIO | None = None
) -> int:
    out, err = out or sys.stdout, err or sys.stderr
    sampler = _build_collectors(args.collectors, err)
    if sampler is None:
        return 2
    sampler.interval = args.interval
    durations: dict[str, list[float]] = defaultdict(list)
    errors: dict[str, int] = defaultdict(int)

    def record(samples: list[Sample]) -> None:
        for s in samples:
            if s.name == COLLECTOR_DURATION:
                durations[s.tags["collector"]].append(s.value)
            elif s.name == COLLECTOR_ERRORS:
                errors[s.tags["collector"]] += 1

    sampler.run(iterations=args.count or 25, on_tick=record)
    out.write(f"{'collector':<10} {'ticks':>5} {'mean ms':>9} {'p95 ms':>9} {'max ms':>9}\n")
    for name in sorted(durations):
        ms = sorted(d * 1000 for d in durations[name])
        p95 = ms[min(len(ms) - 1, round(0.95 * (len(ms) - 1)))]
        line = f"{name:<10} {len(ms):>5} {statistics.mean(ms):>9.3f} {p95:>9.3f} {ms[-1]:>9.3f}"
        if errors[name]:
            line += f"  ({errors[name]} errors)"
        out.write(line + "\n")
    return 0


def format_sample(sample: Sample) -> str:
    tags = ",".join(f"{k}={v}" for k, v in sorted(sample.tags.items()))
    return f"{sample.timestamp:.3f} {sample.name}{{{tags}}} {sample.value:g}"


def render_summary(samples: Sequence[Sample]) -> str:
    """A compact, human-readable view of one tick's samples."""
    by_name: dict[str, list[Sample]] = defaultdict(list)
    for s in samples:
        by_name[s.name].append(s)

    def total(name: str) -> float | None:
        values = [s.value for s in by_name.get(name, [])]
        return sum(values) if values else None

    def one(name: str, **tags: str) -> float | None:
        for s in by_name.get(name, []):
            if all(s.tags.get(k) == v for k, v in tags.items()):
                return s.value
        return None

    lines = [f"pyrometer {__version__}"]
    cpu = one("cpu.percent", cpu="total")
    if cpu is not None:
        line = f"CPU     {_bar(cpu)} {cpu:5.1f}%"
        load1 = one("cpu.load1")
        if load1 is not None:
            line += f"   load {load1:.2f} {one('cpu.load5') or 0:.2f} {one('cpu.load15') or 0:.2f}"
        lines.append(line)
    mem = one("memory.percent")
    if mem is not None:
        used = one("memory.used_bytes") or 0
        tot = one("memory.total_bytes") or 0
        line = f"Memory  {_bar(mem)} {mem:5.1f}%   {_bytes(used)} / {_bytes(tot)}"
        swap = one("swap.percent")
        if swap is not None:
            line += f"   swap {swap:.1f}%"
        lines.append(line)
    for s in sorted(by_name.get("disk.percent", []), key=lambda s: s.tags.get("mount", "")):
        lines.append(f"Disk    {_bar(s.value)} {s.value:5.1f}%   {s.tags.get('mount', '')}")
    rd, wr = total("disk.read_bytes_per_sec"), total("disk.write_bytes_per_sec")
    if rd is not None or wr is not None:
        lines.append(f"Disk IO read {_bytes(rd or 0)}/s   write {_bytes(wr or 0)}/s")
    rx, tx = total("net.recv_bytes_per_sec"), total("net.sent_bytes_per_sec")
    if rx is not None or tx is not None:
        lines.append(f"Network recv {_bytes(rx or 0)}/s   sent {_bytes(tx or 0)}/s")
    for s in by_name.get("gpu.utilization_percent", []):
        gpu = s.tags.get("gpu", "?")
        line = f"GPU {gpu:<3} {_bar(s.value)} {s.value:5.1f}%   {s.tags.get('model', '')}"
        temp = one("gpu.temperature_celsius", gpu=gpu)
        if temp is not None:
            line += f"   {temp:.0f}°C"
        lines.append(line)
    cost = total(COLLECTOR_DURATION)
    if cost is not None:
        lines.append(f"(collection took {cost * 1000:.1f} ms)")
    return "\n".join(lines)


def _bar(percent: float, width: int = 20) -> str:
    filled = max(0, min(width, round(percent / 100 * width)))
    return "[" + "#" * filled + "." * (width - filled) + "]"


def _bytes(n: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(n) < 1024 or unit == "TiB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TiB"


if __name__ == "__main__":
    raise SystemExit(main())
