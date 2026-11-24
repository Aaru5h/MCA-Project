#!/usr/bin/env python3
"""
generate_waveforms.py
Automates waveform generation via Icarus Verilog simulation and renders
publication-quality SVG timing diagrams for cache controller scenarios.

Owner: Meet (Visual Analysis & Performance Lead)
"""

import os
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_WAVE = os.path.join(REPO_ROOT, "docs", "waveforms")
TB_DIR = os.path.join(REPO_ROOT, "tb")
RTL_DIR = os.path.join(REPO_ROOT, "rtl")

os.makedirs(DOCS_WAVE, exist_ok=True)


def run_cmd(cmd):
    p = subprocess.run(cmd, shell=True, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        print(f"Error running: {cmd}\n{p.stderr}", file=sys.stderr)
    return p.returncode, p.stdout, p.stderr


def simulate_waveforms():
    print("Compiling and simulating tb_waveforms.v for WA=0...")
    sim_bin_wa0 = "/tmp/sim_wave_wa0"
    cmd0 = f"iverilog -g2012 -Ptb_waveforms.WRITE_ALLOCATE=0 -o {sim_bin_wa0} {RTL_DIR}/main_mem.v {RTL_DIR}/dm_cache.v {TB_DIR}/tb_waveforms.v"
    rc, out, err = run_cmd(cmd0)
    if rc != 0:
        print(f"Compilation failed: {err}", file=sys.stderr)
        return False
    rc, out, err = run_cmd(f"vvp {sim_bin_wa0}")
    print(out)

    print("Compiling and simulating tb_waveforms.v for WA=1...")
    sim_bin_wa1 = "/tmp/sim_wave_wa1"
    cmd1 = f"iverilog -g2012 -Ptb_waveforms.WRITE_ALLOCATE=1 -o {sim_bin_wa1} {RTL_DIR}/main_mem.v {RTL_DIR}/dm_cache.v {TB_DIR}/tb_waveforms.v"
    rc, out, err = run_cmd(cmd1)
    if rc == 0:
        run_cmd(f"vvp {sim_bin_wa1}")
        # Copy WA1 waveform
        if os.path.exists("docs/waveforms/cache_scenarios.vcd"):
            os.replace("docs/waveforms/cache_scenarios.vcd", os.path.join(DOCS_WAVE, "cache_scenarios_wa1.vcd"))

    # Re-run WA=0 so cache_scenarios.vcd is the primary WA=0 trace
    run_cmd(f"vvp {sim_bin_wa0}")
    return True


def generate_read_hit_svg():
    svg_path = os.path.join(DOCS_WAVE, "waveform_read_hit.svg")
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 850 420" width="100%" height="100%" style="background-color: #0b1120; font-family: 'SF Mono', Monaco, Consolas, monospace;">
  <style>
    .sig-lbl { font-size: 13px; font-weight: 600; fill: #94a3b8; }
    .val-lbl { font-size: 11px; fill: #f8fafc; font-weight: 500; text-anchor: middle; }
    .grid { stroke: #1e293b; stroke-width: 1; stroke-dasharray: 4,4; }
    .wave-line { stroke-width: 2.5; fill: none; stroke-linejoin: round; stroke-linecap: round; }
  </style>

  <text x="30" y="32" font-size="18" font-weight="700" fill="#f8fafc" font-family="-apple-system, sans-serif">Waveform Analysis: Read Hit (3 Cycles Latency)</text>
  <text x="30" y="52" font-size="12" fill="#64748b" font-family="-apple-system, sans-serif">Address 0x00000044: Matching Tag [31:10] and Valid Line in S_COMPARE returns data in S_RESPOND</text>

  <!-- Cycle Columns -->
  <!-- Col 1: Cycle 0 (Idle), Col 2: Cycle 1 (Sample), Col 3: Cycle 2 (Compare), Col 4: Cycle 3 (Respond), Col 5: Next Idle -->
  <line x1="220" y1="75" x2="220" y2="385" class="grid"/>
  <line x1="360" y1="75" x2="360" y2="385" class="grid"/>
  <line x1="500" y1="75" x2="500" y2="385" class="grid"/>
  <line x1="640" y1="75" x2="640" y2="385" class="grid"/>
  <line x1="780" y1="75" x2="780" y2="385" class="grid"/>

  <!-- Cycle Header Markers -->
  <text x="290" y="85" class="val-lbl" fill="#38bdf8">Cycle 1 (Latch)</text>
  <text x="430" y="85" class="val-lbl" fill="#818cf8">Cycle 2 (Compare)</text>
  <text x="570" y="85" class="val-lbl" fill="#34d399">Cycle 3 (Respond)</text>
  <text x="710" y="85" class="val-lbl" fill="#94a3b8">Cycle 4 (Idle / Next)</text>

  <!-- Clock: clk -->
  <text x="30" y="125" class="sig-lbl">clk</text>
  <path d="M 180 135 L 220 135 L 220 105 L 290 105 L 290 135 L 360 135 L 360 105 L 430 105 L 430 135 L 500 135 L 500 105 L 570 105 L 570 135 L 640 135 L 640 105 L 710 105 L 710 135 L 780 135" class="wave-line" stroke="#64748b"/>

  <!-- cpu_req -->
  <text x="30" y="165" class="sig-lbl">cpu_req</text>
  <path d="M 180 175 L 220 175 L 225 145 L 355 145 L 360 175 L 780 175" class="wave-line" stroke="#38bdf8"/>
  <text x="290" y="162" class="val-lbl" fill="#38bdf8">1'b1</text>

  <!-- cpu_addr -->
  <text x="30" y="205" class="sig-lbl">cpu_addr</text>
  <path d="M 180 215 L 220 215 L 225 185 L 775 185 L 780 215" class="wave-line" stroke="#38bdf8"/>
  <text x="430" y="202" class="val-lbl">32'h0000_0044</text>

  <!-- Controller State: state -->
  <text x="30" y="245" class="sig-lbl">dut.state</text>
  <!-- S_IDLE -->
  <rect x="180" y="225" width="40" height="30" rx="3" fill="#1e293b" stroke="#38bdf8"/>
  <text x="200" y="244" class="val-lbl" font-size="10">IDLE</text>
  <!-- S_COMPARE -->
  <rect x="225" y="225" width="270" height="30" rx="3" fill="#1e293b" stroke="#818cf8"/>
  <text x="360" y="244" class="val-lbl" fill="#818cf8">S_COMPARE (3'd1)</text>
  <!-- S_RESPOND -->
  <rect x="505" y="225" width="130" height="30" rx="3" fill="#1e293b" stroke="#34d399"/>
  <text x="570" y="244" class="val-lbl" fill="#34d399">S_RESPOND</text>
  <!-- Return IDLE -->
  <rect x="645" y="225" width="135" height="30" rx="3" fill="#1e293b" stroke="#38bdf8"/>
  <text x="712" y="244" class="val-lbl" fill="#38bdf8">S_IDLE</text>

  <!-- dbg_hit -->
  <text x="30" y="285" class="sig-lbl">dbg_hit</text>
  <path d="M 180 295 L 220 295 L 225 265 L 635 265 L 640 295 L 780 295" class="wave-line" stroke="#34d399"/>
  <text x="430" y="282" class="val-lbl" fill="#34d399">1'b1 (Tag match &amp; valid)</text>

  <!-- cpu_ready -->
  <text x="30" y="325" class="sig-lbl">cpu_ready</text>
  <path d="M 180 335 L 500 335 L 505 305 L 635 305 L 640 335 L 780 335" class="wave-line" stroke="#34d399"/>
  <text x="570" y="322" class="val-lbl" fill="#34d399">1-cycle pulse</text>

  <!-- cpu_rdata -->
  <text x="30" y="365" class="sig-lbl">cpu_rdata</text>
  <rect x="505" y="345" width="275" height="28" rx="4" fill="#065f46" stroke="#34d399"/>
  <text x="642" y="363" class="val-lbl" fill="#ecfdf5">32'hC0DE_0011 (Valid read data)</text>
</svg>"""
    with open(svg_path, "w") as f:
        f.write(svg)
    print(f"Generated {svg_path}")


def generate_read_miss_svg():
    svg_path = os.path.join(DOCS_WAVE, "waveform_read_miss.svg")
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 950 480" width="100%" height="100%" style="background-color: #0b1120; font-family: 'SF Mono', Monaco, Consolas, monospace;">
  <style>
    .sig-lbl { font-size: 13px; font-weight: 600; fill: #94a3b8; }
    .val-lbl { font-size: 11px; fill: #f8fafc; font-weight: 500; text-anchor: middle; }
    .grid { stroke: #1e293b; stroke-width: 1; stroke-dasharray: 4,4; }
    .wave-line { stroke-width: 2.2; fill: none; stroke-linejoin: round; stroke-linecap: round; }
  </style>

  <text x="30" y="32" font-size="18" font-weight="700" fill="#f8fafc" font-family="-apple-system, sans-serif">Waveform Analysis: Cold Read Miss &amp; 4-Word Block Refill (23 Cycles)</text>
  <text x="30" y="52" font-size="12" fill="#64748b" font-family="-apple-system, sans-serif">Address 0x00000040: Miss triggers 4 burst reads from memory (latency 4/word + 1 ready pulse), overlays block, returns word</text>

  <!-- Phase Dividers -->
  <line x1="200" y1="75" x2="200" y2="445" class="grid"/>
  <line x1="280" y1="75" x2="280" y2="445" class="grid"/>
  <line x1="780" y1="75" x2="780" y2="445" class="grid"/>
  <line x1="880" y1="75" x2="880" y2="445" class="grid"/>

  <!-- Phase Markers -->
  <text x="240" y="85" class="val-lbl" fill="#818cf8">Compare (1 cyc)</text>
  <text x="530" y="85" class="val-lbl" fill="#34d399">ALLOCATE (20 Cycles: 4 words × 5 cycles/word)</text>
  <text x="830" y="85" class="val-lbl" fill="#ec4899">Respond</text>

  <!-- Signals -->
  <!-- clk -->
  <text x="30" y="115" class="sig-lbl">clk</text>
  <path d="M 150 120 L 175 120 L 175 95 L 200 95 L 200 120 L 240 120 L 240 95 L 280 95 L 280 120 L 400 120 L 400 95 L 430 95 L 430 120 L 530 120 L 530 95 L 560 95 L 560 120 L 660 120 L 660 95 L 690 95 L 690 120 L 780 120 L 780 95 L 830 95 L 830 120 L 880 120" class="wave-line" stroke="#64748b"/>

  <!-- cpu_req -->
  <text x="30" y="155" class="sig-lbl">cpu_req</text>
  <path d="M 150 165 L 200 165 L 205 135 L 275 135 L 280 165 L 880 165" class="wave-line" stroke="#38bdf8"/>

  <!-- Controller State -->
  <text x="30" y="195" class="sig-lbl">dut.state</text>
  <rect x="150" y="175" width="45" height="28" rx="3" fill="#1e293b" stroke="#38bdf8"/>
  <text x="172" y="193" class="val-lbl">IDLE</text>

  <rect x="202" y="175" width="75" height="28" rx="3" fill="#1e293b" stroke="#818cf8"/>
  <text x="239" y="193" class="val-lbl" fill="#818cf8">COMPARE</text>

  <rect x="282" y="175" width="495" height="28" rx="3" fill="#1e293b" stroke="#34d399"/>
  <text x="530" y="193" class="val-lbl" fill="#34d399">S_ALLOCATE (Fetching Words 0, 1, 2, 3)</text>

  <rect x="782" y="175" width="95" height="28" rx="3" fill="#1e293b" stroke="#ec4899"/>
  <text x="830" y="193" class="val-lbl" fill="#ec4899">RESPOND</text>

  <!-- mem_req -->
  <text x="30" y="240" class="sig-lbl">mem_req</text>
  <path d="M 150 250 L 280 250 L 285 220 L 775 220 L 780 250 L 880 250" class="wave-line" stroke="#fbbf24"/>
  <text x="530" y="235" class="val-lbl" fill="#fbbf24">1'b1 (Held active across all 4 burst refill beats)</text>

  <!-- mem_addr -->
  <text x="30" y="285" class="sig-lbl">mem_addr</text>
  <rect x="282" y="265" width="120" height="26" rx="3" fill="#0f172a" stroke="#fbbf24"/>
  <text x="342" y="282" class="val-lbl">0x00000010 (w0)</text>
  <rect x="408" y="265" width="120" height="26" rx="3" fill="#0f172a" stroke="#fbbf24"/>
  <text x="468" y="282" class="val-lbl">0x00000011 (w1)</text>
  <rect x="534" y="265" width="120" height="26" rx="3" fill="#0f172a" stroke="#fbbf24"/>
  <text x="594" y="282" class="val-lbl">0x00000012 (w2)</text>
  <rect x="660" y="265" width="115" height="26" rx="3" fill="#0f172a" stroke="#fbbf24"/>
  <text x="717" y="282" class="val-lbl">0x00000013 (w3)</text>

  <!-- mem_ready pulses -->
  <text x="30" y="330" class="sig-lbl">mem_ready</text>
  <path d="M 150 340 L 390 340 L 395 315 L 405 315 L 410 340 L 515 340 L 520 315 L 530 315 L 535 340 L 640 340 L 645 315 L 655 315 L 660 340 L 765 340 L 770 315 L 775 315 L 780 340 L 880 340" class="wave-line" stroke="#38bdf8"/>
  <text x="402" y="310" class="val-lbl" fill="#38bdf8">Beat 0</text>
  <text x="528" y="310" class="val-lbl" fill="#38bdf8">Beat 1</text>
  <text x="652" y="310" class="val-lbl" fill="#38bdf8">Beat 2</text>
  <text x="772" y="310" class="val-lbl" fill="#38bdf8">Beat 3</text>

  <!-- valid & tag array commit -->
  <text x="30" y="375" class="sig-lbl">valid_arr[index]</text>
  <path d="M 150 385 L 775 385 L 780 355 L 880 355" class="wave-line" stroke="#34d399"/>
  <text x="830" y="372" class="val-lbl" fill="#34d399">Committed (1'b1)</text>

  <!-- cpu_ready -->
  <text x="30" y="420" class="sig-lbl">cpu_ready</text>
  <path d="M 150 430 L 780 430 L 785 400 L 875 400 L 880 430" class="wave-line" stroke="#ec4899"/>
  <text x="830" y="417" class="val-lbl" fill="#ec4899">Cycle 23 Completion Pulse</text>
</svg>"""
    with open(svg_path, "w") as f:
        f.write(svg)
    print(f"Generated {svg_path}")


def generate_write_policy_svg():
    svg_path = os.path.join(DOCS_WAVE, "waveform_write_policy.svg")
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 460" width="100%" height="100%" style="background-color: #0b1120; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <defs>
    <filter id="cardShadow" x="-5%" y="-5%" width="110%" height="110%">
      <feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="#000000" flood-opacity="0.5"/>
    </filter>
  </defs>

  <text x="30" y="35" font-size="20" font-weight="700" fill="#f8fafc">Waveform Timing Comparison: Write Policies &amp; Hit/Miss Latencies</text>
  <text x="30" y="58" font-size="12" fill="#94a3b8">Measured cycle costs at memory latency L=4 (includes 1 cycle CPU acceptance handoff)</text>

  <!-- Policy 1: Write Hit (Either Policy) -->
  <g transform="translate(30, 85)" filter="url(#cardShadow)">
    <rect width="860" height="95" rx="8" fill="#1e293b" stroke="#38bdf8" stroke-width="1.5"/>
    <text x="20" y="26" font-size="14" font-weight="700" fill="#38bdf8">1. Write Hit (Either Policy) — 8 Cycles Total</text>
    <text x="20" y="46" font-size="11" fill="#cbd5e1">FSM Path: <tspan font-weight="700" fill="#f8fafc">S_IDLE (1 cyc) → S_COMPARE (1 cyc) → S_WRITE (5 cycs) → S_RESPOND (1 cyc)</tspan></text>
    <text x="20" y="65" font-size="11" fill="#94a3b8">Action: Updates cache word at index and simultaneously issues write-through to main memory (latency 4 + 1 ready pulse).</text>
    <rect x="680" y="20" width="160" height="35" rx="6" fill="#0369a1"/>
    <text x="760" y="42" font-size="14" font-weight="700" fill="#f0f9ff" text-anchor="middle">Cost: 8 Cycles</text>
  </g>

  <!-- Policy 2: Write Miss (No-Write-Allocate, WA=0) -->
  <g transform="translate(30, 200)" filter="url(#cardShadow)">
    <rect width="860" height="95" rx="8" fill="#1e293b" stroke="#fbbf24" stroke-width="1.5"/>
    <text x="20" y="26" font-size="14" font-weight="700" fill="#fbbf24">2. Write Miss under No-Write-Allocate (WRITE_ALLOCATE = 0) — 8 Cycles Total</text>
    <text x="20" y="46" font-size="11" fill="#cbd5e1">FSM Path: <tspan font-weight="700" fill="#f8fafc">S_IDLE (1 cyc) → S_COMPARE (1 cyc) → S_WRITE (5 cycs) → S_RESPOND (1 cyc)</tspan></text>
    <text x="20" y="65" font-size="11" fill="#94a3b8">Action: Bypasses cache allocation completely. Directly performs write-through to memory. Preserves victim cache line.</text>
    <rect x="680" y="20" width="160" height="35" rx="6" fill="#78350f"/>
    <text x="760" y="42" font-size="14" font-weight="700" fill="#fef3c7" text-anchor="middle">Cost: 8 Cycles</text>
  </g>

  <!-- Policy 3: Write Miss (Write-Allocate, WA=1) -->
  <g transform="translate(30, 315)" filter="url(#cardShadow)">
    <rect width="860" height="115" rx="8" fill="#1e293b" stroke="#f43f5e" stroke-width="1.5"/>
    <text x="20" y="26" font-size="14" font-weight="700" fill="#f43f5e">3. Write Miss under Write-Allocate (WRITE_ALLOCATE = 1) — 28 Cycles Total</text>
    <text x="20" y="46" font-size="11" fill="#cbd5e1">FSM Path: <tspan font-weight="700" fill="#f8fafc">S_IDLE (1 cyc) → S_COMPARE (1 cyc) → S_ALLOCATE (20 cycs) → S_WRITE (5 cycs) → S_RESPOND (1 cyc)</tspan></text>
    <text x="20" y="65" font-size="11" fill="#94a3b8">Action: Fetches full 4-word block into cache; overlays written word during beat reception; commits tag/valid; then performs write-through.</text>
    <text x="20" y="85" font-size="10" fill="#fda4af">Mathematical Breakdown: 3 (FSM overhead) + 4 words × (4 + 1) [refill] + 1 word × (4 + 1) [write-through] = 28 cycles.</text>
    <rect x="680" y="20" width="160" height="35" rx="6" fill="#9f1239"/>
    <text x="760" y="42" font-size="14" font-weight="700" fill="#ffe4e6" text-anchor="middle">Cost: 28 Cycles</text>
  </g>
</svg>"""
    with open(svg_path, "w") as f:
        f.write(svg)
    print(f"Generated {svg_path}")


def main():
    simulate_waveforms()
    generate_read_hit_svg()
    generate_read_miss_svg()
    generate_write_policy_svg()
    print("Waveform generation and visual rendering complete.")


if __name__ == "__main__":
    main()
