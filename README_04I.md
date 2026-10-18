# Experiment 04I — Held-out 3D acquisition robustness

Dependencies: `experiment_04b.py`, `experiment_04f.py`, `experiment_04g.py`, and `experiment_04h.py` in the same folder; NumPy and SciPy. This is geometry-only acquisition, NOT measurement feedback.

## Tests

```powershell
conda activate rbyrct-3d
python -m unittest -v test_experiment_04i.py
```

## Smoke

```powershell
python experiment_04i.py `
  --size 8 --angles 4 `
  --budgets 64 128 `
  --noise-fractions 0 0.002 `
  --seeds 104729 `
  --phantoms shell cross `
  --candidate-pool 16 `
  --sirt-iterations 20 `
  --output-dir results/experiment04i_smoke
```

## Full experiment (576 reconstructions)

```powershell
python experiment_04i.py `
  --size 16 --angles 12 `
  --budgets 512 1024 2048 4096 `
  --noise-fractions 0 0.002 0.01 `
  --seeds 104729 130363 155921 `
  --phantoms shell cross bands ribbon `
  --candidate-pool 64 `
  --sirt-iterations 400 `
  --output-dir results/experiment04i
```

Outputs: `metrics.csv`, `summary.csv`, `paired_vs_random.csv`, `coverage.csv`, `orders.csv`, `protocol.json`.

Noise is additive Gaussian per scalar ray, with sigma = `noise_fraction * RMS(full clean projection data)`. The same noise realization is shared between methods for each phantom, seed and noise fraction; only acquired rows are passed to SIRT. The geometry-only selection logic and `candidate_pool=64` are frozen from 04H. The held-out shapes are synthetic and handcrafted, not patient data. No physical dose model, Poisson photon counting, or measurement-dependent adaptive selection is included. Deterministic methods repeated across seeds are not statistically independent acquisition replicates; selection overhead for greedy is logged only for the maximum budget order.
