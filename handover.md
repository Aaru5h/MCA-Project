# Handover to Utkarsh: report fixes for Phase II

From: Aarush
Purpose: changes the IEEE report needs so its numbers match the repo.

The current PDF in `report/` is still the Phase I version. Everything below was checked against `main` after Deepak's, Kushagra's and Meet's Phase II commits.

## 1. Synthesis numbers are outdated

The report gives 24,835 cells without write allocation and 24,822 with it. Those come from the old RTL, before the memory-traffic counters were added. The current numbers are:

| Cache size | `WRITE_ALLOCATE` | Generic cells | Flip-flop bits | Mux cells | Warnings |
|---|---:|---:|---:|---:|---:|
| 512 B | 0 | 12,797 | 5,164 | 3,579 | 0 |
| 512 B | 1 | 12,797 | 5,164 | 3,582 | 0 |
| 1 KB | 0 | 24,994 | 9,965 | 6,931 | 0 |
| 1 KB | 1 | 25,080 | 9,965 | 6,906 | 0 |

Update these places:
- the Abstract
- the synthesis table (Table VI)
- the hardware note at the end

Sources: `docs/synthesis/README.md`, `docs/synthesis/traffic_counters/resources.csv`, and the chart `docs/results/plots/plot_synthesis_resources.svg`.

Keep the existing limitation. Maximum frequency and FPGA utilization were not measured: Vivado wasn't available and no target device was specified.

## 2. Add the 512 B synthesis configuration

It's in the table above. The finding: halving the cache roughly halves the cell count, because the data, tag and valid arrays dominate the design. Write allocation changes the count by less than 0.4%.

## 3. Add the memory-traffic comparison

Sources: README "Phase II results", `docs/results/performance_analysis.md` Section 8, `docs/results/memory_traffic.csv`, `docs/results/memory_traffic.md`, and the plot `docs/results/plots/plot_memory_traffic.svg`.

| Trace | Policy | Read misses | Write misses | `mem_reads` | `mem_writes` | Total words |
|---|---|---:|---:|---:|---:|---:|
| `mixed_rw` | no-allocate | 16 | 13 | 64 | 91 | 155 |
| `mixed_rw` | write-allocate | 8 | 8 | 64 | 91 | 155 |
| `smoke` | no-allocate | 5 | 1 | 20 | 2 | 22 |
| `smoke` | write-allocate | 4 | 1 | 20 | 2 | 22 |

Key points for Results and Discussion:
- Both policies moved the same number of memory words on all eight traces. The six read-only traces are identical under both.
- `mem_writes` always equals the number of CPU writes, because the cache is write-through.
- `mem_reads` = 4 × (read misses + `WRITE_ALLOCATE` × write misses).
- Write allocation doesn't add traffic here, because each block it fetches on a write miss would otherwise be fetched by a later read miss. It just fetches the block earlier. That lowers `mixed_rw` read AMAT from 4.94 to 3.97 cycles.
- When written data is never read back, write allocation does add traffic. An isolated cold write moves 4 read words with allocation and none without.

## 4. Mention the fault-injection check

Source: `docs/verification/README.md`, Section 3. Kushagra removed the valid bit from the hit check (`is_hit = tag_match`), and the regression failed. After restoring it, all 12 directed scenarios and all 32 trace/model comparisons passed again. This shows the testbench catches real bugs.

## 5. Reorder the report into the required sections

The required order is:
1. Abstract
2. Literature Review
3. Proposed Solution
4. Results and Discussion
5. Individual Contributions
6. Conclusion
7. References

Literature Review and Individual Contributions are currently missing. Proposed Solution can be built from the current cache organization, RTL implementation and verification methodology sections. Results and Discussion can be built from the current performance analysis and synthesis sections, plus the traffic comparison.

For Individual Contributions, use each person's subsection in the README "Contributions" section. Make sure it matches each person's commits.

## 6. Commit the report source

`report/source/` is empty. Commit the LaTeX source there along with the PDF, in a few commits rather than one, so the history shows steady work.

## Already correct, no change needed

These numbers in the report match the repo:
- AMAT values: smoke 11.33 / 10.86; mixed_rw 4.94 / 6.03 without allocation and 3.97 with it
- hit rates and the per-trace results table
- speedups: 1.88× for repeated_loop, 1.33× for mixed_rw
- the 8-cycle no-cache baseline
- 336 hand-calculated validation cases, 64 workload comparisons, 4 invalid-address checks
- the strided cost rising from 8 to 83 cycles across block sizes
- 97.66% hits for the conflict trace at 4 KB
