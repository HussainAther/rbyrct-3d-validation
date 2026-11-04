# RBYRCT 05B-05: Frozen acquisition-objective audit

This is a **descriptive software experiment**, not a new RBYRCT acquisition policy. It imports and runs the four **unchanged 05B-04 policies** (`gradient`, `coverage`, `capped_gradient`, `projection_disagreement`) with identical specified budgets, geometry, candidate pool and random seed configuration. The policy draws can differ after the histories diverge.

## Output

- `prefix_geometry.csv`: unique voxel coverage fraction, path-weight CV, fraction of uncovered voxels, view diversity/entropy and concentration. Coverage is geometric, not a calibrated uncertainty measurement.
- `policy_overlap.csv`: pairwise same-prefix Jaccard, common-ray counts, set divergence, positional disagreement.
- `view_counts.csv`: distribution over angle/tilt views at each checkpoint.
- `reconstruction_trajectories.csv`: offline MART RMSE versus acquired-ray budget; acquired projection residual is **not** used for selecting rays.
- `timing.csv`: selector wall time and offline checkpoint and final reconstruction wall times, not dose or physical acquisition time.
- `protocol.json`: settings and limitations.

The script reconstructs and reports at the warm-start count, at selected whole-batch checkpoints, and at the endpoint. It uses the same provisional/final MART settings for all policies. No new heuristic is introduced or tuned.

## Run

```powershell
python -m pytest test_experiment_05b_05.py -q
python -m pytest -q
python experiment_05b_05.py `
  --size 8 --angles 4 --factor 2 `
  --phantoms branches layers pores defects `
  --representations replicated `
  --seeds 271828 314159 577215 `
  --budget 128 --warm-rays 16 --batch 8 `
  --candidate-pool 16 --provisional-epochs 4 `
  --mart-epochs 16 --mart-relaxation 0.25 `
  --feature-cap 3 --checkpoint-every 32 `
  --output-dir results/experiment05b/objective_audit_8_first
```

Unzip **only the three files** into the worktree root (do not retain duplicate test files in a nested folder). Use a new output directory for each run. Do not overwrite existing 05B-04 results.

The analysis is exploratory, depends on shared synthetic phantom definitions, and does not by itself demonstrate a reconstruction advantage or physical CT feasibility.
