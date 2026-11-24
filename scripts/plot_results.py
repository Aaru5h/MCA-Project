#!/usr/bin/env python3
"""
plot_results.py
Generates clean, publication-ready vector charts (SVG) from experiment CSVs.

Owner: Meet (Visual Analysis & Performance Lead)
"""

import csv
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_PLOTS = os.path.join(REPO_ROOT, "docs", "results", "plots")
DOCS_EXP = os.path.join(REPO_ROOT, "docs", "results", "experiments")

os.makedirs(DOCS_PLOTS, exist_ok=True)


def load_csv(filename):
    path = os.path.join(DOCS_EXP, filename)
    with open(path) as f:
        return list(csv.DictReader(f))


def generate_cache_size_plot():
    data = load_csv("cache_size_sweep.csv")
    svg_path = os.path.join(DOCS_PLOTS, "plot_cache_size_scaling.svg")

    # Filter traces: random, repeated_loop, sequential, conflict
    traces = ["random.trace", "repeated_loop.trace", "sequential.trace", "conflict.trace"]
    colors = {"random.trace": "#38bdf8", "repeated_loop.trace": "#34d399", "sequential.trace": "#818cf8", "conflict.trace": "#f43f5e"}
    labels = {"random.trace": "Random (1 KB working set)", "repeated_loop.trace": "Repeated Loop (128 B)", "sequential.trace": "Sequential Stream", "conflict.trace": "Conflict Thrashing (1 KB alias)"}

    sizes = [256, 512, 1024, 2048, 4096]
    # Chart dimensions: 800 x 480
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 850 500" width="100%" height="100%" style="background-color: #0b1120; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <text x="40" y="38" font-size="20" font-weight="700" fill="#f8fafc">Cache Size Scaling: Hit Rate vs. Capacity</text>
  <text x="40" y="60" font-size="12" fill="#94a3b8">Block Size = 16 B, Memory Latency = 4, Policy = WA=0. Exposes capacity misses as working set fits in cache.</text>

  <!-- Plot Area: x=100..750, y=90..400 -->
  <rect x="100" y="90" width="650" height="310" fill="#0f172a" stroke="#1e293b" rx="6"/>

  <!-- Horizontal Grid Lines (0% to 100%) -->
  <g stroke="#1e293b" stroke-dasharray="3,3" stroke-width="1">
    <line x1="100" y1="400" x2="750" y2="400"/>
    <line x1="100" y1="322.5" x2="750" y2="322.5"/>
    <line x1="100" y1="245" x2="750" y2="245"/>
    <line x1="100" y1="167.5" x2="750" y2="167.5"/>
    <line x1="100" y1="90" x2="750" y2="90"/>
  </g>

  <!-- Y-Axis Labels -->
  <g font-size="11" fill="#64748b" text-anchor="end">
    <text x="90" y="404">0%</text>
    <text x="90" y="326">25%</text>
    <text x="90" y="249">50%</text>
    <text x="90" y="171">75%</text>
    <text x="90" y="94">100%</text>
  </g>

  <!-- X-Axis Labels (256, 512, 1024, 2048, 4096) -->
  <g font-size="12" fill="#cbd5e1" text-anchor="middle">
    <text x="140" y="425">256 B</text>
    <text x="277" y="425">512 B</text>
    <text x="425" y="425">1024 B (1 KB)</text>
    <text x="572" y="425">2048 B (2 KB)</text>
    <text x="710" y="425">4096 B (4 KB)</text>
    <text x="425" y="450" font-weight="600" fill="#94a3b8">Cache Capacity (Bytes)</text>
  </g>
