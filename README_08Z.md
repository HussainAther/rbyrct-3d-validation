# RBYRCT-08Z — Prespecified spatial-sensitivity concentration intervention

**Purpose.** Exploratory mechanism test following retrospective 08Y. Determine whether a geometry-only penalty against repeatedly sampling already-sensitive voxels changes whole-volume and localized-defect MART reconstruction relative to unmodified full-covariance Gaussian A-optimal ray ordering. This is **not** a confirmatory 3D superiority claim, dose estimate, or independent physical validation.

## Fixed protocol, before reconstruction outcomes

- Four fresh **development** phantom seeds: `910201`, `910202`, `910203`, `910204` (not 08M/08U/08W/08X objects).
- `12^3` volume, four azimuths, same tilt geometry and two forward-model conditions (`same`, `independent`) as 08W.
- Four policies: `coverage`, `information_diag`, `information_full`, `full_spatial_balanced`.
- Ray budget `288`, checkpoints `144/288`, common warm start `24`, sampled candidate pool `16`, batches `16`.
- MART `16` epochs, relaxation `0.25`, noise fraction `0.005`.
- `4 objects × 2 measurement-model conditions × 4 policies × 2 checkpoints = 64` reconstruction records; object is the independent unit (not 64 independent experiments).
- Weights **fixed**: 75% normalized full-covariance Gaussian one-step A-optimal score and 25% normalized spatial novelty, within the same deterministic candidate pools. No post-outcome weight tuning.

### Mathematical intervention

For acquired prefix H, let `w_j = sum_{i in H} |A_ij|`. Candidate spatial novelty is

`N(a) = -sum_j |a_j| w_j / sum_j |a_j|`.

For each candidate pool independently, rescale the full-covariance Gaussian score `S_full(a)` and novelty `N(a)` to `[0,1]` by min–max (constant components map to zero). Select the highest

`0.75 normalize(S_full(a)) + 0.25 normalize(N(a))`

with deterministic lowest-ray-ID tie resolution. Zero coefficient must reproduce unmodified exact full-covariance ray ordering. The reward is **not** Gini itself: it discourages high already-accumulated sensitivity along the candidate path. Its effect on actual weighted-sensitivity Gini must be *measured*, not assumed.

### Engineering gate

Before seeing any phantom or reconstruction outcomes, 08Z checks that:

1. No object truth or detector measurements are used for ordering.
2. The modified order differs from the original full-covariance order.
3. Selection is deterministic.
4. `alpha=0` exactly reproduces unmodified full covariance.
5. Weighted-voxel-sensitivity Gini is **strictly lower** for the modified policy than for full covariance at both `144` and `288` rays.

If either checkpoint fails the Gini gate, the preflight prints/saves the evidence, marks `complete: false` and stops. **Do not reweight or change selectors using new reconstruction outcomes.** A failed directional preflight is a legitimate engineering finding.

## Windows run from repository root

Extract exactly `experiment_08z.py`, `test_experiment_08z.py`, `README_08Z.md` into your existing `rbyrct-3d-05a` root (not a nested folder).

```powershell
python -m pytest test_experiment_08z.py -q
python -m pytest -q
python -m py_compile experiment_08z.py
git add experiment_08z.py test_experiment_08z.py README_08Z.md
git diff --cached --check
```

**Engineering only:**

```powershell
python experiment_08z.py --preflight `
    --output-dir results/experiment08z/engineering_first

Get-Content "results/experiment08z/engineering_first/preflight.json"
```

Require `complete: true`, `intervention_changes_order: true`, `intervention_deterministic: true`, `alpha_zero_equals_full: true`, and both `spatial_gini_reduced_at_checkpoints` values `true`. The new geometry seed was tested locally for this direction, but **the full end-to-end preflight must pass in your Windows checkout**.

**Commit the fixed implementation before looking at the new reconstruction outcomes:**

```powershell
git diff --cached --check
git commit -m "Add spatial-sensitivity intervention for 3D MART acquisition"
```

**Exploratory outcome run (only after passing preflight):**

```powershell
python experiment_08z.py --run `
    --preflight-dir results/experiment08z/engineering_first `
    --output-dir results/experiment08z/reconstruction_first

$dir = "results/experiment08z/reconstruction_first"
Get-Content "$dir/run_status.json"
Import-Csv "$dir/aggregate_summary.csv" | Format-Table -AutoSize
Import-Csv "$dir/spatial_vs_full_object.csv" | Format-Table -AutoSize
Import-Csv "$dir/geometry_summary.csv" | Format-Table -AutoSize
```

Results include acquisition-order fingerprints, source geometry summary, per-object paired error summaries, manifest and output SHA-256 hashes. Raw output directories are **write-once**; do not delete failed or partial runs. Choose a new directory name for a retry.

**After analysis:**

```powershell
Move-Item "results/experiment08z" "..\rbyrct-results\"
git restore -- ":(glob)__pycache__/*.pyc"
git status --short
```

Check destination does not already exist before moving. The 08M frozen protocol and 08Q replay are unchanged.

## Manuscript interpretation boundaries

The 08Y observation that diagonal orderings had lower weighted sensitivity Gini is *descriptive*. 08Z tests the **combined spatial-novelty scoring intervention**, not causal effects of Gini itself. A successful Gini shift plus lower RMSE is consistent with the hypothesis but cannot prove that the Gini shift is the mediator. Report all four policies, both checkpoints, all four objects, and both forward-model conditions whether favorable or unfavorable. Compare paired object-level outcomes; do not count forward models/checkpoints as independent samples. Do not call Gaussian covariance a MART posterior. Do not claim clinical, real-data, dose, or broad 3D tomography benefits from synthetic 12^3 exploratory tests.

A high-impact manuscript should lean on the frozen, independently audited 08M 32^3 result, while disclosing limitations and adding genuinely external/physical validation and stronger baselines—not on filtering mechanism studies for positive outcomes.
