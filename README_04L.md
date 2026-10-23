# RBYRCT Experiment 04L — Feedback Mechanisms, Failure Modes, and Cost

## Scope

Post-04K diagnostic study. Uses **frozen** `experiment_04j.adaptive_order` and `experiment_04j.sirt_silent` plus the **existing 04K** phantoms. No new selection rule, no hyperparameter optimization, and no new independent validation claim. The objective is to understand why feedback wins on torus/slats/wedges but often provides minimal or negative gain on beads, how ray sequences differ, and what the computational overhead costs.

Run from the same directory as the existing `experiment_04b.py`, `experiment_04g.py`, `experiment_04h.py`, `experiment_04i.py`, `experiment_04j.py`, and `experiment_04k.py`.

## 1. Verify tests

```powershell
python -m unittest -v test_experiment_04l.py
```

## 2. Retrospective 04K analysis — no reconstruction required

```powershell
python experiment_04l.py `
  --mode audit `
  --input-dir results/experiment04k `
  --output-dir results/experiment04l_audit
```

Produces `paired_cases.csv`, `negative_cases.csv`, `family_budget.csv`, `timing_inventory.csv`, `divergence_inventory.csv`, and `audit.json` (where source CSVs exist). 04K `orders.csv` times for geometry-only greedy are for *one full maximum-budget order reused across cases*, while adaptive times are *online per case*. They must not be compared as equal units without amortization and a specified deployment workflow. Random and geometry-balanced ordering times were not measured.

## 3. Stress smoke test

```powershell
python experiment_04l.py `
  --mode stress --size 8 --angles 4 `
  --budgets 64 --warm-rays 32 --batch 32 `
  --provisional-iterations 10 --candidate-pool 16 `
  --sirt-iterations 10 20 --noise-fractions 0 0.03 `
  --seeds 104729 --phantoms torus beads `
  --output-dir results/experiment04l_smoke
```

The smoke test is **40 final reconstructions** and does not measure real CT acquisition.

## 4. Recommended diagnostic experiment

Start with a small, interpretable subset rather than the full combinatorial grid:

```powershell
python experiment_04l.py `
  --mode stress --size 16 --angles 12 `
  --budgets 512 1024 2048 `
  --warm-rays 128 --batch 64 `
  --provisional-iterations 60 --candidate-pool 64 `
  --sirt-iterations 200 400 800 `
  --noise-fractions 0 0.03 0.1 `
  --seeds 104729 `
  --phantoms torus beads slats wedges `
  --output-dir results/experiment04l_stress
```

This produces **540 final reconstructions** (4 phantoms × 3 budgets × 3 noise fractions × 3 final reconstruction settings × 5 policies). Each ray schedule is generated **once per phantom/seed/budget/noise** and reused at all final reconstruction iteration counts. The provisional SIRT is frozen at 60 iterations; any changes in final reconstruction accuracy are therefore attributable to evaluating the *same rays* at a different reconstruction iteration count. Extended repeated seeds can follow only after inspecting these results.

## 5. Files

Stress mode outputs `stress_metrics.csv`, `stress_pairs.csv`, `stress_summary.csv`, `stress_orders.csv`, `stress_coverage.csv`, `stress_divergence.csv`, `stress_trace.csv`, and `stress_protocol.json`.

Primary interpretation: `stress_pairs.csv` is a paired adaptive-vs-feedback-off comparison on the same object/seed/noise/budget/final-iteration settings. `stress_summary.csv` preserves the phantom family, noise, budget, and final-iteration dimensions. A relative gain of `(off_RMSE - adaptive_RMSE) / off_RMSE` is positive when adaptive wins.

## Limitations

- Diagnostic analysis of previously examined 04K synthetic phantoms; not a new independent validation set or preregistered hypothesis test.
- Stress-noise fractions mean `sigma = fraction * RMS(full clean candidate projections)`, i.i.d. Gaussian additive noise. Not Poisson photon statistics, detector scatter, or dose estimation.
- 04B CPU sparse matrix is used as both forward and inverse model: matched-operator inverse crime.
- The 04J selector's gradient score is heuristic; not a calibrated Bayesian uncertainty metric.
- Report overhead with acquisition throughput/availability assumptions; ray selection cost and physical steering feasibility are separate from SIRT reconstruction time.
- 3 seeds × 3 noise levels on one synthetic phantom are not nine independent anatomical samples.

## Git commands

```powershell
git switch -c experiment-04l
git add experiment_04l.py test_experiment_04l.py README_04L.md
git commit -m "Add 04L frozen-feedback mechanisms and stress diagnostics"
git push -u origin experiment-04l
```

The existing `experiment-04k` branch and `v0.4k-validation` tag should remain unchanged. Commit diagnostic *summaries* separately only after reviewing the repository's data policy; do not commit large generated results blindly.