"""
    x_coords = {256: 140, 512: 277, 1024: 425, 2048: 572, 4096: 710}

    for tr in traces:
        pts = []
        rows = [r for r in data if r["trace"] == tr]
        for r in rows:
            sz = int(r["cache_size"])
            hr = float(r["hit_rate_pct"])
            x = x_coords[sz]
            y = 400 - (hr / 100.0) * 310
            pts.append((x, y))

        path_d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
        c = colors[tr]
        svg += f'  <path d="{path_d}" fill="none" stroke="{c}" stroke-width="3" stroke-linecap="round"/>\n'
        for x, y in pts:
            svg += f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{c}" stroke="#0f172a" stroke-width="2"/>\n'

    # Legend
    svg += """  <!-- Legend -->
  <g transform="translate(100, 470)" font-size="11">
    <circle cx="10" cy="5" r="4" fill="#38bdf8"/>
    <text x="22" y="9" fill="#cbd5e1">Random (1 KB Set)</text>

    <circle cx="180" cy="5" r="4" fill="#34d399"/>
    <text x="192" y="9" fill="#cbd5e1">Repeated Loop (128 B)</text>

    <circle cx="370" cy="5" r="4" fill="#818cf8"/>
    <text x="382" y="9" fill="#cbd5e1">Sequential</text>

    <circle cx="500" cy="5" r="4" fill="#f43f5e"/>
    <text x="512" y="9" fill="#cbd5e1">Conflict (1 KB Aliasing)</text>
  </g>
</svg>"""

    with open(svg_path, "w") as f:
        f.write(svg)
    print(f"Generated {svg_path}")


def generate_block_size_plot():
    data = load_csv("block_size_sweep.csv")
    svg_path = os.path.join(DOCS_PLOTS, "plot_block_size_tradeoff.svg")

    # Compare sequential.trace vs strided.trace vs random.trace
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 850 500" width="100%" height="100%" style="background-color: #0b1120; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <text x="40" y="38" font-size="20" font-weight="700" fill="#f8fafc">Block Size Trade-Off: Spatial Locality vs. Miss Penalty</text>
  <text x="40" y="60" font-size="12" fill="#94a3b8">Cache = 1024 B, Latency = 4. Increasing block size boosts sequential hit rate but inflates refill time.</text>

  <!-- Plot Area: x=100..750, y=90..400 -->
  <rect x="100" y="90" width="650" height="310" fill="#0f172a" stroke="#1e293b" rx="6"/>

  <g stroke="#1e293b" stroke-dasharray="3,3" stroke-width="1">
    <line x1="100" y1="400" x2="750" y2="400"/>
    <line x1="100" y1="322.5" x2="750" y2="322.5"/>
    <line x1="100" y1="245" x2="750" y2="245"/>
    <line x1="100" y1="167.5" x2="750" y2="167.5"/>
    <line x1="100" y1="90" x2="750" y2="90"/>
  </g>

  <g font-size="11" fill="#64748b" text-anchor="end">
    <text x="90" y="404">0% / 0 cyc</text>
    <text x="90" y="326">25% / 20 cyc</text>
    <text x="90" y="249">50% / 40 cyc</text>
    <text x="90" y="171">75% / 60 cyc</text>
    <text x="90" y="94">100% / 80 cyc</text>
  </g>

  <g font-size="12" fill="#cbd5e1" text-anchor="middle">
    <text x="140" y="425">4 B (1 word)</text>
    <text x="277" y="425">8 B (2 words)</text>
    <text x="425" y="425">16 B (4 words)</text>
    <text x="572" y="425">32 B (8 words)</text>
    <text x="710" y="425">64 B (16 words)</text>
    <text x="425" y="450" font-weight="600" fill="#94a3b8">Block Size (Bytes)</text>
  </g>
"""
    x_coords = {4: 140, 8: 277, 16: 425, 32: 572, 64: 710}

    # Sequential hit rate
    seq_rows = [r for r in data if r["trace"] == "sequential.trace"]
    seq_pts = [(x_coords[int(r["block_size"])], 400 - (float(r["hit_rate_pct"]) / 100.0) * 310) for r in seq_rows]
    seq_d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in seq_pts)
    svg += f'  <path d="{seq_d}" fill="none" stroke="#38bdf8" stroke-width="3"/>\n'
    for x, y in seq_pts:
        svg += f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#38bdf8"/>\n'

    # Sequential AMAT (scale: 0 to 80 cycles)
    seq_amat_pts = [(x_coords[int(r["block_size"])], 400 - (float(r["amat"]) / 80.0) * 310) for r in seq_rows]
    seq_amat_d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in seq_amat_pts)
    svg += f'  <path d="{seq_amat_d}" fill="none" stroke="#34d399" stroke-width="3" stroke-dasharray="6,4"/>\n'
    for x, y in seq_amat_pts:
        svg += f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#34d399"/>\n'

    # Strided AMAT (poor locality: every access misses, penalty surges!)
    str_rows = [r for r in data if r["trace"] == "strided.trace"]
    str_amat_pts = [(x_coords[int(r["block_size"])], 400 - (float(r["amat"]) / 85.0) * 310) for r in str_rows]
    str_amat_d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in str_amat_pts)
    svg += f'  <path d="{str_amat_d}" fill="none" stroke="#f43f5e" stroke-width="3"/>\n'
    for x, y in str_amat_pts:
        svg += f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#f43f5e"/>\n'

    svg += """  <!-- Legend -->
  <g transform="translate(100, 470)" font-size="11">
    <circle cx="10" cy="5" r="4" fill="#38bdf8"/>
    <text x="22" y="9" fill="#cbd5e1">Sequential Hit Rate (%)</text>

    <line x1="200" y1="5" x2="225" y2="5" stroke="#34d399" stroke-width="2.5" stroke-dasharray="4,3"/>
    <text x="235" y="9" fill="#cbd5e1">Sequential AMAT (Cycles = 8.0 const)</text>

    <circle cx="480" cy="5" r="4" fill="#f43f5e"/>
    <text x="492" y="9" fill="#cbd5e1">Strided AMAT (Surges from 8 → 83 cyc!)</text>
  </g>
</svg>"""

    with open(svg_path, "w") as f:
        f.write(svg)
    print(f"Generated {svg_path}")


