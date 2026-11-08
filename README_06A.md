# RBYRCT-06A — Coverage-guarded sequential MART acquisition (development)

**Purpose:** Prototype a geometric safeguard around the existing gradient candidate ranking. This is **development-only**; it is not a held-out superiority study.

## Motivation and literature boundary

- Earlier 05B results show gradient-guided selection can be inferior to coverage-only, and simple spatial inequality alone does not fully predict policy gains.
- Adaptive projection selection, edge-weighted design, and Bayesian A/D-optimal acquisition already exist. See Burger et al. (2021), *Inverse Problems* 37:075006, DOI `10.1088/1361-6420/ac01a4` and Helin et al. (2022), *SIAM J. Sci. Comput.*, DOI `10.1137/21M1409330`.
- **No novelty claim:** 06A is one testable engineering candidate. The distinction from Bayesian design is that it uses a point-estimate MART gradient and an explicit geometry-only safeguard; it does not use posterior covariance or expected information gain.

## Exact decision rule

At each candidate pool `P_t`, the frozen coverage score chooses reference ray `a_c` (same candidate RNG, coverage counts, and view balancing as 05B).

Let `c_t` denote accumulated voxel path-length weights, and `w_a` the candidate's sparse ray-weight row. Define `C_t(a) = Var_v(c_t[v] + w_a[v])`. A candidate is allowed when

`C_t(a) <= C_t(a_c) + eta * max(C_t(a_c), 1e-12)`.

Select the eligible candidate maximizing the **unchanged** 05B gradient-weighted score. Break score ties by lowest ray ID. The reference is always eligible. `eta=0` imposes the strongest guard relative to the reference, `eta=+inf` exactly recovers the gradient score **within each fixed pool**. `eta=.05` is a **prototype engineering setting, not empirically optimized or validated**. A strict guard need not equal coverage-only, because other candidates may have lower imbalance yet a higher gradient score.

All information used before selecting the next batch is the matrix geometry, acquired-ray counts/viewcounts, and MART reconstruction of **already measured rays**. Candidates' unmeasured intensities and phantom ground truth are never read.

## Install / run on your Windows branch

Unzip directly into `C:\Users\shuss\Downloads\rbyrct-3d-05a` (no nested folder):

```powershell
python -m pytest test_experiment_06a.py -q
python -m pytest -q
git diff --check
python experiment_06a.py --output-dir results/experiment06a/development_smoke_first
```

The 4³ manufactured synthetic smoke produces `development_runs.csv`, `batch_audit.csv`, and `protocol.json`. **No RMSE or performance ranking is reported**; the test only checks behavior and computational feasibility.

## Next milestone and safeguards

1. Review the score and constraint geometry, and inspect admissibility rates to confirm the method does something nontrivial.
2. Decide a **single** 06A development configuration, with guard tolerance chosen for interpretability—not by searching held-out 05B successes.
3. Freeze code, policy parameters, object generator seeds, comparators (coverage, gradient, 06A), budget checkpoints, primary estimand, acceptance criteria, and stop rule **before** creating fresh 06B held-out objects.
4. Evaluate prospective 06B only once; report positive, negative, and inconclusive outcomes. No evaluation on 05B-08B or 05B-11 objects for hyperparameter tuning.

Do not interpret the 4³ smoke as evidence of 12³ or practical CT performance, dose reduction, or measurement savings.
