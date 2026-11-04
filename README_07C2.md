# RBYRCT-07C2 — Frozen 32³ localized-defect MART validation

## Scientific purpose

Prospectively test whether the budget-specific fixed-ray accuracy gain seen in **06B at 12³** replicates at **32³** on new, seeded synthetic localized-defect volumes. The development-selected coverage guard remains at **η = 0.05**, with *unchanged* coverage and original gradient comparators. This is a **new** confirmatory synthetic study, not a physical CT experiment or a dose-efficiency demonstration.

**Freeze rule:** Do not alter method or endpoints after looking at study outcomes; run the production configuration once, retain the results whether favorable or unfavorable. Test-scale overrides exist solely for unit/smoke testing.

## Locked production design

| Element | Value |
| --- | --- |
| Reconstruction | MART, 32³ (32,768 voxels); 4 azimuth angles × existing three tilts × 32² rays = 12,288 candidates |
| Forward synthesis | fine-grid factor 2; matched (`A @ coarse truth`) and independent (`project`, linear marching, offset 0.15, step 0.25) |
| Synthetic object seeds | `2077001 + 7919*i` for i=0…7 (eight new instances, not used in 06B, 07C engineering, or earlier validation) |
| Acquisition seeds | 104729 and 130363 (reused *acquisition* seeds for comparability, not independent objects) |
| Noise | 0.5% RMS, nonnegative; deterministic per object/model, shared across policies and acquisition seeds |
| Policies | coverage, gradient, guarded_05 |
| Warm / batch / candidate pool | 64 / 32 / 16 |
| Provisional MART | 2 epochs, relaxation 0.25 |
| Final MART | **16 epochs**, relaxation 0.25. Unlike the 07C engineering profile (4 epochs), this is set for scientific comparison with 06B (16). No accuracy test was used to choose it. |
| Nested ray checkpoints | **1024 / 2048 / 4096** |
| Primary checkpoint | **2048** rays (one-sixth of candidate pool), designated before running full study |
| Primary endpoint | Mean over eight objects of the per-object mean paired relative **whole-volume RMSE gain**, guarded_05 vs coverage, at 2048 rays: `(RMSE_coverage − RMSE_guarded)/RMSE_coverage` |
| Primary descriptive success criterion | Mean gain positive **and** all eight object-averaged gains positive (not a hypothesis test) |
| Secondary endpoints | Gradient baseline; 1024/4096 rays; defect-region and nondefect RMSE gains; matched/independent comparisons; RMSE ≤ 0.10 at saved checkpoints; computational overhead |
| Replication unit | Object (8), not 2 models × 2 acquisition seeds × 8 objects (32 repeated conditions per policy) |

The generated defect evaluation mask identifies voxels with positive coarse host-minus-defective contrast ≥ `max(0.01, 0.08 × max contrast)` and is constructed from the counterfactual defect-free synthetic host. The mask is **evaluation only**: it is never given to any acquisition selector or provisional reconstruction. The 07C engineering mask seed `707001` is not used here. The model family is still parameterized synthetic Gaussian defects within ellipsoidal hosts; this is **not** validation on independent real defect types.

Expected outputs from the full study: **8 objects, 96 complete acquisition histories, 288 checkpoint reconstructions, and 393,216 ray-order rows**. The common coverage order is created once per acquisition seed, and its timing is reported in `matrix_profile.json` separately from `timing.csv`'s per-history selector durations; do not add common setup time repeatedly to checkpoints.

## Installing on Windows

Extract **only the three files** into your existing repository (`C:\Users\shuss\Downloads\rbyrct-3d-05a`):

- `experiment_07c2.py`
- `test_experiment_07c2.py`
- `README_07C2.md`

Keep all existing 05B/06/07 source files unchanged. Run tests:

```powershell
python -m pytest test_experiment_07c2.py -q
python -m pytest -q
git diff --check
```

Execute **one** frozen full study:

```powershell
python experiment_07c2.py `
    --output-dir results/experiment07c2/frozen_32_first
```

On completion:

```powershell
$dir = "results/experiment07c2/frozen_32_first"
Get-Content "$dir/run_status.json"
Get-Content "$dir/study_status.json"
Import-Csv "$dir/object_level_summary.csv" |
    Format-Table object_id, policy, mean_relative_gain, mean_defect_gain -AutoSize
```

Expected `run_status.json`: `"complete": true` and 96 histories. The study can take materially longer than the one-object 07C engineering benchmark because it uses multiple models, seeds, objects and final reconstructions; do not infer timing from short smoke tests.

## Preservation and audit

- Files are created in a **new** output directory; the script refuses to overwrite a nonempty directory.
- `protocol.json` contains prespecified settings and a SHA-256 fingerprint; `environment.txt` captures the runtime environment.
- `acquisition_orders.csv` records every ray in every history; `prefix_reconstructions.csv` records raw RMSE, defect/nondefect RMSE, policy gains and per-checkpoint ray hashes.
- `object_manifest.csv` records synthetic truth, fine truth and evaluation-mask fingerprints plus object generator descriptors.
- `timing.csv`, `guard_batch_audit.csv` and `matrix_profile.json` document costs and safeguard behavior.
- On success, `study_status.json`, `matched_cases.csv`, `object_level_summary.csv`, `threshold_crossings.csv`, and `run_manifest.sha256` are written.
- `run_status.json` and the raw CSVs are updated incrementally. A **partial** run is *not* evidence for any study-level result; do not resume, overwrite or treat it as success. Preserve it and investigate the engineering cause before considering a separately labeled reproducibility run.
- This is not independent raw-output verification. The 06B audit verifies 06B only; a separate independent 07C2 audit is needed after the run.

### Claim boundaries

No physical scanner, dose, material microstructure, real defect-detection performance, precise ray savings, clinical or industrial performance are established by this study. Secondary outcomes are not part of the frozen primary success rule. At 32³ the number of voxels is larger but still not representative of real-world CT resolution.
