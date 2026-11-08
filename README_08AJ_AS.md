# RBYRCT-08AJ-AS: engineering-only input contract qualification

This stage validates the identity and provenance of an **already prepared, unexecuted** 08AJ-AR engineering job. It does **not** create a group catalogue, dispatch a job, reconstruct a volume, or load a prospective phantom. It is deliberately restricted to AR's fixed noncohort allowlist.

Copy the three Python files into the project root. Do not overwrite an existing AS implementation without reviewing its changes.

## Tests (PowerShell)

```powershell
cd C:\Users\shuss\Downloads\rbyrct-3d-05a
python -m pytest test_experiment_08aj_as.py -v
if ($LASTEXITCODE -ne 0) { throw "AS focused tests failed" }

$tests = @(git ls-files -- 'test_experiment_08aj_*.py')
$tests += 'test_experiment_08aj_as.py'
$tests = @($tests | Select-Object -Unique)
python -m pytest @tests -q
if ($LASTEXITCODE -ne 0) { throw "08AJ regression failed" }
```

The focused tests use the existing AR/AN **stubbed 8-cubed fixture**. They do not establish 32-cubed real numerical production qualification. No change to the production or scientific gating is made. If the baseline still contains 379 tests, these twelve tests bring the expected collection to **391 tests**; verify the actual collected number and do not assume a pass.

## Optional manual AS validation using an existing AR fixture

Only use an already **prepared but unexecuted** noncohort AR job (both its group catalogue and job `source.json`/`order.npy` must exist). Replace paths below with your actual engineering-only fixture locations; these are illustrative placeholders.

```powershell
python experiment_08aj_as.py --mode prepare `
    --output-dir results\experiment08aj_as\first_engineering_only `
    --ar-dir <existing_AR_fixture_root> `
    --aa-dir <existing_AA_contract_root> `
    --m-dir <existing_M_contract_root> `
    --job-id engineering_alpha__seed_a__same__information_diag

python experiment_08aj_as_audit.py `
    --output-dir results\experiment08aj_as\first_engineering_only `
    --ar-dir <existing_AR_fixture_root> `
    --aa-dir <existing_AA_contract_root> `
    --m-dir <existing_M_contract_root>
```

AS binds the AR manifest, AN plan, group receipt, measurement arrays, job source and order files to an AS receipt and checks current source and environment fingerprints. Checkpoints and final reconstruction must be absent for this **pre-execution** validation. The AS auditor rehashes all named files and revalidates via AN's input regeneration routines. AS's auditor is **not** an independent MART numerical replay; continue to use the AN/AR auditors for finished engineering jobs.

**All five AQ approval gates remain BLOCKED.** `production_execution_allowed=false`, `frozen=false`, and no confirmatory outcomes were produced.
