# 08AJ-N — Full 16-epoch 32³ MART engineering replay

**NON-CONFIRMATORY, NOT FROZEN.** This package tests the full proposed 16-epoch MART configuration on a **single fixed engineering-only phantom (seed 970099)**, excluded from the 24-object prospective roster. It does not execute any of the 480 proposed policy-condition jobs or compute reconstruction RMSE/policy comparisons.

## Included files
- `experiment_08aj_n.py` — source-locked engineering plan; two models; save 8- and 16-epoch numerical checkpoints; durable per-model commit/reuse.
- `experiment_08aj_n_audit.py` — separate replay from persisted sparse rows and measurements; SHA-256 verification; checks both checkpoints and detects tampering.
- `test_experiment_08aj_n.py` — six tests for guardrails, interruption/resumption, replay, source corruption, and artifact corruption.
- `README_08AJ_N.md` — these instructions.

Extract the four files at the top level of the Windows `rbyrct-3d-05a` project. Requires previous 08AJ modules and original research code; use the existing `rbyrct-3d` Python environment.

## Run in PowerShell

```powershell
python -m pytest test_experiment_08aj_n.py -q

python experiment_08aj_n.py `
    --output-dir results\experiment08aj_n\engineering_first `
    --mode init

python experiment_08aj_n.py `
    --output-dir results\experiment08aj_n\engineering_first `
    --mode check

python experiment_08aj_n.py `
    --output-dir results\experiment08aj_n\engineering_first `
    --mode run

python experiment_08aj_n_audit.py `
    --output-dir results\experiment08aj_n\engineering_first
```

Expected: `6 passed`, `N_PLAN_CREATED`, `N_SOURCE_MATCH`, `N_16_EPOCH_ENGINEERING_PASS`, `N_INDEPENDENT_16_EPOCH_REPLAY_PASS`.

The numerical run may take longer on Windows than prior two-epoch tests. If it is interrupted after one model has committed, rerun `--mode run` on the **same** directory; the already committed model is independently checked before reuse. Never delete or modify a committed receipt to force a different result. If a job was interrupted *while writing*, its `.staging` folder is discarded and regenerated on resume.

## What is actually checked

- Coarse 32³ truth is the block average of a 64³ engineering phantom; models `same` and `independent` share this latent phantom.
- One 2048-ray diagonal-information acquisition at a fixed geometry/seed; 64-ray coverage-derived warm prefix.
- 16-epoch MART with relaxation 0.25 and initial value 0.3; a separate 8-epoch checkpoint.
- SHA-256 fingerprints of the proposal and source files; array and receipt digests; exact acquisition subset matching noisy catalogue.
- Replay with the separate MART implementation at 8 and 16 epochs, within 1e-11 absolute tolerance.

The checkpoint at epoch 8 and the final epoch 16 are computed in separate full-solver invocations from the same initial state, rather than incremental continuation. They should match an uninterrupted 16-epoch solver run.

## Important limits

1. Passing this audit **does not** certify the prospective 480-job execution program, the entire 24-object cohort, policy comparisons, runtime on all phantoms, or the numerical forward projector itself.
2. No registered statistical thresholds or scientific sign-offs are altered; no protocol freeze or execution authorization is created.
3. Only one fixed policy is tested; no objective performance outcome or RMSE is generated.
4. The full production runner, confirmatory analysis, morphology-independence review, statistical power/precision justification, resource-ceiling approvals, and formal source lock remain pending.
5. Do not confuse source hashes in this engineering plan with a signed final prospective lock.

Preserve the completed `engineering_first` output directory unchanged.
