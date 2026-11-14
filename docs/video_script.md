# Phase I video script (maximum 5:00)

Record the screen with QuickTime (File → New Screen Recording) and a voiceover. Rehearse with a timer and aim for about 4:40. Have these ready before recording: the terminal in the repo folder, GTKWave with `trace.vcd` open, and the block diagram and FSM diagram images.

---

## 0:00 – 1:00 · Idea and team

**Screen:** README title, then the team table.

> "Our project is a direct-mapped cache controller written in Verilog. A cache is a small, fast memory between the processor and slow main memory. Ours is 1 kilobyte with 16-byte blocks, and it sits in front of a main-memory model that takes 4 cycles per word."

Each member says one line (about 8 seconds each):

> "I'm Aarush Gupta. I'm the datapath, performance and repo lead: the tag, data and valid storage, the hit logic, and the trace-driven testbench."
> "I'm ___, controller and memory interface lead: the state machine and the memory handshake."
> "I'm ___, verification lead: the directed tests and the waveforms."
> "I'm ___, traces and plots lead: the access traces and the diagrams."
> "I'm ___, report and demo lead: the IEEE report and this video."

**Screen:** block diagram, then the address table in `docs/address_fields.md`.

> "A 32-bit address is split three ways. 4 offset bits pick the byte in a 16-byte block. 1 KB divided by 16 bytes is 64 lines, so 6 index bits pick the line. The other 22 bits are the tag, which tells us which block is stored in that line."

## 1:00 – 2:00 · Running the prototype

**Screen:** terminal.

```bash
iverilog -g2012 -o sim_trace rtl/main_mem.v rtl/dm_cache.v tb/tb_trace.v
vvp sim_trace +TRACE=traces/smoke.trace
```

> "This testbench reads a trace of reads and writes, drives the cache, and checks every value read against a reference copy of memory. The smoke trace covers a cold miss, hits in the same block, a conflict, a write hit and a write miss. We get 8 hits and 6 misses, the field widths 22, 6 and 4, and DATA CHECK PASSED. A hit takes 3 cycles and a miss 23."

If your teammate's directed testbench is ready, run it here too and show it passing.

## 2:00 – 3:30 · Waveform: miss, refill, hit

**Screen:** GTKWave (`vvp sim_trace +TRACE=traces/smoke.trace +WAVES`, then `gtkwave trace.vcd`). Add these signals: `clk`, `cpu_req`, `cpu_addr`, `dut.state`, `dbg_hit`, `mem_req`, `mem_ready`, `mem_addr`, `cpu_ready`, `cpu_rdata`, `hit_count`, `miss_count`.

1. **First access, 0x40:** "The line is not valid yet, so `dbg_hit` is low. The FSM goes to ALLOCATE, `mem_req` rises, and we see four `mem_ready` pulses, one per word, while `mem_addr` counts up. Then the tag is stored, the valid bit is set and `cpu_ready` pulses."
2. **Next access, 0x44:** "Same block, so `dbg_hit` is high. COMPARE goes straight to RESPOND, and the data comes back in 3 cycles with no memory traffic."
3. **Access 0x440:** "This is exactly 1 KB above 0x40, so it has the same index but a different tag. It misses and evicts the old block. Going back to 0x40 then misses again. That is a conflict miss."

## 3:30 – 4:30 · FSM and locality

**Screen:** FSM diagram.

> "The controller has five states: IDLE, COMPARE, ALLOCATE for read misses, WRITE for write-through, and RESPOND. Every write goes to memory. On a write miss we do not load the block: that is no-write-allocate."

**Screen:** `docs/results/config_check.md`.

> "Sequential reads give 75% hits: one miss brings in four words, and the next three hit. That's spatial locality. If we double the block to 32 bytes, the hit rate rises to 87.5%, but the average time per access stays at 8 cycles, because each miss now fetches twice as much. So hit rate alone isn't enough, and we use AMAT: hit time plus miss rate times miss penalty."

## 4:30 – 5:00 · Status and Phase II

> "Done so far: the cache RTL, the memory model, the trace-driven testbench with a Python reference model, the address-field derivation, and a check of three configurations. In Phase II we will run the full set of traces, compare AMAT against a no-cache baseline, sweep cache and block size, add a write-allocate option, and report synthesis results. Thank you."

---

Upload the video to Google Drive with "Anyone with the link can view", paste the link into the README under **Links**, and test it in an incognito window.
