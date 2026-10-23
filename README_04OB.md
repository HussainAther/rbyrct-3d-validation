# RBYRCT Experiment 04O-B — Checkpoint Reliability Audit

**Purpose:** Test whether reliability indicators available from already acquired rays predict whether frozen 04J adaptive acquisition helps or hurts relative to feedback-off. This is **not** a gated policy, not a new optimization pass, and not independent confirmation.

## Installation

Copy these three files alongside `experiment_04o.py`, `experiment_04n.py`, and the existing scripts `experiment_04b.py` through `experiment_04m.py`:

- `experiment_04ob.py`
- `test_experiment_04ob.py`
- `README_04OB.md`

The unmodified 04O-A output directory must contain `paired_cases.csv` and `protocol.json`. The script validates important replay parameters against that protocol and refuses mismatches.

## Tests

```powershell
python -m unittest -v test_experiment_04ob.py
```

## Full experiment (reuses the already completed 04O-A truth labels)

```powershell
python experiment_04ob.py `
  --paired-cases results/experiment04o_a/paired_cases.csv `
  --size 16 --angles 12 --factor 2 `
  --warm-rays 128 --batch 64 `
  --provisional-iterations 60 `
  --diagnostic-iterations 60 `
  --candidate-pool 64 `
  --holdout-fraction 0.2 `
  --checkpoints 128 256 448 768 960 1536 `
  --output-dir results/experiment04ob
```

**Computation note:** The experiment rebuilds the forward models, replays all 288 frozen adaptive schedules, and fits several provisional reconstructions per case. There are **no additional final reconstruction comparisons**; the final RMSE labels come from the completed 04O-A run. This may take significant time.

The checkpoints are **strictly before** each case's final acquisition budget. A 512-ray case uses checkpoints 128, 256 and 448; a 1024-ray case uses 128, 256, 448, 768 and 960; a 2048-ray case adds 1536. The earliest/latest/delta signals are defined within each budget. Feature deltas are *not* automatically comparable across final budgets because the last checkpoint differs. Checkpoint signals use acquired measurements only; final labels use ground-truth reconstruction error, offline.

## Files produced

- `checkpoint_signals.csv` — held-out NRMSE, split feature correlation and instability at each checkpoint, with all case identifiers.
- `case_features.csv` — fixed latest, first-to-latest change, and across-checkpoint mean for held-out NRMSE and instability.
- `associations.csv` — within-budget Pearson and failure-oriented ROC AUC (higher metric means greater failure risk).
- `leave_one_phantom_out.csv` — thresholds fitted on three phantom families, tested on the fourth, at fixed budget. Includes accuracy, balanced accuracy, simple majority baseline, and failure ROC AUC.
- `protocol.json` — full provenance and limitations.

## How to interpret results

- AUC = 0.5 indicates no discrimination; AUC = 1 indicates perfect separation with the assumed risk direction; AUC less than 0.5 means the direction may be reversed.
- AUC and balanced accuracy are undefined when the held-out family contains only wins or only losses. Other classification metrics may still be reported, but must be interpreted with the base rate.
- A high within-sample correlation is not evidence of out-of-family predictive performance. Look at `leave_one_phantom_out.csv`, and compare accuracy with the majority-class baseline.
- The held-out-ray diagnostic samples rays from the *already acquired* adaptive trajectory. It does not protect against selection bias or certify hardware noise robustness.
- Only four existing phantom families are evaluated: a family-holdout analysis is exploratory, not a validation on genuinely new object families.
- The adaptive selector and its 04J scoring policy are **unchanged**. 04O-C should not proceed until the held-out results justify a gate.

## A sensible stop/go decision

Favor a gate only if one predeclared feature has consistent held-out performance across budgets and families, beats majority baselines, does not use future observations, and isn't simply detecting acquisition budget. If none meets these tests, preserve the negative result and redesign the signal before attempting a gate.
