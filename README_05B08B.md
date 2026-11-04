# RBYRCT 05B-08B: Frozen delayed-MART-feedback robustness

**Objective.** Check whether the exploratory `delayed_48` advantage over coverage-only survives newly seeded synthetic objects, new acquisition randomizations, nonnegative noisy projections, and a separately implemented numerical forward projector.

## Installation

Copy these **three** files into the existing `rbyrct-3d-05a` worktree **root**:

- `experiment_05b_08b.py`
- `test_experiment_05b_08b.py`
- `README_05B08B.md`

Do not keep an extracted folder containing a second copy of `test_experiment_05b_08b.py` under the repository: pytest will report an import mismatch.

## Frozen protocol

The four policies are imported from the existing `experiment_05b_07.select_delayed_order`: `coverage`, `gradient`, `capped_gradient`, `delayed_48`. MART relaxation `.25`, provisional epochs `4`, final epochs `16`, 16 warm rays, batch `8`, 16-candidate pool, gradient cap `3`, switch at 48 rays, budget `128`. All policies see the same warm order, full synthetic measurement vector *through an acquired-only access wrapper*, and noise realization; candidates are ranked only using acquired measurements and geometry. MART is unchanged.

Synthetic phantom families are **new parameterized formulas**: `inclusions`, `filaments`, `laminae`, and `voids`. Each `object_seed` generates a different fine-grid 3D density and its block-average coarse truth. Do not count acquisition seeds, noise realizations, or repeated forward models as new independent objects.

- `same` forward model: `A @ coarse_truth` (inverse-crime baseline).
- `independent` forward model: existing 04Q-A trilinear fine-volume ray marching with nonzero detector offset; reconstruction still uses coarse `A`. This is an *independent numerical implementation*, not independent CT hardware or physical validation.
- Noise: additive Gaussian with sigma = `noise_fraction * RMS(clean projections)`, clipped at zero because MART requires nonnegative values. This is **not** a realistic photon-counting noise model.
- Truth is used **only after finalizing each acquisition order** to score reconstruction RMSE.

`protocol.json` records the configuration and its SHA-256 hash before evaluation starts. CSVs: `matched_cases.csv`, `object_manifest.csv`, `object_level_summary.csv`. The summary averages acquisition-seed results **within object** first. For uncertainty intervals or tests, resample at the *object level* and avoid treating its repeated noise/model cases as independent observations.

## Tests

```powershell
python -m pytest test_experiment_05b_08b.py -q
python -m pytest -q
git diff --check
```

## Small smoke run

```powershell
python experiment_05b_08b.py `
    --size 8 --angles 2 --factor 2 `
    --families inclusions --objects-per-family 1 `
    --seeds 104729 --models same independent `
    --noise-fractions 0 0.005 `
    --budget 64 --warm-rays 16 --batch 8 --candidate-pool 8 `
    --provisional-epochs 2 --mart-epochs 4 `
    --output-dir results/experiment05b/robustness_08b_smoke
```

## Primary exploratory robustness run

```powershell
python experiment_05b_08b.py `
    --size 8 --angles 4 --factor 2 `
    --families inclusions filaments laminae voids `
    --objects-per-family 2 `
    --object-seed-base 900001 `
    --seeds 104729 130363 `
    --models same independent `
    --noise-fractions 0 0.005 `
    --offset 0.15 --step 0.25 `
    --budget 128 --warm-rays 16 --batch 8 `
    --candidate-pool 16 --provisional-epochs 4 `
    --mart-epochs 16 --mart-relaxation 0.25 `
    --feature-cap 3 `
    --output-dir results/experiment05b/robustness_08b_frozen_first
```

This run produces **256 policy-case rows** over eight object realizations, two acquisition seeds, two noise levels, two forward-model conditions, and four policies. It is a first robustness check, **not a clinically relevant or statistically powered confirmation study**. Select a fresh output directory for reruns. Do not change parameters based on the result and then call the same objects held out.
