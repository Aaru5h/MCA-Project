#!/usr/bin/env python3
"""Build the Phase II IEEE-style PDF from this self-contained source directory.

Usage: python3 report/source/build_report.py
Requires reportlab and svglib; see BUILD.txt. No LaTeX is used.
"""
import argparse
import csv
import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import BaseDocTemplate, Frame, FrameBreak, PageBreak, PageTemplate
from reportlab.platypus import NextPageTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from svglib.svglib import svg2rlg

HERE = Path(__file__).resolve().parent
W, H, M, GAP = 612, 792, 45, 18
CW, FULL = (W - 2 * M - GAP) / 2, W - 2 * M
BOTTOM, TOP = 48, 738


def register_fonts(directory=None):
    candidates = [Path(directory)] if directory else [
        Path('/System/Library/Fonts/Supplemental'), Path('C:/Windows/Fonts'),
        Path('/usr/share/fonts/truetype/msttcorefonts'),
        Path('/usr/share/fonts/truetype/liberation2'),
        Path('/usr/share/fonts/truetype/liberation'),
    ]
    sets = [
        ('Times New Roman.ttf', 'Times New Roman Bold.ttf', 'Times New Roman Italic.ttf'),
        ('times.ttf', 'timesbd.ttf', 'timesi.ttf'),
        ('LiberationSerif-Regular.ttf', 'LiberationSerif-Bold.ttf', 'LiberationSerif-Italic.ttf'),
    ]
    for directory in candidates:
        for names in sets:
            if all((directory / name).is_file() for name in names):
                for alias, name in zip(('Paper', 'PaperBold', 'PaperItalic'), names):
                    pdfmetrics.registerFont(TTFont(alias, str(directory / name)))
                pdfmetrics.registerFontFamily('Paper', normal='Paper', bold='PaperBold',
                                              italic='PaperItalic', boldItalic='PaperBold')
                for alias in ('Helvetica', 'Times-Roman'):
                    pdfmetrics.registerFont(TTFont(alias, str(directory / names[0])))
                return
    raise RuntimeError('Times New Roman or Liberation Serif fonts are required; use --font-dir.')


def read_csv(name):
    with (HERE / 'data' / name).open(newline='') as handle:
        return list(csv.DictReader(handle))


def arrow(d, x1, y1, x2, y2):
    d.add(Line(x1, y1, x2, y2, strokeWidth=.65, strokeColor=colors.black))
    angle = math.atan2(y2 - y1, x2 - x1)
    d.add(Polygon([x2, y2, x2 - 4 * math.cos(angle - .45), y2 - 4 * math.sin(angle - .45),
                   x2 - 4 * math.cos(angle + .45), y2 - 4 * math.sin(angle + .45)],
                  fillColor=colors.black, strokeColor=colors.black))


def box(d, x, y, width, height, lines):
    d.add(Rect(x, y, width, height, strokeWidth=.55, strokeColor=colors.black,
               fillColor=colors.HexColor('#f5f5f5')))
    for index, text in enumerate(lines):
        d.add(String(x + width / 2, y + height / 2 + (len(lines) - 1) * 5 - index * 10,
                     text, fontName='Paper', fontSize=7.8, textAnchor='middle'))


def architecture():
    d = Drawing(CW, 135)
    box(d, 1, 93, 56, 33, ['CPU trace', 'driver'])
    box(d, 79, 93, 90, 33, ['Request registers', '+ controller FSM'])
    box(d, 192, 93, 59, 33, ['Main memory', 'L cycles/word'])
    arrow(d, 57, 116, 79, 116); arrow(d, 79, 102, 57, 102)
    arrow(d, 169, 116, 192, 116); arrow(d, 192, 102, 169, 102)
    box(d, 4, 28, 80, 37, ['Valid + tag array', 'Index + tag match'])
    box(d, 100, 28, 147, 37, ['Data array and word selector', 'Refill / write overlay'])
    arrow(d, 112, 93, 44, 65); arrow(d, 140, 93, 173, 65); arrow(d, 84, 46, 100, 46)
    d.add(String(CW / 2, 8, 'Traffic counters observe completed memory words',
                 fontName='PaperItalic', fontSize=8, textAnchor='middle'))
    return d


