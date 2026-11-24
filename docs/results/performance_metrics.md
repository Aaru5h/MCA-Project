# Performance accounting and measured no-cache baseline

Owner: Utkarsh. This package implements timing accounting, a runnable no-cache
benchmark, metric validation and saved measurements. The current report is
available in [the report directory](../../report/).

## Reproduce

Requirements: Python 3.10+ and Icarus Verilog (`iverilog` and `vvp`). The Python
scripts use only the standard library. Run these commands from the repository
root. On macOS, install the simulator with `brew install icarus-verilog`.

```bash
# Measure both paths for all eight supplied traces. Prints results; writes no reports.
python3 -B scripts/benchmark.py

# Select a trace, geometry, latency and policy; optionally export a measured CSV.
python3 -B scripts/benchmark.py traces/mixed_rw.trace \
  --cache-size 1024 --block-size 16 --latency 4 --write-allocate 1 \
  --output /tmp/mixed_rw_measured.csv

# Validate accounting and the baseline without rewriting saved evidence.
python3 -B scripts/validate_performance.py

# Explicitly regenerate Utkarsh's measurements and provenance.
python3 -B scripts/validate_performance.py --output docs/results/utkarsh
```

The benchmark compiles the actual Verilog, runs each path with a fresh memory,
requires successful data checks and compares their request counts. Builds use a
temporary directory; compiler errors, simulation errors and timeouts fail the
command. Trace and build paths containing spaces are supported. Trace paths
must fit the testbenches' 255-byte filename limit.

The standalone no-cache testbench can also be run without the comparison script:

```bash
iverilog -g2012 -s tb_no_cache -Ptb_no_cache.LATENCY=4 \
  -o /tmp/no_cache.vvp rtl/main_mem.v tb/tb_no_cache.v
vvp /tmp/no_cache.vvp +TRACE=traces/smoke.trace
```

## What is measured