def generate_latency_plot():
    data = load_csv("latency_sweep.csv")
    svg_path = os.path.join(DOCS_PLOTS, "plot_latency_sensitivity.svg")

    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 850 500" width="100%" height="100%" style="background-color: #0b1120; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <text x="40" y="38" font-size="20" font-weight="700" fill="#f8fafc">Memory Latency Sensitivity: AMAT vs. Memory Delay</text>
  <text x="40" y="60" font-size="12" fill="#94a3b8">Cache = 1024 B, Block = 16 B. Demonstrates insulation of hit-heavy workloads vs. miss-heavy workloads.</text>

  <rect x="100" y="90" width="650" height="310" fill="#0f172a" stroke="#1e293b" rx="6"/>

  <g stroke="#1e293b" stroke-dasharray="3,3" stroke-width="1">
    <line x1="100" y1="400" x2="750" y2="400"/>
    <line x1="100" y1="322.5" x2="750" y2="322.5"/>
    <line x1="100" y1="245" x2="750" y2="245"/>
    <line x1="100" y1="167.5" x2="750" y2="167.5"/>
    <line x1="100" y1="90" x2="750" y2="90"/>
  </g>

  <g font-size="11" fill="#64748b" text-anchor="end">
    <text x="90" y="404">0 cyc</text>
    <text x="90" y="326">20 cyc</text>
    <text x="90" y="249">40 cyc</text>
    <text x="90" y="171">60 cyc</text>
    <text x="90" y="94">80 cyc</text>
  </g>

  <g font-size="12" fill="#cbd5e1" text-anchor="middle">
    <text x="140" y="425">L = 1</text>
    <text x="277" y="425">L = 2</text>
    <text x="425" y="425">L = 4 (default)</text>
    <text x="572" y="425">L = 8</text>
    <text x="710" y="425">L = 16</text>
    <text x="425" y="450" font-weight="600" fill="#94a3b8">Memory Latency per Word (Cycles)</text>
  </g>
