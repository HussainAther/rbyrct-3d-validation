# Experiment 04K — Frozen 04J feedback on additional synthetic 3D phantoms

Run on the `experiment-04k` Git branch. Keep the existing `experiment_04b.py`, `experiment_04g.py`, `experiment_04h.py`, `experiment_04i.py`, and `experiment_04j.py` files beside the added scripts. The 04J selection and SIRT implementations are **imported unmodified**. Commit the two new `.py` files and this README, not the generated `results/` directory.

## Test

```powershell
conda activate rbyrct-3d
python -m unittest -v test_experiment_04k.py
```

## Smoke (20 reconstructions)

```powershell
python experiment_04k.py `
  --size 8 --angles 4 `
  --budgets 64 128 `
  --warm-rays 32 --batch 32 `
  --provisional-iterations 10 --sirt-iterations 20 `
  --candidate-pool 16 --seeds 104729 `
  --phantoms torus beads --noise-fractions 0 `
  --output-dir results/experiment04k_smoke
```

## Full validation (540 reconstructions)

```powershell
python experiment_04k.py `
  --size 16 --angles 12 `
  --budgets 512 1024 2048 `
  --warm-rays 128 --batch 64 `
  --provisional-iterations 60 --sirt-iterations 400 `
  --candidate-pool 64 --feedback-strength 1.0 `
  --seeds 104729 130363 155921 `
  --phantoms torus slats beads wedges `
  --noise-fractions 0 0.002 0.01 `
  --output-dir results/experiment04k
```

Report `paired_vs_feedback_off_control.csv`, `paired_vs_voxel_coverage_greedy.csv`, `summary.csv`, `orders.csv`, and `object_swap.csv`. Files `per_case_vs_*.csv` provide per-phantom paired effects, not only aggregate means.

## Design caveats

These four shapes are new to the 04J pilot, whereas 04I's shell/cross/bands/ribbon were already used during 04J development. This is **additional analytical-family validation**, not blinded preregistration or validation on measured clinical CT. Repeated seeds and noise settings on four fixed shapes are not independent anatomical samples. All methods reconstruct measurements generated using the same CPU matrix (inverse crime), and noise is additive Gaussian—not a photon-statistical physical dose model. Preserve negative results.
