# Utkarsh's measured performance evidence

Owner: Utkarsh. Definitions, assumptions, hand calculations and usage are in
[Performance accounting and measured no-cache baseline](../performance_metrics.md).

| File | Contents |
|---|---|
| [hand_cases.csv](hand_cases.csv) | 336 measured cache/no-cache comparisons, including empty and write-only traces |
| [workloads.csv](workloads.csv) | 64 measured comparisons using the eight supplied workloads |
| [validation.json](validation.json) | Successful validation summary, tool versions, source hashes and hand-case inputs |
| [simulation_output.json](simulation_output.json) | Exact compilation commands, representative latency-4 smoke/mixed simulation output and expected invalid-input diagnostics |
| [compatibility.json](compatibility.json) | Existing five directed and 32 trace checks passed without rewriting their reports |

`timing_source` is `RTL simulation`. All cycle-total columns are measured integer
sums. CSV averages and speedup are rounded to six decimal places; empty cells
mean undefined. Cache and baseline start from identical initial memory for
each trace. Repeated raw baseline samples are omitted because geometry and
allocation policy do not affect the baseline.

Reproduce the performance suite from the repository root:

```bash
python3 -B scripts/validate_performance.py
```

Regenerate these performance artifacts explicitly:

```bash
python3 -B scripts/validate_performance.py --output docs/results/utkarsh
```

The source hashes in `validation.json` identify exactly what was tested. The
raw output replaces repository and temporary build paths with `<REPO>` and
`<BUILD>`; substitute actual paths when replaying a recorded command. Temporary
hand-case traces can be reconstructed from `hand_case_inputs` in the manifest.
Intentional invalid trace runs have nonzero exit codes and fatal diagnostics.

Recheck compatibility with the existing verification suite without regenerating
another owner's reports:

```bash
python3 -B - <<'PY'
from scripts.run_regression import run_directed_suite, run_trace_matrix
directed_ok = run_directed_suite()
traces_ok, rows = run_trace_matrix()
if not directed_ok or not traces_ok or len(rows) != 32:
    raise SystemExit("Existing verification compatibility failed")
print("PASS: 5 directed configurations and 32 trace comparisons")
PY
```

`compatibility.json` records the successful check at this change. The performance
regeneration command preserves that record; the separate compatibility command
above prints a fresh status without changing it.
