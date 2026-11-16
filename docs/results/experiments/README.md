# Empirical Experiment Results and Raw Datasets

Owner: Meet (Visual Analysis & Performance Lead)

This directory contains the raw empirical datasets and multi-parameter sweeps across cache geometries, memory latencies, allocation policies, and memory access workloads.

---

## 1. Datasets Overview

| Dataset CSV | Parameters Swept | Workloads Covered | Key Purpose |
|---|---|---|---|
| [`cache_size_sweep.csv`](cache_size_sweep.csv) | `CACHE_SIZE`: 256 B, 512 B, 1024 B, 2048 B, 4096 B | All 8 benchmark traces | Evaluates capacity misses and working-set footprints |
| [`block_size_sweep.csv`](block_size_sweep.csv) | `BLOCK_SIZE`: 4 B, 8 B, 16 B, 32 B, 64 B | All 8 benchmark traces | Demonstrates spatial locality vs. refill penalty trade-off |
| [`latency_sweep.csv`](latency_sweep.csv) | `LATENCY`: 1, 2, 4, 8, 16 cycles/word | All 8 benchmark traces | Evaluates sensitivity to the "memory wall" |
| [`policy_sweep.csv`](policy_sweep.csv) | `WRITE_ALLOCATE`: 0 (default) vs. 1 | All 8 benchmark traces | Measures impact of write allocation on mixed traffic |
| [`master_experiment_results.csv`](master_experiment_results.csv) | Combined 136 parameter/workload configurations | Complete test matrix | Master dataset for comprehensive analytical evaluation |

---

## 2. CSV Column Schema

Each row records:
1. `trace`: Workload name (e.g. `sequential.trace`, `random.trace`).
2. `cache_size`: Cache capacity in bytes.
3. `block_size`: Line size in bytes.
4. `latency`: Memory latency per word (cycles).
5. `write_allocate`: Allocation policy (0 = no-write-allocate, 1 = write-allocate).
6. `accesses`: Total memory operations in trace.
7. `hits`: Cache hit count.
8. `misses`: Cache miss count.
9. `hit_rate_pct`: Percentage of accesses that hit ($100 \times \text{hits} / \text{accesses}$).
10. `miss_rate_pct`: Percentage of accesses that missed ($100 - \text{hit\_rate\_pct}$).
11. `rd_hits`: Read hit count.
12. `rd_misses`: Read miss count.
13. `wr_hits`: Write hit count.
14. `wr_misses`: Write miss count.
15. `avg_cycles`: Weighted average CPU cycles per access including write-through.
16. `amat`: Average Memory Access Time for reads ($T_{\text{hit}} + \text{Miss Rate} \times T_{\text{penalty}}$).
17. `no_cache_cycles`: Baseline CPU cycles without cache ($L + 4$ cycles/access).
18. `speedup`: Performance ratio compared to no-cache baseline ($\text{no\_cache\_cycles} / \text{cache\_cycles}$).

---

## 3. How to Reproduce

Run the experiment runner and plot generator scripts:

```bash
# 1. Re-run complete parameter sweeps and regenerate all CSVs
python3 scripts/run_experiments.py

# 2. Re-generate publication SVG plots
python3 scripts/plot_results.py
```
