#!/usr/bin/env python3
"""
run_experiments.py - Multi-parameter experiment runner and sweep framework.

Owner: Meet (Visual Analysis & Performance Lead)

Sweeps:
  1. Cache Size sweep: 256 B, 512 B, 1024 B, 2048 B, 4096 B (exposes capacity misses)
  2. Block Size sweep: 4 B, 8 B, 16 B, 32 B, 64 B (exposes spatial locality vs. miss penalty trade-off)
  3. Memory Latency sweep: 1, 2, 4, 8, 16 cycles/word (exposes memory wall sensitivity)
  4. Write Allocation Policy sweep: WA=0 vs. WA=1 across all workloads
  5. Cache vs. No-Cache baseline speedup comparison

Outputs:
  - Formatted terminal report
  - Comprehensive CSV datasets saved to docs/results/experiments/
"""

import argparse
import csv
import os
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_RESULTS = os.path.join(REPO_ROOT, "docs", "results", "experiments")
TRACES_DIR = os.path.join(REPO_ROOT, "traces")

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import scripts.cache_model as model

TRACES = [
    "sequential.trace",
    "repeated_loop.trace",
    "strided.trace",
    "conflict.trace",
    "random.trace",
    "mixed_rw.trace",
    "smoke.trace",
    "seq_check.trace",
]


def compute_cycles(stats, cache_size, block_size, latency, write_allocate):
    """
    Computes exact cycle counts using Deepak's RTL timing contracts (docs/controller_memory.md):
      - Read hit: 3 cycles
      - Read miss: 3 + W * (L + 1)
      - Write hit: 3 + (L + 1)
      - Write miss (WA=0): 3 + (L + 1)
      - Write miss (WA=1): 3 + (W + 1) * (L + 1)
      - No-cache access: 3 + (L + 1) = L + 4 cycles
    """
    w = block_size // 4
    l_plus_1 = latency + 1

    t_rd_hit = 3
    t_rd_miss = 3 + w * l_plus_1
    t_wr_hit = 3 + l_plus_1
    t_wr_miss = (3 + (w + 1) * l_plus_1) if write_allocate == 1 else (3 + l_plus_1)
    t_no_cache = 3 + l_plus_1

    total_accesses = stats["total"]
    if total_accesses == 0:
        return 0, 0, 0, 0, 0, 0

    total_cycles = (
        stats["rd_hits"] * t_rd_hit
        + stats["rd_misses"] * t_rd_miss
        + stats["wr_hits"] * t_wr_hit
        + stats["wr_misses"] * t_wr_miss
    )

    avg_cycles = total_cycles / total_accesses

    total_reads = stats["rd_hits"] + stats["rd_misses"]
    rd_miss_rate = (stats["rd_misses"] / total_reads) if total_reads > 0 else 0.0
    miss_penalty = t_rd_miss - t_rd_hit
    amat = t_rd_hit + rd_miss_rate * miss_penalty

    no_cache_cycles = total_accesses * t_no_cache
    speedup = (no_cache_cycles / total_cycles) if total_cycles > 0 else 1.0

    return avg_cycles, amat, t_no_cache, speedup, t_rd_miss, t_wr_miss


def evaluate_run(trace_name, cache_size, block_size, latency, write_allocate):
    trace_path = os.path.join(TRACES_DIR, trace_name)
    trace_ops = list(model.read_trace(trace_path))
    stats = model.simulate(trace_ops, cache_size, block_size, write_allocate)

    total = stats["total"]
    hits = stats["hits"]
    misses = stats["misses"]
    hit_rate = (100.0 * hits / total) if total > 0 else 0.0
    miss_rate = 100.0 - hit_rate

    avg_cyc, amat, no_cache_cyc, speedup, t_rd_miss, t_wr_miss = compute_cycles(
        stats, cache_size, block_size, latency, write_allocate
    )

    return {
        "trace": trace_name,
        "cache_size": cache_size,
        "block_size": block_size,
        "latency": latency,
        "write_allocate": write_allocate,
        "accesses": total,
        "hits": hits,
        "misses": misses,
        "hit_rate_pct": round(hit_rate, 2),
        "miss_rate_pct": round(miss_rate, 2),
        "rd_hits": stats["rd_hits"],
        "rd_misses": stats["rd_misses"],
        "wr_hits": stats["wr_hits"],
        "wr_misses": stats["wr_misses"],
        "avg_cycles": round(avg_cyc, 2),
        "amat": round(amat, 2),
        "no_cache_cycles": no_cache_cyc,
        "speedup": round(speedup, 2),
    }