Both testbenches drive a request on a falling clock edge and observe completion
on a falling edge. The number of intervening rising edges is its access cost,
including CPU acceptance as cycle 1. This matches
[Deepak's controller timing contract](../controller_memory.md#cycle-costs-and-measured-latency).
A read hit counts accept, compare and respond: **3 cycles**.

Reset, initialization and idle gaps between requests are excluded. Every trace
starts with invalid cache lines and the same memory pattern,
`0xC0DE0000 + word_index`. Writes update a reference memory; subsequent reads are
checked against it. The no-cache bench additionally checks every completed write
directly in backing memory and asserts one memory completion per CPU access.

These are simulated request-service costs. Their ratio describes these blocking
interfaces; it does not measure application execution time or clock frequency.

## Counts, cycle sums and averages

Let `RH`, `RM`, `WH`, `WM` be the numbers of read hits, read misses, write hits
and write misses. Let `C_RH`, `C_RM`, `C_WH`, `C_WM` be their measured cycle sums.

```text
reads       = RH + RM
writes      = WH + WM
accesses    = reads + writes
hits        = RH + WH
misses      = RM + WM
total_cycles = C_RH + C_RM + C_WH + C_WM

read_miss_rate = RM / reads
read_AMAT     = (C_RH + C_RM) / reads
write_average = (C_WH + C_WM) / writes
average_access_cycles = total_cycles / accesses
```

The all-access average weights the measured read and write costs by their counts.
It includes expensive allocating write misses. It is distinct from read AMAT.
The testbench asserts that class counts and cycle sums reconcile with the global
totals and the RTL hit/miss counters.

With fixed read-hit and read-miss costs, the equivalent read formula is:

```text
read_AMAT = read_hit_time + read_miss_rate * (read_miss_time - read_hit_time)
```

Using the overall miss rate in this formula is incorrect when writes are present.
The implementation calculates read AMAT directly from measured read cycles, so
it also works when all reads hit or all reads miss.

An unobserved class has no measured mean: the terminal prints `N/A`, and JSON
uses `null`. Read AMAT is undefined for a write-only trace. For an empty trace,
counts and cycle sums are zero; all access averages and comparison speedup are
undefined. No synthetic class timing is presented as a measurement. A measured
read-miss penalty is printed only when both read classes occurred.

## Baseline assumptions

`tb_no_cache.v` connects a small simulation adapter to the unchanged
`rtl/main_mem.v`. It has no tags, cache data array, allocation or refills.
Every CPU access completes exactly one memory word. Its stages are:

1. Accept and latch the CPU request.
2. Dispatch the memory request, occupying the same stage as the cache's compare.
3. Wait for the fixed-latency memory; consume its registered completion.
4. Pulse the CPU response and return to idle.

The dispatch stage makes the baseline interface overhead match the controller.
It is a deliberate comparison convention, rather than an ideal combinational
connection to memory. Memory contents, trace ordering, reset, address bounds,
alignment rules and request/completion counting match the cache testbench.

For `W = BLOCK_SIZE / 4` and `L = LATENCY`, expected costs from the interface are:

| Operation | Expected cycles |
|---|---:|
| Read hit | `3` |
| Read miss | `3 + W * (L + 1)` |
| Write hit | `3 + (L + 1)` |
| Write miss, no write allocation | `3 + (L + 1)` |
| Write miss, write allocation | `3 + (W + 1) * (L + 1)` |
| No-cache read or write | `1 accept + 1 dispatch + L memory + 1 consume + 1 respond = L + 4` |

These formulas are validation expectations. The benchmark obtains cycle sums by
running the memory and controller, not by substituting these expressions.

```text
speedup = measured_no_cache_total_cycles / measured_cache_total_cycles
```

The two totals cover the same trace. Values above 1 indicate fewer service
cycles with cache. At latency 4, the measured baseline is 8 cycles per read or
write; at latencies 1, 2 and 8, it is respectively 5, 6 and 12 cycles.

## Hand-calculable checks

At 1 KB / 16 B / latency 4, the six-access mixed case is:

```text
R 00000000
R 00000000
W 00000000 12345678
W 00000400 DEADBEEF
R 00000000
R 00000400
```

| Policy | Access costs in order | Total | Read AMAT | No-cache total |
|---|---|---:|---:|---:|
| No-write-allocate | `23, 3, 8, 8, 3, 23` | 68 | 13 | 48 |
| Write-allocate | `23, 3, 8, 28, 23, 23` | 108 | 18 | 48 |

The two blocks conflict. Without write allocation the fourth request preserves
the first block; with allocation it replaces it. The saved simulator measurements
match these totals and the independently specified hit/miss counts.

Additional cases cover an empty trace, one cold read, repeated reads, writes
only, write-then-read and repeated conflicts. In particular, an allocating write
followed by a read has no read misses: its read AMAT is the measured **3 cycles**.
Two writes to the same cold address cost 16 cycles without allocation and 36
with allocation, and have no read AMAT.

## Measured workload snapshot

Configuration: 1 KB / 16 B / latency 4. All rows below use no-write-allocate,
except the explicitly marked write-allocate rows. Each no-cache average is
measured as **8 cycles/access**.

| Trace | Read AMAT | Average across all accesses | Measured speedup |
|---|---:|---:|---:|
| `smoke.trace` | 11.333333 | 10.857143 | 0.736842 |
| `seq_check.trace` | 8.000000 | 8.000000 | 1.000000 |
| `sequential.trace` | 8.000000 | 8.000000 | 1.000000 |
| `repeated_loop.trace` | 4.250000 | 4.250000 | 1.882353 |
| `strided.trace` | 23.000000 | 23.000000 | 0.347826 |
| `conflict.trace` | 23.000000 | 23.000000 | 0.347826 |
| `random.trace` | 8.000000 | 8.000000 | 1.000000 |
| `mixed_rw.trace` | 4.939394 | 6.027344 | 1.327285 |
| `smoke.trace`, write-allocate | 9.666667 | 10.857143 | 0.736842 |
| `mixed_rw.trace`, write-allocate | 3.969697 | 6.027344 | 1.327285 |

For `mixed_rw.trace`, there are 165 reads and 91 writes. Read hits/misses change
from 149/16 to 157/8 with allocation; write hits/misses change from 78/13 to
83/8. Each policy measures 1,543 total cache cycles versus 2,048 baseline
cycles. This workload's better read AMAT is balanced by write-allocation cost.

## Machine-readable output and saved evidence

Each successful simulation emits one line beginning `METRICS,`, followed by a
JSON object with `schema_version: 1`. It includes the engine, latency, request
counts, measured cycle sums and nullable averages. Cache records additionally
include geometry, policy and all four hit/miss classes. Baseline records include
read/write cycle sums and memory transaction count. JSON averages are printed
to six decimal places; integer cycle sums remain exact.

`tb_trace.v` retains the legacy `CSV,` column order for compatibility. Its final
column is still an **estimate** of the interface-matched baseline, explicitly
labelled in terminal output and named `no_cache_estimate_cycles` in JSON.
Undefined legacy averages use `N/A`. The comparison runner never uses that
estimate; it runs `tb_no_cache.v` and computes averages and speedup from integer
cycle sums. Its CSV uses blank cells for undefined averages and speedup, and
rounds floating-point values to six decimal places.

The [saved evidence](utkarsh/README.md) contains:

- 336 hand-calculable comparisons: seven cases across six geometries, four
  memory latencies and both write policies. Geometries are 1024/16, 512/16,
  1024/32, 64/4, 16/16 and 4/4 bytes.
- 64 supplied workload comparisons: eight traces, latencies 1/2/4/8 and both
  policies at the default geometry.
- Four rejection checks: unaligned and out-of-range requests in each bench.
- A manifest with source/trace SHA-256 hashes, tool versions and hand-case inputs.
- Representative raw simulation output and exact compilation commands.

The existing verification runner also passes all five directed configurations
and 32 trace comparisons after the accounting change. Its functions were called
without `save_reports`, preserving the other owner's historical reports.
Those older snapshots may contain the previous mixed-traffic AMAT values;
the current timing evidence is in `docs/results/utkarsh/`.

Meet's sweep scripts, figures and analysis are unchanged by this package. The
measured runner and metric schema provide the baseline and accounting handoff
for subsequent experiment integration.
