**07A verifier patch 1 (2026-11-04):** Corrected the RMSE/gain range check to allow negative finite relative gains, which are valid when adaptive RMSE exceeds coverage RMSE. No frozen 06B result files or analysis formulas were changed. The initial 8,247-check audit was marked FAIL by this validation-rule bug; rerun the corrected verifier and retain both reports for provenance.

# RBYRCT-07A — independent, read-only audit of frozen 06B results

This package **does not rerun 06B or modify its output**. `audit_07a.py` imports no RBYRCT modules and uses only the Python standard library. It independently recomputes metrics from saved RMSEs, checks ray-order fingerprints from the saved acquisition-order records, validates all files against the SHA-256 manifest, recomputes reported threshold crossings, and checks acquisition/timing/guard audit invariants. Output is a JSON audit report written **outside the frozen experiment folder**.

## Windows PowerShell

Extract `audit_07a.py`, `test_audit_07a.py`, and `README_07A.md` directly into your existing `rbyrct-3d-05a` project folder. Then run:

```powershell
python -m pytest test_audit_07a.py -q
python -m pytest -q
python audit_07a.py `
    --results-dir results/experiment06b/frozen_first `
    --report ../rbyrct-results/07A_independent_06B_audit.json
```

The verifier prints a JSON report and writes it outside the original result directory. Its exit status is `0` for PASS, `1` for a detected mismatch, `2` for missing inputs or an unsafe report path. It **must** complete with `"verdict": "PASS"` before treating this as verified.

To inspect the result in PowerShell:

```powershell
Get-Content ../rbyrct-results/07A_independent_06B_audit.json | ConvertFrom-Json | `
    Select-Object verdict, checks_performed, errors, derived_statistics | Format-List
```

**Do not modify, delete, regenerate or overwrite `results/experiment06b/frozen_first`**. Preserve the original `run_manifest.sha256`. If the audit fails, send the full failure list; we should determine whether the issue lies in the saved data, the code, or the audit's own assumptions. Do not silently patch results to satisfy this verifier.

## Checks

1. SHA-256 file manifest integrity and the `protocol_sha256` fingerprint.
2. Frozen production settings, complete 8-object × 2-model × 2-seed × 3-policy design and fixed 144/288/576-ray checkpoints.
3. Exactly 96 full histories (55,296 ray IDs), uniqueness, index order, ray bounds and common 36-ray warm prefixes.
4. All 288 saved reconstructions and checkpoint hashes recomputed as SHA-256 of **little-endian signed int64** ray sequences.
5. Every paired relative gain recomputed from raw saved RMSE, and `shared_with_coverage` from acquisition sets.
6. Every object-level mean/worst gain, 288-ray success rule, all three budget summaries, forward-model comparisons and gradient-versus-guard ordered-history parity.
7. Primary matched-case CSV consistency; threshold-crossing flags reconstructed only from the saved checkpoint RMSEs.
8. Nonnegative timing, repeated selection-time consistency without summing it across checkpoints; guarded batch logs, admissible candidates and guard activation bounds.

## What it cannot independently verify

The audit verifies **internal numerical consistency of the saved data**, not the physical or mathematical correctness of the MART implementation, measurement generator, or exact reconstructed voxel arrays (those are not saved). It cannot establish industrial defect detection, physical dose, causal benefit of the guard, or statistical significance. The reported positive gain at 288 rays is a small synthetic finding and does not persist at 144 or 576 rays. Expect the guard and gradient ordered histories to be identical for most conditions.

The complete 06B CSV directory was not supplied to the authoring session; **the full original 06B experiment has not been independently audited here**. Run this verifier on your Windows directory to obtain that verdict.
