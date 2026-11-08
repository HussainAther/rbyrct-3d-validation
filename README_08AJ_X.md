# RBYRCT-08AJ-X — Estimand and independence-assumption review

**Status:** outcome-free scientific decision draft. NOT a source freeze; no scientific sign-off; confirmatory execution disabled.

## Decision proposed

**Primary reporting target (fixed benchmark):** the arithmetic mean of the 24 prespecified object-level paired gains under the fixed two acquisition seeds and two forward-model conditions. Every object contributes equally (8 per each of 3 families). For each condition, gain is `1 − RMSE_information_diag / RMSE_uniform_multiscale`, with a positive finite reference RMSE required. Average the four conditions *within each object*, then average objects. Report the exact point estimate, object-level values, three family means, and dispersion, without pretending that a sampling confidence interval quantifies uncertainty about this finite list.

**Optional secondary inferential target (conditional synthetic generator):** the equal-weight mean of the expected object-level gains from *independent repeat draws* of each of the three specified synthetic generators, holding the acquisition seeds and forward-model conditions fixed. Under credible independent draws, family-stratified Welch-Satterthwaite t can be prespecified as a conditional interval, with bootstrap-t sensitivity analysis. The three fixed families are not a random sample of imaging populations. The Monte Carlo finding from 08AJ-W does **not** establish object independence; family-shared shocks caused severe undercoverage in the hypothetical calibration.

**Interpretation:** These results would pertain to controlled synthetic imaging only; no inference to clinical CT, dose, patient benefit, or real scanning populations. Do not equate positive statistical gain with practical relevance. A 2% benchmark may be discussed as an engineering target only after explicit pre-outcome sign-off. An independent unit is the generated object, never one of its four repeat conditions or its voxels. Distinct random seeds/hashes do not establish structural novelty, and structurally related families should be described transparently.

### Statistical definition

Let `g[i,a,m] = 1 − RMSE_diag[i,a,m]/RMSE_uniform[i,a,m]` for object `i`, acquisition seed `a` and forward model `m`. Let `g[i]` average over the four `(a,m)` conditions. For fixed object sets `I_f` in each family `f`, `G_fixed = (1/3) ∑_f (1/8) ∑_{i∈I_f} g[i]`. This is an exactly computable finite-benchmark quantity after outcomes (subject to numerical integrity), not a random variable simply because it has 24 terms.

The generator estimand is `G_gen = (1/3) ∑_f E_f[g(X)]`, where the expectation is over hypothetical repeat draws from generator `f` only, with all other specified conditions fixed. Its interpretation and standard error require *scientific approval* of the random-generation model. For independent draws within each family, the proposed Welch variance estimator is `(1/9) ∑_f s_f²/8` and Satterthwaite degrees of freedom are `V² / ∑_f ((s_f²/72)²/7)`, where `V=(1/9)∑_f s_f²/8`. These formulas are only meaningful if model assumptions are justified.

### Unresolved decisions

1. Approve the primary finite-benchmark descriptive target; avoid an unqualified generalization claim.
2. Determine whether generator-resampling inference is scientifically justified; otherwise report inference as exploratory or omit confidence intervals.
3. If justified, approve Welch-t conditional inference and bootstrap-t sensitivity **before** outcomes.
4. Approve the three structurally related synthetic stress-test families' description.
5. Approve practical effect, missingness, computational failure and time/memory rules.
6. Finish and independently certify the *actual* 480-job prospective numerical executor and outcome auditor.
7. Obtain signed scientific approval, commit/hash-lock all sources, and only then authorize outcomes.

## Windows instructions

Extract four files into `rbyrct-3d-05a`: `experiment_08aj_x.py`, `experiment_08aj_x_audit.py`, `test_experiment_08aj_x.py`, `README_08AJ_X.md`. The script checks your existing `experiment_08aj_d.py`, `experiment_08aj_f.py`, `experiment_08aj_u.py`, and `experiment_08aj_w.py` sources.

```powershell
python -m pytest test_experiment_08aj_x.py -q
python experiment_08aj_x.py `
    --output-dir results\experiment08aj_x\estimand_review_first --mode prepare
python experiment_08aj_x.py `
    --output-dir results\experiment08aj_x\estimand_review_first --mode check
python experiment_08aj_x_audit.py `
    --output-dir results\experiment08aj_x\estimand_review_first
Get-Content results\experiment08aj_x\estimand_review_first\run_status.json
```

Expected: `X_ESTIMAND_REVIEW_PREPARED`, `X_ESTIMAND_SOURCE_MATCH`, and `X_INDEPENDENT_ESTIMAND_AUDIT_PASS`. This is a **decision gate**, not an approval gate. Use a new directory instead of overwriting an existing one.
