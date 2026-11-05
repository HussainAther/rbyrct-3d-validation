# RBYRCT-08U — Full-Covariance versus Diagonal A-Optimal Sequential Acquisition

## Research question

Does selecting rays by full-covariance **linear-Gaussian** A-optimal trace reduction improve **MART reconstruction** compared with the established diagonal proxy? The exact Gaussian objective is not a posterior covariance for MART and is not guaranteed to improve MART error.

**Stage:** exploratory development; do not call the results independent confirmation. The frozen 08M archive and its replay are not modified.

## Experimental protocol

- 12³ synthetic 3D tomography; the unchanged 08K/06B geometry and phantom infrastructure.
- 3 fresh exploratory defect-phantom seeds: 880201, 880202, 880203 (distinct from earlier 08K and 08M seeds).
- Matched and independently generated measurement-model conditions; these are paired observations of the **same three** objects, not six independent objects.
- Policies: coverage, `information_diag` (08K), `information_full` (incremental-Cholesky full-covariance Gaussian A-optimal).
- Exactly 288 acquired rays, 24 common warm rays, batch 16, candidate pool 16, acquisition seed 880423.
- MART reconstruction at 144 and 288 rays, 16 epochs, relaxation 0.25. Same 08K synthetic-noise and forward-model settings.
- Report global, defect, and nondefect RMSE and object-balanced paired gains. The direct full-versus-diagonal comparison is reported in **RMSE units**, not Gaussian-score units.
- Expected: 3 objects × 2 forward-model conditions × 3 policies × 2 checkpoints = **36 records**. Six *distinct geometry-only acquisition orders* are NOT expected: ray ordering is identical across objects and forward models, and computed once for each policy.

## Critical algorithmic detail

The exact selector maintains a Cholesky factor of `sigma² I + tau² H H.T` and updates it after **each** selected ray. Scores are computed by the Woodbury expression for `C`, then `||C a||² / (sigma² + a.T C a)`. No dense `n_voxels × n_voxels` posterior is allocated. **This is exact for the assumed Gaussian model**, and still an approximation to any physical CT or nonlinear MART uncertainty model.

The exact and diagonal selectors share the same random candidate-pool generator and warm ray order. Their candidate pools need not stay identical once their selected histories diverge; the experiment compares full **sequential policies**, not matched counterfactual scores on a fixed candidate set.

## Windows PowerShell

Extract **only the three files** in this archive into the repository root. Avoid a nested ZIP-extraction directory, which creates duplicate pytest modules.

```powershell
python -m pytest test_experiment_08u.py -q
python -m pytest -q
git diff --check
```

### Phase A: no-phantom engineering preflight

```powershell
python experiment_08u.py --preflight `
    --output-dir results/experiment08u/engineering_first
```

Review `results/experiment08u/engineering_first/preflight.json`. The preflight produces complete 288-ray orderings, selection timings, deterministic repeat verification, and SHA-256 hashes, without any phantom or reconstructed volume. Full-covariance time is a relevant practical outcome; do not silently discard it if slow.

### Phase B: exploratory comparison (after preflight succeeds)

```powershell
python experiment_08u.py --run `
    --preflight-dir results/experiment08u/engineering_first `
    --output-dir results/experiment08u/reconstruction_first
```

Inspect:

```powershell
$dir = 'results/experiment08u/reconstruction_first'
Get-Content "$dir/run_status.json"
Import-Csv "$dir/aggregate_summary.csv" | Format-Table -AutoSize
Import-Csv "$dir/full_vs_diagonal_object.csv" | Format-Table -AutoSize
```

**Expected count: 36 reconstruction checkpoint rows** across 3 objects × 2 models × 3 policies × 2 checkpoints. The comparison includes object-wise RMSE differences: `full_minus_diagonal_*_rmse < 0` favors the exact policy.

Do not modify the 08U protocol after seeing results. Preserve all signs and negative outcomes, and treat the three objects as the independent sample size. Store results outside the Git repository after reviewing them.

### Commit source after checks

```powershell
git add experiment_08u.py test_experiment_08u.py README_08U.md
git diff --cached --check
git commit -m "Add exploratory exact versus diagonal information acquisition study"
```

## Known limitations

This is a small synthetic **development** sample; no formal significance, dose, clinical, or general-geometry claim. It is not a comparison against other full-covariance numerical approximation methods or modern acquisition-design baselines. It does not alter or add an independent confirmation to frozen 08M. The exact selector may be slower; performance should be reported alongside reconstruction metrics.
