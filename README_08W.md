# RBYRCT-08W: Detector-diversity intervention on full-covariance A-optimal ray ordering

**Scientific scope:** exploratory development intervention, not confirmatory validation. This tests a prespecified hypothesis suggested by retrospective 08V, on four fresh synthetic 12^3 localized-defect objects. No reuse of 08U objects, no edit to frozen 08M/08Q archives.

## Protocol (fixed before outcomes)

- Resolution: 12^3, ray budget 288, checkpoints 144/288, warm-up 24, batch 16, candidates per decision 16.
- Four acquisition policies: `coverage`, `information_diag`, `information_full`, `full_detector_diverse`.
- Four new object seeds: `890201`, `890202`, `890203`, `890204`.
- Same and independent forward-model measurements, paired within objects (4 x 2 x 4 x 2 = **64 reconstruction records**).
- Same reconstruction protocol as 08U: 16 MART epochs, relaxation 0.25, measurement-noise fraction 0.005.
- **Precommitted intervention** (no grid search): for every sampled candidate pool, compute full-covariance one-step Gaussian A-optimal score `s` and detector-bin novelty `v=1/(1+prior selected rays in detector bin)`. Normalize both to [0,1] over the *current* pool, or 0 when constant, and choose the ray maximizing `0.75*normalize(s) + 0.25*normalize(v)`; ties resolved by lowest ray ID. Detector bin is ray ID modulo `size^2`, pooling across projection views.
- At zero weight, the selector MUST reproduce the original full-covariance acquisition order.
- Object-balanced gains are computed by first averaging matched/independent forward models within each object. No hypothesis-test significance or causal mechanism claim is supported with four objects sharing the same acquisition geometry/order.

**Important:** Per-pool score rescaling changes the numeric objective; it is a heuristic intervention, not A-optimality itself. Geometry-only acquisition does not use detector values or defect masks. Higher detector entropy is not guaranteed, and even if higher it cannot establish a causal explanation for better reconstruction.

## Windows run

Extract ONLY the three root-level package files directly into `C:\Users\shuss\Downloads\rbyrct-3d-05a`, not into a nested directory (duplicate test files cause pytest import errors).

```powershell
python -m pytest test_experiment_08w.py -q
python -m pytest -q
git diff --check
```

**Phase A — no truth or reconstruction:**

```powershell
python experiment_08w.py --preflight `
    --output-dir results/experiment08w/engineering_first

Get-Content results/experiment08w/engineering_first/preflight.json
```

Preflight must show `complete: true`, `intervention_deterministic: true`, `alpha_zero_equals_full: true` and `intervention_changes_order: true`. Review the detector entropies without changing the fixed 0.25 weight.

**Phase B — new exploratory phantoms:**

```powershell
python experiment_08w.py --run `
    --preflight-dir results/experiment08w/engineering_first `
    --output-dir results/experiment08w/reconstruction_first

$dir = "results/experiment08w/reconstruction_first"
Get-Content "$dir/run_status.json"
Import-Csv "$dir/aggregate_summary.csv" | Format-Table -AutoSize
Import-Csv "$dir/diverse_vs_full_object.csv" | Format-Table -AutoSize
Import-Csv "$dir/geometry_summary.csv" | Format-Table -AutoSize
```

The script refuses to overwrite existing directories. If there is an interrupted output, preserve it and use a new output directory; do not delete partial evidence.

**After successful execution:**

```powershell
git add experiment_08w.py test_experiment_08w.py README_08W.md
git diff --cached --check
git commit -m "Add detector-diversity intervention in Gaussian A-optimal acquisition"
Move-Item "results/experiment08w" "..\rbyrct-results\"
git restore -- ":(glob)__pycache__/*.pyc"
git status --short
```

Archive the failed, preflight and completed trials together. Do not modify or rerun frozen 08M based on 08W outcomes.
