# Experiment 04O-D — Gate-behavior audit (offline)

**Purpose:** Diagnose why the predeclared 04O-C held-out-NRMSE threshold (`2.0`) failed to protect against subvoxel mismatch. This is a post-hoc audit only: it does not re-run reconstruction, alter ray acquisition, tune the threshold, or claim independent generalization.

## Installation

Extract `experiment_04od.py`, `test_experiment_04od.py`, and `README_04OD.md` into the root of `rbyrct-3d-validation`. Standard Python only; no additional packages.

## Run (PowerShell)

```powershell
conda activate rbyrct-3d
python -m unittest -v test_experiment_04od.py
python experiment_04od.py `
  --input-dir results/experiment04oc_full `
  --output-dir results/experiment04od_audit
```

Input files: `gate_trace.csv` and `metrics.csv` required; `divergence.csv` and `selection_timing.csv` optional. The complete files, not 20/30-line excerpts, are required. `paired_cases.csv` is intentionally not required: the script reconstructs paired outcomes from the complete `metrics.csv` and validates all four policies exist for every condition.

## Outputs

- `case_audit.csv`: one row per matched acquisition condition. Gate checks/switches, first activation/off, last state, ray-weighted on/off fractions, initial/final held-out error, gate/full/constant RMSE and gains versus feedback-off, optional trajectory similarity/timing.
- `group_summary.csv`: grouped by object type/budget; also object type/budget/offset, and phantom/object type/budget.
- `matched_object_contrasts.csv`: matched exact-replicated versus subvoxel cases using the *same* offset, phantom family, seed, budget and noise. Differences in feedback exposure alongside differences in outcome.
- `audit_protocol.json`: provenance and interpretation limitations.

### Interpretation rules

`feedback_strength_next` from a checkpoint applies from its `acquired_before` value until the next checkpoint or final budget. `on_fraction` and `off_fraction` are **ray-weighted fractions of controlled rays**; the initial warm-start prefix (typically 128 rays) is excluded because the trace does not describe a prior feedback choice. A `n_switches` count is based on successive checkpoint decisions (not unlogged batch transitions). `later_on_fraction` covers only intervals **beginning** at or beyond half the final budget; it is a conservative late-interval summary, not exact rays in the latter half. If you want exactly half-budget exposure, add interval clipping in a later analysis. The case-level `gate_gain` is `(feedback_off_rmse - gate_rmse)/feedback_off_rmse` and negative means harm compared with feedback-off.

`matched_object_contrasts.csv` tests whether the gate makes different decisions on replicated/subvoxel versions of the same scenario. Comparable exposure with divergent outcomes suggests that the signal failed to discriminate a scientifically relevant discrepancy, but does not establish why feedback failed. A correlation between interventions and results is observational, not evidence of benefit from intervening.

Timing comparisons are noisy and include selector/diagnostic time—not physical CT scan time. No clinical/dose claims.
