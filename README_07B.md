# RBYRCT-07B: 32³ MART computational feasibility (engineering only)

## Purpose

Profile the **existing** CPU sparse-geometry / MART / coverage-constrained selection implementation at 32³. **Not** an experiment on reconstruction quality, imaging accuracy, dose, defect detection, or a method winning over another. Do not compare the resulting image to truth. No hyperparameter selection. This uses a single deterministic manufactured positive signal only to supply nonnegative projections.

## Fixed production profile

- Volume 32³ = 32,768 voxels, azimuths 4, three existing tilts, maximum candidate rays 12,288.
- Budget 128 rays, common coverage warm prefix 32, subsequent batch 16, candidate pool 16.
- MART 2 provisional epochs and 4 final epochs, relaxation 0.25; acquisition seed 707031.
- Coverage-only, original gradient, 5%-guarded gradient; same sparse matrix and manufactured projections.
- Output: `protocol.json`, `profile.json`, `policy_timing.csv`, `environment.json`.
- The benchmark deliberately runs **one history per policy**, not a replicated accuracy comparison.

## Installation / Windows PowerShell

Copy `experiment_07b.py`, `test_experiment_07b.py`, `README_07B.md` to the existing `rbyrct-3d-05a` repository. Use the existing `(rbyrct-3d)` environment. Existing repository imports include NumPy and SciPy. `psutil` is optional; Windows OS APIs provide process memory metrics if psutil is absent.

```powershell
python -m pytest test_experiment_07b.py -q
python -m pytest -q
git diff --check

python experiment_07b.py `
    --output-dir results/experiment07b/profile_32_first

Get-Content results/experiment07b/profile_32_first/profile.json
Import-Csv results/experiment07b/profile_32_first/policy_timing.csv |
    Format-Table policy, total_selection_including_common_warm_s, final_reconstruction_s, rss_after_policy_bytes -AutoSize
```

**Safety / provenance:** Fresh output directory only; cannot overwrite. Production settings frozen; `--test-scale` overrides permitted solely for toy test invocation, **not** scientific evidence. 32³ sparse geometry still has substantial transient Python-list memory during `system_matrix`; watch system RAM, and terminate if necessary. No process memory budget enforcement is claimed. `process_peak_final_bytes` is an **entire-process** peak (imports and all phases); `rss_after_matrix_bytes` and per-policy RSS are snapshots. `csr_storage_bytes` excludes temporary construction arrays, SciPy indexing copies, and Python allocations. These do not measure GPU or clinical-scale capabilities.

**Interpretation:** If timings/memory are acceptable, the next activity is a *separately specified* larger-scale imaging validation with new objects and prespecified quality criteria. Do not choose the ray budget by inspecting this manufactured signal; no accuracy or RMSE is output by 07B.

The `selection_s` field times only the policy-specific phase; `total_selection_including_common_warm_s` also includes the one-time common warm coverage-order calculation and is the fairer selection-cost comparison for this implementation.
