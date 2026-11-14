# MCA Project 6: Direct-Mapped Cache Controller

A direct-mapped cache controller in synthesizable Verilog, connected to a fixed-latency main-memory model and verified with a trace-driven, self-checking testbench.

Course: Modern Computer Architecture, Newton School of Technology, Rishihood University

## Team

| Member | Role | Owns |
|---|---|---|
| Aarush Gupta | Cache Datapath, Performance & Repo Lead | `rtl/dm_cache.v` (datapath), `tb/tb_trace.v`, `scripts/cache_model.py`, `docs/address_fields.md`, results, README |
| _Member 2_ | Controller, Memory Interface & Synthesis Lead | `rtl/dm_cache.v` (FSM), `rtl/main_mem.v`, FSM diagram, synthesis |
| _Member 3_ | Verification Lead | `tb/tb_dm_cache.v`, waveform screenshots |
| _Member 4_ | Traces & Plots Lead | `scripts/trace_gen.py`, `traces/`, plots, block diagram |
| _Member 5_ | Report & Demo Lead | `report/`, Phase I video |

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

The full derivation is in [`docs/address_fields.md`](docs/address_fields.md). Every width is derived from `CACHE_SIZE` and `BLOCK_SIZE` with `$clog2`, so other configurations need no RTL edits.

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

**AMAT** = hit time + miss rate × miss penalty. `tb_trace.v` measures the hit time and miss penalty from the run itself, so they stay correct when the latency or block size changes.

## Known simplifications

Write-through only (no dirty bits), one request at a time (no pipelining), a fixed-latency memory model, and a 16 KB memory window in the testbench.

## Links

- Phase I video: _to be added_
- IEEE report: `report/` (to be added)
