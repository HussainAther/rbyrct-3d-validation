# 08AJ-AF — Fresh-Input Engineering Catalogue and Independent Numerical Audit

## Scope

This package deliberately creates **one fresh, fixed, noncohort engineering phantom** with seed `971337`, family `irregular_inclusions`, and acquisition seed `971349`. The seed is checked against the disabled AA roster. Unlike AE, it does not rely on previously acquired AB arrays.

For each forward model (`same`, `independent`), one full, deterministic noise catalogue is saved, independently regenerated and shared among all five policies. The saved numerical jobs use the existing project functions: `system_matrix`, `full_resolution_pair`, `model_measurements`, `fair_orders`, and `checked_mart`. The auditor regenerates the object and catalogues, verifies acquisition-order and CSR identities, and independently replays the MART reconstruction and RMSE.

**Limits:** This is not a production executor, not an experimental comparison, not AD checkpoint integration, not proof of statistical superiority, and not authorization to execute any of the 24 reserved synthetic objects. Jobs are committed atomically after calculation; a crashed incomplete staging directory is preserved and intentionally blocks further execution pending investigation. No enforced time or memory cap is added by AF. Production execution remains disabled.

## Files to copy into project root

- `experiment_08aj_af.py`
- `experiment_08aj_af_audit.py`
- `test_experiment_08aj_af.py`

Do not overwrite previous AA–AE source/evidence files. Run commands from your existing `(rbyrct-3d)` Python environment in `C:\Users\shuss\Downloads\rbyrct-3d-05a`.

## Windows commands

```powershell
python -m pytest test_experiment_08aj_af.py -q

$afArgs = @(
    "--output-dir", "results\experiment08aj_af\fresh_engineering_8_first",
    "--aa-dir", "results\experiment08aj_aa\disabled_path_first",
    "--m-dir", "results\experiment08aj_m\contract_first"
)

python experiment_08aj_af.py --mode init @afArgs --n 8
python experiment_08aj_af.py --mode check @afArgs

python experiment_08aj_af.py --mode catalogue @afArgs --model same
python experiment_08aj_af.py --mode catalogue @afArgs --model independent

python experiment_08aj_af.py --mode run @afArgs --policy information_diag --model same
python experiment_08aj_af.py --mode run @afArgs --policy uniform_multiscale --model same

python experiment_08aj_af_audit.py @afArgs
```

Expected initial audit: `AF_INDEPENDENT_FRESH_INPUT_AUDIT_PASS` with two engineering jobs, and two catalogues.

### Optional: full 8³ ten-policy/model verification

After the two runs and initial audit, execute the remaining eight jobs using this PowerShell loop:

```powershell
$policies = @("information_diag", "uniform_multiscale", "coverage", "stratified_random_04h", "complete_view")
$models = @("same", "independent")
foreach ($model in $models) {
    foreach ($policy in $policies) {
        python experiment_08aj_af.py --mode run @afArgs --policy $policy --model $model
        if ($LASTEXITCODE -ne 0) { throw "AF job failed: $policy / $model" }
    }
}
python experiment_08aj_af_audit.py @afArgs --require-complete
```

Expected final audit: `AF_INDEPENDENT_FRESH_INPUT_AUDIT_PASS`, ten jobs and two shared catalogues. Completed jobs are audited and reused, never overwritten.

### Optional: 32³ engineering case (separate folder)

Create a new `$af32Args` with `--output-dir results\experiment08aj_af\fresh_engineering_32_first` and otherwise the same AA/M paths; then run:

```powershell
python experiment_08aj_af.py --mode init @af32Args --n 32
python experiment_08aj_af.py --mode catalogue @af32Args --model same
python experiment_08aj_af.py --mode run @af32Args --policy information_diag --model same
python experiment_08aj_af_audit.py @af32Args
```

The independent 32³ full-resolution projection and reconstruction may be computationally expensive. Do not run a full ten-job 32³ suite until the initial case passes. Avoid claiming prospective numerical certification from any of these engineering results.

## Local verification performed during package preparation

The AF test module passed **10/10 tests with mocked small numerical inputs**, exercising data generation contracts, noise sharing, independent replay, source lock, reuse, held-out seed exclusion, and corruption rejection. Production numerical functions are loaded from your existing Windows project when running outside the local test harness. Thus **full physical 8³/32³ verification awaits Windows execution**.

## Safeguards

- Fixed seed `971337`, different from AB's seed and disjoint from AA's object-seed roster (enforced in code).
- Fresh noise realization per forward-model group, identically reused by all five policies.
- Common warm-ray prefix for the four individual-ray policies; complete-view exempt.
- No production ID, editable seed CLI, unlock, or freeze path.
- Append-only committed job files; incomplete staging preserved without automatic retry.
- Source and AA manifest SHA-256 checks; independent array and truth regeneration.
- `production_execution_allowed=false`, `scientific_signoff=false`, `resource_policy_approved=false`, `frozen=false`, `no_confirmatory_outcomes=true`.
