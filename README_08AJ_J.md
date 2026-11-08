# RBYRCT-08AJ-J — Outcome-free validation orchestration rehearsal

## Scope and important guard

This stage generates a deterministic, **unfrozen** **planning manifest** of 480 intended primary-budget policy-condition jobs (24 phantoms × 2 acquisition seeds × 2 forward models × 5 policies). It does **not** perform projection, MART, RMSE, comparative measurement, or confirmatory analysis. The `execute` option always refuses. This is not a finished production runner, and the independent auditor checks **engineering fixture receipts only**, not reconstruction correctness.

Previous 08AJ-D/H inference and phantom independence review blockers remain. The 64³ complete-view comparison remains a separate feasible-budget study. Do not interpret `PLAN_ONLY_PASS` or `INDEPENDENT_DEMO_AUDIT_PASS` as a protocol freeze or production numerical validation.

## Files

- `experiment_08aj_j.py`: creation of the immutable-at-path 480-job plan, source hashes, status, and exclusive-write engineering recovery receipts.
- `experiment_08aj_j_audit.py`: independent (does not import runner) verification of manifests, source hashes, plan permissions, roster size/family counts, unique receipt set, receipt content and tampering.
- `test_experiment_08aj_j.py`: 9 outcome-free tests of roster, exclusivity, interruption recovery, source mismatch and tampering.
- `README_08AJ_J.md`: instructions.

Copy the three `.py` files into your existing `rbyrct-3d-05a` directory. Keep your earlier 08AJ modules unchanged. Do not copy test data into the prospective output directory.

## Windows PowerShell

Run from the `(rbyrct-3d)` environment in `C:\Users\shuss\Downloads\rbyrct-3d-05a`.

```powershell
python -m pytest test_experiment_08aj_j.py -q

python experiment_08aj_j.py `
    --output-dir results\experiment08aj_j\planning_first `
    --mode plan

python experiment_08aj_j.py `
    --output-dir results\experiment08aj_j\planning_first `
    --mode check

python experiment_08aj_j.py `
    --output-dir results\experiment08aj_j\planning_first `
    --mode demo-recovery

python experiment_08aj_j_audit.py `
    --output-dir results\experiment08aj_j\planning_first

Get-Content results\experiment08aj_j\planning_first\run_status.json
```

For a **deliberate crash/recovery test**, instead of `demo-recovery` first, you may run `--mode simulate-interruption` and then `--mode demo-recovery`. The first command raises `RuntimeError: SIMULATED_INTERRUPTION_BEFORE_COMMIT` **intentionally**. Do not remove any receipts; the next command reuses them. If you already completed `demo-recovery`, use a new output directory for the deliberate interruption exercise.

### Expected success results

1. New tests: `9 passed`.
2. Plan creation: `PLAN_ONLY_PASS`, `planned_jobs: 480`, `frozen: false`, `execution_allowed: false`, `no_confirmatory_outcomes: true`.
3. Check: `PLAN_SOURCE_MATCH`.
4. Recovery: `RECOVERY_FIXTURE_PASS`, 3 **ENGINEERING_DEMO** receipts.
5. Auditor: `INDEPENDENT_DEMO_AUDIT_PASS`, `pass: true`, `engineering_receipts: 3`, `no_production_numerical_audit: true`.

The output directory cannot be overwritten. `plan.json` stores the complete deterministic 480-item roster and exact source SHA-256 fingerprints. The `run_status.json` and `manifest.sha256` bind its contents to the plan. Code changes after creation cause the plan check and independent audit to fail. Failure is a guard, not a signal to bypass the lock.

## What's **not** implemented

- No real policy-condition processing, per-job reconstructions, volume/RMSE artifacts or confirmation execution.
- No independent numerical verification of production reconstructions or reconstruction data hashes.
- No scientifically approved bootstrap precision rationale, effect-size criterion or hardware-calibrated time/resource ceilings.
- No proof of structural/generator independence from prior phantom studies.
- No formal source/analysis freeze or advisor sign-off.

**Next:** 08AJ-K should implement a real numerical runner in a *blocked-by-default* mode with its own independent replay/auditor, using engineering-only synthetic fixture objects, and then resolve scientific lock reviews before enabling production validation. Never reinterpret the three engineering fixture receipts as scientific outcomes.
