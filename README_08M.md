# RBYRCT-08M — prospectively frozen independent 32³ synthetic validation

**Separate freeze and run phases.** This is NOT a pilot and not a parameter search. Do not execute the validation until the protocol lock and implementation have been reviewed and committed. Preserve negative results without changing seeds, parameters, or analysis endpoints.

## Scope and hypothesis

- Independent *objects*: 8 previously unused 32³ localized-defect synthetic phantoms, object seeds fixed in `experiment_08m.py`.
- Acquisition seeds: 2, forward-model conditions: `same`, `independent`.
- Four unchanged selectors: `coverage`, `gradient`, `incremental_25`, and `information_diag` imported **without modification from 08K**.
- Rays: 1,024, 2,048, 4,096. Primary is at 2,048; secondary other budgets, model stratification, and defect-region gain.
- MART: 16 final epochs, relaxation 0.25; provisional feedback 2 epochs; pool 16, batch 32, warm 64.
- Primary outcome: **arithmetic mean across eight phantom-level paired fractional whole-volume RMSE gains** for information versus coverage at 2,048 rays. Each phantom's value FIRST averages its 2 model conditions × 2 acquisition-seed conditions. Do not inflate n to 32 or 64 by counting reuses as independent objects.
- Object-level win count and per-object gains are descriptive. No post-hoc selection of the best checkpoint or variation of the parameter constants.
- The information policy is **geometry-only, not detector-measurement-adaptive**; the results cannot establish clinical utility, dose reduction, or experimental physical CT performance.

## Extract

Unzip these three files into your existing `C:\Users\shuss\Downloads\rbyrct-3d-05a` **repository root**, not into an extra subfolder. This depends on existing installed source modules through 08M0. There are no synthetic-accuracy results in this package.

## Phase A: verify and freeze (BEFORE examining 08M outcomes)

```powershell
python -m pytest test_experiment_08m.py -q
python -m pytest -q
git diff --check
python experiment_08m.py --freeze-protocol --protocol-lock protocol_08m_frozen.json
Get-Content protocol_08m_frozen.json
```

Review all prespecified settings, especially the 8 object seeds, 2 acquisition seeds, source hashes, and primary endpoint. Confirm no overlap with previous independent experimental objects. Review policy constants. **Do not run if any concern needs changing; revise and refreeze before any results are observed.**

Then COMMIT the code and lock in the same checkpoint, BEFORE running:

```powershell
git add experiment_08m.py test_experiment_08m.py README_08M.md protocol_08m_frozen.json
git diff --cached --check
git commit -m "Freeze independent 08M information acquisition validation"
git status --short
```

The `--freeze-protocol` command refuses to overwrite an existing lock. Any changed module hash or protocol field after freeze causes the run to fail closed. Do not work around this by silently rewriting the lock after viewing outcomes.

## Phase B: run ONCE, after frozen commit

```powershell
python experiment_08m.py --run `
  --protocol-lock protocol_08m_frozen.json `
  --output-dir results/experiment08m/frozen_first
```

**Expected:** `complete: true`, `completed_histories: 128`, `completed_reconstructions: 384`. The command refuses an existing nonempty output directory. The information ordering is geometry-only. Its ordering can be identical across different objects and forward models; the acquisition-seed schedules may differ. Do not treat identical ray orders as independent schedules.

Inspect both favorable and unfavorable outcomes:

```powershell
$dir = 'results/experiment08m/frozen_first'
Get-Content "$dir/run_status.json"
Get-Content "$dir/primary_endpoint.json"
Import-Csv "$dir/aggregate_summary.csv" | Format-Table size,acquired,policy,n_objects,mean_global_gain,mean_defect_gain,object_global_wins,object_defect_wins
Import-Csv "$dir/object_level_summary.csv" | Where-Object { $_.acquired -eq '2048' -and $_.policy -eq 'information_diag' } | Format-Table
```

Results contain `protocol.json`, `environment.json`, `object_manifest.csv`, `acquisition_orders.csv`, `guard_batch_audit.csv`, `prefix_reconstructions.csv`, `object_level_summary.csv`, `aggregate_summary.csv`, `primary_endpoint.json`, `run_status.json`, and `sha256.json`.

If interrupted, retain the partial directory unchanged; do not erase it to re-run the same experiment as though it were a first run. Report the interruption. Run the independent 08N output audit after the study, before claiming a validated numerical result.

Once results are inspected and preserved, archive without altering their contents:

```powershell
Move-Item 'results/experiment08m' '..\rbyrct-results\'
git restore -- ':(glob)__pycache__/*.pyc'
git status --short
```

## Limitations

This is independent **synthetic-object** validation of a frozen geometric acquisition rule under a fixed reconstruction program; it is not external dataset validation, not an independent replay of MART physics, not a clinical CT study, and does not estimate radiation dose. The primary sample size is **eight independent phantoms**; two seeds and two forward models are repeated paired conditions. Commit the lock first to preserve prospective credibility.
