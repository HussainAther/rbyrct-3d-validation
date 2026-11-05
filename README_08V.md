# RBYRCT-08V — Retrospective geometric acquisition-pattern diagnostics

## Scope

This is a **read-only**, descriptive study of the **archived 08U 12³** ray orders. It compares geometric diagnostics for the three acquisition policies (`coverage`, `information_diag`, `information_full`) at 144 and 288 rays. It **does not** run MART, select new rays, inspect phantom truth, or use the defect mask to compute geometric metrics.

08U reported a diagonal-selector advantage in whole-volume RMSE on three development phantoms. 08V explores potential *associations* with geometric coverage and redundancy. It cannot establish a causal mechanism, generalization, radiation-dose benefit, or significance. All three objects share each policy's geometry-only ray order.

## Extract and run in PowerShell

Extract the three files **directly into the root** of `rbyrct-3d-05a` (avoid duplicate nested test directories).

```powershell
python -m pytest test_experiment_08v.py -q
python -m pytest -q
git diff --check
```

Confirm that 08U results were archived at `..\rbyrct-results\experiment08u\reconstruction_third` (the unsuccessful `reconstruction_first` and `reconstruction_second` directories should remain untouched).

```powershell
python experiment_08v.py `
  --results-dir ..\rbyrct-results\experiment08u\reconstruction_third `
  --output-dir results/experiment08v/geometry_first
```

The command **refuses to overwrite any existing output directory**. For retries use `geometry_second`, etc.; never delete historical outputs just to rerun.

```powershell
$dir = 'results/experiment08v/geometry_first'
Get-Content "$dir/run_status.json"
Import-Csv "$dir/geometry_by_policy_checkpoint.csv" |
  Select-Object policy,acquired,visited_voxel_fraction,voxel_visit_cv,voxel_visit_gini,view_entropy,detector_entropy,sampled_ray_cosine,shared_ray_fraction_with_coverage |
  Format-Table -AutoSize
Import-Csv "$dir/diagonal_minus_full_summary.csv" | Format-List
Import-Csv "$dir/geometry_with_exploratory_rmse.csv" | Format-Table -AutoSize
```

## Metrics (geometry only)

- **Visited voxel fraction:** fraction of the 12³ voxels with at least one selected nonzero ray-matrix coefficient.
- **Voxel visit CV, Gini, and entropy:** dispersion of nonzero ray visitation counts *including unvisited voxels*. Smaller CV/Gini indicates more even coverage, but does not imply smaller MART error.
- **Path-length CV:** dispersion of cumulative ray path lengths across voxels.
- **View entropy:** normalized frequency entropy across the 12 tilt-by-azimuth groups.
- **Detector entropy:** normalized frequency entropy across the 144 detector coordinates pooling all views.
- **Sampled ray cosine:** average cosine of up to 512 deterministically sampled distinct normalized sparse row pairs (seed `23081`), measuring *one notion* of path overlap, not all-pairs redundancy.
- **Shared-ray fractions:** set intersection of chosen prefix rays with coverage and diagonal policies, divided by prefix budget.
- **Reconstruction overlay:** archived object-balanced RMSE gains are joined afterward from `aggregate_summary.csv`, never used to compute the geometry diagnostics.

Checks include archived SHA-256 file digests, ordering uniqueness, contiguous one-based acquisition indices, full-history fingerprints, and reconstruction-prefix hashes. Success is **archive and geometry diagnostic consistency**, not external source verification or numerical replay.

## Archiving and provenance

If successful:

```powershell
git add experiment_08v.py test_experiment_08v.py README_08V.md
git diff --cached --check
git commit -m 'Add retrospective 08U geometric acquisition diagnostics'
Move-Item 'results/experiment08v' '..\rbyrct-results\'
git restore -- ':(glob)__pycache__/*.pyc'
git status --short
```

Do not modify the frozen 08M, 08N or 08Q datasets. Do not infer statistical significance from the six policy-budget diagnostic rows; these are not independent objects.
