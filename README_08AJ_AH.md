# RBYRCT-08AJ-AH — Atomic Engineering Checkpoints and Supervised Resource Limits

## Purpose and exact scientific status

08AJ-AH hardens the **verified AF engineering-only 32³ numerical inputs** and the **AG row-level recovery**. It introduces an atomic directory commit for each checkpoint, a supervisor with a real process-termination wall timeout, and a per-worker memory limit. It compares the recovered MART arrays against the already audited uninterrupted AF engineering reconstruction. **It does not implement or enable the 24-object prospective study** or certify the 480-job production workload. The proposed resource policy remains **unapproved**.

Package contains exactly four new files:

- `experiment_08aj_ah.py` — fresh AF engineering-input, atomic row-checkpoint MART worker and process supervisor.
- `experiment_08aj_ah_audit.py` — independent 32³ reconstruction/RMSE replay, receipt and checkpoint verification.
- `test_experiment_08aj_ah.py` — 14 automated tests, including interruption/resume, atomic publish, corruption, staged-write rejection, and simulated timeout termination.
- `README_08AJ_AH.md` — these instructions.

Extract into `C:\Users\shuss\Downloads\rbyrct-3d-05a` alongside existing AF, AG, AD, AA, M and numerical modules. Do not overwrite previously audited output directories. Dependencies: NumPy, SciPy, pytest, **psutil** (`python -m pip install psutil` if missing). The test package is not intended to be run on its own outside the existing source directory.

## Windows workflow: isolated 32³ engineering recovery

### 1. Tests and local process-monitor dependency

```powershell
python -c "import psutil; print(psutil.__version__)"
python -m pytest test_experiment_08aj_ah.py -q
```

Expected: `14 passed`.

### 2. Define directories once

```powershell
$ahArgs = @(
    "--output-dir", "results\experiment08aj_ah\fresh_32_atomic_first",
    "--af-dir", "results\experiment08aj_af\fresh_engineering_32_first",
    "--aa-dir", "results\experiment08aj_aa\disabled_path_first",
    "--m-dir", "results\experiment08aj_m\contract_first"
)
```

### 3. Initialize fixed engineering source

```powershell
python experiment_08aj_ah.py --mode init @ahArgs `
    --policy information_diag --model same
```

Expected: `AH_ENGINEERING_GUARD_PREPARED`, `n:32`, `epochs:16`, `production_execution_allowed:false`.

### 4. Deliberately interrupt after 257 rows

```powershell
python experiment_08aj_ah.py --mode run @ahArgs `
    --stop-after-rows 257 --wall-seconds 600 --max-mib 8192
```

Expected: `AH_ENGINEERING_PAUSED`, `rows_done:257`, `supervised:true`.

### 5. Check integrity and resume

```powershell
python experiment_08aj_ah.py --mode check @ahArgs

python experiment_08aj_ah.py --mode run @ahArgs `
    --wall-seconds 600 --max-mib 8192
```

Expected: `AH_SOURCE_AND_ATOMIC_CHAIN_PASS`, then `AH_ENGINEERING_RECOVERY_PASS` with `rows_done:32768` and `max_abs_error_vs_af:0.0` (subject to verified numerical tolerance).

### 6. Independent reconstruction and RMSE audit

```powershell
python experiment_08aj_ah_audit.py @ahArgs
```

Expected: `AH_INDEPENDENT_ATOMIC_RECOVERY_AUDIT_PASS`, `pass:true`, no errors, `rows_audited:32768`, near-zero independent replay/RMSE differences.

### 7. Only after a forcibly stopped worker: explicitly quarantine incomplete staging

Do **not** run the independent final auditor before completion. If `--mode check` reports `unexpected or interrupted staging artifact` after process termination, the checkpoint was **not** atomically published. Preserve the directory and inspect its contents. You may move only uncommitted `.stage-*` checkpoint directories to a manifest-logged quarantine using:

```powershell
python experiment_08aj_ah.py --mode quarantine-staging @ahArgs
python experiment_08aj_ah.py --mode check @ahArgs
```

The quarantine is retained within AH's output evidence; it is never silently deleted. **Never use this operation to bypass corruption of a committed `cp_XXXXXXXX` checkpoint.** If a committed receipt/hash fails, stop and investigate; do not overwrite it.

## Enforcement details and limitations

- Each committed checkpoint is an immutable `checkpoints\cp_XXXXXXXX\` directory containing both `state.npy` and canonical `receipt.json`. Both files are fsynced before a single atomic directory rename publishes them. Receipts link to the preceding committed receipt and are checked before recovery.
- A separate subprocess handles MART, and the parent terminates it after the configured **wall-clock** deadline rather than depending on in-loop checks. **No automatic retry** happens after timeout or memory-related failure.
- On **Windows**, the worker attempts to install a kernel Job Object `JOB_OBJECT_LIMIT_PROCESS_MEMORY` limit before loading numerical input arrays. If assignment fails (for example, an incompatible nested Job Object), the worker **fails closed**. This Windows code path has **not yet been tested locally**; confirm the output on your Windows installation. The parent also monitors resident memory with psutil; this sampling can lag an instantaneous allocation. On Linux, the worker uses `RLIMIT_AS` (virtual address space, not RSS), also paired with a psutil RSS monitor.
- These are **per-invocation** ceilings, not an approved 480-job resource policy or a guarantee about machine-wide memory. `600` seconds and `8192` MiB are engineering proposals, not approved scientific thresholds.
- A hard kill during a write can leave an uncommitted `.stage-*` directory, so the system **fails closed** and requires explicit quarantine. Committed checkpoints remain reusable.
- AH reads AF job arrays/receipts but does not modify AF, AA, AD, AE, or AG evidence. Its fresh inputs are the already-audited **noncohort engineering phantom**, not a newly generated prospective object.
- The independent audit checks the whole checkpoint chain, compares with AF's uninterrupted reconstruction, independently replays MART, and recalculates RMSE using the AF engineering truth.
- The final artifact does not mark production certification, scientific sign-off, a source freeze, or confirmatory permission. All remain false.

## Evidence-preservation guidance

Preserve the previously verified directory `results\experiment08aj_ag\fresh_32_recovery_first` and the full-resolution AF directory. Run AH in the new dedicated directory shown above. Never delete or reinitialize an interrupted run to make an audit pass.
