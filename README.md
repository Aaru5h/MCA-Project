# MCA Project 6: Direct-Mapped Cache Controller

A direct-mapped cache controller in synthesizable Verilog, connected to a fixed-latency main-memory model and verified with a trace-driven, self-checking testbench.

Course: Modern Computer Architecture, Newton School of Technology, Rishihood University

## Team

| Member | Work package | Owns |
|---|---|---|
| Aarush Gupta | Cache datapath, performance and repository lead | Cache datapath and first working controller/memory RTL, trace-driven testbench (`tb/tb_trace.v`), Python reference model, address-field derivation, configuration check, repository setup, README and results integration |
| Deepak | RTL, memory interface and synthesis | `rtl/`, synthesis scripts, `docs/synthesis/`, controller and memory timing notes |
| Kushagra | Verification and workload generation | `tb/tb_dm_cache.v`, testbench correctness checks, `scripts/trace_gen.py`, `traces/`, regression runner |
| Meet | Performance experiments and visual analysis | Sweep scripts, raw performance results, plots, `docs/diagrams/`, `docs/waveforms/` |
| Utkarsh | Performance accounting, baseline and final delivery | Timing metrics in `tb/tb_trace.v`, no-cache benchmark, `report/`, video script and published links |

## Contributions

Each member's work, with the files they own, is listed below. Every package includes implementation, validation and documentation.

### Aarush — Cache datapath, performance and repository (implemented)

- Built the first working cache: the parameterized datapath in `rtl/dm_cache.v` (data, tag and valid arrays, address split and hit check), the controller states, and the fixed-latency memory model in `rtl/main_mem.v`.
- Wrote the trace-driven, self-checking testbench `tb/tb_trace.v` and the Python reference model `scripts/cache_model.py`, and cross-checked their hit and miss counts.
- Derived the address fields in [`docs/address_fields.md`](docs/address_fields.md) and ran the configuration check in [`docs/results/config_check.md`](docs/results/config_check.md).
- Set up the repository and maintained this README. In Phase II, integrated the synthesis and memory-traffic results below and the traffic section of the [performance analysis](docs/results/performance_analysis.md).

### Deepak — RTL, memory interface and synthesis (implemented)

- Hardened the controller reset/recovery path and memory transaction latching, cancellation and latency counter.
- Added parameter diagnostics and support for single-word blocks and single-line caches.
- Added `WRITE_ALLOCATE=1`: a write miss refills, overlays the written word and completes write-through before responding. The default remains `WRITE_ALLOCATE=0`.
- Added `scripts/synthesize.py` and committed generic synthesis statistics, commands, manifests and warning summaries for both policies in [`docs/synthesis/`](docs/synthesis/README.md).
- Documented CPU/memory handshakes, reset semantics, cycle formulas and measured latency 1/2/4/8 results in [`docs/controller_memory.md`](docs/controller_memory.md) and [`docs/results/controller_latency/`](docs/results/controller_latency/README.md). Focused RTL and synthesized-netlist checks passed. Kushagra's regression results are linked below.

### Kushagra — Verification and workload generation (implemented)

- Added `tb/tb_dm_cache.v` with 12 directed checks for cold misses, ascending refill word order, repeated hits, conflict eviction, write-through verification in backing memory, both allocation policies (`WRITE_ALLOCATE=0/1`), handshake contracts (`cpu_ready` 1-cycle pulse), and synchronous reset mid-refill and mid-write.
- Hardened `tb/tb_trace.v` with bounded timeout watchdogs, strict address alignment assertions (`[1:0] == 00`), address range limits against memory size, simulation-level watchdog, and explicit empty-trace handling.
- Added `scripts/trace_gen.py` and generated a reproducible trace suite (`traces/`) covering sequential, repeated-working-set (loop), strided, conflict thrashing, pseudo-random, and mixed read/write workloads with documented random seeds.
- Extended `scripts/cache_model.py` to model both allocation policies (`--write-allocate 0/1`) and handle boundary geometries.
- Added `scripts/run_regression.py` running automated regression across 5 directed configurations and 32 trace/geometry/policy combinations, achieving 100% correlation between RTL and Python model counts. Verification summary and reproduction instructions are in [`docs/verification/`](docs/verification/README.md).

### Meet — Performance experiments, diagrams and waveforms (implemented)

