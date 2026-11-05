# RBYRCT-08X — Detector-only mechanism disentanglement

## Scientific purpose

The completed, exploratory 08W intervention increased detector-position entropy and improved **whole-volume** MART RMSE relative to unmodified full-covariance Gaussian A-optimal ray selection on four 12³ phantoms at 144 and 288 rays. This does **not** establish that entropy alone caused the improvement. 08X asks whether a detector-diversity-only selector reproduces that behavior, or whether the Gaussian information term matters.

### Policies (all geometry-only)

1. `coverage` — original coverage reference.
2. `information_diag` — unchanged 08K diagonal Gaussian surrogate.
3. `information_full` — unchanged 08U full-covariance Gaussian A-optimal score.
4. `full_detector_diverse` — unchanged 08W fixed 0.25 detector novelty blend.
5. `detector_only` — new: choose the candidate with the fewest previous selections of its detector `(row, column)` bin; ties resolve to the lowest ray ID. Reward is `1 / (1 + detector_bin_count)`. No Gaussian information term.

All selectors use the same 24 warm rays, fixed acquisition seed, candidate-pool size 16, batch size 16, and 288-ray budget. Candidate pools are sampled by the same rule, but may diverge across policies once their selected histories differ. No measurements, defects, or truth are used to choose a ray.

### Fixed exploratory protocol

- Resolution: 12³; four new object seeds: 900201, 900202, 900203, 900204.
- Acquisition seed: 900411 + 12, as in the prior experiment's seeded convention.
- Two forward model conditions: `same` and `independent`.
- Five policies × two checkpoints (144 / 288 rays) × two models × four objects = **80 checkpoint reconstructions**.
- MART: 16 epochs, relaxation 0.25, unchanged synthetic noise and measurement definitions from 08W.
- 08W blend coefficient remains **0.25**; no coefficient fitting or selection after inspecting 08X errors.
- Primary *exploratory* comparison: `detector_only` versus `full_detector_diverse` on object-balanced whole-volume RMSE at 288 rays. Secondary descriptive comparisons: detector-only versus diagonal and full, defect RMSE, 144 rays, detector entropy, coverage.
- Only four independent objects; model conditions are repeated paired evaluations. No significance or universal-mechanism claim.

## Installation

Extract exactly these three files into the repository root: `experiment_08x.py`, `test_experiment_08x.py`, `README_08X.md`. Avoid creating a second nested copy of the test module because pytest will fail on duplicate names. 08X imports existing `experiment_08u.py`, `experiment_08k.py`, and older RBYRCT modules.

## Step A — tests and engineering-only preflight

```powershell
python -m pytest test_experiment_08x.py -q
python -m pytest -q
git diff --check

python experiment_08x.py --preflight `
    --output-dir results/experiment08x/engineering_first

Get-Content "results/experiment08x/engineering_first/preflight.json"
```

The preflight must report `complete: true`, `intervention_changes_order: true`, `alpha_zero_equals_full: true`, `intervention_deterministic: true`, `detector_only_deterministic: true`, and `detector_only_distinct_from_full: true`. Check `detector_entropy` and order fingerprints. No phantom truth or reconstruction outcomes are evaluated here.

**Preserve the passed preflight and commit the source BEFORE reconstruction**:

```powershell
git add experiment_08x.py test_experiment_08x.py README_08X.md
git diff --cached --check
git commit -m "Add detector-only mechanism disentanglement study"
git status --short
```

## Step B — exploratory reconstruction

```powershell
python experiment_08x.py --run `
    --preflight-dir results/experiment08x/engineering_first `
    --output-dir results/experiment08x/reconstruction_first

$dir = "results/experiment08x/reconstruction_first"
Get-Content "$dir/run_status.json"
Import-Csv "$dir/aggregate_summary.csv" | Format-Table -AutoSize
Import-Csv "$dir/mechanism_object_comparison.csv" | Format-Table -AutoSize
Import-Csv "$dir/geometry_summary.csv" | Format-Table -AutoSize
```

The script refuses to overwrite existing directories. If output directories already exist, inspect and preserve them and use `_second` paths rather than deleting them blindly. **Expected completed reconstructions: 80**.

### Archiving

After verifying the results, archive all outputs (including preflight and any failed attempts):

```powershell
Move-Item "results/experiment08x" "..\rbyrct-results\"
git restore -- ":(glob)__pycache__/*.pyc"
git status --short
```

Only run the move if the destination does not already exist.

## Interpretation safeguards

- Greater detector entropy is not inherently equivalent to lower MART RMSE.
- `full_detector_diverse` blends two min-max normalized signals within each candidate pool; `detector_only` optimizes only detector-bin novelty. Different acquisition trajectories confound straightforward attribution to a single geometric descriptor.
- A full Gaussian covariance criterion is not a MART posterior uncertainty measure.
- This study is **exploratory**, not a new independent validation. 08M and 08Q remain frozen and unchanged.
- The local package builder checked 16 unit tests; full integration requires the complete Windows repository with `experiment_05b_04` and older simulation modules.
