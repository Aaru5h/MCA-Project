# MCA Project 6: Direct-Mapped Cache Controller

A direct-mapped cache controller in synthesizable Verilog, connected to a fixed-latency main-memory model and verified with a trace-driven, self-checking testbench.

Course: Modern Computer Architecture, Newton School of Technology, Rishihood University

## Team

| Member | Work package | Owns |
|---|---|---|
| Aarush Gupta | Existing Phase I foundation | Initial cache datapath, controller and memory prototype, trace testbench, Python model, address derivation, configuration results, README |
| Deepak | RTL, memory interface and synthesis | `rtl/`, synthesis scripts, `docs/synthesis/`, controller and memory timing notes |
| Kushagra | Verification and workload generation | `tb/tb_dm_cache.v`, testbench correctness checks, `scripts/trace_gen.py`, `traces/`, regression runner |
| Meet | Performance experiments and visual analysis | Sweep scripts, raw performance results, plots, `docs/diagrams/`, `docs/waveforms/` |
| Utkarsh | Performance accounting, baseline and final delivery | Timing metrics in `tb/tb_trace.v`, no-cache benchmark, `report/`, video script and published links |

## Remaining work and ownership

The work is split into four substantial packages across Deepak, Kushagra, Meet and Utkarsh. Each package includes implementation, validation and documentation. Aarush's Phase I foundation is the starting point. Deepak's and Kushagra's packages are implemented below; Meet's and Utkarsh's packages remain pending.

### Deepak — RTL, memory interface and synthesis (implemented)

- Hardened the controller reset/recovery path and memory transaction latching, cancellation and latency counter.
- Added parameter diagnostics and support for single-word blocks and single-line caches.
- Added `WRITE_ALLOCATE=1`: a write miss refills, overlays the written word and completes write-through before responding. The default remains `WRITE_ALLOCATE=0`.
- Added `scripts/synthesize.py` and committed generic synthesis statistics, commands, manifests and warning summaries for both policies in [`docs/synthesis/`](docs/synthesis/README.md).
- Documented CPU/memory handshakes, reset semantics, cycle formulas and measured latency 1/2/4/8 results in [`docs/controller_memory.md`](docs/controller_memory.md) and [`docs/results/deepak_latency/`](docs/results/deepak_latency/README.md). Focused RTL and synthesized-netlist checks passed; permanent regression integration remains in Kushagra's package.

### Kushagra — Verification and workload generation (implemented)

- Added `tb/tb_dm_cache.v` with 12 directed checks for cold misses, ascending refill word order, repeated hits, conflict eviction, write-through verification in backing memory, both allocation policies (`WRITE_ALLOCATE=0/1`), handshake contracts (`cpu_ready` 1-cycle pulse), and synchronous reset mid-refill and mid-write.
- Hardened `tb/tb_trace.v` with bounded timeout watchdogs, strict address alignment assertions (`[1:0] == 00`), address range limits against memory size, simulation-level watchdog, and explicit empty-trace handling.
- Added `scripts/trace_gen.py` and generated a reproducible trace suite (`traces/`) covering sequential, repeated-working-set (loop), strided, conflict thrashing, pseudo-random, and mixed read/write workloads with documented random seeds.
- Extended `scripts/cache_model.py` to model both allocation policies (`--write-allocate 0/1`) and handle boundary geometries.
- Added `scripts/run_regression.py` running automated regression across 5 directed configurations and 32 trace/geometry/policy combinations, achieving 100% correlation between RTL and Python model counts. Verification summary and reproduction instructions are in [`docs/verification/`](docs/verification/README.md).

### Meet — Performance experiments, diagrams and waveforms

- Add an experiment runner for cache-size, block-size, memory-latency and allocation-policy sweeps. Use Kushagra's workloads and Utkarsh's corrected metrics and no-cache benchmark.
- Save commands, configuration details and raw CSV results under `docs/results/`; include workloads that expose capacity and conflict effects rather than only streaming behavior.
- Produce plots for hit rate, average cycles, cache versus no-cache performance and the effect of block size, latency and write allocation. Explain cases where higher hit rate does not reduce access time.
- Create the architecture and FSM diagrams in `docs/diagrams/`, keeping them consistent with Deepak's final RTL.
- Capture and annotate waveforms for read miss/refill, read hit, conflict eviction, write hit/miss and reset in `docs/waveforms/`. Supply the experiment analysis and visual assets for the report and video.

### Utkarsh — Performance accounting, baseline and final delivery

- Correct `tb/tb_trace.v` performance accounting: report read hits, read misses and writes separately, calculate a weighted average for mixed traffic and label estimated timing values explicitly.
- Implement a runnable no-cache benchmark using the same memory model, traces and request/completion timing convention. Check simple hand-calculable cases before Meet uses it for sweeps.
- Document metric formulas and baseline assumptions in `docs/results/`, including the distinction between read AMAT and the average cost of all accesses.
- Assemble the IEEE report source and PDF in `report/` using each owner's technical section, measured results and figures; check that claims match the saved evidence.
- Update `docs/video_script.md` to match the final implementation and team roles, coordinate each member's segment, assemble the recording and add working report/video links to the README. Each member records and explains their own work.

### Integration and completion

1. Deepak and Utkarsh agree on the timing convention; Kushagra supplies directed tests and deterministic workloads. All four can begin their package independently using the current prototype.
2. Kushagra validates Deepak's RTL and both allocation policies. Utkarsh validates performance accounting and the no-cache benchmark before Meet produces final sweeps.
3. Meet publishes reproducible results and figures. Each owner supplies their technical write-up and demo segment; Utkarsh integrates the final report and video.
4. A package is complete when its code or assets, reproduction commands, validation evidence and documentation are committed. Each owner updates the relevant README instructions and status when their deliverables land.

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
tb/         tb_trace.v (trace-driven), tb_dm_cache.v (directed tests, to be added)
traces/     smoke.trace, seq_check.trace (+ workload traces, to be added)
scripts/    cache_model.py, synthesize.py, trace_gen.py (to be added)
docs/       address_fields.md, diagrams/, waveforms/, synthesis/, results/
report/     IEEE report PDF and source
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

`dm_cache` accepts `WRITE_ALLOCATE=0` (default) or `1`. For write-allocation simulation, pass `-Ptb_trace.WRITE_ALLOCATE=1` or refer to the [latency reproduction commands](docs/results/deepak_latency/README.md).

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

### Trace format

One access per line, hex, no `0x`. Lines starting with `#` are comments.

```
R 00000040
W 00000444 12345678
```

## Results so far (Phase I)

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

The configuration check (512 B, and 32 B blocks) is in [`docs/results/config_check.md`](docs/results/config_check.md). Full workload results, corrected AMAT versus a measured no-cache baseline and the size/block sweep remain pending. Generic synthesis for both allocation policies and additional controller latency measurements are now available in the linked documentation.

For read traffic, **AMAT** = read-hit time + read-miss rate × read-miss penalty. The current testbench uses the overall miss rate in this formula, which is incorrect for mixed read/write traffic. Its separately measured average cycles per access includes writes. Corrected accounting and a measured no-cache baseline are assigned to Utkarsh; the existing baseline output is an estimate. Timing values also use fallbacks when a run has no read hits or read misses.

## Known simplifications

Write-through only (no dirty bits), one request at a time (no pipelining), a fixed-latency memory model, and a 16 KB memory window in the testbench. The shared testbench's policy parameter integration, permanent verification and performance-accounting corrections remain assigned to their owners.

## Links

- Phase I video: _to be added_
- IEEE report: `report/` (to be added)
