# Configuration check (Phase I)

Goal: confirm that changing only `CACHE_SIZE` and `BLOCK_SIZE` gives the address-field widths predicted in `docs/address_fields.md`, and that the cache still returns correct data.

Every run below used `tb/tb_trace.v`, memory latency 4. The hit/miss counts were cross-checked against `scripts/cache_model.py`, and every configuration matched the model exactly.

## Field widths printed by the RTL

| Configuration | Lines | Tag / Index / Offset (predicted) | Printed by simulation |
|---|---|---|---|
| 1 KB, 16 B blocks (default) | 64 | 22 / 6 / 4 | 22 / 6 / 4 |
| 512 B, 16 B blocks | 32 | 23 / 5 / 4 | 23 / 5 / 4 |
| 1 KB, 32 B blocks | 32 | 22 / 5 / 5 | 22 / 5 / 5 |

## Results

| Trace | Configuration | Accesses | Hits | Misses | Hit rate | Avg cycles / access | Data check |
|---|---|---|---|---|---|---|---|
| smoke | 1 KB / 16 B | 14 | 8 | 6 | 57.14% | 10.86 | passed |
| smoke | 512 B / 16 B | 14 | 8 | 6 | 57.14% | 10.86 | passed |
| smoke | 1 KB / 32 B | 14 | 8 | 6 | 57.14% | 18.00 | passed |
| seq_check | 1 KB / 16 B | 512 | 384 | 128 | 75.00% | 8.00 | passed |
| seq_check | 512 B / 16 B | 512 | 384 | 128 | 75.00% | 8.00 | passed |
| seq_check | 1 KB / 32 B | 512 | 448 | 64 | 87.50% | 8.00 | passed |

## Timing measured from the simulation (1 KB / 16 B)

| Memory latency | Hit time | Read-miss time | Miss penalty | Write (write-through) |
|---|---|---|---|---|
| 2 | 3 | 15 | 12 | 6 |
| 4 | 3 | 23 | 20 | 8 |
| 8 | 3 | 39 | 36 | 12 |

- **Hit = 3 cycles:** latch the request, compare, respond.
- **Miss penalty = 4 words × (latency + 1):** every word of the block waits `latency` cycles plus one cycle for the ready pulse.

## What this shows

- **Halving the cache to 512 B** changes nothing on these two traces. Both working sets fit, or stream through, the same way: the sequential trace never re-uses a block, and the smoke trace touches only a few lines. A smaller cache will start to hurt on traces with re-use over a larger footprint, such as random access. That is part of the Phase II sweep.
- **Doubling the block to 32 B** raises the sequential hit rate from 75% to 87.5%: 1 miss then 7 hits per block instead of 1 then 3. But the average cost per access stays at 8.00 cycles, because each miss now fetches 8 words instead of 4, so the miss penalty doubles. Hit rate alone is misleading, which is why AMAT is the better single number.
- **Write-through cost:** every write pays a full memory access (8 cycles at latency 4), hit or miss.

## How to reproduce

```bash
iverilog -g2012 -Ptb_trace.CACHE_SIZE=512 -Ptb_trace.BLOCK_SIZE=16 \
         -o sim_trace rtl/main_mem.v rtl/dm_cache.v tb/tb_trace.v
vvp sim_trace +TRACE=traces/seq_check.trace
python3 scripts/cache_model.py traces/seq_check.trace --size 512 --block 16
```
