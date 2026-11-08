# RBYRCT-08AJ-AA | Disabled 480-job numerical pathway and dependency audit

**Status:** Engineering integration passed locally. **NOT a working/certified 480-job reconstruction executor.** This package translates the frozen-disabled 08AJ-M roster into 480 validated per-job numerical **specifications**, groups them into 96 common-noise dependencies (24 objects x 2 acquisition seeds x 2 forward models), provides durable recovery *rehearsal receipts*, and independently validates the linkage to the pre-existing 08AJ-Z ten-job engineering numerical results. It does not execute any of the 24 prospective phantoms, compute prospective RMSE, authorize a freeze, or approve scientific or resource policies.

## Files

- `experiment_08aj_aa.py`: production job specification preparation, source checks, independent recovery receipt creation/reuse, optional Z engineering-link attachment; deliberately refuses production execution.
- `experiment_08aj_aa_audit.py`: separately implemented 480-job, 96-group, per-job parameter and integrity checks; optional independent Z numerical/diagnostic audit.
- `test_experiment_08aj_aa.py`: eight automated tests.
- This README.

Place these four files in your existing `rbyrct-3d-05a` repository beside `experiment_08aj_m.py`, `experiment_08aj_z.py`, their dependencies and auditors.

## Windows PowerShell

```powershell
python -m pytest test_experiment_08aj_aa.py -q

python experiment_08aj_aa.py `
  --output-dir results\experiment08aj_aa\disabled_path_first `
  --m-dir results\experiment08aj_m\contract_first `
  --mode prepare

python experiment_08aj_aa.py `
  --output-dir results\experiment08aj_aa\disabled_path_first `
  --m-dir results\experiment08aj_m\contract_first `
  --mode check

python experiment_08aj_aa.py `
  --output-dir results\experiment08aj_aa\disabled_path_first `
  --m-dir results\experiment08aj_m\contract_first `
  --mode rehearse

# Run a second time to verify all three prior receipts are reused.
python experiment_08aj_aa.py `
  --output-dir results\experiment08aj_aa\disabled_path_first `
  --m-dir results\experiment08aj_m\contract_first `
  --mode rehearse

# Link the independently audited 08AJ-Z engineering-only ten-job evidence.
python experiment_08aj_aa.py `
  --output-dir results\experiment08aj_aa\disabled_path_first `
  --m-dir results\experiment08aj_m\contract_first `
  --z-dir results\experiment08aj_z\engineering_8_first `
  --mode attach-z

python experiment_08aj_aa_audit.py `
  --output-dir results\experiment08aj_aa\disabled_path_first `
  --m-dir results\experiment08aj_m\contract_first `
  --z-dir results\experiment08aj_z\engineering_8_first `
  --require-rehearsal --require-z
```

Expected final verdict: `AA_INDEPENDENT_DISABLED_PATH_AUDIT_PASS`, `job_specifications_audited: 480`, `shared_measurement_groups_audited: 96`, `production_jobs_executed: 0`, `production_numerical_certified: false`.

If `disabled_path_first` already exists, do NOT run `prepare` again; use the existing directory for check/rehearse/audit. Existing receipts are reused only when the exact bytes are unchanged; altered receipts abort. The M and Z source files must remain unchanged relative to the original verified contract. Use a new destination for a fresh preparation; preserve earlier evidence.

## What is blocked and what remains

- Command modes `execute`, `production-run`, `unlock`, and `freeze` all abort. There is no authorization flag.
- The 480 specifications are linked to the original M source-verified plan. The per-job acquisition fields include a 64-ray common prefix for the four individual-ray policies; complete-view retains its full-view constraint.
- The optional Z link re-audits genuine 8^3 engineering numerical results and engineering RMSE. AA itself creates **no numerical result or RMSE**.
- The next implementation requirement is a real per-job **production numerical backend** accepting approved object parameters (not hard-coded engineering-only seed), with durable atomic numerical checkpoints, cost controls, repeatable source lock, and independent RMSE/replay on every job. It must be built and independently tested with noncohort engineering objects BEFORE any 24-object unlock.
- The statistical estimand/uncertainty model, phantom framing, resource limits, named scientific sign-off, and formal source freeze remain pending. No scientific performance claims follow from this milestone.
