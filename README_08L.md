# RBYRCT-08L — read-only audit of 08K information-guided MART

## Purpose

Verify the **saved outputs** of the exploratory RBYRCT-08K 12³/32³ sequential acquisition experiment. This is **not** a new tomography run, a second independent simulation, or a held-out validation. The original 08K directory must remain unchanged.

## Installation

Extract **only** these three files directly into the existing `rbyrct-3d-05a` repository root (do not retain a nested extracted copy with the same `test_audit_08l.py` filename):

- `audit_08l.py`
- `test_audit_08l.py`
- `README_08L.md`

Test in Windows PowerShell:

```powershell
python -m pytest test_audit_08l.py -q
python -m pytest -q
git diff --check
```

Then audit the existing archived 08K experiment:

```powershell
python audit_08l.py `
    --results-dir ..\rbyrct-results\experiment08k\information_sequential_first `
    --report ..\rbyrct-results\08L_08K_independent_saved_output_audit.json `
    --check-masks
```

**Do not rerun 08K.** The audit will refuse to overwrite an existing report and refuses to place the report inside the source directory. If the report filename already exists, inspect it and explicitly choose a new report filename if needed.

## Checks

1. Validate the recorded SHA-256 manifest, completeness status, required files and frozen study structure.
2. Check every selected ray ID is within geometry bounds; acquisition indexes are contiguous; rays are unique; histories have correct length.
3. Recompute little-endian int64 SHA-256 of every acquisition prefix and verify saved fingerprint.
4. Recalculate checkpoint overlap with the corresponding coverage prefix.
5. Recalculate paired global, defect and nondefect RMSE gains from **saved per-checkpoint RMSE fields**; check nonnegative finite RMSEs, selection times and reconstruction times.
6. Reconstruct object-level averages (averaging forward models within object), summary means across objects, object win counts and primary descriptive comparisons.
7. Require information-guided **and** coverage acquisition orders to be exactly identical across objects and forward-model conditions at each fixed grid size. The information policy uses only known geometry, ray IDs, and deterministic seeds; this should hold. Also check that its initial warm prefix matches coverage.
8. With `--check-masks`: regenerate truth and evaluation-only defect masks from the recorded object seeds, using original 06B/07C support modules; compare truth and mask hashes, mask voxel counts and number of defects.
9. Provide separate **same** and **independent** forward-model descriptive results, including defect and global RMSE gains and number of object wins.

The report contains a `verdict` of `PASS` or `FAIL` and details of the checks, along with `model_stratified_results`. Audit failure exits with a nonzero status. An invalid numeric value or unreadable file may raise an exception rather than emit a PASS/FAIL report.

## Important interpretation

If `information_orders_identical_by_size` is true at both 12³ and 32³, the policy is a **geometry-driven ray design** under the saved implementation: it does **not** adapt ray ordering to measured detector responses or object identity. It is acceptable for MART reconstruction to use acquired measurements, but should not be described as a *measurement-adaptive information selector*.

The information score uses a hypothetical diagonal Gaussian uncertainty proxy, **not** MART's calibrated posterior covariance.

The auditor does **not** regenerate measurement noise, independently rerun the 08K MART reconstruction, or validate physical CT dose, defect detection, statistical significance or clinical relevance. The 08K experiment includes **two independent objects per grid size**. Forward-model conditions and ray checkpoints reuse these objects and are not independent replicates. A `PASS` is necessary evidence of saved-output consistency, not a new independent scientific replication.

For prospectively frozen confirmation, reserve entirely new object seeds, forward-model conditions and acquisition seeds **after reviewing 08L**. Do not tune the existing score on the held-out sample.

## Commit and archive

After a PASS and full Python tests:

```powershell
git add audit_08l.py test_audit_08l.py README_08L.md
git diff --cached --check
git commit -m "Add independent 08K saved-output numerical and geometric audit"
git restore -- ":(glob)__pycache__/*.pyc"
git status --short
```

Keep all `08K` experimental outputs unchanged in `..\rbyrct-results\experiment08k\` and the new `08L` JSON report outside the code repository.
