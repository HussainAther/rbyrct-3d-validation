# RBYRCT-08AJ-AL — Multiple Noncohort Objects, Source Isolation, and Row Recovery

## Purpose and hard boundary

AL introduces **two distinct engineering objects** (`engineering_alpha`, `engineering_beta`), generated deterministically with object seeds `972101` and `972103`, both deliberately outside the AA prospective roster. It uses acquisition seed `972119` and model-specific noise seeds `972131` / `972137`. It includes two forward models (`same`, `independent`), two primary policies (`information_diag`, `uniform_multiscale`), four object/model groups, and **eight engineering jobs**. The 480-job prospective study is **not executed and cannot be unlocked** through AL.

Compared with AK, numerical measurements are freshly generated separately for the two engineering objects. Within each object/model group, the two acquisition policies share the same full noisy ray catalogue. The row-level MART worker creates separate, atomic, hash-linked checkpoints per object/model/policy job, with OS memory cap and parent wall-clock timeout inherited from AH's guard utilities.

**Scientific limitation:** These are related synthetic objects and do not validate a clinical or population inference. Running AL is engineering qualification, not scientific hypothesis testing. The two engineering objects must never be substituted for, or counted among, the prospective 24-object benchmark.

## Included files

- `experiment_08aj_al.py`: strict fixed-object roster, fresh catalogues, engineering dispatcher, supervised checkpoint worker.
- `experiment_08aj_al_audit.py`: independently regenerates each object/model catalogue, replays MART, checks per-object checkpoint/final identity, compares RMSE and group separation.
- `test_experiment_08aj_al.py`: 12 fast control tests. These were exercised locally with external numerical imports stubbed; **they are not an end-to-end Windows numerical verification**.
- This README.

Copy the four files into your existing `rbyrct-3d-05a` repository, alongside `experiment_08aj_aa.py`, `experiment_08aj_af.py`, `experiment_08aj_ah.py`, `experiment_08aj_ad.py`, and earlier numerical dependencies. Do not change the existing verified AA/AF/AH/AK evidence.

## A. Initial 8^3 functional verification

```powershell
python -m pytest test_experiment_08aj_al.py -q

$alArgs = @(
  "--output-dir", "results\experiment08aj_al\multi_object_8_first",
  "--aa-dir", "results\experiment08aj_aa\disabled_path_first",
  "--m-dir", "results\experiment08aj_m\contract_first"
)

python experiment_08aj_al.py --mode init @alArgs --n 8
```

Expected `AL_ENGINEERING_OBJECTS_PREPARED`. Create all four engineering object/model catalogues:

```powershell
$alObjects = @("engineering_alpha", "engineering_beta")
$alModels = @("same", "independent")
$alPolicies = @("information_diag", "uniform_multiscale")
foreach ($obj in $alObjects) {
  foreach ($model in $alModels) {
    python experiment_08aj_al.py --mode catalogue @alArgs --object $obj --model $model
    if ($LASTEXITCODE -ne 0) { throw "AL catalogue failed: $obj / $model" }
  }
}
```

Dispatch and run all eight engineering jobs. The dispatcher refuses any object or model outside these fixed names:

```powershell
foreach ($obj in $alObjects) {
  foreach ($model in $alModels) {
    foreach ($policy in $alPolicies) {
      python experiment_08aj_al.py --mode dispatch @alArgs --object $obj --model $model --policy $policy
      if ($LASTEXITCODE -ne 0) { throw "AL dispatch failed: $obj / $model / $policy" }
      python experiment_08aj_al.py --mode run @alArgs --object $obj --model $model --policy $policy --wall-seconds 600 --max-mib 8192
      if ($LASTEXITCODE -ne 0) { throw "AL numerical run failed: $obj / $model / $policy" }
    }
  }
}
```

Finally:

```powershell
python experiment_08aj_al.py --mode check @alArgs
python experiment_08aj_al_audit.py @alArgs --require-complete
```

Expected `AL_INDEPENDENT_MULTI_OBJECT_AUDIT_PASS`, `engineering_objects: 2`, `shared_groups_audited: 4`, `engineering_jobs_audited: 8`, zero errors and zero numerical replay difference.

## B. Optional 32^3 resume test (use new directory, do not overwrite 8^3)

```powershell
$al32Args = @(
  "--output-dir", "results\experiment08aj_al\multi_object_32_first",
  "--aa-dir", "results\experiment08aj_aa\disabled_path_first",
  "--m-dir", "results\experiment08aj_m\contract_first"
)
python experiment_08aj_al.py --mode init @al32Args --n 32
python experiment_08aj_al.py --mode catalogue @al32Args --object engineering_alpha --model same
python experiment_08aj_al.py --mode catalogue @al32Args --object engineering_beta --model same
python experiment_08aj_al.py --mode dispatch @al32Args --object engineering_alpha --model same --policy information_diag
python experiment_08aj_al.py --mode run @al32Args --object engineering_alpha --model same --policy information_diag --stop-after-rows 257 --wall-seconds 600 --max-mib 8192
python experiment_08aj_al.py --mode run @al32Args --object engineering_alpha --model same --policy information_diag --wall-seconds 600 --max-mib 8192
python experiment_08aj_al_audit.py @al32Args
```

The final 32^3 audit will cover one job and two regenerated groups; do **not** use `--require-complete` until all eight jobs and four groups are present. A later full 32^3 exercise should include both objects under both models.

## Evidence rules and limitations

- Each job has its own object/model/policy identity, source receipt, order, checkpoint chain, and final receipt. An object-specific checkpoint cannot be relabeled as another job.
- Each group re-generates exact deterministic clean/noisy measurements when audited; any changed object seed, group receipt, or measurement array causes a failure.
- A partial, uncommitted `.stage-*` directory is treated as an error; **do not delete it** before inspection. There is no automatic retry, unapproved imputation, or outcome-based early stopping.
- The worker installs AH's process memory cap before numerical computation. The parent enforces wall-clock timeout; success under a generous cap is not equivalent to all limit-violation cases being certified.
- An audit pass proves deterministic numerical reproducibility for the exercised engineering fixtures. It does not certify the full 480-job production runner.
- All outputs must retain `production_execution_allowed: false`, `production_480_job_certified: false`, and `no_confirmatory_outcomes: true`.
