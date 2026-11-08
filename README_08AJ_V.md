# RBYRCT-08AJ-V — Hypothetical inference calibration (not frozen)

**Purpose:** Sensitivity-analysis evidence for the proposed 08AJ-D object-level paired gain, *not* reconstruction evidence and *not* a source lock. This stage neither imports the forward projector/MART solver nor executes any confirmatory job.

## Proposed estimand retained

- 24 objects, **eight in each of three fixed families**. Each object's four paired condition-specific gains (two acquisition seeds × same/independent forward models) would first be averaged within that object.
- The study-level estimand is the **equally weighted mean of the three family mean gains**. It is not an estimate for a naturally occurring population of patient scans; the proposed phantom families share a spherical template.
- No condition-level pseudoreplication: hypothetical draws are **24 independent object-level gains**, not 96 supposedly independent observations.
- The 2% gain benchmark is illustrative, and **not** an approved superiority threshold. Lower 95% confidence limit >0 would be a *directional* criterion only.

## Four confidence interval candidates

1. `stratified_percentile` — originally specified equal-family stratified resampling; quantiles of bootstrap means.
2. `stratified_basic` — reverse-percentile (basic) bootstrap.
3. `stratified_bootstrap_t` — studentized bootstrap resampling, with *resampled* stratified standard errors.
4. `stratified_welch_t` — analytic studentized interval using stratified SE and Welch–Satterthwaite degrees of freedom.

All intervals are two-sided nominal 95%; methods are evaluated *against* their known hypothetical population mean. Four generative settings: normal equal variance, centered skewed exponential, standardized Student-t(3) heavy tails, and unequal family variances. The mean grid is 0%, 1%, 2%; object SD is 1%, 3%, 6%. The code uses 250 simulated datasets per setting and 1,000 bootstrap resamples per dataset by default, with seed 941027. Results vary with these choices.

## Local first-run screening (250 trials × 1,000 resamples)

Across **36 scenario/mean/SD combinations**, average empirical coverage was approximately:

| Method | Mean coverage | Minimum observed coverage |
|---|---:|---:|
| Stratified percentile | 91.2% | 86.8% |
| Stratified basic | 91.4% | 84.0% |
| Stratified bootstrap-t | 94.8% | 90.0% |
| Stratified Welch-t | 95.1% | 90.8% |

These *descriptive* averages are over arbitrarily selected hypothetical scenarios, **not method-validation probabilities**. With only 250 trials per setting, an estimated coverage near .95 has Monte Carlo standard error ≈1.4 percentage points; the extremes have additional selection variability. In the normal equal-variance scenario with assumed true gain 2%, percentile-bootstrap detection (lower bound >0) was approximately 100%, 92%, and 42% for SD 1%, 3%, and 6%, respectively. A more conservative interval can have lower detection rates because of greater width.

**Decision:** `NO_METHOD_APPROVED`. The studentized and Welch variants merit increased-trial independent calibration, consideration of the actual fixed-family estimand and plausible gain distributions, and statistician/scientific sign-off before revising the analysis specification. The current 08AJ-D percentile analysis remains a *draft*, not silently replaced.

## Windows PowerShell commands

Extract the four included files to the existing `rbyrct-3d-05a` project directory. Requires existing `numpy`, `scipy`, `pytest`.

```powershell
python -m pytest test_experiment_08aj_v.py -q

python experiment_08aj_v.py `
    --output-dir results\experiment08aj_v\calibration_first

python experiment_08aj_v_audit.py `
    --output-dir results\experiment08aj_v\calibration_first

Get-Content results\experiment08aj_v\calibration_first\run_status.json
```

For a higher-resolution simulation sensitivity check, use a **new** directory and optionally `--trials 1000 --bootstraps 2000`; this is more expensive and should not be mistaken for independent empirical data. The output directory is intentionally never overwritten. The full evidence is `statistical_calibration_evidence.json`. The auditor checks the report's hash, structural completeness, settings, and freeze controls; it is not independent numerical reproduction of Monte Carlo draws.

## Outstanding blockers

1. Review hypothetical scenario relevance and precision/coverage with adequate Monte Carlo repetitions; approve one inference procedure with a rationale and prespecified sensitivity analyses.
2. Approve bounded synthetic stress-test family claims rather than asserting structural independence.
3. Calibrate and approve process resource/failure policies.
4. Complete and independently audit a source-locked prospective 480-job executor and outcome analysis.
5. Obtain explicit scientific sign-off and authorized protocol freeze **before** any confirmatory execution.

**Outcome status:** `frozen=false`; `confirmatory_execution_allowed=false`; `no_confirmatory_outcomes=true`.
