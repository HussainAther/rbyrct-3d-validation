# Experiment 04N — Why does adaptive feedback fail under forward-model mismatch?

04N is a **diagnostic** follow-up to 04M; it does not tune or alter `experiment_04j.adaptive_order` or `sirt_silent`.

## Controls

- `replicated`: build an object on the coarse `n³` grid and replicate each voxel exactly to the fine `(factor*n)³` grid. With zero geometry shift, an exact path integrator should reproduce coarse-grid ray integrals to numerical tolerance. This isolates discretization of the *forward operator*.
- `subvoxel`: evaluate a distinct analytic object at finer resolution and score reconstruction against its coarse block average. This introduces subvoxel structure alongside fine-grid projection.
- `--offsets`: offsets of 0, 0.05, 0.15, 0.30 in coarse voxel units shift detector-plane ray origins **only in the fine measurement simulator**. The coarse model used for both acquisition planning and reconstruction stays unchanged.

All five 04K policies are included. Noise is generated as in 04I/04M, and each paired case shares the same noisy synthetic measurement realization. Only acquired indices are accessed for online selection. Ground-truth image-gradient correlation is computed **after acquisition** for diagnostics; it never enters the selector.

## Files

Place `experiment_04n.py`, `test_experiment_04n.py`, and this README alongside `experiment_04b.py`, `experiment_04f.py`, `experiment_04g.py`, `experiment_04h.py`, `experiment_04i.py`, `experiment_04j.py`, `experiment_04k.py`, `experiment_04m.py`.

Tests:

```powershell
python -m unittest -v test_experiment_04n.py
```

Small smoke run:

```powershell
python experiment_04n.py `
  --size 8 --angles 4 --factor 2 `
  --object-types replicated subvoxel `
  --offsets 0 0.15 `
  --budgets 64 --warm-rays 32 --batch 32 `
  --provisional-iterations 10 --sirt-iterations 20 `
  --candidate-pool 16 --seeds 104729 `
  --phantoms torus beads --noise-fractions 0 `
  --output-dir results/experiment04n_smoke
```

Recommended first full-size **stage A** (isolate exact coarse-to-fine object representation; 120 reconstructions):

```powershell
python experiment_04n.py `
  --size 16 --angles 12 --factor 2 `
  --object-types replicated subvoxel `
  --offsets 0 `
  --budgets 512 1024 2048 `
  --warm-rays 128 --batch 64 `
  --provisional-iterations 60 --sirt-iterations 400 `
  --candidate-pool 64 --seeds 104729 `
  --phantoms torus slats beads wedges `
  --noise-fractions 0 `
  --output-dir results/experiment04n_stage_a
```

**Stage B** offset sweep, **1,440 reconstructions** (2 object types × 4 offsets × 4 phantoms × 3 seeds × 3 budgets × 5 policies × 1 noise):

```powershell
python experiment_04n.py `
  --size 16 --angles 12 --factor 2 `
  --object-types replicated subvoxel `
  --offsets 0 0.05 0.15 0.30 `
  --budgets 512 1024 2048 `
  --warm-rays 128 --batch 64 `
  --provisional-iterations 60 --sirt-iterations 400 `
  --candidate-pool 64 --seeds 104729 130363 155921 `
  --phantoms torus slats beads wedges `
  --noise-fractions 0 `
  --output-dir results/experiment04n_sweep
```

The Stage A count is 2 × 1 × 4 × 1 × 3 × 5 = **120**; Stage B is 2 × 4 × 4 × 3 × 3 × 5 = **1,440**. The larger sweep can be time-consuming.

## Outputs

- `metrics.csv`: per-policy RMSE and coarse-grid coverage diagnostics
- `paired_cases.csv`: case-matched relative gains versus all four comparators
- `paired_summary.csv`: gain and win aggregates by object type, offset and ray budget
- `mismatch_diagnostics.csv`: relative projection discrepancy between fine measurements and coarse predictions
- `provisional_features.csv`: post-hoc prefix RMSE and provisional-vs-truth gradient correlation
- `divergence.csv`: adaptive versus feedback-off ray-set divergence
- `selection_timing.csv`: selection timing **with scope labels** (not all baselines are timed comparably)
- `protocol.json`: parameters and limitations

## Interpretive safeguards

- This isolates synthetic causes; it does not prove a causal explanation for policy failure from correlation alone.
- Same underlying ray-traversal mathematics is shared across simulator grids. This is not independent hardware or physical-model validation.
- No physical CT dose or clinical performance claims follow.
- These are previously explored phantom families, not prospectively untouched held-out data.
- Do not choose hyperparameters from the diagnostic outcomes and describe resulting tests as independent validation.
