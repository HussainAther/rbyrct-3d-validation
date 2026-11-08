# RBYRCT-08AJ-K — Engineering-only numerical runner and independent replay

## Scope

This package uses a **fixed, engineering-only** `smooth_heterogeneity` phantom at 8³, seed `970099`, outside the held-out prospective 24-object roster. It uses 128 selected rays, a fixed diagonal-information acquisition order, two epochs of MART and relaxation 0.25. Both `same` and `independent` forward-projector models are exercised. **It does not compute RMSE, gain, confidence intervals or 24-object policy comparisons.** The primary prospective protocol remains unfrozen and execution remains disabled.

## Files

- `experiment_08aj_k.py`: fixed-size numerical fixture, immutable committed checkpoints, resume and source-integrity checks.
- `experiment_08aj_k_audit.py`: separate auditor, SHA-256 checks, independently coded per-ray MART replay from saved CSR and measurements.
- `test_experiment_08aj_k.py`: eight tests, including tampering, interrupted execution and restart.
- `README_08AJ_K.md`: this guide.

Install all files in the existing `rbyrct-3d-05a` repository alongside the 08AJ-B through J modules. Keep earlier modules unchanged.

## Windows PowerShell

```powershell
python -m pytest test_experiment_08aj_k.py -q

python experiment_08aj_k.py `
    --output-dir results\experiment08aj_k\engineering_first `
    --mode init

python experiment_08aj_k.py `
    --output-dir results\experiment08aj_k\engineering_first `
    --mode check

python experiment_08aj_k.py `
    --output-dir results\experiment08aj_k\engineering_first `
    --mode run

python experiment_08aj_k_audit.py `
    --output-dir results\experiment08aj_k\engineering_first
```

Expected results: 8 tests pass; `ENGINEERING_PLAN_CREATED`, `ENGINEERING_SOURCE_MATCH`, `NUMERICAL_ENGINEERING_PASS`, `INDEPENDENT_NUMERICAL_AUDIT_PASS`; two model replays. The auditor will report each model's maximum absolute numerical discrepancy. It does not certify production results.

Re-run `--mode run` to test idempotent resumption: existing committed checkpoints are verified and reused, never overwritten. To start a fresh separate run, choose a new output directory. Do **not** delete or overwrite prior evidence.

## Safeguards and scope limitations

- `--mode execute` explicitly refuses execution. The fixture has fixed dimensions and a non-prospective phantom seed. No confirmatory outcomes are generated.
- The engineering plan contains relevant source SHA-256 fingerprints. Run and audit detect changed source files.
- Each model's checkpoint includes the acquired row indices, measured values, CSR row data/indices/offsets, clean and noisy candidate catalogues, numerical reconstruction, and an immutable receipt enumerating SHA-256 hashes.
- An interrupted uncommitted staging directory can be recreated. Committed results are independently verified before reuse and cannot be silently overwritten.
- The independent replay uses its **own MART recurrence implementation**, not the production solver wrapper, and recomputes from saved numerical inputs. This is a numerical consistency check, **not** a separate physics forward model validation, a reconstruction-accuracy validation, or a cryptographic signature. Coordinated rehashing of altered artifacts cannot be excluded without externally signed or independently archived evidence.
- This is an 8³ development fixture. It does not prove 32³ production runtime, study-wide reliability, statistical precision, phantom structural independence, or protocol lock readiness. The 08AJ-J 480-job plan remains outcome-free.

## Next

After Windows verification, address scientific sign-off and formal source/protocol freeze. Only then implement and authorize the full 24-object production run with a production-level independent numerical and provenance audit.
