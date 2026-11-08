RBYRCT 05B-03: matched-prefix reliability diagnostic validation

Install: copy experiment_05b_03.py and test_experiment_05b_03.py into the
root of your existing rbyrct-3d-05a worktree (NOT inside a subfolder).

Tests:
    python -m pytest test_experiment_05b_03.py -q
    python -m pytest -q
    git diff --check

Small first run (8^3, selected cases):
    python experiment_05b_03.py --size 8 --angles 4 --factor 2 --phantoms branches --representations replicated --seeds 271828 --budget 128 --warm-rays 16 --batch 8 --switches 32 64 96 --provisional-epochs 4 --diagnostic-epochs 8 --mart-epochs 16 --mart-relaxation 0.25 --output-dir results/experiment05b/diagnostic_validation_8_first

Output files:
    matched_prefix_diagnostics.csv: diagnostic metrics and paired gains
    protocol.json: parameters and limitations

Notes:
- Acquired-only training/diagnostic, offline ground-truth evaluation.
- Uses existing experiment_05b_04s.continue_after_prefix to preserve
  candidate RNG and deterministic same-policy replay checks.
- Not a trained reliability gate: no thresholds are tuned or validated here.
- The same simulated phantom/seed contributes dependent prefixes.
- Use fresh output directories on each run.
- Results from historical 04-series scripts are not overwritten.
