#!/usr/bin/env python3
"""Validate Utkarsh's timing accounting and measured no-cache baseline."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile

from benchmark import Configuration, DEFAULT_TRACES, ROOT, Simulator, comparison_row, write_csv
from cache_model import read_trace, simulate


def require(condition, message):
    # Explicit checks stay active even when Python is launched with -O.
    if not condition:
        raise RuntimeError(message)


def check_average(metrics, key, cycles, count):
    expected = cycles / count if count else None
    actual = metrics[key]
    require(actual is None if expected is None else
            actual is not None and math.isclose(actual, expected, abs_tol=0.00000051),
            f"{key}: expected {expected}, got {actual}")


def check_measurements(cache, baseline, counts, config):
    costs = {
        "rd_hits": 3,
        "rd_misses": 3 + config.block_size // 4 * (config.latency + 1),
        "wr_hits": config.latency + 4,
        "wr_misses": config.latency + 4 +
                     (config.block_size // 4 * (config.latency + 1) if config.write_allocate else 0),
    }
    cycle_keys = {"rd_hits": "rd_hit_cycles", "rd_misses": "rd_miss_cycles",
                  "wr_hits": "wr_hit_cycles", "wr_misses": "wr_miss_cycles"}
    total = 0
    for key, cost in costs.items():
        require(cache[key] == counts[key], f"{key}: expected {counts[key]}, got {cache[key]}")
        require(cache[cycle_keys[key]] == counts[key] * cost,
                f"{cycle_keys[key]} disagrees with hand timing contract")
        total += counts[key] * cost
    reads = counts["rd_hits"] + counts["rd_misses"]
    writes = counts["wr_hits"] + counts["wr_misses"]
    accesses = reads + writes
    require(cache["cache_size"] == config.cache_size and cache["block_size"] == config.block_size
            and cache["write_allocate"] == config.write_allocate, "Cache configuration mismatch")
    for metrics in (cache, baseline):
        require(metrics["accesses"] == accesses and metrics["reads"] == reads
                and metrics["writes"] == writes and metrics["latency"] == config.latency,
                "Request counts or latency disagree")
        check_average(metrics, "avg_cycles", metrics["total_cycles"], accesses)
    require(cache["hits"] == counts["rd_hits"] + counts["wr_hits"], "Hit totals disagree")
    require(cache["misses"] == counts["rd_misses"] + counts["wr_misses"], "Miss totals disagree")
    require(cache["total_cycles"] == total, "Total measured cache cycles disagree")
    check_average(cache, "read_amat", cache["rd_hit_cycles"] + cache["rd_miss_cycles"], reads)
    check_average(cache, "read_hit_avg_cycles", cache["rd_hit_cycles"], counts["rd_hits"])
    check_average(cache, "read_miss_avg_cycles", cache["rd_miss_cycles"], counts["rd_misses"])
    check_average(cache, "write_avg_cycles", cache["wr_hit_cycles"] + cache["wr_miss_cycles"], writes)
    require(baseline["total_cycles"] == accesses * (config.latency + 4),
            "Measured no-cache cycles disagree with the interface timing contract")
    require(baseline["read_cycles"] == reads * (config.latency + 4)
            and baseline["write_cycles"] == writes * (config.latency + 4),
            "Measured no-cache read/write cycles disagree")
    require(baseline["memory_transactions"] == accesses, "Baseline must complete one word per request")
    check_average(baseline, "read_amat", baseline["read_cycles"], reads)
    check_average(baseline, "write_avg_cycles", baseline["write_cycles"], writes)


def hand_cases(config):
    """Explicit hit/miss counts, independent of the Python reference model."""
    conflict = f"{config.cache_size:08X}"
    wa = config.write_allocate
    return [
        ("empty", "# no requests\n", (0, 0, 0, 0)),
        ("cold_read", "R 00000000\n", (0, 1, 0, 0)),
        ("warm_read", "R 00000000\nR 00000000\n", (1, 1, 0, 0)),
        ("write_only", "W 00000000 12345678\nW 00000000 DEADBEEF\n", (0, 0, wa, 2-wa)),
        ("write_then_read", "W 00000000 AABBCCDD\nR 00000000\n", (wa, 1-wa, 0, 1)),
        ("mixed_hand", f"R 00000000\nR 00000000\nW 00000000 12345678\n"
                       f"W {conflict} DEADBEEF\nR 00000000\nR {conflict}\n",
         (2-wa, 2+wa, 1, 1)),
        ("conflict_reads", f"R 00000000\nR {conflict}\nR 00000000\n", (0, 3, 0, 0)),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional directory for CSVs, raw logs and manifest")
    args = parser.parse_args()
    try:
        hand_rows, workload_rows = [], []
        with tempfile.TemporaryDirectory(prefix="performance validation ") as work:
            simulator = Simulator(work)
            geometries = [(1024, 16), (512, 16), (1024, 32), (64, 4), (16, 16), (4, 4)]
            for size, block in geometries:
                for latency in (1, 2, 4, 8):
                    for wa in (0, 1):
                        config = Configuration(size, block, latency, wa)
                        for name, text, expected in hand_cases(config):
                            trace = Path(work) / f"{name}.trace"
                            trace.write_text(text)
                            cache = simulator.measure("cache", trace, config)
                            baseline = simulator.measure("no_cache", trace, config)
                            counts = dict(zip(("rd_hits", "rd_misses", "wr_hits", "wr_misses"), expected))
                            check_measurements(cache, baseline, counts, config)
                            # At L=4, default geometry: 6 requests, 4 reads and
                            # 2 writes cost 68 cycles (WA0) or 108 cycles (WA1).
                            if name == "mixed_hand" and (size, block, latency) == (1024, 16, 4):
                                require(cache["total_cycles"] == (108 if wa else 68),
                                        "Six-access hand calculation failed")
                            row = comparison_row(trace, config, cache, baseline)
                            require(row["speedup"] is None if not cache["accesses"] else
                                    math.isclose(row["speedup"], baseline["total_cycles"] / cache["total_cycles"]),
                                    "Speedup is not the measured total-cycle ratio")
                            hand_rows.append(row)
            print(f"PASS: {len(hand_rows)} hand-calculable cases across 48 configurations")

            for latency in (1, 2, 4, 8):
                for wa in (0, 1):
                    config = Configuration(latency=latency, write_allocate=wa)
                    for trace in DEFAULT_TRACES:
                        counts = simulate(read_trace(trace), config.cache_size, config.block_size, wa)
                        cache = simulator.measure("cache", trace, config)
                        baseline = simulator.measure("no_cache", trace, config)
                        check_measurements(cache, baseline, counts, config)
                        workload_rows.append(comparison_row(trace, config, cache, baseline))
            print(f"PASS: {len(workload_rows)} supplied workload comparisons, both policies and four latencies")

            rejected = 0
            for name, text, diagnostic in [
                ("unaligned", "R 00000002\n", "Unaligned trace address"),
                ("out_of_range", "R 00004000\n", "Trace address out of bounds"),
            ]:
                trace = Path(work) / f"{name}.trace"
                trace.write_text(text)
                for engine in ("cache", "no_cache"):
                    try:
                        simulator.measure(engine, trace, Configuration())
                    except RuntimeError as error:
                        require(diagnostic in str(error), f"Unexpected diagnostic: {error}")
                        rejected += 1
                    else:
                        raise RuntimeError(f"{engine} accepted invalid trace {name}")
            print(f"PASS: {rejected} invalid trace checks; trace and build paths containing spaces")

            if args.output:
                args.output.mkdir(parents=True, exist_ok=True)
                write_csv(args.output / "hand_cases.csv", hand_rows)
                write_csv(args.output / "workloads.csv", workload_rows)
                sources = ["rtl/dm_cache.v", "rtl/main_mem.v", "tb/tb_trace.v", "tb/tb_no_cache.v",
                           "scripts/benchmark.py", "scripts/validate_performance.py", "scripts/cache_model.py"]
                sources += [str(p.relative_to(ROOT)) for p in DEFAULT_TRACES]
                manifest = {
                    "status": "PASS", "owner": "Utkarsh", "timing_source": "RTL simulation",
                    "command": "python3 -B scripts/validate_performance.py --output docs/results/utkarsh",
                    "timing_convention": "CPU acceptance edge through completion inclusive; idle gaps excluded",
                    "baseline": "one word per access, matching accept/dispatch/respond stages; measured L+4",
                    "tools": {"iverilog": simulator.command(["iverilog", "-V"]).splitlines()[0],
                              "vvp": subprocess.run(["vvp", "-V"], text=True, capture_output=True,
                                                    check=True, timeout=10).stderr.splitlines()[0]},
                    "hand_configurations": 48, "hand_cases": len(hand_rows),
                    "workload_comparisons": len(workload_rows), "invalid_trace_checks": rejected,
                    "raw_output_scope": "Compilation commands, latency-4 smoke/mixed workload samples, and invalid trace diagnostics; all 400 comparisons are in the CSVs",
                    "source_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources},
                    "hand_case_inputs": {f"cache{size}_block{block}_wa{wa}":
                                         {name: text for name, text, _ in hand_cases(Configuration(size, block, 4, wa))}
                                         for size, block in geometries for wa in (0, 1)},
                }
                (args.output / "validation.json").write_text(json.dumps(manifest, indent=2) + "\n")
                # Keep representative raw output alongside the complete numeric
                # datasets, without duplicating hundreds of human-readable logs.
                evidence, seen = [], set()
                for log in simulator.logs:
                    if log["command"][0] == "iverilog" or log["returncode"]:
                        evidence.append(log)
                        continue
                    if log["command"][0] != "vvp":
                        continue
                    trace_name = log["command"][-1]
                    if not any(trace_name.endswith("/" + name) for name in ("smoke.trace", "mixed_rw.trace")):
                        continue
                    line = next(line for line in log["stdout"].splitlines() if line.startswith("METRICS,"))
                    metrics = json.loads(line[8:])
                    if metrics["latency"] != 4:
                        continue
                    key = (trace_name, metrics["engine"], metrics.get("write_allocate"))
                    if key not in seen:
                        evidence.append(log)
                        seen.add(key)
                # Normalize paths so snapshots do not depend on a temporary name.
                logs = json.dumps(evidence, indent=2).replace(str(ROOT), "<REPO>").replace(work, "<BUILD>")
                (args.output / "simulation_output.json").write_text(logs + "\n")
                print(f"Saved measured results and validation evidence to {args.output}")
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"Performance validation failed: {error}\n")


if __name__ == "__main__":
    main()
