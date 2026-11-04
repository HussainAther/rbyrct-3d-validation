# 05B-07: Delayed MART reconstruction feedback

This is an **exploratory** algorithmic control study, not a validated improvement.

Files: `experiment_05b_07.py`, `test_experiment_05b_07.py`, `README_05B07.md`.
Place them in the **root** of the `rbyrct-3d-05a` Git worktree, not in a nested extraction directory.

## Hypothesis

Coverage-only acquisition during the earliest batches may avoid poorly informed
MART gradient-feedback decisions. Compare delayed feedback beginning at 48 or 80
acquired rays against frozen coverage-only, immediate gradient, and immediate
capped-gradient controls.

## Reproducibility and information access

- Each policy uses the **same** geometry, warm prefix, candidate RNG seed,
  random candidate-pool draws, deterministic tie-break, and 05B scoring function.
  Candidate draws *necessarily diverge in identity* as earlier selections diverge.
- `delayed_48` and `delayed_80` use coverage-only scoring up to their respective
  switch batch boundaries, then use exactly the frozen gradient score.
- Acquired observations alone enter provisional MART. An `AcquiredOnly` spy
  regression test verifies measurement accesses.
- Coverage scoring skips unnecessary provisional MART; this is a more honest
  computational baseline than the older feedback-off implementation.
- Synthetic truth is used **only offline** for RMSE evaluation after selections.
- Final MART reconstruction uses the same relaxation and epoch budget per policy.
- Current `delay_48/80` choices come from prior exploratory results, so these
  runs cannot provide untouched confirmation of the delayed-policy hypothesis.
- This experiment uses the 04M Siddon-like fine-grid projection family and
  does not support physical scanner performance or dose claims.

## Tests

```powershell
python -m pytest test_experiment_05b_07.py -q
python -m pytest -q
git diff --check
```

## First 8^3 comparison

```powershell
python experiment_05b_07.py `
    --size 8 `
    --angles 4 `
    --factor 2 `
    --phantoms branches layers pores defects `
    --representations replicated `
    --seeds 271828 314159 577215 `
    --budget 128 `
    --warm-rays 16 `
    --batch 8 `
    --candidate-pool 16 `
    --provisional-epochs 4 `
    --mart-epochs 16 `
    --mart-relaxation 0.25 `
    --feature-cap 3 `
    --output-dir results/experiment05b/delayed_feedback_8_first
```

The output directory must not already contain files. No 04-series scripts or
existing 05B files are overwritten.

## Outputs

- `delayed_feedback.csv`: endpoint RMSE, gains vs. coverage, selection time,
  final reconstruction time, and ray overlap with coverage.
- `reconstruction_trajectories.csv`: RMSE at checkpoints, including warm prefix.
- `selection_timing.csv`: selection runtime and number of feedback batches.
- `protocol.json`: full parameters and interpretation limits.

To compare alternative switch points, modify the isolated policy list and
validation logic in the new experiment; retain this frozen first version for
reproducibility. Do not optimize switch points on the same cases and then claim
those cases as independent validation.
