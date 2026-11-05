# RBYRCT-08AD — Independent 08AC voxel-MART replay

## Scope

Replay **all 192 frozen 08AC voxel reconstructions** using archived ray histories from `experiment08ac/engineering_first` and the completed `experiment08ac/reconstruction_first` archive. The replay implements its own MART row iteration, Gaussian-noise generation, voxel RMSE, paired gains, object summaries, aggregates, and primary contrasts. It does **not** import `experiment_05b_mart`, production noise code, acquisition selectors, or evaluation-metric helpers. The original synthetic phantom generator, 3D system geometry, independent synthetic forward projector, and evaluation-only defect-mask generator are reused; these five source files must hash-match the frozen protocol lock.

This is a **source-locked numerical replay**, not an independent experiment with different physics or empirical CT data. The original 08AC archive contains RMSE metrics but not original voxel arrays, so the replay compares fresh voxel-derived RMSE with archived metrics, not original-versus-replayed voxel equality.

## PowerShell instructions (Windows repository root)

Extract `replay_08ad.py`, `test_replay_08ad.py`, and `README_08AD.md` directly into `C:\Users\shuss\Downloads\rbyrct-3d-05a`. Activate `rbyrct-3d` Conda environment. Keep the frozen protocol lock `protocol_08ac_frozen.json` and the research modules untouched.

```powershell
cd C:\Users\shuss\Downloads\rbyrct-3d-05a
conda activate rbyrct-3d

python -m pytest test_replay_08ad.py -q
```

Run the full replay:

```powershell
$base = "..\rbyrct-results\experiment08ac"
if (-not (Test-Path "$base\reconstruction_first\run_status.json")) {
    $base = "results\experiment08ac"
}
if (-not (Test-Path "$base\reconstruction_first\run_status.json")) {
    throw "Original 08AC reconstruction archive not found"
}
if (-not (Test-Path "$base\engineering_first\preflight.json")) {
    throw "Original 08AC preflight archive not found"
}

python replay_08ad.py `
    --results-dir "$base\reconstruction_first" `
    --preflight-dir "$base\engineering_first" `
    --source-dir . `
    --output-dir results\experiment08ad\full_replay_first
```

Inspect all checks:

```powershell
$dir = "results\experiment08ad\full_replay_first"
Get-Content "$dir\replay_report.json"
Get-Content "$dir\run_status.json"
Import-Csv "$dir\aggregate_replayed.csv" | Format-Table -AutoSize
Import-Csv "$dir\primary_replayed.csv" | Format-Table -AutoSize
Import-Csv "$dir\voxel_rmse_comparison.csv" |
    Sort-Object {[double]$_.abs_difference} -Descending |
    Select-Object -First 12 | Format-Table -AutoSize
```

Expected **on PASS**: 192 fresh 32^3 `.npy` volumes, 576 RMSE comparisons, 576 paired gain comparisons, 48 object summaries, 8 policy/budget aggregates, and 6 primary-object contrasts; zero errors. Expect ~9.657769736799208 **percentage points** for the primary spatial-minus-full mean, and all six object wins. If any source hash or numerical comparison fails, the script refuses to report PASS.

After a complete PASS and review, preserve the output separate from the repository:

```powershell
python -m pytest -q
git diff --check
git add replay_08ad.py test_replay_08ad.py README_08AD.md
git diff --cached --check
git commit -m "Add independent voxel-level replay of frozen 08AC MART study"
Move-Item "results\experiment08ad" "..\rbyrct-results\"
git status --short
```

Do not move an existing directory over another archive; inspect destinations first. Reruns require a **new, nonexistent** output directory, e.g. `full_replay_second`; failed runs are intentionally retained for audit. For storage-constrained work, `--no-volumes` omits `.npy` files but still calculates every reconstruction and metric, though saved volumes are preferable for future analysis.

## Independence and scientific limits

- The reimplemented row-wise multiplicative MART is **not imported** from the production reconstructor.
- Source-file SHA checks bind the shared synthetic truth, geometric matrix and projector to the prospective protocol lock.
- Acquisition order selection is **not** replayed or independently verified beyond byte hashes and full/prefix order hashes.
- This verifies numerically reproduced **RMSE and gains** from reconstructed voxels; original 08AC reconstruction voxels were not preserved.
- The six phantoms are independent synthetic objects. Two acquisition seeds and two forward-model variants are matched repetitions within each object, not 24 independent objects.
- This does not substantiate clinical superiority, dose reduction, physical scanner engineering, or generalization to other geometries.
