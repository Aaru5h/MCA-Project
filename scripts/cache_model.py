#!/usr/bin/env python3
"""
cache_model.py - reference model of the direct-mapped cache, used to cross-check the Verilog.

It models only hits and misses (write-through, no-write-allocate):
  read hit   -> hit
  read miss  -> miss, block is loaded into the line
  write hit  -> hit  (cache copy updated; memory also written)
  write miss -> miss (memory written, cache NOT changed)

Usage:
  python3 scripts/cache_model.py traces/smoke.trace
  python3 scripts/cache_model.py traces/smoke.trace --size 512 --block 16

If tb_trace.v reports different hit/miss counts for the same trace and
configuration, there is a bug in the RTL or in the trace reader.
"""
import argparse


def read_trace(path):
    with open(path) as f:
        for raw in f:
            parts = raw.split()
            if len(parts) < 2 or parts[0].startswith("#"):
                continue
            yield parts[0].upper(), int(parts[1], 16)


def simulate(trace, cache_size, block_size):
    lines = cache_size // block_size
    stored = [None] * lines          # stored tag per line, None = invalid
    hits = misses = 0
    for op, addr in trace:
        block = addr // block_size
        index = block % lines
        tag = block // lines
        if stored[index] == tag:
            hits += 1
        else:
            misses += 1
            if op == "R":
                stored[index] = tag  # allocate on read miss only
    return hits, misses


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("--size", type=int, default=1024, help="cache size in bytes")
    ap.add_argument("--block", type=int, default=16, help="block size in bytes")
    args = ap.parse_args()

    hits, misses = simulate(list(read_trace(args.trace)), args.size, args.block)
    total = hits + misses
    print(f"{args.trace}: {args.size} B cache, {args.block} B blocks")
    print(f"accesses={total} hits={hits} misses={misses} hit_rate={100 * hits / total:.2f}%")


if __name__ == "__main__":
    main()
