# RBYRCT-08M0 — 4,096-ray geometry-based information-selection engineering profile

**Scope:** Engineering feasibility only. No synthetic phantom is built; no forward measurements, defect masks, reconstructions, RMSE scores or prospective 08M scientific objects are used. This is **not** validation. Frozen 08K geometry-only information selection is imported unchanged, with 08J variance parameters unchanged (`PRIOR_VARIANCE=1`, `OBSERVATION_VARIANCE=1`).

## Inputs and fixed configuration

- Grid: `32³` (32,768 voxels); `ANGLES=4`, existing `TILTS` (12,288 candidate rays).
- Geometry: existing `experiment_04b.system_matrix`, CSR, unchanged.
- Warm order: existing `experiment_04h.voxel_coverage_order`, first 64 rays.
- Budget: 4,096; batch size 32; candidate pool size 16; engineering-only acquisition seed **811011**.
- Information selector: **exact** `experiment_08k.select_information`, run twice from the same warm order and geometry.
- Known-geometry information score: `a^T D² a / (sigma² + a^T D a)`, with diagonal precision proxy `D_j = 1/(tau^-2 + sum_{i acquired} A_ij²/sigma²)`. The proxy is **not** a posterior covariance for nonlinear MART.
- A `CommitOnly` substitute disallows reading measurement data; it tracks each acquired selection via `commit`.
- No object seeds are used. Do not substitute this engineering seed into the later 08M frozen scientific validation.

## Extract and test (PowerShell)

Extract the **three files** in the ZIP directly into your `rbyrct-3d-05a` repository root. Do not keep a duplicate nested directory inside the repository (pytest import-name collision).

```powershell
python -m pytest test_experiment_08m0.py -q
python -m pytest -q
git diff --check
```

## Full-budget engineering run

```powershell
python experiment_08m0.py `
  --output-dir results/experiment08m0/fullbudget_first
```

The program produces:

- `protocol.json`: frozen engineering parameters and scope;
- `profile.json`: matrix build timing, CSR bytes, shared coverage-order timing, information selector timings, RSS and peak working set if `psutil` supplies it, and whether the information order equals coverage;
- `policy_timing.csv`: separate records for both identical runs, including separate selection time and shared-coverage cost;
- `order_fingerprints.json`: SHA-256 hashes for full orders and the 1,024, 2,048 and 4,096-ray prefixes;
- `run_status.json`: `complete: true` only after both runs pass all ordering and repeatability checks;
- `engineering_manifest.sha256`: hashes of the report files.

Results are saved after each completed repeat, so a failed second repeat leaves partial evidence marked incomplete. No existing nonempty directory is overwritten.

## Inspect

```powershell
$dir = 'results/experiment08m0/fullbudget_first'
Get-Content "$dir/run_status.json"
Get-Content "$dir/profile.json"
Import-Csv "$dir/policy_timing.csv" | Format-List *
Get-Content "$dir/order_fingerprints.json"
```

A successful run must show `complete: true`, `completed_repeats: 2`, identical 4,096-ray and checkpoint hashes, 4,096 unique in-range selected rays, warm prefix preserved, and exactly 4,032 ordered post-warm commits in each repetition. Check the `information_identical_to_coverage` field rather than assuming the ordering is different. The Windows peak working-set value is process memory, **not** CSR-matrix storage.

Interpret the timings cautiously: `information_selection_seconds` covers the selector and excludes building the geometry and the common coverage reference. `selection_plus_common_coverage_seconds` adds the one-time shared reference cost; it does not represent two independent reference-order computations.

## After successful run

Only after `run_status.json` confirms complete:

```powershell
git add experiment_08m0.py test_experiment_08m0.py README_08M0.md
git diff --cached --check
git commit -m "Add 4096-ray information acquisition engineering preflight"
Move-Item 'results/experiment08m0' '..\rbyrct-results\'
git restore -- ":(glob)__pycache__/*.pyc"
git status --short
```

Before the full 08M validation, freeze a new scientific protocol with *different, previously unused object and acquisition seeds*. Engineering feasibility is not evidence for superior tomography or clinical performance.
