# Experiment 04J — feedback-dependent 3D ray acquisition (exploratory pilot)

Keep these scripts next to `experiment_04b.py`, `experiment_04f.py`, `experiment_04g.py`, `experiment_04h.py`, and `experiment_04i.py`.

## Correctness tests

```powershell
conda activate rbyrct-3d
python -m unittest -v test_experiment_04j.py
```

## Smoke test

```powershell
python experiment_04j.py `
  --size 8 --angles 4 `
  --budgets 64 128 --warm-rays 32 --batch 32 `
  --provisional-iterations 15 --sirt-iterations 20 `
  --candidate-pool 16 --seeds 104729 `
  --phantoms shell cross --noise-fractions 0 `
  --output-dir results/experiment04j_smoke
```

## Recommended first 16-cubed pilot (40 reconstructions)

```powershell
python experiment_04j.py `
  --size 16 --angles 12 `
  --budgets 512 1024 --warm-rays 128 --batch 64 `
  --provisional-iterations 60 --sirt-iterations 400 `
  --candidate-pool 64 --seeds 104729 `
  --phantoms shell cross --noise-fractions 0 0.01 `
  --output-dir results/experiment04j_pilot
```

## Extended exploratory run (540 final reconstructions; selection can be slow)

```powershell
python experiment_04j.py `
  --size 16 --angles 12 `
  --budgets 512 1024 2048 `
  --warm-rays 128 --batch 64 `
  --provisional-iterations 60 --sirt-iterations 400 `
  --candidate-pool 64 --seeds 104729 130363 155921 `
  --phantoms shell cross bands ribbon `
  --noise-fractions 0 0.002 0.01 `
  --output-dir results/experiment04j
```

## Policies

- `adaptive_feedback`: 04H frozen coverage-greedy warm start; at every batch boundary reconstruct *already measured* rays using provisional 04F SIRT, compute local 3D gradient magnitude, then use geometry coverage + that feedback to choose subsequent rays.
- `feedback_off_control`: same candidate subpool, update schedule, reconstruction overhead and acquisition scoring, but feedback strength = zero.
- `voxel_coverage_greedy`: frozen 04H ordering; no measurement feedback.
- `random`, `geometry_balanced`: original 04G policies.

All use the same 04B matrix and final 04F-style SIRT with 400 iterations. Projection noise is synthetic additive Gaussian. Repeated use of previously studied 04I phantom families makes this an exploratory experiment, *not* an independent holdout test.

## Outputs

- `metrics.csv` and `summary.csv`: error and residuals
- `paired_vs_feedback_off.csv` and `paired_vs_greedy.csv`: most important causal-style controls, with paired comparisons
- `paired_vs_random.csv`: comparison to random
- `object_swap.csv`: whether swapping the simulated object changes selected rays after warm start
- `divergence.csv`: difference between adaptive, feedback-off, and frozen schedules
- `adaptive_trace.csv`: intermediate-feedback updates
- `orders.csv`: unique order hashes, timing and coverage metrics
- `protocol.json`: configuration and methodological caveats

**Pass criteria:** objectively verify (1) chosen rays depend on past measurements, (2) changing the object changes selected rays, (3) improvements over `feedback_off_control`, if any, hold at equal ray budgets, across objects and noise levels. A data-dependent schedule by itself is not evidence of reconstruction gain.
