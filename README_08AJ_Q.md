# RBYRCT-08AJ-Q: Actual per-job numerical engineering executor + independent audit

This package is an **engineering-only** numerical rehearsal. It does not run any of the 24 prospective objects; its seed is fixed at `970099` and family is fixed at `smooth_heterogeneity`. It never unlocks the 480-job contract, freezes the scientific protocol, or computes performance outcomes.

## Included files

- `experiment_08aj_q.py`: fixed noncohort engineering job executor; durable per-job checkpoints, resumption, plan/source checks.
- `experiment_08aj_q_audit.py`: independent audit of source fingerprints, each policy's selected ray indices, forward/noise catalogue, sparse rows, and MART numerical replay.
- `test_experiment_08aj_q.py`: eight regression tests, including genuine runs, paired noise, recovery, and corruption detection.
- `README_08AJ_Q.md`: this file.

Place these **four files** next to the existing RBYRCT modules in `rbyrct-3d-05a`. Existing `experiment_08aj_*` sources are unchanged. Use distinct output directories: initialization refuses to overwrite existing results.

## Windows PowerShell: fast 8^3 multi-policy rehearsal

```powershell
python -m pytest test_experiment_08aj_q.py -q

python experiment_08aj_q.py `
    --output-dir results\experiment08aj_q\engineering_8_first `
    --mode init

python experiment_08aj_q.py `
    --output-dir results\experiment08aj_q\engineering_8_first `
    --mode check

python experiment_08aj_q.py `
    --output-dir results\experiment08aj_q\engineering_8_first `
    --mode run --policy information_diag --model same

python experiment_08aj_q.py `
    --output-dir results\experiment08aj_q\engineering_8_first `
    --mode run --policy uniform_multiscale --model same

python experiment_08aj_q.py `
    --output-dir results\experiment08aj_q\engineering_8_first `
    --mode run --policy complete_view --model independent

python experiment_08aj_q_audit.py `
    --output-dir results\experiment08aj_q\engineering_8_first
```

Expected last verdict: `Q_INDEPENDENT_ENGINEERING_AUDIT_PASS`, `audited_jobs: 3`. Running an existing job again should return `Q_ENGINEERING_JOB_REUSED`, after verifying that its saved evidence still passes the independent audit.

## Windows PowerShell: full 32^3 / 16-epoch single-policy engineering job

The following is deliberately **one** job, not the 480-job confirmation study:

```powershell
python experiment_08aj_q.py `
    --output-dir results\experiment08aj_q\engineering_32_first `
    --mode init --n 32

python experiment_08aj_q.py `
    --output-dir results\experiment08aj_q\engineering_32_first `
    --mode run --policy coverage --model independent

python experiment_08aj_q_audit.py `
    --output-dir results\experiment08aj_q\engineering_32_first
```

The actual 32^3 run uses 2048 selected rays and 16 MART epochs, with complete 12288-ray noisy catalogue. A full independent replay recomputes the 16-epoch recurrence; it can take longer than a small test. Other named policies and models are allowed **only for the fixed engineering phantom**.

## Scope and remaining limitations

- Each job saves selected order, observed measurements, clean/noisy full catalogues, selected CSR geometry, 16-epoch reconstruction (or 2 epochs at 8^3), canonical receipt and SHA-256 of every artifact.
- Paired policies with the same forward model observe exactly the same noisy full catalogue for this engineering-only seed.
- The auditor checks the policy order against a freshly recomputed geometry/selector, reconstructs the expected noisy catalogue and sparse rows, and independently replays MART.
- Execution is fixed to one engineering object and one acquisition seed. **This does not implement the 480-job production executor or per-object performance analysis.**
- Runtime/memory ceilings, signed source lock, scientific phantom independence review, power/precision justification, and protocol approval remain unresolved.
- No outcome-based tuning or confirmatory measurements are allowed by this script. Do not treat engineering reconstruction files as prospective study evidence.
