# RBYRCT 08AJ-AE — Locked AA-template dispatch into AD row-checkpoint MART (engineering only)

This package adds a **real orchestration integration** between the already validated AA 480-job *specification* and AD's verified row-level restart engine, using only an existing, independently audited **AB engineering job** as its numerical input.

**It does not execute a single AA 24-object prospective job.** AA has 480 permanently disabled object-specific job specifications; AE maps their **ten policy/model templates** (48 prospective specifications per template) to the ten corresponding fixed-seed AB engineering jobs. AE may execute only those ten noncohort engineering jobs, never the 480 identities. The source remains unfrozen; the scientific study remains unauthorized.

## Included files

- `experiment_08aj_ae.py`: immutable dispatch plan, AA/AB source-locked template mapping, engineering dispatch, AD resume wrapper.
- `experiment_08aj_ae_audit.py`: separate independent audit, replays each *completed* AD job and verifies its RMSE.
- `test_experiment_08aj_ae.py`: 11 dispatcher/gate tests (source drift, forbidden identity, tamper, failure preservation, pending-vs-complete, handoff).
- This README.

Required **existing** modules: `experiment_08aj_aa.py`, `experiment_08aj_aa_audit.py`, `experiment_08aj_m.py`, `experiment_08aj_ab.py`, `experiment_08aj_ab_audit.py`, `experiment_08aj_ad.py`, `experiment_08aj_ad_audit.py`, and their other pre-existing dependencies. Do not overwrite any source or past evidence. Copy only the four AE files into your `rbyrct-3d-05a` folder.

## Windows PowerShell — 32³, 16-epoch integration test

```powershell
python -m pytest test_experiment_08aj_ae.py -q

$aeArgs = @(
  '--output-dir', 'results\experiment08aj_ae\engineering_32_first',
  '--aa-dir', 'results\experiment08aj_aa\disabled_path_first',
  '--m-dir', 'results\experiment08aj_m\contract_first',
  '--ab-dir', 'results\experiment08aj_ab\engineering_32_first'
)

python experiment_08aj_ae.py --mode init @aeArgs
python experiment_08aj_ae.py --mode check @aeArgs

# The initial 32³ AB evidence currently contains information_diag__same.
python experiment_08aj_ae.py --mode dispatch @aeArgs --policy information_diag --model same

# Simulate an interrupted engineering MART job after 257 rows.
python experiment_08aj_ae.py --mode run @aeArgs --policy information_diag --model same --stop-after-rows 257
python experiment_08aj_ae.py --mode check @aeArgs

# Continue from the immutable AD checkpoint; do not re-init.
python experiment_08aj_ae.py --mode run @aeArgs --policy information_diag --model same

# Independent numerical replay and RMSE verification.
python experiment_08aj_ae_audit.py @aeArgs --require-complete
```

Expected verdicts, in order:

- `AE_ENGINEERING_DISPATCH_PREPARED`
- `AE_SOURCE_AND_ENGINEERING_GATE_MATCH`
- `AE_ENGINEERING_TEMPLATE_DISPATCHED`
- `AE_ENGINEERING_EXECUTION_PAUSED` (257 rows)
- `AE_SOURCE_AND_ENGINEERING_GATE_MATCH`
- `AE_ENGINEERING_EXECUTION_PASS` (32,768 rows)
- `AE_INDEPENDENT_ENGINEERING_DISPATCH_AUDIT_PASS` with `audited_completed_engineering_jobs: 1`, zero errors, `production_execution_allowed: false`

The independent audit replays all 32,768 MART row updates of the completed engineering reconstruction and compares RMSE against the saved AB engineering reference. It can be computationally intensive. The earlier AB evidence is read-only; AD states and checkpoint chain live under AE's new directory.

## Repeat / corruption behavior

- Repeating `init` refuses to overwrite a directory.
- `check` recomputes AA and AB fingerprints and refuses changed AE source, altered AA roster, or changed AB input contract.
- `dispatch` refuses unapproved policies/models, requires an independently audited AB engineering reference, and binds immutable AD numerical input hashes.
- `run` re-verifies source and the existing checkpoint chain. The executor never deletes or repairs broken/orphaned evidence.
- `audit --require-complete` fails if **any dispatched job** remains incomplete. Without the flag, it reports pending checkpoints separately from completed audited jobs.
- No API accepts a prospective object ID, cohort seed, production roster ID, unlock, or source freeze.

## Still blocking production

AE is engineering-template orchestration, **not a production job executor**. It does not load cohort truth, generate fresh per-object measurements, or iterate the 480 object-specific jobs. AD has a monitored in-loop wall-time limit, not a hard OS termination guard; hard memory limits and a production failure/resource policy are not certified. Scientific independence, fixed-benchmark interpretation, statistical plan, resource ceilings, source freeze, and scientific sign-off remain open. No confirmatory outcomes have been produced.

Local developer tests exercised the dispatcher with isolated dependency fixtures and passed 11/11. A real end-to-end Windows numerical integration and audit against AA/AB evidence must be completed before claiming 08AJ-AE's engineering milestone is verified.
