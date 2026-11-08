# RBYRCT-08AJ-W: Statistical Method Review and Dependence Sensitivity

**Status:** CONDITIONAL RECOMMENDATION ONLY. The proposed confirmatory 24-object study is NOT frozen and execution remains prohibited.

## Scope

This package uses *only hypothetical gains* (no MART or RBYRCT reconstruction outcomes). The estimand is an equally weighted average of three fixed synthetic families, each with eight independent hypothetical objects; the primary analysis averages 2 acquisition seeds x 2 forward models within each object before computing the family-weighted overall mean. Its conclusions **do not establish that real objects are independent**.

We test normal, centered exponential, t(3) heavy tail, and unequal-family variance scenarios. Hypothetical means are 0% and 2%, hypothetical object SDs 3% and 6%, with common-family latent-shock mixing rho = 0, 0.15, and 0.35. There are 4 scenarios x 3 rho settings x 2 SDs x 2 means x 4 methods = **192 rows**. The rho values are *latent shock mixing parameters*, not necessarily observed Pearson correlations (especially for non-Gaussian noise).

Methods: stratified percentile bootstrap, stratified basic bootstrap, stratified bootstrap-t, and an analytical family-stratified Welch-Satterthwaite t interval. Bootstrap methods resample whole hypothetical object-level gains within each of the three fixed families. The true gain and the 2% relevance threshold are not interchangeable: confidence that mean gain > 0 is a different question from confidence that mean gain > 2%.

## Results of the local 600-trial / 400-resample run

Independent-object scenario mean coverages: percentile 90.65%, basic 90.94%, bootstrap-t 94.55%, Welch-t 95.22%. This is an unweighted mean across 16 hypothetical independent-object settings, not a formal performance guarantee. The lowest estimated coverage for Welch-t was 92% in an individual setting. These values have Monte Carlo uncertainty and simulation-design limitations.

Welch-t sensitivity to shared within-family shocks: at rho = 0.15, mean coverage ~79.58%; rho = 0.35, ~61.98%. This demonstrates the potential inferential failure **if** object gains have within-family dependence, not evidence that the 24 prospective objects actually do.

**Conditional recommendation:** use family-stratified Welch-t as the primary interval *only if* the object-independence assumptions and the fixed-family estimand are scientifically accepted. Report bootstrap-t as a sensitivity analysis. If objects are effectively correlated within families, do not simply use a 24-independent-object confidence interval; revisit experimental units, population estimand, and design. Three families alone cannot support reliable population-level cluster inference.

## Windows PowerShell

Extract `experiment_08aj_w.py`, `experiment_08aj_w_audit.py`, `test_experiment_08aj_w.py`, and dependency `experiment_08aj_v.py` into the repo. If you already have `experiment_08aj_v.py`, keep your verified original; it should implement the same underlying interval functions.

```powershell
python -m pytest test_experiment_08aj_w.py -q

python experiment_08aj_w.py `
    --output-dir results\experiment08aj_w\method_review_first `
    --trials 600 --bootstraps 400

python experiment_08aj_w_audit.py `
    --output-dir results\experiment08aj_w\method_review_first

Get-Content results\experiment08aj_w\method_review_first\run_status.json
```

Expected verdicts `W_STATISTICAL_METHOD_REVIEW_PREPARED` and `W_INDEPENDENT_AUDIT_PASS`; expected settings = 192. The output directory must not already exist. For a more precise Monte Carlo comparison, launch a separate new directory with `--trials 2000 --bootstraps 1000` (slower); this still does not resolve structural dependence.

## Decision blockers not cleared

- Review whether the fixed-family synthetic benchmark and independent object-level units are scientifically defensible.
- Confirm the analysis estimand, interval method, asymmetry/outlier sensitivity, and effect threshold with scientific review.
- Finalize failure and resource ceilings.
- Complete production 480-job numerical executor and independent outcome audit, then source lock and sign-off.

**No outcome-based method tuning, confirmatory execution, or automatic sign-off is permitted.**
