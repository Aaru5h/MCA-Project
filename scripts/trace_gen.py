#!/usr/bin/env python3
"""
trace_gen.py - Workload trace generator for cache verification and performance analysis.

Verification Lead: Kushagra

Supported workload patterns:
  1. sequential    : Linear stride-4 memory scan across blocks.
  2. repeated_loop : Iterated loop over a working set that fits in cache.
  3. strided       : Strided access skipping across block boundaries.
  4. conflict      : Multiple distinct addresses aliasing to the same cache line index.
  5. random        : Deterministic pseudo-random memory access with recorded seed.
  6. mixed_rw      : Mixed read/write operations with read-after-write checks.

Usage:
  python3 scripts/trace_gen.py --generate-suite
  python3 scripts/trace_gen.py --pattern sequential --count 256 --output traces/custom.trace
"""

import argparse
import os
import random
import sys


def write_header(f, pattern, count, seed, bounds, expected):
    f.write(f"# Trace: {pattern}\n")
    f.write(f"# Access count: {count}\n")
    f.write(f"# Deterministic Seed: {seed}\n")
    f.write(f"# Address range: {bounds[0]:#010x} - {bounds[1]:#010x} (Word aligned)\n")
    f.write(f"# Expected behavior: {expected}\n")
    f.write("# Format: R <hex_addr> | W <hex_addr> <hex_data>\n")
    f.write("# ------------------------------------------------------------\n")


def gen_sequential(count=256, base=0x0000, stride=4, seed=42):
    ops = []
    expected = "High spatial locality; 1 cold miss per 16B block followed by 3 hits (75% hit rate)."
    addr = base
    for _ in range(count):
        ops.append(f"R {addr:08X}\n")
        addr += stride
    return ops, (base, base + (count - 1) * stride), expected


def gen_repeated_loop(iterations=4, working_set_words=32, base=0x0000, seed=42):
    ops = []
    count = iterations * working_set_words
    expected = (
        f"Working set ({working_set_words * 4} B) fits in cache. Iteration 1 cold misses, "
        "iterations 2+ achieve 100% hits due to temporal locality."
    )
    for _ in range(iterations):
        for w in range(working_set_words):
            addr = base + (w * 4)
            ops.append(f"R {addr:08X}\n")
    max_addr = base + (working_set_words - 1) * 4
    return ops, (base, max_addr), expected


def gen_strided(count=128, stride=64, base=0x0000, seed=42):
    ops = []
    expected = "Stride (64 B) exceeds block size (16 B); poor spatial locality causing low hit rate."
    addr = base
    for _ in range(count):
        ops.append(f"R {addr:08X}\n")
        addr += stride
    max_addr = base + (count - 1) * stride
    return ops, (base, max_addr), expected


def gen_conflict(count=128, cache_size=1024, index_offset=0x40, seed=42):
    ops = []
    expected = (
        f"Alternates between addresses with same index (0x{index_offset:02x}) but different tags "
        "(addr, addr + 1KB, addr + 2KB), provoking 100% conflict miss thrashing."
    )
    # Three addresses aliasing to the same line
    aliases = [index_offset + (k * cache_size) for k in range(3)]
    for i in range(count):
        addr = aliases[i % len(aliases)]
        ops.append(f"R {addr:08X}\n")
    return ops, (min(aliases), max(aliases)), expected


def gen_random(count=256, max_words=256, base=0x0000, seed=42):
    rng = random.Random(seed)
    ops = []
    expected = f"Uniform pseudo-random accesses within {max_words * 4} B working set; deterministic seed {seed}."
    max_addr = base + (max_words - 1) * 4
    for _ in range(count):
        w = rng.randint(0, max_words - 1)
        addr = base + (w * 4)
        ops.append(f"R {addr:08X}\n")
    return ops, (base, max_addr), expected


def gen_mixed_rw(count=256, working_set_words=64, seed=42):
    rng = random.Random(seed)
    ops = []
    expected = "Mixed read/write operations with RAW dependencies, testing write-through and allocation."
    for i in range(count):
        w = rng.randint(0, working_set_words - 1)
        addr = w * 4
        is_write = rng.random() < 0.35
        if is_write:
            val = rng.randint(0x1000_0000, 0xEFFF_FFFF)
            ops.append(f"W {addr:08X} {val:08X}\n")
        else:
            ops.append(f"R {addr:08X}\n")
    return ops, (0, (working_set_words - 1) * 4), expected


SUITE = {
    "traces/sequential.trace": lambda: gen_sequential(count=256, base=0x0000, stride=4, seed=42),
    "traces/repeated_loop.trace": lambda: gen_repeated_loop(iterations=4, working_set_words=32, base=0x0000, seed=42),
    "traces/strided.trace": lambda: gen_strided(count=128, stride=64, base=0x0000, seed=42),
    "traces/conflict.trace": lambda: gen_conflict(count=128, cache_size=1024, index_offset=0x40, seed=42),
    "traces/random.trace": lambda: gen_random(count=256, max_words=256, base=0x0000, seed=42),
    "traces/mixed_rw.trace": lambda: gen_mixed_rw(count=256, working_set_words=64, seed=42),
}


def generate_trace_file(path, gen_func, pattern_name, seed=42):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    ops, bounds, expected = gen_func()
    with open(path, "w") as f:
        write_header(f, pattern_name, len(ops), seed, bounds, expected)
        f.writelines(ops)
    print(f"Generated {path} ({len(ops)} operations)")


def main():
    parser = argparse.ArgumentParser(description="Deterministic workload trace generator.")
    parser.add_argument("--generate-suite", action="store_true", help="Generate complete trace test suite into traces/")
    parser.add_argument("--pattern", choices=["sequential", "repeated_loop", "strided", "conflict", "random", "mixed_rw"],
                        default="sequential", help="Workload pattern")
    parser.add_argument("--count", type=int, default=256, help="Number of memory accesses")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed")
    parser.add_argument("--output", type=str, default="", help="Output trace file path")
    args = parser.parse_args()

    if args.generate_suite:
        for path, gen_func in SUITE.items():
            pattern_name = os.path.basename(path).replace(".trace", "")
            generate_trace_file(path, gen_func, pattern_name)
        print("Trace suite generation complete.")
        return

    pattern_map = {
        "sequential": lambda: gen_sequential(count=args.count, seed=args.seed),
        "repeated_loop": lambda: gen_repeated_loop(iterations=4, working_set_words=args.count // 4, seed=args.seed),
        "strided": lambda: gen_strided(count=args.count, seed=args.seed),
        "conflict": lambda: gen_conflict(count=args.count, seed=args.seed),
        "random": lambda: gen_random(count=args.count, seed=args.seed),
        "mixed_rw": lambda: gen_mixed_rw(count=args.count, seed=args.seed),
    }

    out_path = args.output if args.output else f"traces/{args.pattern}.trace"
    generate_trace_file(out_path, pattern_map[args.pattern], args.pattern, seed=args.seed)


if __name__ == "__main__":
    main()
