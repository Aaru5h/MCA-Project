# Verification and Regression Summary

Owner: Kushagra (Verification & Workload Lead)

This directory contains the verification assets, test suites, and cross-model regression results for the direct-mapped cache controller.

## 1. Verification Deliverables

- **Directed Unit Testbench (`tb/tb_dm_cache.v`)**: Covers 12 targeted scenarios including cold misses, ascending refill word order, repeated hits, conflict eviction, write-through verification directly in backing memory, both allocation policies (`WRITE_ALLOCATE=0/1`), handshake contracts (`cpu_ready` 1-cycle pulse), and synchronous reset mid-refill and mid-write.
- **Hardened Trace Testbench (`tb/tb_trace.v`)**: Added bounded timeout watchdogs, strict address word-alignment assertions, memory address range bounds checking, explicit empty-trace handling, and simulation-level watchdog.
- **Workload Trace Generator (`scripts/trace_gen.py`)**: Generates deterministic reproducible access traces covering sequential, repeated loop, strided, conflict thrashing, pseudo-random, and mixed read/write workloads with documented random seeds.
- **Policy-Aware Python Model (`scripts/cache_model.py`)**: Models cache hit/miss behavior under both no-write-allocate and write-allocate policies, supporting command-line execution and automated programmatic verification.
- **Automated Regression Suite (`scripts/run_regression.py`)**: Runs complete end-to-end regression verifying RTL simulation against Python reference model.

## 2. Regression Results Matrix

| Configuration | Trace | Accesses | RTL Hits | Model Hits | RTL Misses | Model Misses | Hit Rate | AMAT (cyc) | Status |
|---|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| 1KB_16B_L4_WA0 | `smoke.trace` | 14 | 8 | 8 | 6 | 6 | 57.14% | 11.33 | **PASS** |
| 1KB_16B_L4_WA0 | `seq_check.trace` | 512 | 384 | 384 | 128 | 128 | 75.00% | 8.0 | **PASS** |
| 1KB_16B_L4_WA0 | `sequential.trace` | 256 | 192 | 192 | 64 | 64 | 75.00% | 8.0 | **PASS** |
| 1KB_16B_L4_WA0 | `repeated_loop.trace` | 128 | 120 | 120 | 8 | 8 | 93.75% | 4.25 | **PASS** |
| 1KB_16B_L4_WA0 | `strided.trace` | 128 | 0 | 0 | 128 | 128 | 0.00% | 23.0 | **PASS** |
| 1KB_16B_L4_WA0 | `conflict.trace` | 128 | 0 | 0 | 128 | 128 | 0.00% | 23.0 | **PASS** |
| 1KB_16B_L4_WA0 | `random.trace` | 256 | 192 | 192 | 64 | 64 | 75.00% | 8.0 | **PASS** |
| 1KB_16B_L4_WA0 | `mixed_rw.trace` | 256 | 227 | 227 | 29 | 29 | 88.67% | 4.94 | **PASS** |
| 1KB_16B_L4_WA1 | `smoke.trace` | 14 | 9 | 9 | 5 | 5 | 64.29% | 9.67 | **PASS** |
| 1KB_16B_L4_WA1 | `seq_check.trace` | 512 | 384 | 384 | 128 | 128 | 75.00% | 8.0 | **PASS** |
| 1KB_16B_L4_WA1 | `sequential.trace` | 256 | 192 | 192 | 64 | 64 | 75.00% | 8.0 | **PASS** |
| 1KB_16B_L4_WA1 | `repeated_loop.trace` | 128 | 120 | 120 | 8 | 8 | 93.75% | 4.25 | **PASS** |
| 1KB_16B_L4_WA1 | `strided.trace` | 128 | 0 | 0 | 128 | 128 | 0.00% | 23.0 | **PASS** |
| 1KB_16B_L4_WA1 | `conflict.trace` | 128 | 0 | 0 | 128 | 128 | 0.00% | 23.0 | **PASS** |
| 1KB_16B_L4_WA1 | `random.trace` | 256 | 192 | 192 | 64 | 64 | 75.00% | 8.0 | **PASS** |
| 1KB_16B_L4_WA1 | `mixed_rw.trace` | 256 | 240 | 240 | 16 | 16 | 93.75% | 3.97 | **PASS** |
| 512B_16B_L4_WA0 | `smoke.trace` | 14 | 8 | 8 | 6 | 6 | 57.14% | 11.33 | **PASS** |
| 512B_16B_L4_WA0 | `seq_check.trace` | 512 | 384 | 384 | 128 | 128 | 75.00% | 8.0 | **PASS** |
| 512B_16B_L4_WA0 | `sequential.trace` | 256 | 192 | 192 | 64 | 64 | 75.00% | 8.0 | **PASS** |
| 512B_16B_L4_WA0 | `repeated_loop.trace` | 128 | 120 | 120 | 8 | 8 | 93.75% | 4.25 | **PASS** |
| 512B_16B_L4_WA0 | `strided.trace` | 128 | 0 | 0 | 128 | 128 | 0.00% | 23.0 | **PASS** |
| 512B_16B_L4_WA0 | `conflict.trace` | 128 | 0 | 0 | 128 | 128 | 0.00% | 23.0 | **PASS** |
| 512B_16B_L4_WA0 | `random.trace` | 256 | 123 | 123 | 133 | 133 | 48.05% | 13.39 | **PASS** |
| 512B_16B_L4_WA0 | `mixed_rw.trace` | 256 | 227 | 227 | 29 | 29 | 88.67% | 4.94 | **PASS** |
| 1KB_32B_L8_WA0 | `smoke.trace` | 14 | 8 | 8 | 6 | 6 | 57.14% | 33.0 | **PASS** |
| 1KB_32B_L8_WA0 | `seq_check.trace` | 512 | 448 | 448 | 64 | 64 | 87.50% | 12.0 | **PASS** |
| 1KB_32B_L8_WA0 | `sequential.trace` | 256 | 224 | 224 | 32 | 32 | 87.50% | 12.0 | **PASS** |
| 1KB_32B_L8_WA0 | `repeated_loop.trace` | 128 | 124 | 124 | 4 | 4 | 96.88% | 5.25 | **PASS** |
| 1KB_32B_L8_WA0 | `strided.trace` | 128 | 0 | 0 | 128 | 128 | 0.00% | 75.0 | **PASS** |
| 1KB_32B_L8_WA0 | `conflict.trace` | 128 | 0 | 0 | 128 | 128 | 0.00% | 75.0 | **PASS** |
| 1KB_32B_L8_WA0 | `random.trace` | 256 | 224 | 224 | 32 | 32 | 87.50% | 12.0 | **PASS** |
| 1KB_32B_L8_WA0 | `mixed_rw.trace` | 256 | 239 | 239 | 17 | 17 | 93.36% | 6.49 | **PASS** |

