# RBYRCT-07D: Read-only numerical and guard-scale audit

## Purpose

Audit the **completed, frozen 07C2 32³ study** without rerunning or changing any acquisition policy. Check full CSV and SHA-256 provenance, per-condition ray-order hashes, whole/defect/background RMSE consistency, paired relative RMSE gains, object-balanced summaries, threshold crossings, guard activation, and matching gradient/guarded ray histories. Optional object/mask regeneration verifies the synthetic truth and defect-mask hashes **without reconstructing** the measurements. Optional geometry sensitivity examines the relative size of the proposed variance change against the preexisting voxel-coverage variance; it is **not** an exact replay of the original random candidate pools.

The original `guard_batch_audit.csv` stores aggregate admissibility information, **not** the sixteen candidate ray identifiers or individual projected imbalance scores. Consequently this audit **cannot prove** which normalization term caused the nonbinding guard. An exact causal diagnosis would require separately instrumented engineering tests, not silently altering 07C2.

## Windows PowerShell

Copy `audit_07d.py`, `test_audit_07d.py`, and this README into `C:\Users\shuss\Downloads\rbyrct-3d-05a`.

```powershell
python -m pytest test_audit_07d.py -q
python -m pytest -q
git diff --check

python audit_07d.py `
  --results-dir results/experiment07c2/frozen_32_first `
  --report ../rbyrct-results/07D_07C2_independent_audit.json `
  --check-masks --geometry
```

The default report destination is **outside the frozen result directory**. If 07C2 has been archived, replace `--results-dir` with `../rbyrct-results/experiment07c2/frozen_32_first`.

The audit exits **0** on PASS, **1** on computed discrepancies, **2** on missing files or other errors. Do not edit the frozen CSVs to make the audit pass. If a check fails, inspect and correct only the verifier when justified, preserving the failed report.

## Scientific boundaries

- The primary endpoint was whole-volume RMSE improvement at 2,048 rays. A negative result remains a negative result.
- Stored RMSEs permit independent **arithmetic and consistency auditing** but not reproduction of all voxel-level squared errors: full reconstructed volumes were not archived.
- The defect-region evaluator's mask is reconstructed from the frozen generator and verified against stored SHA-256 hashes with `--check-masks`; that does not independently confirm physical validity.
- The global variance geometric diagnostic samples a frozen *coverage-only* prefix on one acquisition seed, not the stochastic candidate pools used during guarded selection.
- Guard differences should be distinguished from gradient-vs-coverage reconstruction performance. No new acquisition or solver hyperparameter tuning is authorized.
