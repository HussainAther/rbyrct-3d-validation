# RBYRCT-08AJ-AN — Two Engineering Objects × Two Acquisition Seeds × Two Models × Five Policies

## Purpose and scope

Extends 08AJ-AL's independently audited engineering-only object-isolation and checkpointed MART execution to a production-shaped **40-job engineering matrix**:

- Fixed NONCOHORT objects: `engineering_alpha` (seed `972101`, localized defects), `engineering_beta` (seed `972103`, smooth heterogeneity).
- Fixed engineering acquisition seeds: `seed_a=972119`, `seed_b=972121`. **Not** the prospective seeds `940411` and `940829`.
- Forward models: `same`, `independent`.
- All five policies: `information_diag`, `uniform_multiscale`, `coverage`, `stratified_random_04h`, `complete_view`.
- **Eight** source-locked object/acquisition/model catalogues. Each catalogue is shared across its five policies, so any policy acquiring the same ray reads exactly the same noise realization. Noise seeds are deterministic SHA-256 derived per catalogue.
- For the first four individual-ray policies, the common warm start is eight rays at n=8 and 64 rays at n=32. The `complete_view` policy remains exempt and uses two complete detector views.
- `n=8`: 128 rays, two epochs. `n=32`: 2048 rays, 16 epochs, relaxation 0.25.
- Each engineering job owns a separate immutable source receipt, atomic row-level checkpoint chain, and final reconstruction/RMSE receipt. Supervisor enforces a process wall-time deadline and invokes the existing AH OS memory guard.

**This is NOT the 24-object prospective cohort.** The source checks the disabled AA/M production contract and ensures that all fixed engineering object, acquisition, and noise seeds are disjoint from the prospective roster. The code rejects `production-run`, `unlock`, `freeze`, unknown objects and arbitrary seeds. It cannot enable confirmatory execution.

## Files to extract alongside your existing project files

- `experiment_08aj_an.py`
- `experiment_08aj_an_audit.py`
- `test_experiment_08aj_an.py`
- `README_08AJ_AN.md`

Requires the prior existing scripts and dependencies (including AA, AF, AH, AD, 08AJ-E/G and the 08AJ-K independent auditor), and `numpy`, `scipy`, `psutil`, `pytest`.

## Windows PowerShell: 8³ rehearsal

Run from the project's `(rbyrct-3d)` environment. **Never overwrite a prior evidence directory**.

```powershell
python -m pytest test_experiment_08aj_an.py -q

$anArgs = @(
    "--output-dir", "results\experiment08aj_an\engineering_8_first",
    "--aa-dir", "results\experiment08aj_aa\disabled_path_first",
    "--m-dir", "results\experiment08aj_m\contract_first"
)

python experiment_08aj_an.py --mode init @anArgs --n 8

$anObjects = @("engineering_alpha", "engineering_beta")
$anAcquisitions = @("seed_a", "seed_b")
$anModels = @("same", "independent")
$anPolicies = @("information_diag", "uniform_multiscale", "coverage", "stratified_random_04h", "complete_view")

foreach ($obj in $anObjects) {
    foreach ($acq in $anAcquisitions) {
        foreach ($model in $anModels) {
            python experiment_08aj_an.py --mode catalogue @anArgs `
                --object $obj --acquisition $acq --model $model
            if ($LASTEXITCODE -ne 0) { throw "AN catalogue failure: $obj/$acq/$model" }
        }
    }
}

python experiment_08aj_an.py --mode check @anArgs
```

### First controlled, interrupted job

```powershell
python experiment_08aj_an.py --mode dispatch @anArgs `
    --object engineering_alpha --acquisition seed_a --model same --policy information_diag

python experiment_08aj_an.py --mode run @anArgs `
    --object engineering_alpha --acquisition seed_a --model same --policy information_diag `
    --stop-after-rows 32 --wall-seconds 600 --max-mib 8192

python experiment_08aj_an.py --mode check @anArgs

python experiment_08aj_an.py --mode run @anArgs `
    --object engineering_alpha --acquisition seed_a --model same --policy information_diag `
    --wall-seconds 600 --max-mib 8192

python experiment_08aj_an_audit.py @anArgs
```

Expected: `AN_ENGINEERING_PAUSED`, `AN_ENGINEERING_JOB_PASS`, and `AN_INDEPENDENT_MULTI_SEED_AUDIT_PASS` with one completed job audited. **Do not** use `--require-complete` until all 40 jobs have completed.

### Complete the 40-job engineering set

```powershell
foreach ($obj in $anObjects) {
    foreach ($acq in $anAcquisitions) {
        foreach ($model in $anModels) {
            foreach ($policy in $anPolicies) {
                python experiment_08aj_an.py --mode dispatch @anArgs `
                    --object $obj --acquisition $acq --model $model --policy $policy
                if ($LASTEXITCODE -ne 0) { throw "AN dispatch failure: $obj/$acq/$model/$policy" }
                python experiment_08aj_an.py --mode run @anArgs `
                    --object $obj --acquisition $acq --model $model --policy $policy `
                    --wall-seconds 600 --max-mib 8192
                if ($LASTEXITCODE -ne 0) { throw "AN job failure: $obj/$acq/$model/$policy" }
            }
        }
    }
}

python experiment_08aj_an.py --mode check @anArgs
python experiment_08aj_an_audit.py @anArgs --require-complete
```

Expected final audit: `AN_INDEPENDENT_MULTI_SEED_AUDIT_PASS`, `engineering_objects=2`, `acquisition_seeds=2`, `shared_groups_audited=8`, `engineering_jobs_audited=40`, `errors=[]`. The auditor independently replays all completed MART reconstructions, recomputes RMSE, checks all object/seed/model evidence receipts, compares group catalogues and noise seeds, enforces common individual-ray prefixes, and checks that the complete-view arm comprises two full detector views.

## Subsequent 32³ qualification

**Only after the 8³ audit passes**, use a fresh root `results\experiment08aj_an\engineering_32_first` and initialize `--n 32`. Begin with two acquisition seeds of one object, each policy under both forward models (20 jobs) and audit. Only then consider all 40 at 32³. Real full-resolution runs may consume much more time and storage; never force a re-run or substitute failure/imputation based on outcome values. The user must explicitly approve moving to the next qualification step.

## Interpretation and restrictions

Local bundled tests use noncohort **stubbed numerical fixtures** to exercise control logic. They do **not** establish Windows numerical compatibility or production qualification. Any engineering RMSE observed is a software fixture observation, not prospective scientific evidence. The 480-job production executor remains disabled, `production_480_job_certified=false`, `resource_policy_approved=false`, `scientific_signoff=false`, and the protocol remains unfrozen. Retain all evidence directories; investigate integrity failures before retrying.
