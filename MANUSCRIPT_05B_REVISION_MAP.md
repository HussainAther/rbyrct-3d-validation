# Manuscript 05B revision map — do not reuse historical numerical claims

**Evidence status: pending MART full-study reruns. No new results are certified by this document.**

- **Title/abstract:** describe MART-driven sequential acquisition explicitly; replace quantitative success/failure numbers only after complete reruns.
- **Methods / reconstruction:** define per-ray multiplicative update from 04B, relaxation, clipping, positivity, zero-ray safeguards, ordered epochs, and initialization. State that provisional and final reconstructions use MART, and describe computational budget separately from number of acquired rays.
- **Acquisition:** retain 04J geometry/feature candidate scoring only insofar as MART-produced gradient features change selection. Acquired-ray-only oracle requirements must be formally stated and tested.
- **Controls:** feedback-off, geometry-balanced, coverage-greedy, reliability gate; distinguish MART-at-end from MART-at-selection.
- **Experimental designs:** regenerated 05B-04P and 05B-04QB with independent projector, repeated families/seeds and model mismatches; characterize cross-projector differences as numerical, not real-scanner validation.
- **Results:** blank until full fresh MART results; never transplant SIRT-derived ~4–6% gains or negative mismatch percentages.
- **Ablations:** convergence/relaxation/ordering and cross-combination {SIRT,MART} feedback × {SIRT,MART} evaluation.
- **Limitations:** phantom-only, noise simplification, underdetermination, acquisition costs, unavailable dose physics, resource limits, and method-specific outcomes.
- **Discussion:** compare the distinct SIRT-based historical method with MART RBYRCT, discuss positive or negative evidence neutrally.
- **Supplement:** include new protocol.json, paired case data, order hashes, test logs, exact run configuration and environment.

The manuscript should be redrafted **after** 05B data collection and analysis, not revised by simply changing the word SIRT to MART.
