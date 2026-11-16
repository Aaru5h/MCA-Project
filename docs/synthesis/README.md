# Cache synthesis

Owner: Deepak. The synthesis top is `dm_cache`, including the datapath, controller, counters and debug outputs. `main_mem` is the fixed-latency simulation model and is excluded from the hardware resource count.

## Reproduce

Install Yosys, then run from the repository root:

```bash
python3 scripts/synthesize.py --cache-size 1024 --block-size 16 --write-allocate 0
python3 scripts/synthesize.py --cache-size 1024 --block-size 16 --write-allocate 1
```

The script uses Python's standard library, invokes Yosys without a shell and exits unsuccessfully on synthesis or structural-check failure. `--yosys /path/to/yosys` selects another executable. `--output /path/to/output` selects an output directory, including paths containing spaces. A failed rerun removes the previous success manifest.

Each run writes the following under `generated/cache1024_block16_wa0/` or `generated/cache1024_block16_wa1/`:

| File | Contents |
|---|---|
| `synthesis.ys` | Exact Yosys commands and selected parameters |
| `synthesis.txt` | Full tool output, including warnings and checks |
| `warnings.txt` | Unique warning lines; empty means no warnings |
| `statistics.json` | Generic cell and wire counts |
| `netlist.json`, `netlist.v` | Synthesized design for inspection or simulation |
| `run.json` | Tool version, target, source SHA-256, command, parameters and successful checks |

Generated files are ignored by Git. The `results/` directories contain committed statistics, manifests, commands, warnings and final log excerpts from the measured runs. Their commands refer to the generated output locations used during those runs; use the Python commands above to reproduce them on another machine. Check the manifest's source SHA-256 against the RTL before using a snapshot for a report.

## Target and measured results

Target: **generic Yosys cells**, using `synth -top dm_cache` and its default ABC mapping. No FPGA part, ASIC cell library, placement, routing or clock constraint was supplied. Tool: Yosys 0.71+post, Git revision `5628c13240f670b97aaaca3d47940c4afb8ff572`, AppleClang 21.0.0.21000401.

Configuration: 1 KB data cache, 16-byte blocks, 64 lines, 22-bit tags. Both policy variants retain the same external ports and statistics/debug outputs.

| Write allocation | Generic cells | Flip-flop bits | Mux cells | Wire bits | Warnings |
|---|---:|---:|---:|---:|---:|
| Disabled (default) | 24,835 | 9,901 | 6,937 | 25,183 | 0 |
| Enabled | 24,822 | 9,901 | 6,931 | 25,139 | 0 |

Flip-flop bits sum the `DFF` cell types in `statistics.json`; mux cells count `$_MUX_`. These are subsets of the total, not additional cells. The data/tag arrays map to flip-flops and selection logic in this generic flow, so the final memory count is zero. This does not show that an FPGA implementation uses zero block RAM. The small cell-count difference between policies is an optimization result for this tool run, not a claim that write allocation improves timing or area on a particular device.

Both variants passed `check -assert -nolatches`, checking structural problems such as undriven signals, conflicting drivers, combinational loops and inferred latches. Their generated Verilog netlists also passed focused CPU/memory simulation checks at latency 4 for writes, conflicts, randomized requests, reset interruption, data, counters and cycle costs. This is functional sampling, not a formal equivalence proof.

No maximum clock frequency, physical area, power or timing closure is claimed. Those require a selected device/library and a target-specific constrained flow. Cycle-level latency is documented separately in `docs/controller_memory.md`.
