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

The remaining work is split into four substantial packages across Deepak, Kushagra, Meet and Utkarsh. Each package includes implementation, validation and documentation. Aarush's existing implementation is the starting point; it still needs the checks below. The assignments below are pending work, not completed features.

### Deepak — RTL, memory interface and synthesis

- Review and harden the controller FSM, refill sequencing, write-through handshake and reset behavior in `rtl/dm_cache.v` and `rtl/main_mem.v`; resolve RTL defects exposed by verification.
- Define and enforce supported cache geometry and memory-latency parameters, including the zero-width selector cases for 4-byte blocks and single-line caches.
- Implement the write-allocate option planned in the video script, keeping no-write-allocate as the default. Document its refill/write sequence and coordinate policy tests with Kushagra.
- Add a reproducible synthesis script and save tool version, target, commands, warnings and resource statistics in `docs/synthesis/`. Distinguish generic synthesis statistics from target-specific timing claims.
- Document the CPU/memory handshake and expected hit, refill and write cycle counts. Cross-check these against Meet's latency runs and supply the RTL/synthesis section for the report.

### Kushagra — Verification and workload generation

- Add `tb/tb_dm_cache.v` with directed checks for cold misses, every word of a refill, repeated hits, conflicts, write hits/misses, both allocation policies and reset during an access.
- Check backing-memory contents after writes and after cache eviction, so cached reads cannot hide a broken write-through path. Check ready pulses, request completion and hit/miss counters.
- Harden testbench correctness checks with bounded waits, fatal failures, strict trace parsing, alignment/range checks and explicit empty-trace handling. Coordinate edits to `tb/tb_trace.v` with Utkarsh, who owns its performance calculations.
- Add `scripts/trace_gen.py` and reproducible sequential, repeated-working-set, strided, conflict, random and mixed read/write traces. Record seeds, address limits and expected behavior.
- Extend the Python model for the allocation option and add a regression command that compares RTL/model counts across configurations and latencies, exits unsuccessfully on failures and saves a verification summary for the report.

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
| Write policy | write-through, no-write-allocate |
| Memory latency | 4 cycles per word (`LATENCY`) |

The full derivation is in [`docs/address_fields.md`](docs/address_fields.md). Widths are derived from `CACHE_SIZE` and `BLOCK_SIZE` with `$clog2`. The documented configurations are 1 KB / 16 B, 512 B / 16 B and 1 KB / 32 B; parameter edge cases still need validation as assigned above.

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
| `ALLOCATE` | Read miss: fetch the 4 words of the block, then set tag and valid |
| `WRITE` | Any write: send the word to memory (write-through). On a hit the cache copy is updated too; on a miss the cache is untouched (no allocate) |
| `RESPOND` | Pulse `cpu_ready` for one cycle |

## Repository layout

```
rtl/        dm_cache.v, main_mem.v
tb/         tb_trace.v (trace-driven), tb_dm_cache.v (directed tests, to be added)
traces/     smoke.trace, seq_check.trace (+ workload traces, to be added)
scripts/    cache_model.py (Python reference model), trace_gen.py (to be added)
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

The configuration check (512 B, and 32 B blocks) is in [`docs/results/config_check.md`](docs/results/config_check.md). Full trace results, AMAT versus a no-cache baseline, the size/block sweep and synthesis come in Phase II.

For read traffic, **AMAT** = read-hit time + read-miss rate × read-miss penalty. The current testbench uses the overall miss rate in this formula, which is incorrect for mixed read/write traffic. Its separately measured average cycles per access includes writes. Corrected accounting and a measured no-cache baseline are assigned to Utkarsh; the existing baseline output is an estimate. Timing values also use fallbacks when a run has no read hits or read misses.

## Known simplifications

Write-through only (no dirty bits), one request at a time (no pipelining), a fixed-latency memory model, and a 16 KB memory window in the testbench.

## Links

- Phase I video: _to be added_
- IEEE report: `report/` (to be added)
