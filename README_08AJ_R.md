# RBYRCT-08AJ-R — Multi-policy numerical engineering verification

**This is a noncohort engineering harness, NOT a scientific results study.** It wraps the existing 08AJ-Q numerical executor; production / prospective execution remains disabled. No object from the 24-object prospective cohort is used. It runs one fixed engineering phantom (`smooth_heterogeneity`, seed `970099`). It must not be used to assert which acquisition policy is superior.

## Files

- `experiment_08aj_r.py`: ten-job engineering plan and resumable job orchestration.
- `experiment_08aj_r_audit.py`: separate auditor with per-job independent MART replay plus cross-policy paired-noise, shared-prefix, and complete-view checks.
- `test_experiment_08aj_r.py`: eight test cases, including complete 8³ execution, recovery, tamper detection and invalid-plan rejection.

Requires all files from the existing 08AJ-Q, 08AJ-G, and earlier stages, unmodified. Install/extract these three new files into the same source directory as `experiment_08aj_q.py`.

## Engineering design

- Five policies: `information_diag`, `uniform_multiscale`, `coverage`, `stratified_random_04h`, `complete_view`.
- Two forward models: `same`, `independent`.
- Ten actual numerical jobs per engineering plan, **not** the 480 prospective jobs.
- 8³ quick engineering fixture: 128 rays, 2 MART epochs, 8-ray prefix for four individual-ray policies.
- 32³ engineering fixture: 2048 rays, 16 MART epochs, 64-ray prefix for four individual-ray policies.
- Whole-detector `complete_view` has no forced warm prefix.
- One full noisy catalogue per model, shared by all policies in that model. Different forward models may have different catalogues.
- The runner preserves completed Q receipts. A repeated job independently audits existing numerical evidence before reuse. Uncommitted `.staging__` directories cause the audit to fail until execution recovery clears them.
- No reconstruction RMSE, gains, success rates or inferential statistics are computed.

## Windows PowerShell commands

**1. Automated tests**

```powershell
python -m pytest test_experiment_08aj_r.py -q
```

**2. Quick 8³ all-policy engineering verification**

```powershell
python experiment_08aj_r.py `
    --output-dir results\experiment08aj_r\engineering_8_first `
    --mode init

python experiment_08aj_r.py `
    --output-dir results\experiment08aj_r\engineering_8_first `
    --mode run

python experiment_08aj_r_audit.py `
    --output-dir results\experiment08aj_r\engineering_8_first `
    --require-complete
```

Expected final verdict: `R_INDEPENDENT_MULTI_JOB_AUDIT_PASS`, `audited_jobs: 10`, no errors.

**3. Full-resolution 32³ engineering verification**

```powershell
python experiment_08aj_r.py `
    --output-dir results\experiment08aj_r\engineering_32_first `
    --mode init --n 32

python experiment_08aj_r.py `
    --output-dir results\experiment08aj_r\engineering_32_first `
    --mode run

python experiment_08aj_r_audit.py `
    --output-dir results\experiment08aj_r\engineering_32_first `
    --require-complete
```

**Important:** This is compute-intensive. Run each step only once, or resume with `--mode run` on the same directory if a run is interrupted. The executor reuses committed receipts and recomputes an incomplete job; it does *not* resume partial MART epochs within a job. Do not reinitialize an existing directory and do not remove evidence folders. If an interrupted job leaves staging, the next `--mode run` cleans and recomputes that unfinished job; retain diagnostic copies if investigating a failure. For incremental execution, use `--mode run --policy coverage --model independent`, replacing names as desired. All ten jobs must exist before `--require-complete` succeeds.

Use `--mode check` to verify source integrity independently of job execution:

```powershell
python experiment_08aj_r.py `
    --output-dir results\experiment08aj_r\engineering_32_first `
    --mode check
```

## Scope and limitations

Local verification: eight new tests passed; all ten 8³ policy/model combinations were executed and independently audited. A single 32³ / 16-epoch diagonal-information / matched-model job passed independent replay. A full ten-job 32³ local run exceeded the available execution time and was **not certified locally**; the full 32³ set requires Windows verification. Timing or memory ceilings have not been formally signed off.

The independent auditor reuses the separately implemented `independent_mart` in `experiment_08aj_k_audit.py`, via 08AJ-Q's auditor. The cross-policy checks compare full measurement catalogues, overlapping-ray samples, warm prefixes, and complete-view cardinality. All checks are for the engineering phantom only.

**Remaining scientific requirements**: structural/generator-level phantom-family independence review; preapproval of the primary estimand, sample-size/precision rationale, 20,000-resample stratified bootstrap and failure/resource ceilings; production 480-job executor and independent outcome audit; scientific source lock and signed protocol freeze. Infeasible 64³ complete-view comparisons remain outside the primary 32³ study.
