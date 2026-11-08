# RBYRCT-08AJ-O — disabled integration contract and 16-epoch evidence link

This package contains four new files:

- `experiment_08aj_o.py` — deterministic disabled integration contract, source/roster checks, non-numerical interruption recovery, N engineering evidence attachment.
- `experiment_08aj_o_audit.py` — separate contract/receipt/source and N numerical replay auditor.
- `test_experiment_08aj_o.py` — eight unit tests for gating, integrity, recovery, and non-numerical fixture corruption.
- `README_08AJ_O.md` — these instructions.

All existing 08AJ-D through N source files should remain unchanged. **Do not replace your M or N results.**

## Prerequisites

Your completed and audited output directories should exist:

- `results\experiment08aj_l\draft_first` (08AJ-L, 2-epoch engineering)
- `results\experiment08aj_m\contract_first` (08AJ-M, disabled 480-job plan, linked to L)
- `results\experiment08aj_n\engineering_first` (08AJ-N, 16-epoch engineering evidence)

The program uses the existing M contract and N engineering outputs. **It does not run or certify the 480 production jobs.**

## Windows PowerShell commands

Run from `C:\Users\shuss\Downloads\rbyrct-3d-05a` in your `(rbyrct-3d)` environment. Extract the four files to that directory.

```powershell
python -m pytest test_experiment_08aj_o.py -q

python experiment_08aj_o.py `
    --output-dir results\experiment08aj_o\integration_first `
    --m-dir results\experiment08aj_m\contract_first `
    --mode prepare

python experiment_08aj_o.py `
    --output-dir results\experiment08aj_o\integration_first `
    --m-dir results\experiment08aj_m\contract_first `
    --mode check

python experiment_08aj_o.py `
    --output-dir results\experiment08aj_o\integration_first `
    --m-dir results\experiment08aj_m\contract_first `
    --mode simulate-recovery

python experiment_08aj_o.py `
    --output-dir results\experiment08aj_o\integration_first `
    --m-dir results\experiment08aj_m\contract_first `
    --n-dir results\experiment08aj_n\engineering_first `
    --mode attach-n-engineering

python experiment_08aj_o_audit.py `
    --output-dir results\experiment08aj_o\integration_first `
    --m-dir results\experiment08aj_m\contract_first `
    --n-dir results\experiment08aj_n\engineering_first `
    --l-dir results\experiment08aj_l\draft_first `
    --require-n `
    --require-recovery
```

Expected verdict sequence:

1. `8 passed`
2. `O_CONTRACT_PREPARED`
3. `O_CONTRACT_SOURCE_MATCH`
4. `O_RECOVERY_FIXTURE_PASS`
5. `O_N_ENGINEERING_LINK_PASS`
6. `O_INDEPENDENT_INTEGRATION_AUDIT_PASS`

The two N numerical cases replay at epochs 8 and 16; this can take some time on Windows. A repeat of `prepare` against the same output folder correctly raises `FileExistsError`. Repeated `simulate-recovery` should **reuse** the three receipts; repeated `attach-n-engineering` should return `O_N_ENGINEERING_LINK_REUSED` after re-auditing N. Use a fresh output directory for an unrelated run. Do not edit prior results.

## Precisely what this package proves

- The existing M roster has exactly 480 disabled jobs, and the existing source snapshots still match.
- The O contract declares required input/output names and a *future*, not implemented, numerical receipt schema.
- O operational receipt regeneration is idempotent, and corrupted committed receipts are rejected.
- Existing N 32^3 16-epoch noncohort engineering artifacts can be bound cryptographically to the O contract and independently replayed by N's numerical auditor.
- The separate O auditor checks the M contract (including its L link), O receipts and execution gate, and the N evidence link.

**Not established:** a numerical executor for arbitrary policies/cohort objects; atomic result commits for production; full 480-job numerical audit; precision/power rationale; morphology novelty/structural independence; final scientific approvals; signed immutable source lock. Thus `production_executor_certified=false`, `execution_allowed=false`, `frozen=false`, and `no_confirmatory_outcomes=true` remain mandatory.

## Remaining review requirements

1. Scientifically assess whether new phantom families are materially independent of earlier development objects, not merely unequal in seed/hash.
2. Sign off object-level primary estimand, family-stratified bootstrap assumptions, precision rationale and effect-size interpretation.
3. Approve resource limits, failure and retry policy.
4. Implement and independently audit the actual per-policy production numerical executor, with source and artifact integrity protections.
5. Freeze an approved protocol and source revision **before** generating any confirmatory results.

The 64^3 complete-view constraint remains outside this primary 32^3 study; at 64^3 one full detector view needs at least 4096 rays.
