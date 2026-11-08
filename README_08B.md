# RBYRCT-08B: Acquired-Only Incremental Guard Integration

**Development-only acquisition mechanics. No reconstruction-accuracy experiment.**

## What changed

- Adds `experiment_08b.py`, alongside the unchanged `experiment_08a.py` math and frozen selectors.
- Uses exactly the original gradient candidate pool sampling (`default_rng(seed+317)`), coverage reference scoring, feature scoring, and deterministic ray-ID tie breaking.
- Replaces only the eligibility rule with 08A's incremental-variance guard, at the predeclared development setting `lambda=0.25`.
- Retains `AcquiredOnly` and only commits new observations *after* an entire batch of ray IDs has been selected. No phantom or evaluation mask enters `select_incremental`.
- Compares coverage, gradient, incremental_25 on new manufactured positive signals. Signals create measurements but are never used to calculate reconstruction accuracy.
- Reports guard-binding choices, actual interventions on the unconstrained gradient best ray from the same pool, ray-history differences, timing, hashes, and batch diagnostics.

## Run (PowerShell, repository root)

```powershell
python -m pytest test_experiment_08b.py -q
python -m pytest -q
git diff --check
python experiment_08b.py --output-dir results/experiment08b/acquisition_first
$dir = 'results/experiment08b/acquisition_first'
Import-Csv "$dir/policy_summary.csv" | Format-Table size,signal_seed,policy,budget,selection_seconds,guard_binding_choices,guard_intervention_choices,same_as_gradient -AutoSize
```

For a narrower single-resolution dry run, use `--size 12` with a **different empty output directory**.

## Scope and interpretation

Default geometry is 12^3 at 288 rays (24 warm, batches of 16), and 32^3 at 1024 rays (64 warm, batches of 32); candidate pool is 16 and provisional MART is 2 epochs. Two *new* manufactured signals are used per resolution, with an 08-series acquisition seed. This is not the frozen 12^3 or 32^3 study design.

A 'guard-binding choice' means at least one candidate was excluded. An 'intervention choice' means the guard changed the best gradient candidate within the **same current pool**. Neither is guaranteed to imply that the end-to-end trajectory differs, so the runner also reports paired ray-order fingerprints and per-position matches.

Even if the new selector diverges from gradient, these data establish **mechanics and reproducibility only**, not improved reconstruction quality, physical dose, noise robustness, or defect detection. No 06B/07C2 output files are accessed; those results remain frozen.

Note: Running the full 32^3 acquisition profile may take longer than tests. The output directory must not preexist with files. The code does not claim a historical source-code branch matches the user’s local Git commit; validate tests on the user’s machine before committing.
