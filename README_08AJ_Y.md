# RBYRCT-08AJ-Y — Scientific decision consolidation and production gap closure

**Status:** review only; frozen `false`, confirmatory execution **disabled**. This stage is not a scientific sign-off, a completed production runner, or an experiment.

## What this stage does

- Carries forward the Windows-verifiable status and known review fingerprints for 08AJ-T, U, V, W, X. It hashes the *status files* for a durable reference; it does **not** fully reproduce or independently certify every prior scientific analysis.
- Consolidates the five freeze blockers in the 08AJ-T gate framework, cross-referencing the seven pending decisions in 08AJ-X.
- Separates the 24-object fixed-benchmark descriptive target from conditional synthetic-generator inference.
- Preserves the explicitly unfinished 480-job numerical production executor and independent outcome auditor.
- Blocks `freeze` and `run`, and detects drift in five code-module hashes, status-file contents and approval flags.

## Files

Only four new files need to be extracted into your repository: `experiment_08aj_y.py`, `experiment_08aj_y_audit.py`, `test_experiment_08aj_y.py`, and this README. Existing experiment sources and prior results remain unchanged.

## Run in Windows PowerShell (from the `rbyrct-3d-05a` directory)

```powershell
python -m pytest test_experiment_08aj_y.py -q

python experiment_08aj_y.py `
  --mode prepare `
  --output-dir results\experiment08aj_y\consolidation_first `
  --t-dir results\experiment08aj_t\freeze_candidate_first `
  --u-dir results\experiment08aj_u\scientific_review_first `
  --v-dir results\experiment08aj_v\calibration_first `
  --w-dir results\experiment08aj_w\method_review_first `
  --x-dir results\experiment08aj_x\estimand_review_first

python experiment_08aj_y.py `
  --mode check `
  --output-dir results\experiment08aj_y\consolidation_first `
  --t-dir results\experiment08aj_t\freeze_candidate_first `
  --u-dir results\experiment08aj_u\scientific_review_first `
  --v-dir results\experiment08aj_v\calibration_first `
  --w-dir results\experiment08aj_w\method_review_first `
  --x-dir results\experiment08aj_x\estimand_review_first

python experiment_08aj_y_audit.py `
  --output-dir results\experiment08aj_y\consolidation_first `
  --t-dir results\experiment08aj_t\freeze_candidate_first `
  --u-dir results\experiment08aj_u\scientific_review_first `
  --v-dir results\experiment08aj_v\calibration_first `
  --w-dir results\experiment08aj_w\method_review_first `
  --x-dir results\experiment08aj_x\estimand_review_first

Get-Content results\experiment08aj_y\consolidation_first\run_status.json
Get-Content results\experiment08aj_y\consolidation_first\scientific_decision_register.json
```

Expected verdicts: `Y_GAP_REGISTER_PREPARED`, `Y_SOURCES_AND_DECISIONS_MATCH`, `Y_INDEPENDENT_GAP_AUDIT_PASS`; **five gates still blocked**. The prior evidence fingerprint fields refer to Windows results reported for 08AJ-T, V, W and X. U has no status fingerprint field, but its status file is hashed. If you point to a different legitimate local run with a different fingerprint, the tool will reject it rather than silently treating the different analysis as the same evidence. Preserve `consolidation_first`; use a fresh directory if rerunning.

## Decision summary

| Gate | Recommendation | Still needed |
| --- | --- | --- |
| G1: Phantom scope | 24 predefined phantoms, three related stress-test families; no clinical claims | Named review of generator-level and morphological evidence |
| G2: Statistical interpretation | Fixed-object descriptive mean primary; optional generator-level Welch-t conditional | Approval of assumptions, precision, reporting, practical relevance and multiplicity |
| G3: Failure and resources | No imputation, outcome-driven tuning or silent retries | Explicit wall-clock/peak memory limits, deterministic retry and failure policy |
| G4: Live production | Do not unlock | 480-job true executor + independent truth/RMSE auditor, qualified on engineering-only fixtures |
| G5: Freeze | Do not freeze | Signed scientific approval, commit/tag, environment lock, independent source audit, explicit authorization |

## Scientific cautions

- The prior ten-job 32³ engineering audit passed on the user's Windows machine, but that is not evidence of a positive diagonal-ordering effect and does not certify the 480-job study.
- Distinct random seeds and hashes establish nonidentity, not population independence.
- A confidence interval for a defined synthetic generator is conditional on justified sampling assumptions. No sampling CI is required for a fully observed fixed list of 24 objects.
- This document is a **decision register** rather than a final scientific decision; no reviewer is auto-signed.
- The old 08AJ-T and 08AJ-X data are never modified or reinterpreted as approvals.
