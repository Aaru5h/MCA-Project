# Cache synthesis

Owner: Deepak. The synthesis top is `dm_cache`, including the datapath, controller, counters and debug outputs. `main_mem` is the fixed-latency simulation model and is excluded from the hardware resource count.

## Phase II results with memory traffic counters

Synthesized the same `dm_cache` RTL with 16-byte blocks at both cache sizes and both write policies. All four runs used Yosys 0.71+post and passed `check -assert -nolatches` with zero warnings. Both 32-bit traffic outputs are present in each generated netlist.

| Cache size | `WRITE_ALLOCATE` | Generic cells | Flip-flop bits | Mux cells |
|---|---:|---:|---:|---:|
| 512 B | 0 | 12,797 | 5,164 | 3,579 |
| 512 B | 1 | 12,797 | 5,164 | 3,582 |
| 1 KB | 0 | 24,994 | 9,965 | 6,931 |
| 1 KB | 1 | 25,080 | 9,965 | 6,906 |

Use [resources.csv](traffic_counters/resources.csv) for the resource chart. The [run manifest](traffic_counters/manifest.json) records the RTL hash, tool version, commands, and checks. Individual Yosys statistics are in the same directory. Flip-flop bits sum the generic DFF cell types. Muxes count the `$_MUX_` cell type. Both are subsets of total generic cells.

Vivado was unavailable in the measurement environment, and the repository did not specify a target FPGA part or clock constraint. FPGA utilization and maximum frequency are therefore unmeasured. To report them later, specify the FPGA part and tool version, collect utilization for the same four configurations, and use post-route timing at the fastest tested clock that meets timing. Generic Yosys cell counts cannot supply those measurements.

## Reproduce

Install Yosys, then run from the repository root:

```bash
for size in 512 1024; do
    for policy in 0 1; do
        python3 scripts/synthesize.py --cache-size "$size" --block-size 16 --write-allocate "$policy" || exit 1
    done
done
```

The script uses Python's standard library, invokes Yosys without a shell and exits unsuccessfully on synthesis or structural-check failure. `--yosys /path/to/yosys` selects another executable. `--output /path/to/output` selects an output directory, including paths containing spaces. A failed rerun removes the previous success manifest.

Each run writes the following under its size and policy directory in `generated/`:

| File | Contents |
|---|---|
| `synthesis.ys` | Exact Yosys commands and selected parameters |
| `synthesis.txt` | Full tool output, including warnings and checks |
| `warnings.txt` | Unique warning lines; empty means no warnings |
| `statistics.json` | Generic cell and wire counts |
| `netlist.json`, `netlist.v` | Synthesized design for inspection or simulation |
| `run.json` | Tool version, target, source SHA-256, command, parameters and successful checks |

Generated files are ignored by Git. The `traffic_counters/` snapshots correspond to the Phase II runs. Check the manifest's source SHA-256 against the RTL before using a snapshot for a report.

## Archived results before memory traffic counters

The historical snapshots under `results/` apply to an earlier RTL revision. The target was **generic Yosys cells**, using `synth -top dm_cache` and its default ABC mapping. Tool: Yosys 0.71+post, Git revision `5628c13240f670b97aaaca3d47940c4afb8ff572`, AppleClang 21.0.0.21000401.

Configuration: 1 KB data cache, 16-byte blocks, 64 lines, 22-bit tags. Both policy variants retain the same external ports and statistics/debug outputs.

| Write allocation | Generic cells | Flip-flop bits | Mux cells | Wire bits | Warnings |
|---|---:|---:|---:|---:|---:|
| Disabled (default) | 24,835 | 9,901 | 6,937 | 25,183 | 0 |
| Enabled | 24,822 | 9,901 | 6,931 | 25,139 | 0 |

Flip-flop bits sum the `DFF` cell types in `statistics.json`; mux cells count `$_MUX_`. These are subsets of the total, not additional cells. The data/tag arrays map to flip-flops and selection logic in this generic flow, so the final memory count is zero. This does not show that an FPGA implementation uses zero block RAM. The small cell-count difference between policies is an optimization result for this tool run, not a claim that write allocation improves timing or area on a particular device.

Both variants passed `check -assert -nolatches`, checking structural problems such as undriven signals, conflicting drivers, combinational loops and inferred latches. Their generated Verilog netlists also passed focused CPU/memory simulation checks at latency 4 for writes, conflicts, randomized requests, reset interruption, data, counters and cycle costs. This is functional sampling, not a formal equivalence proof.

No maximum clock frequency, physical area, power or timing closure is claimed. Those require a selected device/library and a target-specific constrained flow. Cycle-level latency is documented separately in `docs/controller_memory.md`.
