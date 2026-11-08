# RBYRCT-05B-10 — Acquisition Failure Mechanism Audit

## Scope

A **retrospective, descriptive** 8³ MART diagnosis of the frozen 05B-08B acquisition policies, with optional (default-on) 05B-09 ray-sequence fingerprint verification. No online policy, MART update, scoring formula, or historical 04-series code is modified. Designed to test whether spatial sampling, error localization, and score/value alignment differ between the policy ray sets. Does not establish the cause of final-budget differences.

## Files

Place at worktree root: `experiment_05b_10.py`, `test_experiment_05b_10.py`, `README_05B10.md`. Do not leave the extraction folder nested inside the worktree (pytest import collision).

```
python -m pytest test_experiment_05b_10.py -q
python -m pytest -q
 git diff --check
```

Expected local total: **130 tests** if your local branch had 125 tests before installation. The separate validation checkout had **125 passing tests** including five new 05B-10 tests, because it has fewer prior tests.

## Run

Requires the original 05B-08B and 05B-09 result directories, particularly `matched_cases.csv`, `protocol.json`, and `ray_fingerprints.csv`. The defaults match the original 08B frozen protocol:

```powershell
python experiment_05b_10.py `
    --source-dir results/experiment05b/robustness_08b_frozen_first `
    --fingerprints-dir results/experiment05b/frozen_rays_09_first `
    --checkpoints 48 112 `
    --audit-candidates 6 `
    --audit-source-policies coverage gradient `
    --output-dir results/experiment05b/mechanism_10_first
```

**Expected full run:** 64 matched measurement/acquisition conditions x four policy ray sets = 256 verified 08B RMSE anchors and 256 verified 09 ray fingerprints; 256 geometry records, 256 error-localization records, 1,536 candidate counterfactuals and 1,024 ranking rows (64 conditions x 2 source policies x 2 checkpoints x 6 candidates or 4 scores).

`--output-dir` must be empty or new. Any 08B RMSE anchor or 09 SHA mismatch fails before writing a completed output. Ray sets are deterministically reproduced; 08B/09 did not save all ray IDs in a reusable binary artifact. This is a replay rather than direct loading of stored ray sequences.

## Output

* `geometry.csv`: ray-order fingerprint, fraction of voxels intersected, CV of voxel hits and accumulated weights, Gini of weights, view entropy, and number of shared rays with coverage.
* `error_localization.csv`: RMSE, RMSE in top quartile of truth attenuation, RMSE elsewhere, fraction of squared error concentrated in top quartile. The top quartile is **not** a clinically meaningful segmentation.
* `candidate_counterfactuals.csv`: offline value of inserting one sampled candidate after a frozen acquired prefix; reports all four score values and one-ray RMSE/heldout projection reductions.
* `candidate_rankings.csv`: diagnostic score/rank correspondence, best-of-sampled-pool ray, score-chosen candidate, one-step regret and negative-improvement flag. There is **no claim that the score-chosen ray was the actual online next ray**.
* `protocol.json`: source directories, parameters, verification counts, limitations.

All score calculation is acquired-only, via the existing `acquired_only_scores`. Ground truth and measurements of unacquired candidates are accessed **after** score calculation for the retrospective offline value. Each source policy's eligible diagnostic candidate pool differs because its acquired prefix differs; compare score policies *within* a source-history pool. Do not treat cross-history score differences as controlled causal comparisons. The sampled diagnostic pools are not guaranteed to include historically chosen next rays.

## Scientific cautions

* Repeated conditions on eight synthetic objects are not 256 independent objects. Aggregate by object before making across-object claims; report outcomes by family, numerical forward model, and noise condition.
* Gini/CV/view entropy describe sampling, not complete information content. No scanner dose/calibrated uncertainty inference.
* Fixed 16-epoch MART error maps are solver-dependent; 05B-09 addressed sensitivity to final epochs across its predefined grid.
* Correlation between coverage imbalance and RMSE loss does not prove spatial concentration *caused* the loss.
* Small sampled candidate pools and one-step offline value do not quantify full-budget sequential regret.
* This is intended to diagnose rather than tune against the same 08B phantom distribution.