def fsm():
    d = Drawing(CW, 145)
    box(d, 4, 105, 50, 25, ['IDLE']); box(d, 96, 105, 64, 25, ['COMPARE'])
    box(d, 194, 105, 54, 25, ['RESPOND'])
    box(d, 72, 32, 72, 28, ['ALLOCATE']); box(d, 181, 32, 67, 28, ['WRITE'])
    arrow(d, 54, 117, 96, 117); arrow(d, 160, 117, 194, 117)
    d.add(String(177, 127, 'read hit', fontName='Paper', fontSize=6.8, textAnchor='middle'))
    arrow(d, 112, 105, 112, 60)
    d.add(String(106, 83, 'read miss /', fontName='Paper', fontSize=6.7, textAnchor='end'))
    d.add(String(106, 73, 'WA write miss', fontName='Paper', fontSize=6.7, textAnchor='end'))
    arrow(d, 154, 105, 214, 60); arrow(d, 144, 46, 181, 46); arrow(d, 221, 60, 221, 105)
    d.add(String(204, 82, 'other writes', fontName='Paper', fontSize=6.8, textAnchor='middle'))
    d.add(String(162, 35, 'WA', fontName='Paper', fontSize=6.8, textAnchor='middle'))
    arrow(d, 140, 60, 198, 105)
    d.add(Line(220, 130, 220, 140, strokeWidth=.6))
    d.add(Line(220, 140, 29, 140, strokeWidth=.6)); arrow(d, 29, 140, 29, 130)
    d.add(String(CW / 2, 8, 'Reset: invalidate lines and return to IDLE',
                 fontName='Paper', fontSize=8, textAnchor='middle'))
    return d


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE.parent / 'MCA_Direct_Mapped_Cache_IEEE_Report.pdf')
    parser.add_argument('--font-dir', type=Path)
    args = parser.parse_args()
    register_fonts(args.font_dir)
    styles = {
        'body': ParagraphStyle('body', fontName='Paper', fontSize=10, leading=11.5,
                               alignment=TA_JUSTIFY, firstLineIndent=10, spaceAfter=5),
        'abstract': ParagraphStyle('abstract', fontName='PaperBold', fontSize=9, leading=10.5,
                                   alignment=TA_JUSTIFY, spaceAfter=7),
        'section': ParagraphStyle('section', fontName='Paper', fontSize=10, leading=12,
                                  alignment=TA_CENTER, spaceBefore=7, spaceAfter=6),
        'sub': ParagraphStyle('sub', fontName='PaperItalic', fontSize=10, leading=11.5,
                              spaceBefore=5, spaceAfter=5),
        'caption': ParagraphStyle('caption', fontName='Paper', fontSize=8.1, leading=9.4,
                                  spaceBefore=4, spaceAfter=7),
        'tcap': ParagraphStyle('tcap', fontName='Paper', fontSize=8.1, leading=9.5,
                               alignment=TA_CENTER, spaceBefore=6, spaceAfter=4),
        'cell': ParagraphStyle('cell', fontName='Paper', fontSize=8.1, leading=9.4),
        'headcell': ParagraphStyle('headcell', fontName='PaperBold', fontSize=8, leading=9.4),
        'eq': ParagraphStyle('eq', fontName='Paper', fontSize=9.2, leading=12,
                             alignment=TA_CENTER, spaceBefore=3, spaceAfter=5),
        'ref': ParagraphStyle('ref', fontName='Paper', fontSize=8.1, leading=9.6,
                              leftIndent=14, firstLineIndent=-14, spaceAfter=7, wordWrap='CJK'),
        'wide': ParagraphStyle('wide', fontName='Paper', fontSize=10, leading=12,
                               alignment=TA_JUSTIFY, spaceAfter=7),
    }
    def p(text, style='body'):
        return Paragraph(text, styles[style])
    def sec(text):
        return p(text.upper(), 'section')
    def sub(text):
        return p(text, 'sub')
    def table(title, headers, rows, widths):
        cells = [[p(escape(str(x)).replace('\n', '<br/>'), 'headcell') for x in headers]]
        cells += [[p(escape(str(x)), 'cell') for x in row] for row in rows]
        result = Table(cells, colWidths=widths, hAlign='CENTER')
        result.setStyle(TableStyle([
            ('LINEABOVE', (0, 0), (-1, 0), .55, colors.black),
            ('LINEBELOW', (0, 0), (-1, 0), .35, colors.black),
            ('LINEBELOW', (0, -1), (-1, -1), .55, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        return [p(title.replace('\n', '<br/>'), 'tcap'), result, Spacer(1, 5)]
    def external_plot(name):
        plot = svg2rlg(str(HERE / 'assets' / name))
        ratio = FULL / plot.width
        plot.scale(ratio, ratio)
        plot.width, plot.height = FULL, plot.height * ratio
        return plot

    workloads = {int(policy): read_csv(f'workloads_wa{policy}.csv') for policy in (0, 1)}
    def measured(name, policy=0):
        return next(row for row in workloads[policy] if row['trace'] == name + '.trace')
    resources = read_csv('resources.csv')
    traffic = read_csv('memory_traffic.csv')
    evidence = json.loads((HERE / 'data/evidence.json').read_text())
    assert len(resources) == 4 and len(traffic) == 16
    for row in traffic:
        assert int(row['mem_reads']) == 4 * (int(row['read_misses']) + int(row['write_allocate']) * int(row['write_misses']))
        assert row['mem_writes'] == row['cpu_writes']

    abstract = p('<b>Abstract</b> - This paper presents the Phase II design and evaluation of a parameterized direct-mapped cache controller in Verilog. The default 1 KB cache uses 16-byte blocks, write-through and selectable write allocation. New RTL counters measure completed backing-memory reads and writes. Across eight workloads, both policies transfer identical word totals at the default configuration; mixed traffic moves 64 read words and 91 write words. Allocation lowers its read AMAT from 4.94 to 3.97 cycles while the overall mean remains 6.03. A measured eight-cycle no-cache baseline gives 1.88 times speedup for repeated-loop traffic. Validation passes 336 hand-calculable cases, 64 workload comparisons and four invalid-address checks. Counter-enabled generic synthesis uses 12,797 cells at 512 B and 24,994/25,080 at 1 KB for allocation disabled/enabled. FPGA utilization and maximum frequency remain unmeasured.', 'abstract')
    index = p('<b><i>Index Terms</i></b> - Direct-mapped cache, Verilog, write allocation, memory traffic, AMAT, verification, generic synthesis.', 'abstract')
    ah, ih = abstract.wrap(FULL, 1000)[1], index.wrap(FULL, 1000)[1]
    first_top = 556 - ah - 9 - ih - 13

    cols = []
    # Page 1: literature review and configuration.
    cols.append([
        sec('I. Literature Review'),
        p('Memory hierarchies exploit temporal reuse of recently accessed data and spatial reuse of neighboring addresses. Direct mapping gives each block one possible cache line, simplifying selection and tag lookup; blocks sharing that line can nevertheless evict one another. Larger blocks capture adjacent words but increase refill work when those words are unused [1].'),
        p('Write policy determines when backing memory is updated and whether a write miss installs a line. Write-through propagates every store. Write allocation can benefit later reads of that block, while no-write-allocate avoids fetching unused neighbors for write-only traffic. Allocation must therefore be evaluated using both read latency and total memory traffic [1].'),
        p('Jouppi studied small fully associative miss/victim caches and stream buffers as additions to direct-mapped caches [2]. A victim cache retains displaced lines to reduce mapping conflicts; stream buffers target useful sequential prefetching. These mechanisms illustrate alternatives to simply increasing the main cache, but neither is implemented in this project.'),
        p('This work uses a small blocking controller to make these trade-offs observable. It adds policy-aware verification, completed-word traffic counters and an interface-matched measured baseline. The reported results concern the supplied finite traces and serial fixed-latency memory, rather than reproducing published application benchmarks or claiming processor-level speedup.'),
    ])
    cols.append([
        sec('II. Proposed Solution'),
        sub('A. Geometry and Interface'),
        p('The controller accepts aligned 32-bit byte addresses and transfers 32-bit words. Cache capacity C and block size B are powers of two, with C at least B and B at least four bytes. Phase II synthesizes both capacities in Table I.'),
        *table('TABLE I\nPHASE II CACHE AND EXPERIMENT CONFIGURATION', ['Parameter', '512 B', '1 KB'], [
            ('Data capacity', '512 bytes', '1024 bytes'), ('Lines / words per line', '32 / 4', '64 / 4'),
            ('Tag / index bits', '23 / 5', '22 / 6'), ('Block / offset bits', '16 B / 4', '16 B / 4'),
            ('Word width', '32 bits', '32 bits'), ('Memory window', '16 KB', '16 KB'),
            ('Default memory latency', '4 cycles', '4 cycles'), ('Write allocation', '0 and 1', '0 and 1'),
            ('Traffic outputs', '2 x 32 bits', '2 x 32 bits'),
        ], [112, 70, 70]),
        p('For the default 1 KB cache, tag, index and offset occupy [31:10], [9:4] and [3:0]. Bits [3:2] select one of four words; [1:0] must be zero. Offset width is log<sub>2</sub>B, index width is log<sub>2</sub>(C/B), and the remaining bits form the tag.'),
        sub('B. Data Path'),
        p('Data, tag and valid arrays are indexed by the latched request. A hit requires a valid selected line and matching tag. The default data array stores 8192 bits and adds 1408 tag bits and 64 valid bits before controller, statistics and traffic-counter registers.'),
    ])
    # Page 2: solution details and experimental method.
    cols.append([
        sub('C. Controller and Write Policies'),
        p('The five-state FSM in Fig. 2 accepts one request at a time. IDLE latches its controls; COMPARE counts one hit or miss. Read hits return the selected word. ALLOCATE reads every block word in ascending order, committing the new tag and valid state after the final beat.'),
        architecture(), p('Fig. 1. Cache data path and fixed-latency memory interface. Completed-word counters observe the memory handshake.', 'caption'),
        fsm(), p('Fig. 2. Controller transitions. WA denotes write allocation. Refill and memory-wait self-loops are implicit.', 'caption'),
        p('Every write completes write-through before acknowledgement. A write hit updates the cached word. With WA = 0, a write miss preserves the victim line and bypasses allocation. With WA = 1, it refills the block, overlays the written word, commits the line, then writes to memory. Neighboring words retain their refill values.'),
        sub('D. Memory Handshake and Reset'),
        p('Memory latches the word address, direction and write data when a transaction starts. It completes after L sampling edges; the controller consumes registered ready on the following edge. This one-edge bubble lets the next refill address advance, adding one handoff cycle per word. Active-low synchronous reset invalidates cache lines and cancels unfinished transfers; memory contents already committed are retained.'),
    ])
    cols.append([
        sub('E. Traffic Counters and Timing Metrics'),
        p('Two 32-bit outputs, mem_reads and mem_writes, increment on a rising edge with mem_req and mem_ready, according to mem_we before the FSM advances. Each refill word counts separately. Both counters clear on synchronous reset and wrap after 2<super>32</super> increments. Canceled, incomplete words do not count.'),
        p('Read AMAT uses read cycles only; the weighted all-access mean includes every read and write. Unobserved class means are undefined, reported as N/A or JSON null. Let A be access count and R be read count:'),
        p('AMAT<sub>R</sub> = measured read cycles / R,  (1)', 'eq'),
        p('T<sub>all</sub> = total measured cycles / A.  (2)', 'eq'),
        p('Both benches drive on falling edges and count rising edges from CPU acceptance through completion, including acceptance as cycle 1. Initialization and idle gaps are excluded. The no-cache adapter retains accept, dispatch and response stages but performs one memory word per request; its measured cost is L + 4, or eight cycles at L = 4.'),
        sub('F. Verification and Workloads'),
        p('Icarus Verilog/vvp 13.0 [3] runs directed checks and a trace bench that compares returned reads with reference memory. Five directed configurations and 32 RTL/model trace comparisons pass. Independent performance checks cover seven hand cases, six geometries, four latencies and both policies: 336 comparisons. Eight workloads at four latencies and both policies add 64 comparisons; four negative checks reject invalid addresses.'),
        *table('TABLE II\nDETERMINISTIC TRACE SUITE', ['Trace', 'Accesses', 'Primary pattern'], [
            ('sequential', 256, '1 KB linear stream'), ('repeated_loop', 128, '4 passes over 32 words'),
            ('strided', 128, '64-byte stride'), ('conflict', 128, '0x40 / 0x440 / 0x840'),
            ('random', 256, 'Sampling within 1 KB'), ('mixed_rw', 256, '165 reads; 91 writes'),
            ('smoke', 14, 'Cold, conflict and writes'), ('seq_check', 512, '2 KB linear stream'),
        ], [83, 43, 126]),
        p('Generated random traffic uses seed 42. Every trace starts cold with the same known backing-memory contents. Phase II traffic measurements run each of the eight traces under both policies and verify the data and counter totals.'),
    ])
    # Page 3: numerical results and interpretation.
    default_rows = []
    for name in ('smoke', 'seq_check', 'sequential', 'repeated_loop', 'strided', 'conflict', 'random', 'mixed_rw'):
        row = measured(name)
        default_rows.append((name, row['accesses'], f"{float(row['read_amat']):.2f}",
                             f"{float(row['cache_avg_cycles']):.2f}", f"{float(row['speedup']):.2f}"))
    cols.append([
        sec('III. Results and Discussion'),
        sub('A. Measured Performance'),
        p('At 1 KB / 16 B / L = 4, measured costs are 3 cycles for a read hit, 23 for a read miss, 8 for an ordinary write and 28 for an allocating write miss. Table III uses WA = 0. All means are cycles; every baseline run measures 8 cycles/access.'),
        *table('TABLE III\nDEFAULT MEASURED WORKLOAD COMPARISON', ['Trace', 'A', 'Read\nAMAT', 'All\nmean', 'Speedup'], default_rows, [91, 30, 45, 43, 43]),
        p('The loop retains its 128-byte working set: 120 of 128 requests hit. It uses 544 cache cycles against 1024 baseline cycles. Smoke instead costs 136 read cycles and 16 write cycles: read AMAT is 136/12 = 11.33, while its all-access mean is 152/14 = 10.86. Its 112-cycle baseline is faster for this cold-start trace.'),
        sub('B. Allocation and Mixed-Traffic Cost'),
        *table('TABLE IV\nMIXED-RW POLICY COMPARISON', ['Metric', 'WA = 0', 'WA = 1'], [
            ('Read hits / misses', '149 / 16', '157 / 8'), ('Write hits / misses', '78 / 13', '83 / 8'),
            ('Read AMAT (cycles)', '4.939394', '3.969697'), ('All-access mean', '6.027344', '6.027344'),
            ('Cache total cycles', '1543', '1543'), ('Baseline cycles', '2048', '2048'),
        ], [116, 68, 68]),
        p('Allocation reduces mixed-trace read cost from 815 to 655 cycles, but raises write cost from 728 to 888. The 160-cycle read saving is exactly offset by write cost. Read AMAT improves by 19.63%, yet total service cost and 1.33 times speedup remain unchanged. Higher hit rate alone therefore does not establish faster mixed traffic.'),
        p('The broader model-based sweeps contain 136 rows, or 112 unique configurations. They predict sequential cost L + 4 despite larger blocks, and strided cost rising from 8 to 83 cycles as blocks grow from 4 to 64 bytes. These analytical results are distinct from measured RTL runs.'),
    ])
    traffic_rows = []
    for name in ('mixed_rw', 'smoke'):
        for policy in (0, 1):
            row = next(r for r in traffic if r['trace'] == name + '.trace' and int(r['write_allocate']) == policy)
            traffic_rows.append((name, policy, row['read_misses'], row['write_misses'], row['mem_reads'], row['mem_writes']))
    resource_rows = [(f"{int(r['cache_size'])} B", r['write_allocate'], f"{int(r['generic_cells']):,}",
                      f"{int(r['flip_flop_bits']):,}", f"{int(r['mux_cells']):,}") for r in resources]
    cols.append([
        sub('C. Measured Backing-Memory Traffic'),
        p('All 16 traffic runs pass data and word-count checks. At the default configuration, both policies transfer identical read and write totals on every trace; the six read-only traces are policy-independent. Table V shows the two mixed traces, with RM and WM denoting CPU read and write misses.'),
        *table('TABLE V\nCOMPLETED MEMORY WORDS FOR MIXED TRACES', ['Trace', 'WA', 'RM', 'WM', 'Reads', 'Writes'], traffic_rows, [70, 25, 34, 34, 44, 45]),
        p('For W words per block, counters must satisfy (3). Because every CPU write reaches memory, write-through also gives (4). The runner compares these expectations with values captured from RTL; it does not substitute calculated totals for measurements.'),
        p('mem_reads = W (RM + WA x WM),  (3)', 'eq'),
        p('mem_writes = CPU write count.  (4)', 'eq'),
        p('For mixed_rw, WA = 0 performs 16 read-miss refills; WA = 1 performs eight read-miss and eight write-miss refills. Both fetch 64 read words and commit 91 writes: 155 words in total. Smoke likewise moves 20 reads and two writes, or 22 words. Allocation fetches blocks earlier and avoids the corresponding later read misses in these traces.'),
        p('This equality is workload-specific. A fresh isolated cold write measures zero reads and one write with WA = 0, but four reads and one write with WA = 1. If written blocks are not reused, allocation adds refill traffic and cost. Figure 3 summarizes the measured suite.'),
        sub('D. Counter-Enabled Generic Synthesis'),
        *table('TABLE VI\nCURRENT GENERIC SYNTHESIS WITH TRAFFIC COUNTERS', ['Cache', 'WA', 'Cells', 'FF bits', 'Muxes'], resource_rows, [47, 24, 65, 58, 58]),
        p('All four Yosys 0.71+post runs record zero warnings and successful structural/latch checks [4]. Their source manifest matches the current RTL. Main memory is excluded from these counts. Figure 4 shows that halving capacity reduces generic cells by about 49%; allocation changes total cells by less than 0.4% at either size.'),
    ])
    # Page 4: use the team's unchanged vector plots at readable full width.
    figures = [
        sec('III. Results and Discussion (continued)'),
        external_plot('plot_memory_traffic.svg'),
        p('Fig. 3. Completed memory read and write words for all eight traces at 1 KB, 16-byte blocks and latency 4. Reproduced from Meet\'s Phase II plot and Deepak\'s measured traffic CSV. Both policies transfer equal totals for this suite.', 'caption'),
        p('<b>Traffic takeaway:</b> Allocation reduces mixed-trace read misses without adding total memory words here; an isolated cold write demonstrates that this is not guaranteed for write-only workloads.', 'wide'),
        external_plot('plot_synthesis_resources.svg'),
        p('Fig. 4. Generic Yosys cell and flip-flop counts including traffic counters, for both capacities and policies. Reproduced from the Phase II resource CSV and chart. Halving cache capacity approximately halves mapped resources.', 'caption'),
        p('<b>Interpretation:</b> These counts describe a generic synthesis flow. They do not measure FPGA LUT utilization, physical area, power or clock frequency. Vivado was unavailable in the recorded environment and no target FPGA or clock constraint was specified.', 'wide'),
    ]
    # Page 5: finish results, then contributions, conclusion and references.
    cols.append([
        sub('E. Verification and Deliberate-Bug Evidence'),
        p('The recorded Phase II fault-injection experiment removed the valid-bit qualification, replacing is_hit = line_valid &amp; tag_match with is_hit = tag_match. The directed regression failed, including reset-recovery checks in scenarios 9 and 12. Restoring the valid check returned all twelve directed scenario groups and 32 trace/model comparisons to passing. This is evidence that the suite detects that fault, rather than an exhaustive correctness proof.'),
        p('For report validation, the current counter-enabled RTL was rechecked without rewriting team reports: all 336 hand cases, 64 workload comparisons, four invalid-address checks, five directed configurations and 32 trace comparisons passed. All 16 regenerated traffic rows matched the committed CSV. Synthesis figures are source-matched saved results; no new synthesis or physical timing claim is made.'),
        sub('F. Limitations'),
        p('The controller is blocking, single-request and write-through, with aligned word transfers and a 16 KB simulated memory window. Fixed per-word latency and the ready bubble differ from burst or variable-latency memory. Traces are short and synthetic; cold misses are included and inter-request gaps excluded. Service-cycle ratios are not complete-application speedups. Generic resource counts do not establish a target-specific maximum frequency.'),
        sec('IV. Individual Contributions'),
        p('<b>Aarush Gupta:</b> Built the initial cache datapath, controller/memory prototype, self-checking trace bench and Python model; derived address fields and configuration checks. In Phase II, integrated README contributions, synthesis results and the memory-traffic discussion.'),
        p('<b>Deepak Mishra:</b> Hardened transactions and reset, added boundary geometries and write allocation, implemented completed-word traffic counters, measured both policies, and published 512 B/1 KB synthesis evidence and the Vivado limitation.'),
        p('<b>Kushagra Bhardwaj:</b> Added directed checks, deterministic workload generation, the policy-aware model and regression runner. Rechecked the counter-enabled design in both modes and documented the valid-bit fault experiment and restored passing results.'),
        p('<b>Meet Ahuja:</b> Built sweeps, diagrams, waveform tooling and performance plots. In Phase II, prepared traffic/resource charts, repaired SVG exports and cleaned stale documentation and controller-latency paths.'),
        p('<b>Utkarsh:</b> Corrected read/mixed-traffic accounting, implemented the measured no-cache benchmark and performance validation, and integrated the IEEE report. Phase II work reorganizes the required sections, updates evidence and discussion, audits authorship and supplies reproducible PDF-generation source.'),
    ])
    cols.append([
        sec('V. Conclusion'),
        p('A parameterized direct-mapped cache with selectable write allocation has been implemented, verified and evaluated with a matched no-cache path. Phase II adds counters that make backing-memory traffic observable at completed-word granularity. At the default geometry, repeated-loop traffic achieves 1.88 times service-cycle speedup and mixed traffic 1.33 times against the measured eight-cycle baseline.'),
        p('Write allocation improves mixed-trace read AMAT from 4.94 to 3.97 cycles while leaving its overall mean at 6.03. Both policies move 155 words on that trace and 22 on smoke because write-miss refills replace later read-miss refills. The isolated-cold-write check shows the boundary of this result: allocation adds four read words when the block is not otherwise needed.'),
        p('Counter-enabled synthesis uses 12,797 generic cells at 512 B under either policy, compared with 24,994 and 25,080 at 1 KB. Capacity therefore dominates the observed resource scaling, while the policy difference is small. FPGA utilization and maximum frequency remain unmeasured and require a chosen target and constrained implementation flow.'),
        p('Future work should evaluate set associativity, write buffering, burst-capable memory and application-derived traces, then perform target-specific utilization and timing analysis. The current evidence supports a narrower conclusion: locality, write reuse, refill cost and memory protocol must be considered together; hit rate alone is insufficient.'),
        sec('References'),
        p('[1] D. A. Patterson and J. L. Hennessy, <i>Computer Organization and Design RISC-V Edition: The Hardware Software Interface</i>, 2nd ed. Morgan Kaufmann, 2020, ch. 5. [Online]. Available: <link href="https://shop.elsevier.com/books/computer-organization-and-design-risc-v-edition/patterson/978-0-12-820331-6">Elsevier, ISBN 978-0-12-820331-6</link>.', 'ref'),
        p('[2] N. P. Jouppi, "Improving direct-mapped cache performance by the addition of a small fully-associative cache and prefetch buffers," in <i>Proc. 17th Annual Int. Symp. Computer Architecture (ISCA)</i>, 1990, pp. 364-373, doi: <link href="https://doi.org/10.1145/325164.325162">10.1145/325164.325162</link>.', 'ref'),
        p('[3] S. Williams, "Icarus Verilog documentation." [Online]. Available: <link href="https://steveicarus.github.io/iverilog/">https://steveicarus.github.io/iverilog/</link>.', 'ref'),
        p('[4] YosysHQ, "Generic synthesis commands," <i>Yosys documentation</i>. [Online]. Available: <link href="https://yosyshq.readthedocs.io/projects/yosys/en/latest/cmd/index_techlibs_common.html">yosyshq.readthedocs.io/projects/yosys/en/latest/cmd/index_techlibs_common.html</link>.', 'ref'),
    ])

    def on_page(canvas, doc):
        canvas.saveState()
        if doc.page == 1:
            canvas.setFont('Paper', 24)
            canvas.drawCentredString(W / 2, 717, 'Design and Evaluation of a Direct-Mapped')
            canvas.drawCentredString(W / 2, 690, 'Cache Controller Using Verilog HDL')
            for name, enrollment, x, y in [
                ('Aarush Gupta', '2401020001', 132, 665), ('Deepak Mishra', '2401010142', 306, 665),
                ('Kushagra Bhardwaj', '2401010247', 480, 665), ('Meet Ahuja', '2401010273', 132, 619),
                ('Utkarsh', '2401010484', 306, 619),
            ]:
                canvas.setFont('Paper', 11); canvas.drawCentredString(x, y, name)
                canvas.setFont('PaperItalic', 9)
                canvas.drawCentredString(x, y - 14, 'Enrollment No. ' + enrollment)
            canvas.setFont('PaperItalic', 9)
            canvas.drawCentredString(W / 2, 573, 'Course project report, Modern Computer Architecture')
            abstract.drawOn(canvas, M, 556 - ah)
            index.drawOn(canvas, M, 556 - ah - 9 - ih)
        canvas.setFont('Paper', 8); canvas.drawCentredString(W / 2, 27, str(doc.page))
        canvas.restoreState()

    def frames(top):
        return [Frame(x, BOTTOM, CW, top - BOTTOM, id=str(i), leftPadding=0,
                      rightPadding=0, topPadding=0, bottomPadding=0)
                for i, x in enumerate((M, M + CW + GAP))]

    def height(items, width):
        return sum(item.wrap(width, 10000)[1] + item.getSpaceBefore() + item.getSpaceAfter()
                   for item in items)

    overflow = []
    for i, col in enumerate(cols):
        limit = (first_top if i < 2 else TOP) - BOTTOM
        used = height(col, CW)
        print(f'Column {i + 1}: {used:.1f} / {limit:.1f} pt')
        if used > limit:
            overflow.append(f'Column {i + 1} exceeds available height by {used - limit:.1f} pt')
    used = height(figures, FULL)
    print(f'Figure page: {used:.1f} / {TOP - BOTTOM:.1f} pt')
    if used > TOP - BOTTOM:
        overflow.append('Figure page is too tall')
    if overflow:
        raise RuntimeError('; '.join(overflow))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(str(args.output), pagesize=(W, H), leftMargin=M, rightMargin=M,
                         topMargin=54, bottomMargin=BOTTOM,
                         title='Phase II: Design and Evaluation of a Direct-Mapped Cache Controller',
                         author='Aarush Gupta; Deepak Mishra; Kushagra Bhardwaj; Meet Ahuja; Utkarsh',
                         subject='IEEE-style report in seven required sections', pageCompression=1)
    doc.addPageTemplates([
        PageTemplate(id='First', frames=frames(first_top), onPage=on_page, autoNextPageTemplate='Body'),
        PageTemplate(id='Body', frames=frames(TOP), onPage=on_page),
        PageTemplate(id='Figures', frames=[Frame(M, BOTTOM, FULL, TOP - BOTTOM, id='figures',
                     leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)], onPage=on_page),
    ])
    story = []
    for i, col in enumerate(cols[:6]):
        if i:
            story.append(FrameBreak())
        story.extend(col)
    story += [NextPageTemplate('Figures'), PageBreak()] + figures
    story += [NextPageTemplate('Body'), PageBreak()] + cols[6] + [FrameBreak()] + cols[7]
    doc.build(story)
    print('Saved', args.output.resolve())
    print('Evidence code revision:', evidence['code_revision'])


if __name__ == '__main__':
    main()