- Added multi-parameter experiment runner `scripts/run_experiments.py` sweeping cache sizes (256 B–4096 B), block sizes (4 B–64 B), memory latencies (1–16 cycles), and allocation policies across all 8 benchmark workloads.
- Saved raw CSV datasets in [`docs/results/experiments/`](docs/results/experiments/README.md) and authored comprehensive architectural analysis in [`docs/results/performance_analysis.md`](docs/results/performance_analysis.md).
- Generated publication-grade vector plots in `docs/results/plots/` for cache size scaling, block size trade-offs, latency sensitivity, and speedup over no-cache baseline.
- Created synthesizable cache datapath architecture and controller FSM diagrams in [`docs/diagrams/`](docs/diagrams/README.md), strictly consistent with Deepak's final RTL.
- Implemented `tb/tb_waveforms.v` and `scripts/generate_waveforms.py`, capturing VCD traces and annotating 7 execution scenarios (read hit, read miss, conflict eviction, write hit/miss under both policies, and mid-transaction reset recovery) in [`docs/waveforms/`](docs/waveforms/README.md).

### Utkarsh — Performance accounting, baseline and report (implemented)

- Corrected `tb/tb_trace.v` read AMAT and mixed-traffic accounting, with separate read/write hit/miss counts and cycle sums, measured averages, explicit estimates and `N/A`/JSON `null` for unobserved classes.
- Added `tb/tb_no_cache.v` and `scripts/benchmark.py` to measure the same traces against the unchanged memory model using the controller's request/completion convention. Comparisons use measured integer cycle totals.
- Added `scripts/validate_performance.py`: 336 hand-calculable cases across 48 configurations, 64 workload comparisons and four invalid-address checks pass. The existing five directed configurations and 32 trace comparisons also pass without rewriting their reports.
- Documented formulas, baseline assumptions and reproduction commands in [performance metrics](docs/results/performance_metrics.md), with saved measurements and source hashes in [Utkarsh's results](docs/results/utkarsh/README.md). These supply the accounting and baseline handoff for experiment integration.
- Wrote the IEEE report ([PDF](report/MCA_Direct_Mapped_Cache_IEEE_Report.pdf)) and the Phase I video script, and published the delivery links.

## Cache parameters

| Parameter | Value |
|---|---|
| Cache size | 1 KB (`CACHE_SIZE = 1024`) |
| Block size | 16 B = 4 words (`BLOCK_SIZE = 16`) |
| Lines | 64 |
| Address | 32-bit byte address |
| Fields | tag 22 `[31:10]` · index 6 `[9:4]` · offset 4 `[3:0]` |
| Write policy | write-through; no-write-allocate by default, optional `WRITE_ALLOCATE=1` |
| Memory latency | 4 cycles per word (`LATENCY`) |

The full derivation is in [`docs/address_fields.md`](docs/address_fields.md). Widths are derived from `CACHE_SIZE` and `BLOCK_SIZE` with `$clog2`. Power-of-two configurations include single-word blocks and single-line caches; supported limits and parameter diagnostics are documented in [`docs/controller_memory.md`](docs/controller_memory.md).

## Architecture

```
            req / we / addr / wdata
   CPU  ─────────────────────────────▶ ┌────────────────────┐
(testbench)◀──── rdata / ready / busy  │  Controller FSM    │
                                       │ IDLE → COMPARE →   │
                                       │ ALLOCATE | WRITE → │
                                       │ RESPOND            │
                                       └──┬──────────┬──────┘
                    index ┌───────────────┘          │ mem_req / we / addr / wdata
                          ▼                          ▼
       ┌───────────┬───────────┬───────────┐   ┌──────────────┐
       │ Data array│ Tag array │ Valid bits│   │ Main memory  │
       │ 64 × 4 w  │ 64 × 22 b │ 64 × 1 b  │   │ 4 cycles/word│
       └─────┬─────┴─────┬─────┴─────┬─────┘   └──────────────┘
             │           └──▶ (tag ==) AND valid ──▶ hit
             └──▶ rdata
```

**One request:** the address is split into tag, index and offset. The index selects a line. If the line is valid and its stored tag equals the address tag, it is a **hit** and the word is returned in 3 cycles. Otherwise it is a **miss**: the controller fetches all 4 words of the block from memory, stores the tag, sets the valid bit and returns the word (23 cycles at latency 4).

| State | What happens |
|---|---|
| `IDLE` | Wait for `cpu_req`, then latch address, data and read/write |
| `COMPARE` | Check hit; count hit or miss; choose the next state |
| `ALLOCATE` | Read miss, or write miss with allocation enabled: fetch the block, then set tag and valid. An allocating write overlays its word and proceeds to `WRITE` |
| `WRITE` | Send the written word to memory and wait for completion. A write hit updates the cached copy; a miss preserves the victim unless write allocation is enabled |
| `RESPOND` | Pulse `cpu_ready` for one cycle |

## Repository layout

```
rtl/        dm_cache.v, main_mem.v
tb/         Trace-driven, directed, no-cache, and waveform testbenches
traces/     Eight checked-in workloads
scripts/    Trace generation, regression, benchmarks, plots, and synthesis
docs/       Address fields, controller timing, verification, waveforms, and results
report/     IEEE report PDF
```

## How to run

Install the tools (macOS):

```bash
brew install icarus-verilog yosys
brew install --cask gtkwave      # or the Surfer / WaveTrace extension in VS Code
```

Run a trace:

```bash
iverilog -g2012 -o sim_trace rtl/main_mem.v rtl/dm_cache.v tb/tb_trace.v
vvp sim_trace +TRACE=traces/smoke.trace
```

Expected: `hits / misses : 8 / 6` and `DATA CHECK PASSED`.

Change the configuration or memory latency without editing the RTL:

```bash
iverilog -g2012 -Ptb_trace.CACHE_SIZE=512 -Ptb_trace.BLOCK_SIZE=32 -Ptb_trace.LATENCY=8 \
         -o sim_trace rtl/main_mem.v rtl/dm_cache.v tb/tb_trace.v
vvp sim_trace +TRACE=traces/seq_check.trace
```

Dump a waveform (`trace.vcd`) by adding `+WAVES`:

```bash
vvp sim_trace +TRACE=traces/smoke.trace +WAVES
gtkwave trace.vcd
```

Cross-check the hit/miss counts with the Python model:

```bash
python3 scripts/cache_model.py traces/smoke.trace --size 1024 --block 16
```

### Controller options and synthesis

`dm_cache` accepts `WRITE_ALLOCATE=0` (default) or `1`. For write-allocation simulation, pass `-Ptb_trace.WRITE_ALLOCATE=1` or refer to the [latency reproduction commands](docs/results/controller_latency/README.md).

```bash
python3 scripts/synthesize.py --write-allocate 0
python3 scripts/synthesize.py --write-allocate 1
```

Both default-size variants passed generic synthesis with zero warnings. [Synthesis results](docs/synthesis/README.md) describe the tool, cell counts and target limitations. These are generic resource results, with no device-specific frequency or physical area claim.

### Directed verification and regression

Run the complete regression suite to cross-check RTL against the Python reference model across 32 configuration/trace combinations:

```bash
python3 scripts/run_regression.py
```

Run directed unit verification covering 12 corner cases, handshakes, memory write-through checks and mid-transaction reset recovery:

```bash
iverilog -g2012 -o sim_dm_cache rtl/main_mem.v rtl/dm_cache.v tb/tb_dm_cache.v
vvp sim_dm_cache
```

Generate synthetic workload traces across 6 memory access patterns:

```bash
python3 scripts/trace_gen.py --generate-suite
```

Detailed verification matrices and reproduction commands are documented in [`docs/verification/README.md`](docs/verification/README.md).

### Measured cache/no-cache benchmark

Measure all eight supplied traces with the cache and an interface-matched no-cache path:

```bash
python3 -B scripts/benchmark.py
python3 -B scripts/benchmark.py traces/mixed_rw.trace --write-allocate 1
python3 -B scripts/validate_performance.py
```

The comparison runs both Verilog testbenches with the same memory, trace and timing convention. It reports measured read AMAT, the weighted average across reads and writes, and speedup from measured total cycles. [Metric definitions](docs/results/performance_metrics.md) explain the baseline overhead and undefined values. [Saved evidence](docs/results/utkarsh/README.md) includes 400 measured comparisons and source hashes. The testbench's legacy no-cache estimate remains explicitly labelled; the comparison uses the runnable baseline.

### Performance sweeps and waveform generation

Run multi-parameter sweeps across geometries, latencies, policies, and workloads, and render visual plots:

```bash
python3 scripts/run_experiments.py
python3 scripts/plot_results.py
```

Generate cycle-accurate waveforms and timing diagrams for 7 controller scenarios:

```bash
python3 scripts/generate_waveforms.py
gtkwave docs/waveforms/cache_scenarios.vcd
```

Detailed performance trade-off analysis is documented in [`docs/results/performance_analysis.md`](docs/results/performance_analysis.md). Diagrams are in [`docs/diagrams/`](docs/diagrams/README.md) and waveform walkthroughs in [`docs/waveforms/`](docs/waveforms/README.md).

### Trace format

One access per line, hex, no `0x`. Lines starting with `#` are comments.

```
R 00000040
W 00000444 12345678
```

## Phase I results

Measured at memory latency 4, 1 KB / 16 B:

| Quantity | Cycles |
|---|---|
| Hit time | 3 |
| Read-miss time | 23 |
| Miss penalty | 20 (= 4 words × (latency + 1)) |
| Write (write-through) | 8 |

| Trace | Accesses | Hit rate | Avg cycles / access |
|---|---|---|---|
| smoke | 14 | 57.14% | 10.86 |
| seq_check (2 KB sequential) | 512 | 75.00% | 8.00 |

The configuration check (512 B, and 32 B blocks) is in [`docs/results/config_check.md`](docs/results/config_check.md). Corrected read AMAT and measured no-cache comparisons are available in [Utkarsh's results](docs/results/utkarsh/README.md). Meet's size/block sweeps are linked in the performance section above. Generic synthesis for both allocation policies and additional controller latency measurements are available in the linked documentation.

For read traffic, **AMAT** is measured read cycles divided by reads, equivalent to read-hit time + read-miss rate × read-miss penalty for fixed class costs. The separately measured average cycles per access includes writes. At the default configuration, `smoke.trace` measures read AMAT **11.33** and all-access average **10.86** cycles; `mixed_rw.trace` measures **4.94** and **6.03** respectively. The runnable no-cache benchmark measures **8.00** cycles/access. Unobserved class timings are `N/A`, and write-only traces have no read AMAT. Full formulas and assumptions are in [performance metrics](docs/results/performance_metrics.md).

## Phase II results

### Synthesis

Generic Yosys synthesis of `dm_cache` (datapath, controller and the new memory-traffic counters) with 16-byte blocks. All four runs passed `check -assert -nolatches` with zero warnings. Details and reproduction commands are in [`docs/synthesis/README.md`](docs/synthesis/README.md); the chart is [`plot_synthesis_resources.svg`](docs/results/plots/plot_synthesis_resources.svg).

| Cache size | `WRITE_ALLOCATE` | Generic cells | Flip-flop bits | Mux cells | Warnings |
|---|---:|---:|---:|---:|---:|
| 512 B | 0 | 12,797 | 5,164 | 3,579 | 0 |
| 512 B | 1 | 12,797 | 5,164 | 3,582 | 0 |
| 1 KB | 0 | 24,994 | 9,965 | 6,931 | 0 |
| 1 KB | 1 | 25,080 | 9,965 | 6,906 | 0 |

Halving the cache roughly halves the cell count, because the data, tag and valid arrays dominate the design. Write allocation changes the count by less than 0.4%. Yosys's generic flow has no FPGA memory primitives, so the arrays become flip-flops and multiplexers; an FPGA tool would normally map them to block or distributed RAM. **Maximum clock frequency and FPGA utilization were not measured:** Vivado was not available and no target device was specified. These counts are generic resources, not device area.

### Memory traffic: write-allocate vs no-write-allocate

The controller now counts completed backing-memory reads (`mem_reads`) and writes (`mem_writes`) in 32-bit words. All eight traces were run at 1 KB, 16 B blocks and latency 4 under both policies ([CSV](docs/results/memory_traffic.csv), [plot](docs/results/plots/plot_memory_traffic.svg), [notes](docs/results/memory_traffic.md)).

| Trace | Policy | Read misses | Write misses | `mem_reads` | `mem_writes` | Total words |
|---|---|---:|---:|---:|---:|---:|
| `mixed_rw` | no-allocate | 16 | 13 | 64 | 91 | 155 |
| `mixed_rw` | write-allocate | 8 | 8 | 64 | 91 | 155 |
| `smoke` | no-allocate | 5 | 1 | 20 | 2 | 22 |
| `smoke` | write-allocate | 4 | 1 | 20 | 2 | 22 |

The six read-only traces are identical under both policies. Memory writes always equal CPU writes, because the cache is write-through. On these traces, write allocation does not change total traffic: every block it fetches on a write miss would otherwise have been fetched by a later read miss. It moves the refill earlier, which lowers `mixed_rw` read AMAT from 4.94 to 3.97 cycles. When written data is never read again, write allocation adds traffic: an isolated cold write moves 4 read words with allocation and none without. The full discussion is in the [performance analysis](docs/results/performance_analysis.md#8-memory-traffic-write-allocate-vs-no-write-allocate).

## Known simplifications

Write-through only (no dirty bits), one request at a time (no pipelining), a fixed-latency memory model, and a 16 KB memory window in the testbench. The measured baseline retains the controller's CPU acceptance, dispatch and response overhead. Reported speedup compares request-service cycles under those interfaces; it is not an application execution-time measurement.

## Links

- Phase I video: [LINK](https://drive.google.com/drive/folders/1_QyPkVoRIa9bW9kRykw4dKXffOf_pbuJ?usp=sharing)
- IEEE report: [View PDF](report/MCA_Direct_Mapped_Cache_IEEE_Report.pdf)
