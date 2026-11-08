# RBYRCT 08AJ-T — Scientific Decisions & Freeze-Readiness Candidate

**Status: FREEZE_BLOCKED. This is not a frozen protocol, production runner, or approval.**

## Purpose

08AJ-S established that the 08AJ-R 32³, 2,048-ray, 16-epoch ten-job engineering rehearsal passed independently on the user's Windows system. That evidence validates the engineering configuration, **not** scientific generalization or the 480-job production executor. 08AJ-T packages the 08AJ-S review as a versioned, source-hashed *candidate* and independently checks that all five unresolved gates remain visible and execution disabled. **No phantom generation, MART execution, performance comparisons, or use of the 24 prospective objects occurs here.**

## Files in ZIP

- `experiment_08aj_t.py`: create and verify a read-only freeze-readiness candidate snapshot.
- `experiment_08aj_t_audit.py`: separate auditor for source hashes, 08AJ-S decision register, candidate integrity, and disabled execution gates.
- `test_experiment_08aj_t.py`: eight automated regression checks.
- `RBYRCT_08AJ_S_Decision_Register.json`: exact prior review decision register, unchanged.
- `08AJ_PROTOCOL_DESIGN.md`: existing protocol design file, included in case absent locally; do not overwrite a modified local file without reviewing changes.
- `08AJ_T_Scientific_Decision_Checklist.md`: scientific signoff checklist and actionable next steps.
- `README_08AJ_T.md`: this guide.

These scripts require existing RBYRCT source files from 08AJ-B through 08AJ-R in the same directory. They do not copy or modify earlier results.

## Windows PowerShell

From `(rbyrct-3d)` in `C:\Users\shuss\Downloads\rbyrct-3d-05a` after extracting the ZIP:

```powershell
python -m pytest test_experiment_08aj_t.py -q

python experiment_08aj_t.py `
    --output-dir results\experiment08aj_t\freeze_candidate_first `
    --mode prepare

python experiment_08aj_t.py `
    --output-dir results\experiment08aj_t\freeze_candidate_first `
    --mode check

python experiment_08aj_t_audit.py `
    --output-dir results\experiment08aj_t\freeze_candidate_first

Get-Content results\experiment08aj_t\freeze_candidate_first\run_status.json
```

Expected verdicts, in order:

- `8 passed`
- `T_FREEZE_READINESS_REVIEW_REQUIRED`, with **five** blocking gates.
- `T_CANDIDATE_SOURCE_MATCH`
- `T_INDEPENDENT_FREEZE_GATE_AUDIT_PASS`, even though `frozen: false`.

**The passing auditor is evidence that the freeze is safely blocked and the candidate is internally consistent, not permission to run the 480 jobs.**

## Scientific decision register (T-01–T-05)

| Gate | Status | Exit evidence required |
|---|---|---|
| T-01 Structural novelty | BLOCKED | Compare phantom morphology and generator construction against historical cohorts; retain bounded scope as synthetic stress tests. |
| T-02 Statistical rationale | BLOCKED | Approve object-level estimand, conditional bootstrap interpretation, precision simulation and practical effect language. |
| T-03 Resources and failures | BLOCKED | Define Windows-calibrated per-job/total runtime, memory ceiling and deterministic retry policy. |
| T-04 Production implementation | BLOCKED | Implement, validate, and independently audit the **480-job** executor and RMSE outcomes using a separate engineering fixture. |
| T-05 Formal source freeze | BLOCKED | Record source commit/tag, environment, named approvals and explicit separate authorizing gate. |

The frozen plan must keep 08AJ-F's authoritative **fine-64³ -> coarse-32³** truth definition; never reuse obsolete direct-32³ hashes from the initial 08AJ-D draft. The primary metric is the mean per-object of four paired fractional RMSE gains (`information_diag` vs warm-start-matched `uniform_multiscale`). 24 objects, not 96 conditions, are the analysis units. The object-stratified percentile bootstrap (20,000 resamples; seed 941007) remains a **proposal requiring approval**. The suggested 2% practical benefit is **not** an approved gate. Whole-view sampling at 32³ is secondary, and a 2,048-ray full-view condition at 64³ is infeasible and excluded.

## Safety and reproducibility

- `prepare` **refuses to overwrite** an existing destination; preserve `freeze_candidate_first` as evidence. For a new candidate, use a new output directory name.
- `check` verifies that the current source bytes still match this candidate. Editing a source after `prepare` makes the check fail as intended.
- The independent auditor catches tampering with the candidate, the review, the source files, and the blocked status.
- The scripts expose no execution/unlock/freeze implementation. CLI `--mode freeze`, `execute`, or `unlock` are refused.
- The candidate does **not** contain a Git commit, signed scientific approvals, a certified production executor, or the Windows environment freeze; those cannot be inferred from successful engineering tests.

## After the Windows checks

The next practical task is **not** another isolated engineering stage. Close T-01–T-03 in a scientific signoff meeting, and implement the actual 480-job runner plus outcome auditor under T-04. Once all gates have evidence and approval, create a separate, signed immutable source lock, then authorize prospectively. Never modify this candidate in place to manufacture an approval.
