# RBYRCT-05B-04: exploratory acquisition-score ablation

Copy `experiment_05b_04.py` and `test_experiment_05b_04.py` into the **root** of the existing `rbyrct-3d-05a` worktree. Do not extract a duplicate test folder into that root.

This experiment does not modify the existing 05B selector. It uses the existing MART reconstruction and compares:
- `gradient`: frozen 05B gradient feature scoring, tested against `adaptive_order` for exact order equivalence;
- `coverage`: frozen 05B feedback-off scoring, tested for exact order equivalence;
- `capped_gradient`: the existing gradient score capped at `--feature-cap` (default 3); and
- `projection_disagreement`: two MART reconstructions of disjoint acquired subsets; candidate selection uses **predicted** projection disagreement, never candidate observations.

Every policy uses the same warm prefix, candidate RNG seed, candidate-pool size, batch size, relaxation and final reconstruction. After policies diverge, their remaining candidate sets differ, so the same RNG state does not imply identical candidate rays.

## Test

```powershell
python -m pytest test_experiment_05b_04.py -q
python -m pytest -q
git diff --check
```

## 8^3 exploratory comparison

```powershell
python experiment_05b_04.py `
  --size 8 --angles 4 --factor 2 `
  --phantoms branches defects `
  --representations replicated `
  --seeds 271828 314159 577215 `
  --budget 128 --warm-rays 16 --batch 8 --candidate-pool 16 `
  --provisional-epochs 4 --mart-epochs 16 --mart-relaxation 0.25 `
  --feature-cap 3 `
  --output-dir results/experiment05b/score_ablation_8_first
```

Creates `score_ablation.csv` and `protocol.json`. Requires a fresh output directory. This is not confirmatory evidence or physical CT validation. The disagreement heuristic is not a calibrated uncertainty measure. Ground truth is accessed only for offline RMSE reporting. Noisy and independent-projector experiments have not yet been added.

## Suggested Git checkpoint

```powershell
git add experiment_05b_04.py test_experiment_05b_04.py README_05B04.md
git diff --cached --check
git commit -m "Add exploratory MART acquisition score ablation"
```
