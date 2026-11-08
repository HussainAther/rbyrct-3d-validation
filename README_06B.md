# RBYRCT-06B — frozen prospective localized-defect 3D MART validation

**Status:** implementation preflight tested; the full 12³ confirmatory study has **NOT** been run in this package. Run it **once** on the untouched frozen settings. Do not change parameters or select objects based on outcome.

This is a synthetic computational validation. It does not establish physical CT, imaging-dose, industrial hardware, or clinical performance.

## Files to copy into `rbyrct-3d-05a`

- `experiment_06b.py`
- `test_experiment_06b.py`

These depend on code **already committed** in the repo: `experiment_06a.py` (guard), `experiment_05b_04.py` (coverage/gradient selector), `experiment_05b_11_stage2.py` (provenance/CSV helpers), `experiment_05b_gate.py` (acquired-only), and existing geometry / MART / independent projector modules. Do **not** remove or edit those dependencies.

## Frozen question

Does the **06A2 development-selected 5% coverage-guarded MART acquisition** improve 12³ coarse-grid reconstruction RMSE for **previously unseen synthetically generated localized-defect objects**, compared with coverage-only acquisition, at **288 measured rays**?

This is a deliberately narrow application hypothesis, not a universal superiority claim.

## Fixed production design

- 12³ coarse grid and 24³ fine truth, 4 azimuths × 3 tilts × 12² detector pixels = 1,728 candidate rays.
- 8 independently parameterized new defect objects, with object seeds `1066001 + 7919 * i` for `i=0..7`. Each object is a host ellipsoid with texture and 2–4 localized rotated attenuative Gaussian defects. This is a **new 06B generator**, not the old 06A2 deterministic `object_pair` family; its parameters were specified before accessing 06B outcomes.
- Paired policies: `coverage`, `gradient`, and `guarded_05`. Guard parameter `eta=.05`, unchanged from 06A2; frozen baseline `select_order` and guarded `acquire_guarded`, same candidate-draw rules.
- Two acquisition seeds `104729,130363`, two forward models: matched coarse linear (`A @ truth`) and independent fine-grid trilinear projector with 0.15 detector offset and 0.25 marching step.
- Shared generated measurement noise: additive Gaussian at 0.5% RMS, nonnegative clipping, reused across policies/seeds for a given object/model.
- 576-ray acquisition histories; nested checkpoints at 144, **288 (primary)**, 576 rays.
- Common initial 36-ray coverage prefix, sequential batches of 12, candidate pool 24, provisional MART 4 epochs, final MART 16 epochs, relaxation 0.25.
- **Primary endpoint:** object-balanced mean of paired `(RMSE_coverage - RMSE_guarded) / RMSE_coverage` at 288 rays, averaging four model×acquisition-seed conditions within each object then averaging across **8 objects**. Positive indicates better guarded policy.
- **Prespecified stringent descriptive success criterion:** primary mean gain > 0 **and** all 8 object-level means > 0. This is not a hypothesis test; no p value or statistical guarantee is implied. Report both overall mean and object-level distribution even if criterion fails.
- **Secondary:** original gradient baseline, checkpoints 144 and 576, 0.10 RMSE threshold first observed at checkpoints (censored, no interpolated ray savings), selection overhead, and forward mismatch.
- **Stop rule:** exactly one frozen full run, regardless of positive or negative result. No 06B-driven model or policy tuning. If a technical failure occurs, retain and document the partially written folder rather than overwriting it.

The same eight objects are evaluated repeatedly under two forward models and two acquisition seeds; these **32 matched conditions are not 32 independent structural objects**.

## Windows PowerShell commands

From your `rbyrct-3d` conda environment and project root:

```powershell
python -m pytest test_experiment_06b.py -q
python -m pytest -q
git diff --check

python experiment_06b.py `
    --output-dir results/experiment06b/frozen_first

$dir = 'results/experiment06b/frozen_first'
Get-Content "$dir/study_status.json"
Import-Csv "$dir/object_level_summary.csv" |
    Format-Table object_id, policy, mean_relative_gain -AutoSize
```

Expected production counts: 8 objects, **96 complete ray histories**, **288 checkpoint reconstructions**, **55,296 acquisition-order rows**, 24 object-policy summary records, and 96 threshold records. The full run is not executed in this package.

## Outputs

- `protocol.json` — original frozen protocol and hash, written **before** acquisition.
- `environment.txt` — Python/OS/library and Git provenance.
- `object_manifest.csv` — seeds, per-object truth hashes and generator parameters.
- `acquisition_orders.csv` — sequential acquired ray order, permitting audit of unique rays.
- `prefix_reconstructions.csv` — all RMSEs, gains and checkpoint ray fingerprints.
- `matched_cases.csv` — primary 288-ray matched conditions.
- `object_level_summary.csv` — unit-of-replication aggregation.
- `threshold_crossings.csv` — first observed qualifying checkpoint for RMSE <=0.10.
- `timing.csv` — selection and reconstruction wall-clock timings (selection_s is repeated per checkpoint; **do not sum** that column over checkpoints).
- `guard_batch_audit.csv` — guard eligibility/binding diagnostics.
- `study_status.json` — counts, primary result and engineering status.
- `run_manifest.sha256` — file fingerprints for reproducibility audit.

## Interpretation and constraints

- 06A2 development showed benefit on its *fixed defect examples*, influencing selection of the defect-focused hypothesis. 06B provides independent **parameter instances within a related, researcher-designed phantom class**, not validation on real defect scans or another institution's object generator.
- An improvement in global RMSE does **not** establish improved defect detection or localization; those are separate, currently unmeasured task-specific metrics.
- The simulated independent model includes geometric offset and interpolation mismatch; the noise is **not Poisson counting noise**.
- The primary endpoint is RMSE at a fixed budget, not independently measured exact rays-to-quality or practical dose.
- One study with eight objects remains a small synthetic validation. If results are positive, evaluate uncertainty and external generalization before making a broad recommendation.
