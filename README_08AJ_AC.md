# RBYRCT 08AJ-AC — Production-readiness candidate and guarded engineering launcher

## Scientific status

**NOT APPROVED, NOT FROZEN, NOT READY FOR CONFIRMATORY EXECUTION.**

This module does not run, load or select any of the 24 prospective phantoms. It verifies and cryptographically records existing, noncohort AB numerical evidence at 8³ and 32³, checks the disabled AA/M production specifications, references Y's five scientific decision gates, and checks Z's **proposed** resource/failure policy. It provides an **optional** guard around a single engineering-only AB job. The guard uses a hard wall-clock process termination, a sampled process-tree RSS ceiling (not a hard operating-system memory limit), immutable attempt evidence and no automatic retries. The numerical output is independently replayed following successful guarded execution.

The AC independent audit **passes when it verifies that the readiness finding is still BLOCKED**. It does not certify the planned 480 numerical jobs or scientific hypotheses. Mid-epoch checkpoint restart is not implemented; AB can reuse completed jobs but preserves incomplete staging for investigation.

## Contents

- `experiment_08aj_ac.py` — checks source/evidence locks, writes immutable readiness candidate, optional guarded engineering launch.
- `experiment_08aj_ac_audit.py` — independently replays all attached AB numerical jobs and confirms the blocked readiness status.
- `test_experiment_08aj_ac.py` — 10 automated tests.

Copy these **three Python files** into the same project directory as all existing `experiment_08aj_*` modules. Do not replace any earlier scripts. `psutil` is required *only* for optional guarded execution; the guard fails closed if the dependency is missing.

## Windows commands from `(rbyrct-3d)` PowerShell

### 1. New tests

```powershell
python -m pytest test_experiment_08aj_ac.py -q
```

### 2. Prepare immutable readiness candidate from your existing evidence

```powershell
python experiment_08aj_ac.py `
  --mode prepare `
  --output-dir results\experiment08aj_ac\readiness_first `
  --aa-dir results\experiment08aj_aa\disabled_path_first `
  --m-dir results\experiment08aj_m\contract_first `
  --ab8-dir results\experiment08aj_ab\engineering_8_first `
  --ab32-dir results\experiment08aj_ab\engineering_32_first `
  --y-dir results\experiment08aj_y\consolidation_first `
  --z-dir results\experiment08aj_z\engineering_8_first
```

Expected `AC_READINESS_CANDIDATE_PREPARED`, 5 blockers, zero confirmatory outcomes. **Do not rerun `prepare` on an existing directory**; overwriting is prohibited.

### 3. Recheck source and recorded artifact integrity

```powershell
python experiment_08aj_ac.py `
  --mode check `
  --output-dir results\experiment08aj_ac\readiness_first `
  --aa-dir results\experiment08aj_aa\disabled_path_first `
  --m-dir results\experiment08aj_m\contract_first `
  --ab8-dir results\experiment08aj_ab\engineering_8_first `
  --ab32-dir results\experiment08aj_ab\engineering_32_first `
  --y-dir results\experiment08aj_y\consolidation_first `
  --z-dir results\experiment08aj_z\engineering_8_first
```

Expected `AC_SOURCE_AND_BLOCKER_GATE_MATCH`.

### 4. Independently replay all existing AB engineering evidence

```powershell
python experiment_08aj_ac_audit.py `
  --output-dir results\experiment08aj_ac\readiness_first `
  --aa-dir results\experiment08aj_aa\disabled_path_first `
  --m-dir results\experiment08aj_m\contract_first `
  --ab8-dir results\experiment08aj_ab\engineering_8_first `
  --ab32-dir results\experiment08aj_ab\engineering_32_first `
  --y-dir results\experiment08aj_y\consolidation_first `
  --z-dir results\experiment08aj_z\engineering_8_first
```

Expected `AC_INDEPENDENT_READINESS_GAP_AUDIT_PASS`, zero audit errors, with at least two audited 8³ and one 32³ job matching the previously reported Windows runs. The 32³ MART replay can be CPU-intensive. A PASS means **the evidence and outstanding blockers are consistent**, not that confirmatory execution is permitted.

### 5. Optional: guarded numerical launcher for ONE additional engineering-only job

This step is optional and is **not** needed to pass AC. **Do not run it against `engineering_8_first` or `engineering_32_first` after you have prepared your AC snapshot**; new artifacts would intentionally invalidate the immutable AC evidence snapshot. To exercise the guard, first initialize a *separate* AB engineering directory:

```powershell
python -m pip install psutil
python experiment_08aj_ab.py `
  --mode init --n 8 `
  --output-dir results\experiment08aj_ab\engineering_8_guard_trial `
  --aa-dir results\experiment08aj_aa\disabled_path_first `
  --m-dir results\experiment08aj_m\contract_first
python experiment_08aj_ac.py `
  --mode guarded-run `
  --ab-dir results\experiment08aj_ab\engineering_8_guard_trial `
  --aa-dir results\experiment08aj_aa\disabled_path_first `
  --m-dir results\experiment08aj_m\contract_first `
  --policy information_diag --model same `
  --attempt-dir results\experiment08aj_ac\guard_trial_first
```

Expected `AC_GUARDED_ENGINEERING_JOB_PASS`. Failure attempts and partial AB staging remain in place; **no automatic retry** is allowed. The launcher cannot exceed the proposed 600-second wall limit or the 8 GiB RSS threshold, but it can be configured to stricter limits. This is a proposed engineering guard, not a validated resource policy for the full cohort.

## Remaining blockers

1. Accountable review of related synthetic phantom families, structural independence, and claim scope.
2. Approval of the fixed-24-object descriptive estimand and strictly conditional population inference.
3. Precision rationale and prespecified statistical/effect decision rules.
4. Approved and empirically validated operational resource/failure ceilings, including strict monitoring/OS constraints and recovery semantics.
5. An actual, locked, all-roster 480-job production numerical executor with independent outcome audit and *subsequent* source freeze and approval.

No data-dependent decisions can be inferred from the engineering fixtures. Nothing in AC changes `confirmatory_execution_allowed: false`.
