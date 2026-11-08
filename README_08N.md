# RBYRCT-08N — Independent frozen 08M saved-output audit

**Scope:** Read-only numerical verification of the already-executed **08M** prospectively frozen 32³ study. No tuning, new acquisition, or re-running of the 08M validation. The audit writes a **new report outside** the 08M archive.

## Input and preconditions

Run from the `rbyrct-3d-05a` repository root on Windows. Extract only these three files from the ZIP directly into the repository root:

- `audit_08n.py`
- `test_audit_08n.py`
- `README_08N.md`

The following existing materials must already be present:

- `protocol_08m_frozen.json`, committed **before** the validation experiment;
- all 15 frozen experiment source modules (`experiment_08m.py`, `experiment_08k.py`, etc.) still matching their lock hashes;
- `..\rbyrct-results\experiment08m\frozen_first\`, the previously archived complete 08M output.

Do not modify the old archive, source files, or protocol lock to make the audit pass. If code hashes mismatch, stop and investigate the exact Git commit/source state.

## Tests

```powershell
python -m pytest test_audit_08n.py -q
python -m pytest -q
git diff --check
```

The final test in `test_audit_08n.py` automatically checks the entire archived run when the archive and committed lock exist; otherwise it is skipped. Report pass/skip counts accurately.

## Run the read-only audit

```powershell
python audit_08n.py `
    --results-dir ..\rbyrct-results\experiment08m\frozen_first `
    --protocol-lock protocol_08m_frozen.json `
    --source-dir . `
    --report ..\rbyrct-results\08N_08M_frozen_saved_output_audit.json `
    --check-masks
```

Use a new report path if that report already exists; the auditor refuses to overwrite reports. It also refuses to place its report inside the frozen results folder.

### What the audit actually verifies

1. The archived `protocol.json` exactly matches the externally supplied frozen `protocol_08m_frozen.json`.
2. All **15 source files** in the current repository match the lock's source SHA-256 values.
3. All **10 listed data files** match the archived `sha256.json` manifest; the archive's `sha256.json` is not itself independently authenticated by a separate external signature. The protocol lock is an externally committed reference if its Git history is intact.
4. The complete Cartesian structure: **8 objects × 2 acquisition seeds × 2 forward models × 4 policies = 128** ray histories; **128 × 3 = 384** checkpoint reconstructions.
5. Every full ray history has 4,096 unique in-range ray IDs and sequential positions; every 1,024/2,048/4,096-ray hash and shared-with-coverage count matches its history.
6. Every global/defect/nondefect **paired fractional gain** is recomputed from the stored raw RMSE **numbers**, and each of eight object means is recomputed over four forward-model/seed conditions. The prespecified 2,048-ray primary result is recalculated over the eight object means.
7. Information and coverage ray ordering is consistent across objects/models **within each acquisition seed**, while distinct seeds are permitted to generate different orderings. Information orders preserve coverage's first 64 warm rays.
8. With `--check-masks`, re-create each synthetic phantom and defect mask from the recorded seed, checking truth hashes, mask hashes, mask voxel counts and defect counts. This post-hoc truth access is strictly for evaluation.
9. Aggregate summaries, win counts, guard-trace JSON syntax, and model-specific descriptive outcomes.

### Explicit limitations

- **Not an independent physical simulation replication.** The saved dataset lacks full reconstructed voxel arrays and raw detector measurements; 08N does *not* recompute per-voxel RMSE from these arrays or replay MART.
- A matched source hash does not prove that source files were continuously unchanged while 08M was running, nor does an archive checksum provide an externally signed chain of custody.
- No new held-out objects or geometries are evaluated here. The original study has eight independent synthetic objects; model and acquisition-seed repeats do not increase the independent sample size.
- `information_diag` is a **geometry-based schedule**, not an intensity-responsive adaptive policy.
- The report uses `PASS` specifically for *saved-output audit consistency*, not for scientific generality or clinical applicability.

## After the report

Inspect the PASS/FAIL verdict and any errors. If PASS, commit the 08N code and move on to manuscript evidence revision or a separate reconstruction replay/independent code audit—not tuning or redoing the frozen 08M run.

```powershell
git add audit_08n.py test_audit_08n.py README_08N.md
git diff --cached --check
git commit -m "Add independent frozen 08M saved-output numerical audit"
git restore -- ":(glob)__pycache__/*.pyc"
git status --short
```
