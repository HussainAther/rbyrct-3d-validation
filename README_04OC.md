# Experiment 04O-C: Prospective reliability-gated 3D acquisition pilot

## Research question

Can an acquired-only held-out residual signal reduce the failure of 04J reconstruction-driven selection under unresolved subvoxel structure, while retaining an advantage for exactly replicated objects? **04O-C is exploratory, not independent confirmation**. The threshold `2.0` is a predeclared engineering pilot value, **not** a validated threshold, not fitted on 04O-B's test folds, and not evidence of prospective utility.

### Four matched acquisition policies

- `adaptive_feedback`: exact frozen 04J feedback strength 1.0.
- `feedback_off_control`: exact frozen 04J strength 0.0.
- `constant_feedback`: constant strength 0.25, to measure whether merely weakening the heuristic suffices.
- `reliability_gate`: strength 1.0 when acquired-only held-out NRMSE <= 2.0; otherwise strength 0.0. Diagnostic check at the warm start and thereafter every 256 acquired rays (at the next batch boundary). During intervening batches, prior strength persists.

The exact frozen 04J candidate selection score, random candidate schedule and SIRT estimator are reused. The reliability diagnostic uses acquired observations only, fits using a training subset, evaluates a disjoint *acquired* holdout, and never reads phantom truth. An explicit guarded observation wrapper rejects unacquired measurement accesses. Final RMSE against ground truth is calculated only after acquisition is complete. The gate is not trained or validated on new phantom families: 04O-C uses existing 04N families and must not be advertised as independent replication.

**Important caveat:** The held-out rays themselves were adaptively sampled; the indicator can be biased and is not a detector calibration estimate. The default threshold is arbitrary/exploratory and must not be retrospectively changed to claim success on the same trials. Gate diagnostics add substantial processing time; `selection_timing.csv` reports full selector and diagnostic time, not detector or wall-clock hardware scan speed.

## Installation

Copy `experiment_04oc.py`, `test_experiment_04oc.py`, `README_04OC.md` into the repo with 04B through 04O-B. Dependencies are the same Python/NumPy/SciPy setup used in 04O-B.

## Tests

```powershell
conda activate rbyrct-3d
python -m unittest -v test_experiment_04oc.py
```

## Pilot: 64 reconstructions

```powershell
python experiment_04oc.py `
  --size 16 --angles 12 --factor 2 `
  --object-types replicated subvoxel `
  --offsets 0 0.15 `
  --phantoms torus beads `
  --seeds 104729 `
  --budgets 1024 2048 `
  --noise-fractions 0 `
  --warm-rays 128 --batch 64 `
  --provisional-iterations 60 --diagnostic-iterations 60 `
  --sirt-iterations 400 --candidate-pool 64 `
  --threshold 2.0 --gate-strength 0 `
  --constant-strength 0.25 --diagnostic-every 256 `
  --output-dir results/experiment04oc_pilot
```

8 scenarios (2 object types x 2 offsets x 2 phantoms), two budgets, four policies => **64 reconstructions**.

## Broader exploratory benchmark: 384 reconstructions

```powershell
python experiment_04oc.py `
  --size 16 --angles 12 --factor 2 `
  --object-types replicated subvoxel `
  --offsets 0 0.15 `
  --phantoms torus slats beads wedges `
  --seeds 104729 130363 155921 `
  --budgets 1024 2048 `
  --noise-fractions 0 `
  --warm-rays 128 --batch 64 `
  --provisional-iterations 60 --diagnostic-iterations 60 `
  --sirt-iterations 400 --candidate-pool 64 `
  --threshold 2.0 --gate-strength 0 `
  --constant-strength 0.25 --diagnostic-every 256 `
  --output-dir results/experiment04oc_full
```


## Outputs

- `metrics.csv`: final RMSE per policy and matched condition.
- `paired_cases.csv`: paired RMSE gain vs feedback-off for 04J, constant strength, and gate.
- `gate_trace.csv`: at each diagnostic checkpoint, measured error, train/holdout sizes, decision and acquired prefix.
- `divergence.csv`: acquisition order divergence compared with frozen 04J.
- `selection_timing.csv`: selector plus diagnostic time, versus final reconstruction time.
- `protocol.json`: all parameters and study caveats.

## Decision rule

Before any changes to threshold or score, compare gated policy against **both** feedback-off and constant feedback. Look for reduced negative tails under subvoxel mismatch and retained wins in replicated conditions, with timing. Any positive 04O-C results on the existing four families require a later 04P evaluation with truly novel phantom generators, fresh seeds, and a locked policy before making generalization claims.
