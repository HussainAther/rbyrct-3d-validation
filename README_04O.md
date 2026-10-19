# Experiment 04O-A — Acquired-only reliability signals

## Purpose
Determine whether an **acquired-data-only** signal identifies cases where the frozen 04J measurement-feedback selector is worse than feedback-off under 04N model mismatch. **No new selector, no gate, no tuning, no clinical/dose claim.**

Inputs use the existing repository scripts `experiment_04b.py`, `experiment_04g.py`, `experiment_04h.py`, `experiment_04i.py`, `experiment_04j.py`, `experiment_04k.py`, `experiment_04m.py`, `experiment_04n.py`.

## Run (PowerShell)

Extract `experiment_04o.py`, `test_experiment_04o.py`, and this README alongside the other 04-series scripts.

```powershell
conda activate rbyrct-3d
python -m unittest -v test_experiment_04o.py
```

Smoke:

```powershell
python experiment_04o.py `
  --size 8 --angles 4 --factor 2 `
  --object-types replicated subvoxel --offsets 0 0.15 `
  --budgets 64 --warm-rays 32 --batch 16 `
  --provisional-iterations 10 --sirt-iterations 20 `
  --candidate-pool 16 --seeds 104729 `
  --phantoms torus beads --noise-fractions 0 `
  --output-dir results/experiment04o_smoke
```

Full exploratory diagnostic:

```powershell
python experiment_04o.py `
  --size 16 --angles 12 --factor 2 `
  --object-types replicated subvoxel `
  --offsets 0 0.05 0.15 0.30 `
  --budgets 512 1024 2048 `
  --warm-rays 128 --batch 64 `
  --provisional-iterations 60 --sirt-iterations 400 `
  --candidate-pool 64 --seeds 104729 130363 155921 `
  --phantoms torus slats beads wedges `
  --noise-fractions 0 `
  --output-dir results/experiment04o_a
```

This configuration runs **576 final reconstructions** (288 paired cases, two policies) plus provisional diagnostic fits; may take significant time. For faster initial diagnostics, limit `--seeds 104729 --offsets 0 0.15` (96 final reconstructions).

## Observable signals

For each selected adaptive prefix, use only its acquired ray IDs:

1. `heldout_nrmse`: deterministic 20% acquired-ray validation split, fitted on remaining acquired rays.
2. `feature_split_correlation`: correlation between gradient-based image scores from two disjoint subsets of the training rays.
3. `feature_instability = 1 - feature_split_correlation`.

These are **unvalidated proxies**, not calibrated risk scores. Prefix diagnostics are measured *post hoc* on the already-frozen acquisition trajectory, without affecting future ray choice. Truth is used only to compute the final adaptive-versus-feedback-off RMSE label. The held-out rays were selected adaptively and are not statistically independent; be cautious interpreting their errors.

## Outputs

- `metrics.csv`: matched policy RMSE, model-mismatch severity, selection elapsed seconds.
- `signals.csv`: acquired-only reliability diagnostics by prefix.
- `paired_cases.csv`: RMSE gain and earliest/latest observed diagnostics.
- `summary.csv`: descriptive gain and signal means by object-type/offset/budget.
- `associations.csv`: exploratory Pearson correlation of signals with paired gain, by budget.
- `divergence.csv`: comparison of adaptive and feedback-off acquisition orders.
- `protocol.json`: frozen protocol and limitations.

Correlations alone cannot establish predictive validity. In particular, repeated seeds/offsets on four hand-designed phantom families are correlated. Do **not** choose thresholds from 04O-A and then claim performance on those same families is independently validated. Reserve new families/seeds for 04P.
