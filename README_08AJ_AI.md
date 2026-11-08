# RBYRCT-08AJ-AI — Controlled Engineering Failure Tests and Locked Roster Link

## Scientific scope

08AJ-AI exercises **noncohort, nonnumerical child workers** under deliberate wall-time and memory pressure, preserves an isolated incomplete staging write, and fingerprints the already-verified **AA 480-job disabled roster** and **AH completed 32³ engineering evidence**. It does **not** execute a MART reconstruction, validate 480 numerical outcomes, or authorize any prospective object. The resource/failure policy is still **not approved**. On Windows, the memory-pressure worker exercises the same kernel Job Object process-memory API used by AH, but in a separate isolated process; it is **not** a full AH numerical-worker failure test.

Four new files: `experiment_08aj_ai.py`, `experiment_08aj_ai_audit.py`, `test_experiment_08aj_ai.py`, `README_08AJ_AI.md`. Copy them into the existing `rbyrct-3d-05a` directory without replacing any previous scripts or results. Dependencies: `psutil`, `pytest` and all existing AA/AF/AH dependencies.

## Run on Windows PowerShell

**1. Tests**

```powershell
python -m pytest test_experiment_08aj_ai.py -q
```

Expected: `15 passed`. The tests include real short-lived subprocess failure cases and an isolated memory-cap worker. They do not modify your saved imaging results.

**2. Define paths using existing independently verified evidence**

```powershell
$aiArgs = @(
    "--output-dir", "results\experiment08aj_ai\controlled_failure_first",
    "--aa-dir", "results\experiment08aj_aa\disabled_path_first",
    "--m-dir", "results\experiment08aj_m\contract_first",
    "--ah-dir", "results\experiment08aj_ah\fresh_32_atomic_first",
    "--af-dir", "results\experiment08aj_af\fresh_engineering_32_first"
)
```

**3. Prepare immutable source/evidence snapshot**

```powershell
python experiment_08aj_ai.py --mode prepare @aiArgs
python experiment_08aj_ai.py --mode check @aiArgs
```

Expected: `AI_LOCKED_FAILURE_GATE_PREPARED`, then `AI_LOCKED_SOURCES_AND_CHECKPOINTS_MATCH`. This reads and fingerprints the AA contract, AH completed checkpoint chain, and AH source. It verifies 480 *disabled specifications*, 96 groups, and ten policy/model template labels. It does **not** execute any of the 480.

**4. Deliberately terminate a sleeping child on wall-time limit**

```powershell
python experiment_08aj_ai.py --mode exercise @aiArgs --kind wall --wall-seconds 0.6
```

Expected: `WALL_TIMEOUT_WORKER_TERMINATED`. A dummy child sleeps; no numerical work is performed. In unusual startup environments, a timeout can occur before the worker is fully initialized, but process termination is still tested.

**5. Check kernel memory-cap rejection on a standalone worker**

```powershell
python experiment_08aj_ai.py --mode exercise @aiArgs --kind memory --wall-seconds 15
```

Expected: `OS_MEMORY_DENIAL_CONFIRMED`, if the Windows Job Object successfully installs the 256 MiB process-memory cap and Python reports an explicit `MemoryError` when attempting to exceed it. This worker allocates memory in **one child process**, up to 1 GiB in the *fault-injection scenario*, and uses no tomography arrays. If Windows cannot install the cap, or memory denial is not clearly observed, the result is **`MEMORY_ENFORCEMENT_NOT_CONFIRMED`**. **Do not label that outcome a pass.** The output is preserved for diagnosis and the independent audit will fail closed.

**6. Test an interrupted staging directory and explicit quarantine**

```powershell
python experiment_08aj_ai.py --mode exercise @aiArgs --kind atomic-stage --wall-seconds 3
python experiment_08aj_ai.py --mode quarantine @aiArgs
```

Expected: `WALL_TIMEOUT_WORKER_TERMINATED`, then `AI_ORPHAN_STAGE_QUARANTINED`. The test creates a temporary **AI-owned** `.stage-*` directory, terminates the child before publishing any final result, and retains the partial bytes in an audit-logged quarantine. It never touches committed AH checkpoints. The quarantine operation is explicit and cannot be rerun as an overwrite.

**7. Verify unchanged original evidence and all three fault cases**

```powershell
python experiment_08aj_ai.py --mode check @aiArgs
python experiment_08aj_ai_audit.py @aiArgs --require-all
```

Expected: `AI_LOCKED_SOURCES_AND_CHECKPOINTS_MATCH`, then `AI_INDEPENDENT_GUARD_AUDIT_PASS` with `audited_fault_cases: 3`, `roster_specs: 480`, `shared_groups: 96`, `protected_ah_evidence_unchanged: true`, no errors, and `production_execution_allowed: false`.

## Interpretation and safeguards

- The AA roster stays **execution-disabled**. The link proves engineering-template membership, not object-specific production dispatch.
- The preserved AH source, checkpoint directories, and final receipt are **read-only** to AI. Any altered or missing protected evidence fails the source check.
- The stage-failure test is an isolated **atomic-commit analogue**, not a direct forced kill during AH numerical checkpoint serialization. A direct AH-worker crash-injection test remains useful future work.
- Memory denial in this isolated worker is evidence that the OS-enforced API can reject controlled allocations; it does **not** establish all AH allocations or full-machine memory limits. On Linux, RLIMIT_AS limits virtual address space, not RSS.
- All case receipts are write-once. An inconclusive/failing case must be investigated without deleting or rerunning it in place; use a **new AI output directory** if a separate test attempt is scientifically justified, recording why.
- No scientific approvals or source freeze are granted. `resource_policy_approved`, `scientific_signoff`, `frozen`, `production_480_job_certified`, and `production_execution_allowed` remain false.

Preserve `results\experiment08aj_ah\fresh_32_atomic_first` and the new AI results unchanged.
