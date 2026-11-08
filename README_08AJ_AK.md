# RBYRCT 08AJ-AK — Locked four-job engineering-shadow dispatch

## Purpose and honest scope

Build on independently audited AA (480 disabled job specifications), AF (fresh noncohort engineering measurements), and AH (atomic row checkpointing and supervised MART). AK is a **four-job engineering shadow**, NOT an object-specific 480-job production executor. It reuses the same fixed AF engineering object, its two model-specific measurement catalogues, and the independently audited full-resolution AF reconstructions. The four jobs are information_diag and uniform_multiscale crossed with same and independent models. No prospective object/seed or cohort evaluation is exposed.

Each AK dispatch creates its own AH checkpoint directory. A second execution of the same dispatched job can resume from the last committed AH checkpoint. Previously completed AF inputs and outputs remain unchanged. The independent AK auditor delegates numerical checks to the existing independent AH audit and requires four completed jobs when `--require-complete` is set.

**Still blocked:** source-freeze approval, resource-policy approval, scientific review, production job-specific inputs and 480-job certification. All production and unlock CLI modes refuse execution.

## Install

Copy `experiment_08aj_ak.py`, `experiment_08aj_ak_audit.py`, and `test_experiment_08aj_ak.py` into your current `rbyrct-3d-05a` directory. Do not overwrite previous AA/AF/AH evidence.

## Windows commands

```powershell
python -m pytest test_experiment_08aj_ak.py -q

$akArgs = @(
    "--output-dir", "results\experiment08aj_ak\shadow_32_first",
    "--af-dir", "results\experiment08aj_af\fresh_engineering_32_first",
    "--aa-dir", "results\experiment08aj_aa\disabled_path_first",
    "--m-dir", "results\experiment08aj_m\contract_first"
)

python experiment_08aj_ak.py --mode prepare @akArgs
python experiment_08aj_ak.py --mode check @akArgs

python experiment_08aj_ak.py --mode dispatch @akArgs --policy information_diag --model same
python experiment_08aj_ak.py --mode run @akArgs --policy information_diag --model same --stop-after-rows 256 --wall-seconds 600 --max-mib 8192
python experiment_08aj_ak.py --mode check @akArgs
python experiment_08aj_ak.py --mode run @akArgs --policy information_diag --model same --wall-seconds 600 --max-mib 8192
python experiment_08aj_ak_audit.py @akArgs
```

Expected outputs: `AK_LOCKED_SHADOW_ROSTER_PREPARED`, `AK_LOCKED_SHADOW_SOURCES_MATCH`, `AK_ENGINEERING_JOB_DISPATCHED`, `AK_ENGINEERING_JOB_PAUSED`, then `AK_ENGINEERING_JOB_PASS` and partial `AK_INDEPENDENT_MULTI_JOB_ENGINEERING_AUDIT_PASS` (one job audited).

After verifying the first job, exercise the remaining three without overwriting the first:

```powershell
foreach ($model in @("same", "independent")) {
    foreach ($policy in @("information_diag", "uniform_multiscale")) {
        python experiment_08aj_ak.py --mode dispatch @akArgs --policy $policy --model $model
        if ($LASTEXITCODE -ne 0) { throw "AK dispatch failed: $policy / $model" }
        python experiment_08aj_ak.py --mode run @akArgs --policy $policy --model $model --wall-seconds 600 --max-mib 8192
        if ($LASTEXITCODE -ne 0) { throw "AK run failed: $policy / $model" }
    }
}
python experiment_08aj_ak_audit.py @akArgs --require-complete
```

Final target: `AK_INDEPENDENT_MULTI_JOB_ENGINEERING_AUDIT_PASS`, 4 audited completed engineering jobs, zero numerical/RMSE discrepancies. Inspect any `AK_ENGINEERING_JOB_STOPPED` and preserve its checkpoints; do not claim completion. `AK_ENGINEERING_JOB_PAUSED` is an intentional partial result when you specify `--stop-after-rows`.

## Test evidence scope

The 12 local tests use controlled mocks for numerical execution; they exercise plan/dispatch integrity, duplicate safety, tampering rejection, execution lock, pause handling, and incomplete audit detection. Real four-job numerical execution and independent replay require Windows tests using actual AF evidence.

## Important limitations

- Source-lock semantics are inherited from AA/AF/AH checks, and dispatch receipts are immutable; this is not a formal final source freeze.
- Revalidation can be computationally costly because AF and AH independent evidence checks may replay reconstructions.
- The same fixed engineering phantom is reused across both forward-model groups. **Do not present these as distinct prospective objects or independent study replicates.**
- AH supervision enforces configured wall-clock and memory controls per worker; those values remain unapproved for production.
- No production numerical jobs can be initiated, and no confirmatory outcomes are generated.
