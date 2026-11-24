#!/usr/bin/env python3
"""Measure completed memory word traffic across all traces under both policies."""
import argparse
import csv
from pathlib import Path
import subprocess
import tempfile

from benchmark import Configuration, DEFAULT_TRACES, ROOT, Simulator


def traffic_row(trace, config, metrics):
    reads = metrics["mem_reads"]
    writes = metrics["mem_writes"]
    refills = metrics["rd_misses"] + config.write_allocate * metrics["wr_misses"]
    expected_reads = (config.block_size // 4) * refills
    expected_writes = metrics["writes"]
    if (reads, writes) != (expected_reads, expected_writes):
        raise RuntimeError(
            f"{trace.name} (WRITE_ALLOCATE={config.write_allocate}): "
            f"measured {reads} memory reads and {writes} writes, "
            f"expected {expected_reads} reads and {expected_writes} writes"
        )
    return {
        "trace": trace.name,
        "cache_size": config.cache_size,
        "block_size": config.block_size,
        "latency": config.latency,
        "write_allocate": config.write_allocate,
        "accesses": metrics["accesses"],
        "cpu_reads": metrics["reads"],
        "cpu_writes": metrics["writes"],
        "read_misses": metrics["rd_misses"],
        "write_misses": metrics["wr_misses"],
        "mem_reads": reads,
        "mem_writes": writes,
        "mem_total_words": reads + writes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-size", type=int, default=1024)
    parser.add_argument("--block-size", type=int, default=16)
    parser.add_argument("--latency", type=int, default=4)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/results/memory_traffic.csv")
    args = parser.parse_args()
    try:
        if not DEFAULT_TRACES:
            raise RuntimeError("No .trace files found in traces/")
        rows = []
        with tempfile.TemporaryDirectory(prefix="cache_traffic_") as work:
            simulator = Simulator(work)
            for policy in (0, 1):
                config = Configuration(args.cache_size, args.block_size, args.latency, policy)
                for trace in DEFAULT_TRACES:
                    metrics = simulator.measure("cache", trace, config)
                    rows.append(traffic_row(trace, config, metrics))
        # Publish only after every trace passes its data and traffic checks.
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        print(f"Saved {len(rows)} verified traffic measurements to {args.output}")
    except (OSError, KeyError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"Memory traffic measurement failed: {error}\n")


if __name__ == "__main__":
    main()
