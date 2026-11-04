# RBYRCT-05B-06 — Offline candidate-ranking audit

This new study does not modify any existing 05B or historical 04 acquisition policy.

It audits fixed candidate pools sampled independently of the frozen source-policy
trajectory. Each candidate is ranked by four acquired-only score formulas, then
**retrospectively** receives its synthetic measurement and is appended as one ray
for a fixed-epoch MART reconstruction from the standard positive initialization.

Offline outcomes are the change in ground-truth RMSE and the change in prediction
error on disjoint unacquired validation rays. Neither outcome enters online
acquisition or the scoring procedure.

Outputs:
- `candidate_counterfactuals.csv`: four policy scores plus one-ray outcomes.
- `ranking_diagnostics.csv`: Spearman score/benefit association, preferred
  candidate, offline best candidate, and one-step regret.
- `protocol.json`: parameters, scientific limitations, and evaluation definitions.

Run `python -m pytest test_experiment_05b_06.py -q`, then the full suite.

Example quick run:

```powershell
python experiment_05b_06.py `
  --size 8 --angles 4 --factor 2 `
  --phantoms branches defects --representations replicated `
  --seeds 271828 314159 577215 `
  --budget 128 --warm-rays 16 --batch 8 `
  --candidate-pool 16 --audit-candidates 8 `
  --checkpoints 16 48 80 112 `
  --provisional-epochs 4 --mart-epochs 16 --mart-relaxation 0.25 `
  --feature-cap 3 --source-policy coverage `
  --output-dir results/experiment05b/ranking_audit_8_first
```

**Interpretation:** One-ray counterfactual gains are *not* final-budget gains.
A positive correlation is preliminary association, not proof of acquisition
advantage. No new score is trained, selected, or deployed in this experiment.
