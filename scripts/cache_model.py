#!/usr/bin/env python3
"""
cache_model.py - Reference model of the direct-mapped cache, used to cross-check the Verilog.

Verification Lead: Kushagra

Models hit and miss behavior under both write-allocation policies:
  No-write-allocate (default, WRITE_ALLOCATE=0):
    read hit   -> hit
    read miss  -> miss, block is loaded into the line
    write hit  -> hit  (cache copy updated; memory also written)
    write miss -> miss (memory written, cache NOT allocated)

  Write-allocate (WRITE_ALLOCATE=1):
    read hit   -> hit
    read miss  -> miss, block loaded into cache line
    write hit  -> hit  (cache copy updated; memory also written)
    write miss -> miss, block refilled/allocated into cache line and written

Usage:
  python3 scripts/cache_model.py traces/smoke.trace
  python3 scripts/cache_model.py traces/smoke.trace --size 512 --block 16 --write-allocate 1
"""
import argparse
import sys


def read_trace(path):
    with open(path) as f:
        for raw in f:
            parts = raw.split()
            if len(parts) < 2 or parts[0].startswith("#"):
                continue
            op = parts[0].upper()
            if op not in ("R", "W"):
                continue
            addr = int(parts[1], 16)
            yield op, addr


def simulate(trace, cache_size=1024, block_size=16, write_allocate=0):
    if cache_size < 4 or block_size < 4 or cache_size < block_size:
        raise ValueError(f"Invalid geometry: cache_size={cache_size}, block_size={block_size}")
    if (cache_size & (cache_size - 1)) != 0 or (block_size & (block_size - 1)) != 0:
        raise ValueError("Cache and block sizes must be powers of two")
    if write_allocate not in (0, 1):
        raise ValueError("write_allocate must be 0 or 1")

    lines = cache_size // block_size
    stored = [None] * lines  # stored tag per line, None = invalid

    hits = misses = 0
    rd_hits = rd_misses = 0
    wr_hits = wr_misses = 0

    for op, addr in trace:
        block = addr // block_size
        index = block % lines
        tag = block // lines

        is_hit = (stored[index] == tag)
        if is_hit:
            hits += 1
            if op == "R":
                rd_hits += 1
            else:
                wr_hits += 1
        else:
            misses += 1
            if op == "R":
                rd_misses += 1
                stored[index] = tag  # Allocate on read miss
            else:
                wr_misses += 1
                if write_allocate == 1:
                    stored[index] = tag  # Allocate on write miss under WA=1

    return {
        "hits": hits,
        "misses": misses,
        "total": hits + misses,
        "rd_hits": rd_hits,
        "rd_misses": rd_misses,
        "wr_hits": wr_hits,
        "wr_misses": wr_misses,
    }


def main():
    ap = argparse.ArgumentParser(description="Direct-mapped cache reference model.")
    ap.add_argument("trace", help="Path to trace file")
    ap.add_argument("--size", type=int, default=1024, help="Cache size in bytes (default 1024)")
    ap.add_argument("--block", type=int, default=16, help="Block size in bytes (default 16)")
    ap.add_argument("--write-allocate", "-w", type=int, choices=[0, 1], default=0,
                    help="Write allocation policy: 0=no-write-allocate, 1=write-allocate")
    args = ap.parse_args()

    try:
        stats = simulate(list(read_trace(args.trace)), args.size, args.block, args.write_allocate)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    total = stats["total"]
    hits = stats["hits"]
    misses = stats["misses"]
    hit_rate = (100.0 * hits / total) if total > 0 else 0.0

    print(f"{args.trace}: {args.size} B cache, {args.block} B blocks, write_allocate={args.write_allocate}")
    print(f"accesses={total} hits={hits} misses={misses} hit_rate={hit_rate:.2f}%")
    print(f"reads: hits={stats['rd_hits']} misses={stats['rd_misses']} | writes: hits={stats['wr_hits']} misses={stats['wr_misses']}")


if __name__ == "__main__":
    main()
