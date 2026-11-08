# RBYRCT 08AJ-L: Protocol Review and 32^3 Engineering Replay (DRAFT)

This package is deliberately **not a scientific protocol lock**. It cannot run the proposed 24-object cohort. It prepares a versioned protocol-review manifest and runs **one fixed, non-cohort phantom** at 32^3 under one policy for matched and independent forward projections. The engineering replay uses **2 MART epochs**, while the proposed primary study uses **16 epochs**. Thus 16-epoch production replay has **not** been certified.

## Copy into the existing repository

Extract these four files into `C:\Users\shuss\Downloads\rbyrct-3d-05a`:

- `experiment_08aj_l.py`
- `experiment_08aj_l_audit.py`
- `test_experiment_08aj_l.py`
- `README_08AJ_L.md`

These files do not replace prior scripts.

## PowerShell

```powershell
python -m pytest test_experiment_08aj_l.py -q

python experiment_08aj_l.py `
  --output-dir results\experiment08aj_l\draft_first `
  --mode init

python experiment_08aj_l.py `
  --output-dir results\experiment08aj_l\draft_first `
  --mode check

python experiment_08aj_l.py `
  --output-dir results\experiment08aj_l\draft_first `
  --mode run

python experiment_08aj_l_audit.py `
  --output-dir results\experiment08aj_l\draft_first
```

Expected verdicts: `DRAFT_PREPARED`, `DRAFT_SOURCE_MATCH`, `L_NUMERICAL_ENGINEERING_PASS`, `L_INDEPENDENT_REPLAY_PASS`. Use a **new output directory** when repeating from the beginning. `run` can safely reuse already-audited checkpoints but refuses altered committed checkpoints.

The output contains `protocol_review_draft.json`, `run_status.json`, and two immutable engineering checkpoints under `engineering_jobs/`. The auditor validates file hashes, provenance, selected measurements, geometry and numerical replay using a separately implemented MART recurrence. The numerical fixture uses `smooth_heterogeneity` seed **970099**, which is excluded from the 24-object prospective seed roster. It computes **no RMSE, gains, policy rankings, or other confirmatory outcomes**.

## Review register (not signed or frozen)

1. Generator/morphological independence versus historical cohorts requires expert structural review. An earlier exact seed/hash audit alone is insufficient.
2. The 24-object inferential precision/power rationale, family stratification, practical effect interpretation and hypotheses require scientific approval.
3. Production runtime/memory ceilings, failure handling and retries need a signed policy.
4. The 64^3 complete-view comparator is **out of scope for the 32^3 primary**; at 64^3 it requires a ray budget >=4096.
5. A complete 480-job resumable numerical production runner and independent outcome auditor do not exist yet. A 32^3 two-epoch fixture is not that runner.
6. Git commit, source lock, protocol approvals and prospective execution authorization remain pending.

`--mode freeze` and `--mode production` always fail intentionally. No user approval is inferred by running this preflight. The source hashes refer to the installed files at the time of draft creation, not to a signed immutable repository revision. Preserve earlier 08AJ-D through K outputs.
