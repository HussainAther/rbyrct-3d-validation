# 08AJ-B: Conventional geometry-only acquisition baseline preflight

**Status:** Engineering/development only. No scientific reconstruction results generated, no locked 08AJ comparison or phantom experiment. Does not change existing 08M, 08AC or 08AD files.

This package provides two deliberately independent acquisition-policy definitions using the *same ray IDs as* `experiment_04b.system_matrix`: `ray_id = (tilt*angles + azimuth)*(n*n) + detector_row*n + detector_col`.

1. `uniform_multiscale`: round-robin among all `angles * tilts` views; within each view use the same deterministic multiscale detector-cell sequence constructed by reversing the base-4 digits of the detector-cell Morton code. At resolutions 32³/64³ (power of two), short sequences distribute detector cells across increasingly fine spatial blocks. This is a **newly specified numerical baseline**, not a textbook or physically executable uniform-view CT acquisition. It does not take an acquisition seed.
2. `stratified_random_04h`: reuses **unchanged** `experiment_04h.stratified_order`, which uniformly shuffles view order and detector-cell permutations per view using a fixed RNG seed, then cycles once through views at each detector rank. This is **historical repository code**, not a newly invented algorithm.

Both policies generate a full unique-ray permutation and take the first `budget` IDs. Every complete `angles*tilts` ray cycle contains exactly one ray from each view. Neither policy inspects a matrix, phantom, detector intensity, defect mask, or MART reconstruction.

## Installation / Windows PowerShell

Copy `experiment_08aj_b.py`, `test_experiment_08aj_b.py`, and this README to `C:\Users\shuss\Downloads\rbyrct-3d-05a` (repository root). Keep `experiment_04h.py` and its imports present.

```powershell
python -m pytest test_experiment_08aj_b.py -q
python experiment_08aj_b.py --output-dir results\experiment08aj_b\baseline32_first
Get-Content results\experiment08aj_b\baseline32_first\run_status.json
Get-Content results\experiment08aj_b\baseline32_first\baseline_report.json
```

Optional geometry-only scale check (no reconstruction):

```powershell
python experiment_08aj_b.py --size 64 --budget 2048 --output-dir results\experiment08aj_b\baseline64_first
```

The default 32³ test uses 4 azimuth angles, 3 frozen tilts, and a 4,096-ray prefix. The 64³ optional command uses 2,048 selected rays. Existing destinations cause failure instead of overwrite. Both policies' selected-ID arrays, summaries, and SHA-256 manifests are saved to the output folder. Keep the generated results out of Git until archival strategy is chosen.

## Before 08AJ validation

The **primary baseline choice is still provisional**. A detector-grid multiscale sampler is not the same as conventional *full projection-view* angular sampling. We must define an additional physically constrained full-view baseline or explicitly narrow our comparison to freely selectable rays. We must also lock scientific object seeds/families, exact measurement noise and forward-model rules, inference plan, resource limits, source hashes, and all outcomes before comparative reconstruction runs.
