#!/usr/bin/env python3
"""Plot the checked-in Phase II memory traffic and Yosys resource measurements."""
import argparse
import csv
from io import StringIO
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs/results"
TRAFFIC_CSV = RESULTS / "memory_traffic.csv"
RESOURCES_CSV = ROOT / "docs/synthesis/traffic_counters/resources.csv"


def read_rows(path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def style_axis(axis, label):
    axis.set_xlabel(label)
    axis.set_axisbelow(True)
    axis.grid(axis="x", color="#d9e2ec", linewidth=0.8)
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.spines["bottom"].set_color("#a4b2c3")
    axis.tick_params(axis="both", length=0, pad=7)


def memory_traffic_figure():
    rows = read_rows(TRAFFIC_CSV)
    traces = sorted({row["trace"] for row in rows})
    measurements = {(row["trace"], int(row["write_allocate"])): row for row in rows}
    expected = {(trace, mode) for trace in traces for mode in (0, 1)}
    configs = {(row["cache_size"], row["block_size"], row["latency"]) for row in rows}
    if not traces or measurements.keys() != expected or len(measurements) != len(rows):
        raise ValueError("Traffic CSV must have exactly one row per trace and write policy")
    if len(configs) != 1:
        raise ValueError("Both traffic policies must use the same cache geometry and latency")
    size, block, latency = configs.pop()

    fig, axes = plt.subplots(1, 2, sharey=True, figsize=(9.6, 5.3))
    fig.subplots_adjust(left=0.16, right=0.96, top=0.75, bottom=0.17, wspace=0.23)
    fig.text(0.05, 0.94, "Backing-memory traffic by write policy", size=17, weight="bold")
    fig.text(0.05, 0.88, f"{int(size):,} B cache, {block} B blocks, {latency}-cycle memory latency")
    positions = range(len(traces))

    for axis, metric, label in zip(axes, ("mem_reads", "mem_writes"),
                                   ("Completed read words", "Completed write words")):
        for mode, offset, color, legend in (
            (0, -0.18, "#184f75", "No-write-allocate (0)"),
            (1, 0.18, "#168174", "Write-allocate (1)"),
        ):
            counts = [int(measurements[trace, mode][metric]) for trace in traces]
            bars = axis.barh([position + offset for position in positions], counts,
                             height=0.30, color=color, label=legend)
            axis.bar_label(bars, labels=[str(count) if count else "" for count in counts],
                           padding=4, fontsize=8)
        axis.set_xlim(0, max(int(row[metric]) for row in rows) * 1.18 or 1)
        style_axis(axis, label)

    axes[0].set_yticks(positions, labels=[Path(trace).stem for trace in traces])
    axes[0].invert_yaxis()
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper left", bbox_to_anchor=(0.04, 0.85),
               ncols=2, frameon=False)
    fig.text(0.05, 0.045, "Counts are 32-bit words. Blank bars represent zero. Panel scales differ.",
             size=9, color="#46546a")
    return fig


def synthesis_resources_figure():
    rows = sorted(read_rows(RESOURCES_CSV),
                  key=lambda row: (int(row["cache_size"]), int(row["write_allocate"])))
    settings = [(int(row["cache_size"]), int(row["write_allocate"])) for row in rows]
    if settings != [(512, 0), (512, 1), (1024, 0), (1024, 1)]:
        raise ValueError("Resource CSV must include both policies at 512 B and 1 KB")
    if {row["block_size"] for row in rows} != {"16"}:
        raise ValueError("Resource CSV must use 16-byte blocks throughout")

    totals = [int(row["generic_cells"]) for row in rows]
    flop_bits = [int(row["flip_flop_bits"]) for row in rows]
    muxes = [int(row["mux_cells"]) for row in rows]
    other = [total - flops - mux for total, flops, mux in zip(totals, flop_bits, muxes)]
    if min(other) < 0:
        raise ValueError("Resource breakdown exceeds total cell count")

    fig, axis = plt.subplots(figsize=(9.6, 4.05))
    fig.subplots_adjust(left=0.18, right=0.94, top=0.70, bottom=0.23)
    fig.text(0.05, 0.91, "Cache synthesis resources", size=17, weight="bold")
    fig.text(0.05, 0.83, "Yosys generic mapping, 16 B blocks, memory traffic counters included")
    positions = range(len(rows))
    axis.barh(positions, flop_bits, height=0.56, label="Flip-flop cells", color="#184f75")
    axis.barh(positions, muxes, height=0.56, left=flop_bits, label="Mux cells", color="#168174")
    final_bars = axis.barh(positions, other, height=0.56, label="Other cells", color="#c5d3e1",
                           left=[flops + mux for flops, mux in zip(flop_bits, muxes)])
    axis.bar_label(final_bars, labels=[f"{total:,}" for total in totals], padding=6, fontsize=9)
    axis.set_yticks(positions, labels=[f"{'1 KB' if size == 1024 else '512 B'} / WA={mode}"
                                     for size, mode in settings])
    axis.invert_yaxis()
    axis.set_xlim(0, max(totals) * 1.15)
    axis.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))
    style_axis(axis, "Generic cells")
    handles, labels = axis.get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper left", bbox_to_anchor=(0.04, 0.79),
               ncols=3, frameon=False)
    fig.text(0.05, 0.055, "WA = WRITE_ALLOCATE. Counts describe generic logic cells.",
             size=9, color="#46546a")
    return fig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=RESULTS / "plots")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with plt.rc_context({"font.size": 10, "text.color": "#18283b", "axes.labelcolor": "#18283b",
                         "svg.fonttype": "none", "svg.hashsalt": "mca-phase2-results"}):
        for filename, build in (
            ("plot_memory_traffic.svg", memory_traffic_figure),
            ("plot_synthesis_resources.svg", synthesis_resources_figure),
        ):
            fig = build()
            with StringIO() as svg:
                fig.savefig(svg, format="svg", metadata={"Date": None})
                clean_svg = "\n".join(line.rstrip() for line in svg.getvalue().splitlines())
            (args.output_dir / filename).write_text(clean_svg + "\n", encoding="utf-8")
            plt.close(fig)


if __name__ == "__main__":
    main()
