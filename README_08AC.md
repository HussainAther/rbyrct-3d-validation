# RBYRCT-08AC — Frozen fresh 32³ spatial-sensitivity study

**Status:** Implementation package. No new 08AC reconstruction outcomes have been observed or claimed. This study is designed to test whether the 08Z spatial-sensitivity intervention generalizes to new synthetic 32³ objects. No frozen 08M files are changed.

## Frozen design and primary comparison

- **32³** voxel grid, 4 projection angles and the repository's original tilt geometry; 2× mismatch forward grid.
- **Six NEW development/validation synthetic phantoms**: seeds 920201–920206 (none from 08M/08Z).
- **Two acquisition seeds** 920411 and 920829; each ray order is geometry-only and shared across objects, within its seed.
- **Two measurement conditions** per object/acquisition seed: matched reconstruction model and independently sampled finer-grid projector.
- **Policies**: geometric coverage, 08K diagonal information, 08U full-covariance Gaussian A-optimal, and **08Z full covariance + 25% spatial novelty** (unchanged formula/weight; no tuning).
- **Ray checkpoints:** 512 (secondary) and **1024 (primary)**. These are not 08M's primary 2048-ray budget. The 08AC primary 1024-ray comparison must not be portrayed as a confirmation of the 08M 2048-ray effect.
- **16 MART epochs**, relaxation 0.25 and measurement noise fraction 0.005, matching the prior setup.
- **192 reconstruction records** = 6 independent objects × 2 acquisition seeds × 2 models × 4 policies × 2 checkpoints.
- **Primary endpoint:** mean whole-volume fractional RMSE gain of spatially balanced full covariance **relative to unmodified full covariance**, averaged over the four paired conditions *within each independent object* and then across **six objects**. Object-level win count is descriptive. No post-hoc winner selection or significance claim.
- Secondary: whole-volume gains versus coverage and diagonal information, defect and nondefect RMSE gains, checkpoint 512, sensitivity Gini, model- and acquisition-seed-level outcomes.

The 08AC spatial selector **still uses exact Gaussian A-optimal scoring**. It has NOT been replaced with a cheaper diagonal approximation. Its computational burden is potentially substantial at 32³ and 1024 acquired rays. Do not change the 1024-ray protocol after inspecting results to improve the apparent effect; document resource problems as feasibility findings instead.

## Windows PowerShell steps

Extract `experiment_08ac.py`, `test_experiment_08ac.py`, `README_08AC.md` directly into the repository root `C:\Users\shuss\Downloads\rbyrct-3d-05a` (do not extract into a nested directory).

### Step 1 — validate the implementation

```powershell
python -m pytest test_experiment_08ac.py -q
python -m pytest -q
python -m py_compile experiment_08ac.py
git diff --check
```

If any test fails, **stop and share the output**. The local test is not a full 32³ integration run.

### Step 2 — create a source-and-protocol lock

```powershell
python experiment_08ac.py --freeze-protocol --lock-path protocol_08ac_frozen.json
Get-Content protocol_08ac_frozen.json

git add experiment_08ac.py test_experiment_08ac.py README_08AC.md protocol_08ac_frozen.json
git diff --cached --check
git diff --cached --stat
git commit -m "Freeze 08AC fresh 32-cubed spatial-sensitivity study"
```

The lock SHA-256 fingerprints the 08AC driver, 08Z selector, exact and diagonal scoring modules, geometry, measurement/model and MART dependencies. Once frozen, changing these source bytes causes the study to refuse execution; do not regenerate the lock to conceal changes.

### Step 3 — geometry-only full-budget preflight

```powershell
python experiment_08ac.py --preflight `
    --lock-path protocol_08ac_frozen.json `
    --output-dir results/experiment08ac/engineering_first

Get-Content results/experiment08ac/engineering_first/preflight.json
Import-Csv results/experiment08ac/engineering_first/geometry_preflight.csv |
    Format-Table -AutoSize
```

The preflight computes all four **1024-ray acquisition orders for both seeds**, stores their SHA-256 fingerprints and measures sensitivity Gini at 512 and 1024 rays. It uses no object truth, masks, detector measurements or reconstructions. **Gini reduction is reported, not an acceptance criterion:** the validation cannot discard unfavorable geometric outcomes. The preflight may be much slower than 12³ work owing to full-covariance scoring. If this fails or resource use is excessive, preserve the directory and report the error without quietly shrinking budgets.

### Step 4 — locked reconstruction study

Only if preflight reports `complete: true`:

```powershell
python experiment_08ac.py --run `
    --lock-path protocol_08ac_frozen.json `
    --preflight-dir results/experiment08ac/engineering_first `
    --output-dir results/experiment08ac/reconstruction_first
```

The run reads **the preflight-approved ray orders** rather than recomputing or altering acquisition. It fails on changed order files, hash mismatches, wrong prefix lengths, and any source/protocol drift. It refuses to overwrite existing output.

### Step 5 — assess every outcome

```powershell
$dir = "results/experiment08ac/reconstruction_first"
Get-Content "$dir/run_status.json"
Import-Csv "$dir/aggregate_summary.csv" | Format-Table -AutoSize
Import-Csv "$dir/primary_object_comparison.csv" | Format-Table -AutoSize
Import-Csv "$dir/object_level_summary.csv" |
    Where-Object {$_.acquired -eq '1024'} |
    Format-Table -AutoSize
```

For **successful** execution, `run_status.json` should indicate 192/192 completed reconstructions. Independently audit saved-output arithmetic and eventually replay reconstructed voxels before manuscript claims. **Do not claim clinical dose savings, detector-feedback adaptivity, general superiority, or external replication.**

### Archive later, after verifying results

```powershell
# Check that the destination does not already exist.
Test-Path "..\rbyrct-results\experiment08ac"
# Only if False:
Move-Item "results/experiment08ac" "..\rbyrct-results\"
git restore -- ":(glob)__pycache__/*.pyc"
git status --short
```

## Important interpretive boundaries

At 32³, exact Gaussian covariance is an **assumed Bayesian linear-Gaussian** score, not a MART posterior. Same/independent measurement models and multiple acquisition seeds are **paired repeats**, not 24 independent objects. The primary independent sample size is **six synthetic objects**. A nonpositive study result must remain in the record. Compared with 08M, this differs in object seeds, acquisition seeds, policies, and primary budget; **do not combine results as if they were a single frozen trial**.
