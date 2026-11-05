# RBYRCT-08AB — Independent voxel-level MART replay of 08Z

**Goal:** Strengthen 08Z's evidence beyond the 08AA saved-CSV arithmetic audit. 08AB regenerates each of the four 08Z synthetic objects and both measurement conditions, replays **all 64** archived reconstruction records with a separately implemented sequential MART kernel, recomputes voxel-based RMSE from phantom truth and defect masks, and compares results against the archived metrics and gains. **It does not rerun or tune acquisition selectors.**

## Integrity and scope

- Verify all ten 08Z SHA-256-manifest files and the completed 64-record run status.
- Verify the approved 08Z engineering preflight and the **exact four complete 288-ray order SHA-256 fingerprints**; check every reconstructed 144/288 prefix.
- Regenerate `defect_dev_910201` through `defect_dev_910204`; verify both regenerated truth and defect-mask SHA-256 hashes against 08Z's object manifest.
- Recreate matched-geometry and independent-projector measurement conditions with precisely the 08Z noise seeds and Gaussian/nonnegative clipping convention.
- Reconstruct each acquisition using an independently coded sparse CSR MART update and recompute `global_rmse`, `defect_region_rmse`, and `nondefect_rmse` from individual voxel values.
- Compare all **192 RMSE values** and all **192 fractional gains** against archived values, then recalculate the 32 object-level and 8 aggregate rows, with object-level wins.
- Save 64 individual `.npy` voxel vectors and SHA-256 volume manifest by default. Every output goes into a new directory, and 08Z/08AA archives remain read-only.

## Run from PowerShell in the repo root

Extract exactly `replay_08ab.py`, `test_replay_08ab.py`, `README_08AB.md` directly into `C:\Users\shuss\Downloads\rbyrct-3d-05a`.

```powershell
python -m pytest test_replay_08ab.py -q
python -m pytest -q
git diff --check
```

**Use archived 08Z results** (if 08Z is not yet archived, change the two input paths to `results\experiment08z\...`):

```powershell
python replay_08ab.py `
    --results-dir ..\rbyrct-results\experiment08z\reconstruction_second `
    --preflight-dir ..\rbyrct-results\experiment08z\engineering_first `
    --source-dir . `
    --output-dir results/experiment08ab/full_replay_first
```

Inspect:

```powershell
$dir = 'results/experiment08ab/full_replay_first'
Get-Content "$dir/replay_report.json"
Get-Content "$dir/run_status.json"
Import-Csv "$dir/aggregate_replayed.csv" | Format-Table -AutoSize
Import-Csv "$dir/voxel_rmse_comparison.csv" |
    Sort-Object {[double]$_.abs_difference} -Descending |
    Select-Object -First 12 |
    Format-Table -AutoSize
```

**Pass condition:** `verdict: PASS`, `complete: true`, `volumes_replayed: 64`, `voxel_rmse_comparisons: 192`, no errors, and all saved gain/object summaries agree. On failure, preserve the output folder and investigate; do not classify it as a passed replay. Running again requires a new `--output-dir` (e.g. `full_replay_second`). The standard tolerance is an absolute/relative `2e-8`; it is stated in the report. `--no-volumes` can disable the 64 `.npy` files, but is not recommended for manuscript reproducibility.

After a successful run:

```powershell
git add replay_08ab.py test_replay_08ab.py README_08AB.md
git diff --cached --check
git commit -m "Add independent voxel-level replay of 08Z reconstructions"
Move-Item 'results/experiment08ab' '..\rbyrct-results\'
git restore -- ':(glob)__pycache__/*.pyc'
git status --short
```

## Scientific limits

An independent MART algorithm and RMSE calculation strengthen numerical verification, but **08AB is a source-locked replay, not independent physical-model replication**. It reuses the project's original phantom generator, sparse geometry, and independent forward projector; none of these establishes instrument or patient validity. We cannot test original voxel-by-voxel equality because 08Z did not save its reconstructed voxel vectors; instead we compare independently recomputed voxel RMSE and gain values. There are four independent synthetic objects, not eight; the paired forward-model conditions do not increase the object sample size. The study is exploratory, 12³, and cannot establish general 3D superiority, clinical dose reduction, or statistical significance. Frozen 08M remains untouched.