## 3. Negative Testing & Fault Injection (Deliberate-Bug Verification)

To ensure verification fidelity and prove that testbenches reliably catch design faults, a deliberate fault injection experiment was conducted:

- **Injected Fault**: In `rtl/dm_cache.v`, the line valid check was bypassed (`is_hit = tag_match` instead of `is_hit = line_valid & tag_match`).
- **Expected Behavior**: Post-reset cold accesses and uninitialized lines must never falsely hit on unallocated cache blocks even if tag bits happen to match.
- **Observed Failure**:
  - `tb/tb_dm_cache.v` immediately flagged fatal errors on **Test 9** (`Clean cold miss after reset recovery`) and **Test 12** (`Cold miss after mid-write reset recovery`).
  - Stage 1 directed regression failed across all configurations, and the test runner exited with error status.
- **Restoration & Verification**: Restoring `is_hit = line_valid & tag_match` confirmed 100% pass across all 12 directed scenarios and all 32 cross-model trace checks.

## 4. How to Reproduce

```bash
# 1. Run complete automated regression suite
python3 scripts/run_regression.py

# 2. Run standalone directed unit testbench
iverilog -g2012 -o sim_dm_cache rtl/main_mem.v rtl/dm_cache.v tb/tb_dm_cache.v
vvp sim_dm_cache

# 3. Run trace generator
python3 scripts/trace_gen.py --generate-suite

# 4. Run trace simulation with custom allocation policy
iverilog -g2012 -Ptb_trace.WRITE_ALLOCATE=1 -o sim_trace rtl/main_mem.v rtl/dm_cache.v tb/tb_trace.v
vvp sim_trace +TRACE=traces/smoke.trace
```