"""
    x_coords = {1: 140, 2: 277, 4: 425, 8: 572, 16: 710}
    traces = ["conflict.trace", "sequential.trace", "repeated_loop.trace"]
    colors = {"conflict.trace": "#f43f5e", "sequential.trace": "#38bdf8", "repeated_loop.trace": "#34d399"}

    for tr in traces:
        rows = [r for r in data if r["trace"] == tr]
        pts = [(x_coords[int(r["latency"])], 400 - (float(r["amat"]) / 80.0) * 310) for r in rows]
        path_d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
        c = colors[tr]
        svg += f'  <path d="{path_d}" fill="none" stroke="{c}" stroke-width="3"/>\n'
        for x, y in pts:
            svg += f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{c}"/>\n'

    svg += """  <!-- Legend -->
  <g transform="translate(100, 470)" font-size="11">
    <circle cx="10" cy="5" r="4" fill="#f43f5e"/>
    <text x="22" y="9" fill="#cbd5e1">Conflict (0% Hit Rate: Sharp Linear Surge)</text>

    <circle cx="310" cy="5" r="4" fill="#38bdf8"/>
    <text x="322" y="9" fill="#cbd5e1">Sequential (75% Hit Rate: Moderate Slope)</text>

    <circle cx="610" cy="5" r="4" fill="#34d399"/>
    <text x="622" y="9" fill="#cbd5e1">Repeated Loop (93.8%: Insulated)</text>
  </g>
</svg>"""

    with open(svg_path, "w") as f:
        f.write(svg)
    print(f"Generated {svg_path}")


def generate_speedup_plot():
    data = load_csv("cache_size_sweep.csv")
    svg_path = os.path.join(DOCS_PLOTS, "plot_speedup_vs_nocache.svg")

    # Bar chart for default configuration (1 KB, 16 B, L=4, WA=0)
    rows = [r for r in data if int(r["cache_size"]) == 1024]

    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 850 480" width="100%" height="100%" style="background-color: #0b1120; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <text x="40" y="38" font-size="20" font-weight="700" fill="#f8fafc">Performance Speedup: Cache vs. No-Cache Baseline</text>
  <text x="40" y="60" font-size="12" fill="#94a3b8">Baseline: Single-word access directly to main memory (8 cycles/access at Latency 4). Speedup &gt; 1.0x indicates performance gain.</text>

  <!-- Plot Area -->
  <rect x="180" y="90" width="600" height="320" fill="#0f172a" stroke="#1e293b" rx="6"/>

  <!-- Baseline 1.0x Line -->
  <line x1="380" y1="90" x2="380" y2="410" stroke="#f59e0b" stroke-width="2" stroke-dasharray="4,4"/>
  <text x="380" y="80" font-size="11" font-weight="700" fill="#f59e0b" text-anchor="middle">1.0x (No-Cache Baseline)</text>

  <g font-size="12" fill="#cbd5e1" text-anchor="end">
"""
    y = 120
    for r in rows:
        name = r["trace"].replace(".trace", "")
        speedup = float(r["speedup"])
        # map speedup 0..2.5 to width: 0 is x=180, 1.0 is x=380, 2.0 is x=580 (width per 1.0x = 200px)
        bar_w = speedup * 200
        color = "#34d399" if speedup >= 1.0 else "#f43f5e"

        svg += f'    <text x="170" y="{y+16}">{name}</text>\n'
        svg += f'    <rect x="180" y="{y}" width="{bar_w:.1f}" height="24" rx="4" fill="{color}"/>\n'
        svg += f'    <text x="{180 + bar_w + 10:.1f}" y="{y+17}" font-size="11" font-weight="700" fill="{color}" text-anchor="start">{speedup:.2f}x ({r["avg_cycles"]} cyc)</text>\n'
        y += 38

    svg += """  </g>
</svg>"""

    with open(svg_path, "w") as f:
        f.write(svg)
    print(f"Generated {svg_path}")


def main():
    generate_cache_size_plot()
    generate_block_size_plot()
    generate_latency_plot()
    generate_speedup_plot()
    print("All performance plots successfully generated.")


if __name__ == "__main__":
    main()
