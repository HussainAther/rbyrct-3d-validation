# RBYRCT-06A2 — bounded 8³ development evaluation

**Purpose:** Compare frozen coverage-only, gradient, strict coverage guard (eta=0), and the previously proposed 5% guard (eta=0.05), **without** tuning on held-out results. This is an **exploratory development experiment**, not confirmatory evidence of an RBYRCT performance advantage.

## Frozen design

- Reconstruction volume: 8 × 8 × 8; 4 azimuthal settings and the existing three tilts; fine-grid factor 2; zero geometry offset.
- Existing 05B-04P **development** analytic phantom families: branches, layers, defects; each in replicated and subvoxel representations. These are deterministic family definitions, **not six independently sampled new objects**.
- Acquisition seeds: 271828 and 314159 (not independent phantom replications).
- Budget 128 rays; warm prefix 16; batches 8; candidate pool 16; acquired-only selection.
- Provisional MART 4 epochs, final MART 16 epochs, relaxation 0.25; noiseless simulated projection data, original fine-resolution Siddon-like operator.
- Four policies: `coverage` (existing 05B-04 selector), `gradient` (existing 05B-04 selector), `strict` (06A eta=0) and `guarded_05` (06A eta=0.05). Neither the MART reconstruction nor the acquisition score/guard is modified.
- **48 policy-case rows** = 3 families × 2 representations × 2 acquisition seeds × 4 policies.
- One development run only; do not search eta values based on these outcomes.

## Install on Windows

Extract these three files **directly into** `C:\Users\shuss\Downloads\rbyrct-3d-05a` on the current `experiment-05b-mart-restoration` branch:

```powershell
python -m pytest test_experiment_06a2.py -q
python -m pytest -q
git diff --check
python experiment_06a2.py `
    --output-dir results/experiment06a2/development_first
```

Expected focused tests: 5; prior full suite 144, expected 149 if no other changes. The script refuses to overwrite a nonempty output directory; use a new directory for any deliberate repeat.

## Outputs

- `development_cases.csv`: per-scenario RMSE, paired gain, overlapping ray count, runtime, SHA-256 ray fingerprint and oracle-access assertion.
- `guard_batch_audit.csv`: number of admissible candidates, guard binding and coverage-reference frequency per acquisition batch (strict and guarded only).
- `development_summary.csv`: descriptive summaries by family, representation, and policy.
- `protocol.json`: exact parameter choices and inferential cautions.

**Interpretation:** An adaptive policy can be meaningfully different from coverage-only without achieving better RMSE. A strict guard need not reproduce coverage-only. The `eta=+inf` equivalence to the frozen gradient selection is tested separately. Ground truth and full simulated projections are used for OFFLINE RMSE only; access to unacquired observations is blocked during selection. Acquisition seeds are computational replicates, not distinct physical or biological objects.

## Freeze before prospective 06B

After inspecting this single development comparison, decide whether to freeze `guarded_05` unchanged (or declare it unsuitable). Any fresh 06B validation objects, 3D scale, model-mismatch conditions, baselines, outcome criteria, and stopping rule must be set before looking at those results. Do **not** tune using 05B-08B or 05B-11 held-out results.
