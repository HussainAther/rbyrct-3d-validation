# RBYRCT-08G — Acquired-only split-history disagreement score (development)

## Purpose

Test an **observable, defect-agnostic candidate ranking proxy**, without replacing any frozen or existing acquisition selector. This is a *development-only ranking experiment*, not a scientific validation of reconstruction gains or a deployable new policy.

**What changed:** 08G computes a new candidate score at saved 08E-style probe states. **What did not change:** original 08E gradient and `incremental_25` acquisition decisions, sampling RNG, MART acquisition settings, ground-truth-free selector, or the earlier 06B/07C2 frozen studies.

### Derivation

For already acquired ray IDs `H_t`, let `A_H` be the known sparse projection rows and `y_H` their measured detector values. Split the acquisition *order* deterministically into even and odd positions, forming two disjoint acquired-only datasets. Reconstruct positive MART estimates `x_even` and `x_odd` with eight epochs and relaxation 0.25. For any unacquired candidate ray with **known geometry** `a` define:

```
S_disagree(a | H_t) = abs(a @ (x_even - x_odd)) / max(sum(abs(a)), 1e-12)
```

This is a normalized disagreement in predicted line-integral average (more precisely, a path-weighted value), **not** a calibrated posterior variance or a predicted error reduction. It requires no measurement of the candidate ray. Sorting higher scores first (tie: smaller ray ID) is the **hypothetical** new ranking assessed retrospectively.

A weakness to investigate is that disjoint-subset reconstructions may disagree because each half is underdetermined or has anisotropic geometric coverage. This score is a heuristic proposed for mechanistic testing, not a mathematical guarantee of information gain.

### Data, separation and evaluation

- New development object seeds: `809101`, `809102` at 12³; `809201`, `809202` at 32³. These are distinct from the 08E, 08C, 06B and 07C2 seeds.
- Exactly the 08E-style **original acquisition policies** (`gradient`, `incremental_25`), 2 probe states/history, pool of 16, matched forward model.
- 12³ budget 144, warm 24; 32³ budget 512, warm 64. 8 histories total, 16 probe pools, expected 256 candidate records.
- Ground truth, regenerated defect mask and unmeasured candidate intensities are used **only after an entire acquisition history has finished** for retrospective one-ray labels. They are **never inputs** to `disagreement_score`.
- `candidate_diagnostics.csv` contains score and retrospective candidate evaluation rows; `object_balanced_summary.csv` compares within-pool score–benefit correlations and hypothetical top-disagreement-ray regret against actual gradient/incremental selections, aggregated by object first.
- Hypothetical regret is **one-ray local counterfactual** regret and does not predict end-to-end sequential acquisitions under a changed score. Candidate sets and reconstruction states differ across the two existing policies; comparisons are descriptive.

### Install

Unzip the three new files **directly into** `rbyrct-3d-05a` (avoid duplicate nested copies):

- `experiment_08g.py`
- `test_experiment_08g.py`
- `README_08G.md`

08G **imports `experiment_08e.py`** and the prior modules already in the Windows repository; do not replace those source files. No additional numerical package beyond existing `numpy`, `scipy`, `pytest` is intended.

### Windows PowerShell

```powershell
python -m pytest test_experiment_08g.py -q
python -m pytest -q
git diff --check

python experiment_08g.py `
    --output-dir results/experiment08g/disagreement_first

$dir = "results/experiment08g/disagreement_first"
Get-Content "$dir/run_status.json"
Import-Csv "$dir/object_balanced_summary.csv" |
    Select-Object size,policy,n_objects,n_pools,disagreement_defect_regret,gradient_selected_defect_regret,disagreement_global_regret,gradient_selected_global_regret,disagreement_score_vs_defect_spearman,gradient_score_vs_defect_spearman,same_selected_ray |
    Format-List
```

`run_status.json` must show `complete: true`. The runner rejects overwriting existing output. `sha256.json` preserves result-file hashes. Please do not commit the outcome files to the main code repository before inspecting them.

### Interpreting results

- Better *retrospective* rankings would motivate a **separate** acquired-only acquisition implementation and later development-only reconstruction comparisons.
- A good correlation can arise even when a hypothetical selected ray is rarely the best candidate. Inspect both rank correlation and regret.
- With two objects per size, this is **not** a held-out or statistically powered experiment. Do not claim superiority of a new acquisition strategy from it.
- Split-history instability may reflect geometric undersampling, noise and reconstruction initialization. No assertion of calibrated uncertainty or physical CT dose reduction is made.

### Local verification status

Six isolated focused tests passed in the provided development environment. A complete end-to-end run and whole-repository test suite **have not been executed here** because the local snapshot lacks some older original project modules. Run both on your intact Windows repo.
