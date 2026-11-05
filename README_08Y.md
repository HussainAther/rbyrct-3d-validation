# RBYRCT-08Y — Voxel-level Information and Sensitivity Diagnostics

## Objective

Retrospectively analyze the **existing** 08U, 08W, and 08X fixed ray orders at 12³, 144/288 rays. This study tests whether the diagonal information policy produces distinctive spatial distributions of weighted ray sensitivity, per-voxel squared ray coefficients, and a diagonal linear-Gaussian information surrogate. It does **not** test reconstruction performance anew or establish a causal mechanism. No selection policy or parameter is tuned.

## Source archives

Use the archived `reconstruction_third` directory from 08U, and `reconstruction_first` from 08W and 08X. The script verifies each source archive's `sha256.json`, all fixed ray histories and reconstruction prefix fingerprints (36 + 64 + 80 = **180** archived reconstruction rows). It does not modify archived data.

Check the actual paths first. If 08W/08X have not yet been moved into `..\rbyrct-results`, you can point the command at their still-local `results/experiment08w/reconstruction_first` and `results/experiment08x/reconstruction_first` instead. Avoid moving an archive while the diagnostic runs.

## Install

Extract exactly these three files into the root of `rbyrct-3d-05a` (not inside a second folder, which can create pytest module collisions):

- `experiment_08y.py`
- `test_experiment_08y.py`
- `README_08Y.md`

## Tests

```powershell
python -m pytest test_experiment_08y.py -q
python -m pytest -q
git diff --check
```

The 15 focused tests include a complete manufactured-source-archive smoke run, simulated archive tampering and prefix-hash failures, and direct tests of the diagonal precision and spatial metrics. The actual Windows archive integration remains to be run.

## Run

```powershell
python experiment_08y.py `
    --08u-dir ..\rbyrct-results\experiment08u\reconstruction_third `
    --08w-dir ..\rbyrct-results\experiment08w\reconstruction_first `
    --08x-dir ..\rbyrct-results\experiment08x\reconstruction_first `
    --output-dir results/experiment08y/information_geometry_first
```

If an output folder already exists, the script refuses to overwrite it. Use a new output name rather than deleting previous results.

## Read results

```powershell
$dir = 'results/experiment08y/information_geometry_first'
Get-Content "$dir/run_status.json"
Import-Csv "$dir/voxel_information_by_policy_checkpoint.csv" |
    Select-Object study,policy,acquired,diagonal_variance_mean,relative_variance_reduction_mean,weighted_sensitivity_gini,central_cube_relative_variance_reduction_mean,outer_region_relative_variance_reduction_mean,mean_global_gain_vs_coverage |
    Format-Table -AutoSize
Import-Csv "$dir/diagonal_vs_alternatives.csv" |
    Format-Table -AutoSize
```

The NPZ file `voxel_surrogate_fields.npz` contains 3D arrays (`12 x 12 x 12`) for visits, weighted sensitivity, squared sensitivity, diagonal precision, diagonal variance, and relative variance reduction, keyed by e.g. `08X__information_diag__288__variance`.

## Definitions / claim boundaries

For acquired rows H and system matrix A:

- voxel visit count: `sum_{i in H} 1[A_ij != 0]`;
- weighted sensitivity: `sum_{i in H} |A_ij|`;
- squared sensitivity: `sum_{i in H} A_ij^2`;
- diagonal precision surrogate: `p_j = prior_variance^-1 + observation_variance^-1 sum_{i in H} A_ij^2`;
- diagonal variance surrogate: `D_j = 1/p_j`;
- relative surrogate variance reduction: `1 - D_j/prior_variance`;
- central cube: the geometric central half-side cube, **not** the defect mask.

The Gaussian hyperparameters are imported unchanged from the existing 08U implementation (not fitted against the outcomes). This is the inverse **diagonal precision**, not the true posterior covariance diagonal or a MART uncertainty estimate. It cannot be interpreted as a physical dose, a measured Fisher information matrix, or proof that a policy caused reconstruction gains. The sampled policy orders are geometry-only and fixed across phantoms within each study; geometry rows are not independent replications. Outcomes are displayed separately by study, never pooled across different seed/phantom cohorts.

## Expected output counts

- 24 policy/checkpoint geometric rows (6 08U, 8 08W, 10 08X).
- 18 diagonal-versus-alternative rows.
- 144 saved voxel field arrays (24 times 6).
- 180 archived reconstruction rows checked.

The frozen 08M archive and 08Q replay are not modified.

## Preserve

After successful run, inspect results before commit and archive:

```powershell
git add experiment_08y.py test_experiment_08y.py README_08Y.md
git diff --cached --check
git commit -m "Add retrospective voxel information and sensitivity diagnostics"
Move-Item 'results/experiment08y' '..\rbyrct-results\'
git restore -- ':(glob)__pycache__/*.pyc'
git status --short
```
