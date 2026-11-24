# Phase II memory traffic and verification handoff

Deepak's RTL, traffic runs, and synthesis measurements are ready for Kushagra. **Kushagra verifies the change first. Meet starts the traffic and resource plots after Kushagra records the regression and deliberate-bug results.**

## Measurements

[`memory_traffic.csv`](memory_traffic.csv) contains 16 RTL measurements. Each of the eight checked-in traces runs from a fresh reset under both policies at 1 KB, 16 bytes per block, and a four-cycle memory latency. `cpu_reads` and `cpu_writes` count CPU accesses. `mem_reads` and `mem_writes` count completed 32-bit words on the backing-memory interface. `mem_total_words` is their sum.

Both policies produced the same memory read and write totals for every checked-in trace at this configuration. For `mixed_rw.trace`, no-write-allocate performed 16 read-miss refills. Write allocation performed eight read-miss refills and eight write-miss refills. Both moved 64 read words and 91 write words. For `smoke.trace`, both moved 20 read words and two write words. These totals describe this trace set and configuration.

The measurement runner checks read data using the existing trace bench. For each completed trace, it also checks the RTL counters against the observed access classes:

- `mem_reads = (BLOCK_SIZE / 4) * (read_misses + WRITE_ALLOCATE * write_misses)`
- `mem_writes = cpu_writes` under either write-through policy.

The counter values are captured from the RTL. The formulas check the captured numbers. `tb_trace` adds the two fields to its existing schema-version-1 `METRICS` record and preserves its legacy CSV column order.

Run from the repository root with Icarus Verilog and Python:

```bash
python3 scripts/measure_memory_traffic.py --output /tmp/mca-memory-traffic.csv
diff -u docs/results/memory_traffic.csv /tmp/mca-memory-traffic.csv
```

The checked-in CSV passed all 16 data and traffic checks with Icarus Verilog 13.0. A second run at 512 B, 4-byte blocks, and latency 1 passed all 16 checks. An isolated cold write measured 0 reads and 1 write without allocation, and 4 reads and 1 write with allocation at the default geometry. The existing regression passed in a scratch copy, and a temporary monitor checked the RTL counters against memory completions through the directed tests under both policies, including reset. Kushagra's permanent regression update and deliberate-bug check are still pending.

## Kushagra then Meet

1. Run `python3 scripts/run_regression.py` on clean `main` and save the verification summary in `docs/verification/`. The current matrix already covers both policies at the default geometry. Add the opposite policy for configurations that currently run only one mode so the entire matrix covers both. The runner regenerates the verification README and CSV.
2. Wire the new output ports into the directed bench. Check that a read hit adds no traffic, a cold read adds one block of reads, and a write adds exactly one memory write. Use an isolated cold write to distinguish allocation modes. Confirm both counters clear on reset during an access, and check that a pending word is counted only when its completion is accepted.
3. In an isolated checkout, remove the valid-bit check from the hit predicate and record which tests fail. Run the same selection with the clean RTL again and record the passing result. Keep the deliberate mutation out of `main`. Share the verification summary with Utkarsh and hand off to Meet when the clean run passes.
4. After Kushagra's verification, Meet can use [the traffic CSV](memory_traffic.csv) and [the comparable 512 B and 1 KB synthesis CSV](../synthesis/traffic_counters/resources.csv). Label the resource chart as generic Yosys cells. The [synthesis notes](../synthesis/README.md) cover the tool, structural checks, and why FPGA utilization and frequency remain unmeasured.
