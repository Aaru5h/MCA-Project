#!/usr/bin/env python3
"""Utkarsh's measured cache/no-cache comparison; Python standard library only."""
import argparse
import csv
from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRACES = sorted((ROOT / "traces").glob("*.trace"))


@dataclass(frozen=True)
class Configuration:
    cache_size: int = 1024
    block_size: int = 16
    latency: int = 4
    write_allocate: int = 0

    def __post_init__(self):
        if (self.block_size < 4 or self.cache_size < self.block_size
                or self.cache_size > 2**30 or self.cache_size & (self.cache_size - 1)
                or self.block_size & (self.block_size - 1)):
            raise ValueError("Require power-of-two sizes: 4 <= block <= cache <= 2**30")
        if self.latency < 1 or self.write_allocate not in (0, 1):
            raise ValueError("Latency must be positive and write allocation must be 0 or 1")
        if self.block_size > 16384:
            raise ValueError("A cache block must fit in the testbench's 16 KB memory")


class Simulator:
    """Compile once per configuration, then run each trace with a fresh memory."""

    def __init__(self, work, timeout=60):
        self.work = Path(work).resolve()
        self.timeout = timeout
        self.binaries = {}
        self.commands = []
        self.logs = []
        for tool in ("iverilog", "vvp"):
            if not shutil.which(tool):
                raise RuntimeError(f"Required tool '{tool}' not found in PATH")

    def command(self, args):
        self.commands.append([str(arg) for arg in args])
        result = subprocess.run(args, cwd=self.work, text=True, capture_output=True,
                                timeout=self.timeout, check=False)
        self.logs.append({"command": self.commands[-1], "stdout": result.stdout,
                          "stderr": result.stderr, "returncode": result.returncode})
        if result.returncode:
            raise RuntimeError(f"Command failed ({result.returncode}): {args}\n"
                               f"{result.stdout}\n{result.stderr}")
        return result.stdout

    def compile(self, engine, config):
        key = (engine, config if engine == "cache" else config.latency)
        if key not in self.binaries:
            top = "tb_trace" if engine == "cache" else "tb_no_cache"
            binary = self.work / f"benchmark_{len(self.binaries)}.vvp"
            args = ["iverilog", "-g2012", "-Wall", "-s", top, "-o", str(binary),
                    f"-P{top}.LATENCY={config.latency}"]
            if engine == "cache":
                args += [f"-P{top}.CACHE_SIZE={config.cache_size}",
                         f"-P{top}.BLOCK_SIZE={config.block_size}",
                         f"-P{top}.WRITE_ALLOCATE={config.write_allocate}",
                         str(ROOT / "rtl/dm_cache.v")]
            args += [str(ROOT / "rtl/main_mem.v"), str(ROOT / f"tb/{top}.v")]
            self.command(args)
            self.binaries[key] = binary
        return self.binaries[key]

    def measure(self, engine, trace, config):
        if engine not in ("cache", "no_cache"):
            raise ValueError(f"Unknown benchmark engine: {engine}")
        trace = Path(trace).resolve(strict=True)
        # Both Verilog benches use a 256-byte plusarg buffer. Reject truncation.
        if len(str(trace).encode()) > 255:
            raise ValueError("Trace path exceeds the testbench's 255-byte limit")
        binary = self.compile(engine, config)
        output = self.command(["vvp", str(binary), f"+TRACE={trace}"])
        records = [line[8:] for line in output.splitlines() if line.startswith("METRICS,")]
        if len(records) != 1 or "DATA CHECK PASSED" not in output:
            raise RuntimeError(f"Missing metrics or data check for {engine}: {trace}\n{output}")
        metrics = json.loads(records[0])
        if metrics.get("schema_version") != 1 or metrics.get("engine") != engine:
            raise RuntimeError(f"Unexpected metrics schema for {engine}: {metrics}")
        return metrics


def comparison_row(trace, config, cache, baseline):
    for key in ("accesses", "reads", "writes", "latency"):
        if cache[key] != baseline[key]:
            raise RuntimeError(f"Cache/baseline {key} mismatch for {trace}")
    accesses = cache["accesses"]
    reads = cache["reads"]
    row = {
        "trace": Path(trace).name,
        "cache_size": config.cache_size, "block_size": config.block_size,
        "latency": config.latency, "write_allocate": config.write_allocate,
        "accesses": accesses, "reads": reads, "writes": cache["writes"],
    }
    for key in ("hits", "misses", "rd_hits", "rd_misses", "wr_hits", "wr_misses",
                "rd_hit_cycles", "rd_miss_cycles", "wr_hit_cycles", "wr_miss_cycles"):
        row[key] = cache[key]
    row.update({
        "cache_total_cycles": cache["total_cycles"],
        "no_cache_total_cycles": baseline["total_cycles"],
        "no_cache_read_cycles": baseline["read_cycles"],
        "no_cache_write_cycles": baseline["write_cycles"],
        "no_cache_memory_transactions": baseline["memory_transactions"],
        "cache_avg_cycles": cache["total_cycles"] / accesses if accesses else None,
        "read_amat": (cache["rd_hit_cycles"] + cache["rd_miss_cycles"]) / reads if reads else None,
        "no_cache_avg_cycles": baseline["total_cycles"] / accesses if accesses else None,
        "speedup": baseline["total_cycles"] / cache["total_cycles"] if accesses else None,
        "timing_source": "RTL simulation",
    })
    return row


def write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: round(value, 6) if isinstance(value, float) else value
                             for key, value in row.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("traces", nargs="*", type=Path, help="Default: all eight repository traces")
    parser.add_argument("--cache-size", type=int, default=1024)
    parser.add_argument("--block-size", type=int, default=16)
    parser.add_argument("--latency", type=int, default=4)
    parser.add_argument("--write-allocate", type=int, choices=(0, 1), default=0)
    parser.add_argument("--output", type=Path, help="Optional measured comparison CSV")
    args = parser.parse_args()
    try:
        config = Configuration(args.cache_size, args.block_size, args.latency, args.write_allocate)
        rows = []
        with tempfile.TemporaryDirectory(prefix="cache_benchmark_") as work:
            simulator = Simulator(work)
            for trace in args.traces or DEFAULT_TRACES:
                cache = simulator.measure("cache", trace, config)
                baseline = simulator.measure("no_cache", trace, config)
                row = comparison_row(trace, config, cache, baseline)
                rows.append(row)
                def fmt(value):
                    return "N/A" if value is None else f"{value:.6f}"
                print(f"{row['trace']}: read AMAT={fmt(row['read_amat'])}, "
                      f"cache={fmt(row['cache_avg_cycles'])}, "
                      f"no-cache={fmt(row['no_cache_avg_cycles'])} cycles/access, "
                      f"speedup={fmt(row['speedup'])}")
        if args.output:
            write_csv(args.output, rows)
            print(f"Saved {len(rows)} measured comparisons to {args.output}")
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"Benchmark failed: {error}\n")


if __name__ == "__main__":
    main()
