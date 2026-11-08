# RBYRCT 08AJ-AB — Execution core with engineering-only access

**Status:** numerical backend implemented and tested for **engineering-shadow jobs only**. The 480 planned prospective jobs remain **DISABLED**. This package does not freeze the scientific protocol or authorize confirmatory outcomes.

## What is new

- A genuine per-job 32^3-compatible numerical core built from the same system matrix, five acquisition policies, matched/independent forward models, paired catalogue, and MART recurrence used in the earlier engineering tests.
- A fixed, noncohort `smooth_heterogeneity` object with seed `970099`; no API or CLI accepts a prospective object seed, production ID, or arbitrary truth volume. The program refuses every production execution command.
- An immutable receipt and eight `.npy` artifacts for each completed job: selected ray order, measured rays, full clean/noisy catalogues, selected CSR matrix components, and reconstruction. Saved receipts contain measured engineering RMSE and SHA-256 checksums.
- An independent auditor recomputing the ray order, forward/noisy catalogues, sparse geometry, reconstruction using an independent MART implementation, and RMSE; it also checks shared noisy measurements and common warm starts when multiple policies under one model are present.
- Safe resume: preexisting completed jobs are independently replayed before reuse; tampered artifacts are rejected. Unexpected unfinished staging is preserved for diagnosis and explicitly blocks rerun.
- AB verifies both the full disabled AA roster and the original M contract before every execution. Source drift closes the engineering gate.

## Scope and limits

The engineering runner supports two settings:

| Size | Rays | MART epochs | Prefix | Usage |
|---|---:|---:|---:|---|
| 8^3 | 128 | 2 | 8 | Quick regression and all-policy demonstration |
| 32^3 | 2048 | 16 | 64 | Production-setting **engineering-only** numerical rehearsal |

The AA contract includes **480** production specifications and **96** shared measurement groups. AB checks their integrity but **does not execute any of those specifications**. It does **not** yet provide an independently certified 480-job prospective numerical driver, a complete population of numerical results, scientific sign-off, resource-policy approval, or an immutable source freeze.

The 8^3 and 32^3 engineering objects are outside the 24-object prospective cohort. Their RMSE values are *engineering diagnostics*, not confirmatory policy-performance outcomes.

## Windows PowerShell procedure

Extract **four files** into your `rbyrct-3d-05a` repository:

- `experiment_08aj_ab.py`
- `experiment_08aj_ab_audit.py`
- `test_experiment_08aj_ab.py`
- `README_08AJ_AB.md`

Earlier `experiment_08aj_m.py`, `experiment_08aj_aa.py`, 08AJ-Q/G/E, and the numerical dependencies must remain unchanged; AB relies on their saved source hashes.

### 1. Test

```powershell
python -m pytest test_experiment_08aj_ab.py -q
```

Expected: **9 passed**.

### 2. Prepare the 8^3 engineering shadow

```powershell
python experiment_08aj_ab.py `
    --output-dir results\experiment08aj_ab\engineering_8_first `
    --aa-dir results\experiment08aj_aa\disabled_path_first `
    --m-dir results\experiment08aj_m\contract_first `
    --mode init --n 8
```

Expected: `AB_ENGINEERING_BACKEND_PREPARED`.

### 3. Verify the disabled source-lock contract

```powershell
python experiment_08aj_ab.py `
    --output-dir results\experiment08aj_ab\engineering_8_first `
    --aa-dir results\experiment08aj_aa\disabled_path_first `
    --m-dir results\experiment08aj_m\contract_first `
    --mode check
```

Expected: `AB_SOURCE_AND_LOCK_PASS`.

### 4. Execute two real engineering jobs

```powershell
python experiment_08aj_ab.py `
    --output-dir results\experiment08aj_ab\engineering_8_first `
    --aa-dir results\experiment08aj_aa\disabled_path_first `
    --m-dir results\experiment08aj_m\contract_first `
    --mode run --policy information_diag --model same

python experiment_08aj_ab.py `
    --output-dir results\experiment08aj_ab\engineering_8_first `
    --aa-dir results\experiment08aj_aa\disabled_path_first `
    --m-dir results\experiment08aj_m\contract_first `
    --mode run --policy uniform_multiscale --model same
```

Both should return `AB_NUMERICAL_ENGINEERING_JOB_PASS`. Repeat a run to verify `AB_ENGINEERING_JOB_REUSED` (the existing evidence is independently replayed, not overwritten).

### 5. Run the independent replay and RMSE audit

```powershell
python experiment_08aj_ab_audit.py `
    --output-dir results\experiment08aj_ab\engineering_8_first `
    --aa-dir results\experiment08aj_aa\disabled_path_first `
    --m-dir results\experiment08aj_m\contract_first
```

Expected: `AB_INDEPENDENT_SHADOW_AUDIT_PASS` and `audited_engineering_jobs: 2`. `--require-complete` should **fail** unless all ten shadow jobs are present.

### Optional: 32^3, 16-epoch shadow job

Only after the 8^3 checks pass:

```powershell
python experiment_08aj_ab.py `
    --output-dir results\experiment08aj_ab\engineering_32_first `
    --aa-dir results\experiment08aj_aa\disabled_path_first `
    --m-dir results\experiment08aj_m\contract_first `
    --mode init --n 32

python experiment_08aj_ab.py `
    --output-dir results\experiment08aj_ab\engineering_32_first `
    --aa-dir results\experiment08aj_aa\disabled_path_first `
    --m-dir results\experiment08aj_m\contract_first `
    --mode run --policy information_diag --model independent

python experiment_08aj_ab_audit.py `
    --output-dir results\experiment08aj_ab\engineering_32_first `
    --aa-dir results\experiment08aj_aa\disabled_path_first `
    --m-dir results\experiment08aj_m\contract_first
```

32^3 independent replay may take significantly longer. Do not treat an incomplete run or audit as PASS.

## Integrity and recovery notes

- `init` refuses to reuse an existing evidence directory. **Do not delete or overwrite previous successful runs.**
- Partial `.staging__<job>` directories are retained and flagged. Investigate rather than deleting without documentation.
- The SHA-256 snapshot covers AB itself, its auditor, the upstream AA/M/Q/G/E programs, and selected numerical dependencies. If the upstream sources changed, do not bypass the error; investigate, version the change, and prepare a new candidate.
- Individual engineering job receipts are NOT automatically resource-certified. The earlier Z ceilings are proposed, not approved; AB is an execution core and independent audit, not an operating-system watchdog.
- The actual 480-job prospective cohort and its primary statistical analysis are deliberately inaccessible. A separate approved, frozen protocol and production execution authorization must be designed and verified before that study can be run.
