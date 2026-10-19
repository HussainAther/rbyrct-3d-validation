# RBYRCT Experiment 04P — Out-of-Family 3D Confirmation

Purpose: frozen-policy confirmation on **four previously unused synthetic analytic phantom families** (`branches`, `layers`, `pores`, `defects`). Evaluate matched replicated objects against fine-grid subvoxel structure, using equal ray counts. This is **not an independent forward physics simulator**: the original 04M high-resolution projector shares the same Siddon-like integration family as the original coarse projector.

## Prerequisites

Place `experiment_04p.py` and `test_experiment_04p.py` next to existing `experiment_04b.py`, `experiment_04g.py`, `experiment_04h.py`, `experiment_04i.py`, `experiment_04j.py`, `experiment_04m.py`, `experiment_04n.py`, and `experiment_04oc.py`. Activate your existing `rbyrct-3d` conda environment.

```powershell
conda activate rbyrct-3d
python -m unittest -v test_experiment_04p.py
```

## Stage 1: pilot (40 reconstructions; 8 matched scenarios)

```powershell
python experiment_04p.py `
  --size 16 --angles 12 --factor 2 `
  --phantoms branches layers `
  --object-types replicated subvoxel `
  --offsets 0 `
  --seeds 271828 `
  --budgets 1024 2048 `
  --noise-fractions 0 `
  --warm-rays 128 --batch 64 `
  --provisional-iterations 60 `
  --diagnostic-iterations 60 `
  --sirt-iterations 400 --candidate-pool 64 `
  --threshold 2.0 --gate-strength 0 `
  --diagnostic-every 256 `
  --output-dir results/experiment04p_pilot
```

## Stage 2: out-of-family full run (480 reconstructions; 96 matched scenarios)

```powershell
python experiment_04p.py `
  --size 16 --angles 12 --factor 2 `
  --phantoms branches layers pores defects `
  --object-types replicated subvoxel `
  --offsets 0 0.15 `
  --seeds 271828 314159 577215 `
  --budgets 1024 2048 `
  --noise-fractions 0 `
  --warm-rays 128 --batch 64 `
  --provisional-iterations 60 `
  --diagnostic-iterations 60 `
  --sirt-iterations 400 --candidate-pool 64 `
  --threshold 2.0 --gate-strength 0 `
  --diagnostic-every 256 `
  --output-dir results/experiment04p_full
```

Optional separate exploratory noise extension: run with `--noise-fractions 0 0.002` into a **different output directory**; avoid treating the extra noise condition as a fresh independent phantom population. This doubles the full workload.

## What is frozen?

- Full adaptive and feedback-off selection are imported unchanged from **04J**.
- Geometry-balanced baseline is imported unchanged from **04G**.
- Voxel-coverage greedy order imported unchanged from **04H**.
- Reliability gate and threshold **2.0** imported unchanged from **04O-C**. The gate was not selected using these four new families.
- There is no hyperparameter search and no truth-dependent selection. Final truth is only used for RMSE and operator mismatch diagnostics.

## Outputs

- `metrics.csv`: each policy RMSE.
- `paired_cases.csv`: paired RMSE gains versus feedback-off, positive means lower RMSE.
- `paired_summary.csv`: descriptive mean and median gains and number of wins, stratified by object type, offset, ray budget, noise and policy.
- `mismatch_diagnostics.csv`: projection difference of fine forward model versus coarse forward model of the target, for post-hoc analysis.
- `gate_trace.csv`: acquisition-time diagnostic decisions.
- `timing.csv`: recorded selection times for online selectors only; baseline selection-time fields are blank.
- `protocol.json`: frozen settings and caveats.

## Primary interpretation

Primary: 2048-ray adaptive-vs-feedback-off mean **paired relative RMSE gain** in replicated vs subvoxel conditions, and the proportion of positive cases, stratified by offset. Secondary: 1024 rays; additional geometry and greedy comparisons; unchanged 04O-C gate transfer. Summaries do **not** quantify uncertainty accounting for only four independent phantom families. Do not treat 3 seeds times offsets as independent object populations. Do not select a new gate on these cases then claim this is a pure holdout.

This is synthetic 3D tomography only: no modeled physical dose, photon counts, hardware steering implementation, independent physical forward model, or patient imaging validation.
