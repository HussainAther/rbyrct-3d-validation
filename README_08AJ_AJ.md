# RBYRCT 08AJ-AJ — real MART worker termination and exact recovery

## Scope

Engineering-only failure test. Reuses the already independently audited **AF fresh-input 32^3 job** (`information_diag`, `same`) as a numerical reference. Creates a **new isolated AH worker** inside AJ's output directory. Reads AA's 480 disabled job specifications and 96 shared-catalogue groups only to validate their locked provenance. Never reads the prospective 24-object cohort, enables production, freezes a protocol, or changes existing AH/AF/AA files.

New files (copy ONLY these five into the existing `rbyrct-3d-05a` project):

- `experiment_08aj_aj.py` — source lock, real MART worker kill, guarded AH resume
- `experiment_08aj_aj_worker.py` — AH row-level worker, with **post-commit** hold for repeatable termination
- `experiment_08aj_aj_audit.py` — independently validates the failure receipt, preserved checkpoint hash, final result and AH numerical replay
- `test_experiment_08aj_aj.py` — 15 unit/control tests
- `README_08AJ_AJ.md`

Dependencies: the existing `experiment_08aj_aa.py`, `experiment_08aj_ah.py`, `experiment_08aj_ah_audit.py`, AF/AG/AD and their imported project dependencies. Requires `psutil`, NumPy, SciPy. Do NOT overwrite those previously audited modules with old copies.

## Windows PowerShell

From `(rbyrct-3d) PS C:\Users\shuss\Downloads\rbyrct-3d-05a>`:

```powershell
python -m pytest test_experiment_08aj_aj.py -q

$ajArgs = @(
  "--output-dir", "results\experiment08aj_aj\live_failure_32_first",
  "--af-dir", "results\experiment08aj_af\fresh_engineering_32_first",
  "--aa-dir", "results\experiment08aj_aa\disabled_path_first",
  "--m-dir", "results\experiment08aj_m\contract_first"
)

python experiment_08aj_aj.py --mode init @ajArgs `
  --policy information_diag --model same

python experiment_08aj_aj.py --mode check @ajArgs

python experiment_08aj_aj.py --mode kill-worker @ajArgs `
  --target-rows 256 --wall-seconds 120 --max-mib 8192

python experiment_08aj_aj.py --mode check @ajArgs

python experiment_08aj_aj.py --mode resume @ajArgs `
  --wall-seconds 600 --max-mib 8192

python experiment_08aj_aj_audit.py @ajArgs
```

Expected (subject to full Windows execution):

- `AJ_LIVE_ENGINEERING_GATE_PREPARED`
- `AJ_ENGINEERING_SOURCE_AND_CHECKPOINT_PASS`
- `AJ_REAL_MART_WORKER_KILLED` (requires a live actual MART worker killed AFTER at least 256 fully committed row updates and BEFORE full completion)
- `AJ_REAL_WORKER_RECOVERY_PASS`
- `AJ_INDEPENDENT_REAL_WORKER_FAILURE_AUDIT_PASS`, `pass:true`, `errors:[]`, all 32768 MART row updates audited, 0 or tolerance-bounded RMSE/replay differences.

The worker's deliberate ~0.4 s delay **after** each checkpoint publication does not affect the numerical updates. The supervisor terminates the child upon finding a committed `cp_00000256` (or later) while the worker is still running. The recoverer uses the unmodified AH implementation without any delay. Existing AF reconstruction is an immutable numerical reference; the independent AH auditor reruns MART and recalculates RMSE.

### Fail-closed behavior

- If source inputs or implementation hashes drift, stop.
- If an incomplete `.stage-*` checkpoint directory remains, the AH verification refuses recovery; preserve evidence and investigate, don't erase it. For operator-reviewed cleanup the existing AH `--mode quarantine-staging` command can move these staging directories to quarantine in the **new AJ worker subdirectory**; do not apply it to existing verified AH evidence.
- If the kill is not observed while the real worker is active, AJ **does not** record a successful fault receipt. It may leave partial checkpoints for investigation. Use a NEW output directory for a new clean test rather than overwriting records.
- If resume exceeds the wall or memory cap, it returns `AJ_RESUME_NOT_COMPLETE` and preserves valid checkpoints; do not call that a pass.
- The fault receipt and successful resume receipt use create-once semantics. Repeating `kill-worker` or `resume` does not overwrite them.
- The lock remains `production_execution_allowed:false`, `production_480_job_certified:false`, `resource_policy_approved:false`, `scientific_signoff:false`.

### Verification boundaries

The 15 new tests were run locally with **test-only dependency stubs** because the local packaging folder does not contain the user's full RBYRCT project modules. They verify AJ source/argument/receipt control logic, NOT a real numerical kill/replay. The user must run the full Windows command sequence to verify the integrated numerical behavior. Successful completion is evidence for this tested engineering case, not 480-job numerical certification, robustness to all crash timings, or approved scientific analysis.