def run_cache_size_sweep():
    print("\n--- Running Cache Size Sweep (256 B -> 4096 B, Block=16B, L=4, WA=0) ---")
    sizes = [256, 512, 1024, 2048, 4096]
    results = []
    for sz in sizes:
        for tr in TRACES:
            res = evaluate_run(tr, cache_size=sz, block_size=16, latency=4, write_allocate=0)
            results.append(res)
    return results


def run_block_size_sweep():
    print("\n--- Running Block Size Sweep (4 B -> 64 B, Cache=1024B, L=4, WA=0) ---")
    blocks = [4, 8, 16, 32, 64]
    results = []
    for b in blocks:
        for tr in TRACES:
            res = evaluate_run(tr, cache_size=1024, block_size=b, latency=4, write_allocate=0)
            results.append(res)
    return results


def run_latency_sweep():
    print("\n--- Running Memory Latency Sweep (L=1 -> 16, Cache=1024B, Block=16B, WA=0) ---")
    latencies = [1, 2, 4, 8, 16]
    results = []
    for l in latencies:
        for tr in TRACES:
            res = evaluate_run(tr, cache_size=1024, block_size=16, latency=l, write_allocate=0)
            results.append(res)
    return results


def run_policy_sweep():
    print("\n--- Running Write Allocation Policy Sweep (WA=0 vs WA=1, Cache=1024B, Block=16B, L=4) ---")
    results = []
    for wa in (0, 1):
        for tr in TRACES:
            res = evaluate_run(tr, cache_size=1024, block_size=16, latency=4, write_allocate=wa)
            results.append(res)
    return results


def save_csv(filename, data):
    os.makedirs(DOCS_RESULTS, exist_ok=True)
    filepath = os.path.join(DOCS_RESULTS, filename)
    if not data:
        return
    headers = list(data[0].keys())
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)
    print(f"  Saved {len(data)} rows to {filepath}")


def print_summary_table(title, rows, filter_trace="random.trace"):
    print(f"\n{title} (Sample Workload: {filter_trace}):")
    print(
        f"{'Config':<25} | {'Hits':>5} | {'Misses':>6} | {'Hit Rate':>8} | {'Avg Cyc':>8} | {'AMAT':>6} | {'Speedup':>7}"
    )
    print("-" * 78)
    for r in rows:
        if r["trace"] == filter_trace:
            cfg = f"{r['cache_size']}B/{r['block_size']}B/L{r['latency']}/WA{r['write_allocate']}"
            print(
                f"{cfg:<25} | {r['hits']:>5} | {r['misses']:>6} | {r['hit_rate_pct']:>7.1f}% | {r['avg_cycles']:>8.2f} | {r['amat']:>6.2f} | {r['speedup']:>6.2f}x"
            )


def main():
    parser = argparse.ArgumentParser(description="Multi-parameter cache experiment sweep runner.")
    parser.add_argument("--all", action="store_true", help="Run all parameter sweeps and export CSVs")
    args = parser.parse_args()

    cs_res = run_cache_size_sweep()
    save_csv("cache_size_sweep.csv", cs_res)
    print_summary_table("Cache Size Scaling", cs_res, filter_trace="random.trace")

    bs_res = run_block_size_sweep()
    save_csv("block_size_sweep.csv", bs_res)
    print_summary_table("Block Size Scaling", bs_res, filter_trace="sequential.trace")

    lat_res = run_latency_sweep()
    save_csv("latency_sweep.csv", lat_res)
    print_summary_table("Memory Latency Sensitivity", lat_res, filter_trace="conflict.trace")

    pol_res = run_policy_sweep()
    save_csv("policy_sweep.csv", pol_res)
    print_summary_table("Write Policy Comparison", pol_res, filter_trace="mixed_rw.trace")

    # Master complete dataset
    all_res = cs_res + bs_res + lat_res + pol_res
    save_csv("master_experiment_results.csv", all_res)

    print("\n[SUCCESS] Experiment runner completed. All raw results exported to docs/results/experiments/")


if __name__ == "__main__":
    main()
