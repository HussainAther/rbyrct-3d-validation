# RBYRCT-05B: MART restoration (exploratory implementation)

**Status: implementation + small-scale smoke validation; NOT a completed scientific reproduction or submission-ready manuscript.**

The historical `experiment_04*.py` scripts and previous result files are **preserved**. Some of those historical adaptive experiments use SIRT. Do not present their numerical outcomes as evidence for MART-driven RBYRCT.

## New files and roles

| File | Role |
|---|---|
| `experiment_05b_mart.py` | MART solver, with strictly positive initialization; per-row update copied mathematically from 04B / 04F |
| `experiment_05b_adaptive.py` | MART reconstruction for acquired-only feedback and the 04J scoring/candidate algorithm |
| `experiment_05b_diagnostics.py` | MART training/holdout and split-feature diagnostics using acquired measurements only |
| `experiment_05b_gate.py` | MART reliability-gated acquisition, with acquired-only measurement protection |
| `experiment_05b_04p.py` | Five-policy 04P geometry/phantom study rerun with MART in both feedback and final reconstruction |
| `experiment_05b_04qb.py` | Five-policy independent forward-projector 04QB rerun with MART |
| `experiment_05b_04r.py` | MART-specific acquisition trajectory and reconstruction checkpoints |
| `experiment_05b_04s.py` | MART-specific matched-prefix policy switching; needs 05B-04R inputs |
| `experiment_05b_benchmark.py` | Small sphere MART vs historical SIRT engineering comparison (not a performance claim) |
| `experiment_05b_resources.py` | Conservative grid admission limits; never override the large-run memory floor |
| `test_experiment_05b.py` | Numerical and acquired-only regression tests |

## Solver conventions

The per-ray update follows historical 04B: `x_j <- max(tiny, x_j * exp(clip(lambda * w_j / max(w) * log(max(b_i,tiny)/max(dot(w,x),tiny)), -12,12)))`, with `tiny = 1e-10`, initial `x=0.3`, relaxation `0.15`. Original reference `experiment_04b.mart` requires ground truth to print RMSE; new solver takes **no ground truth**. MART **epochs** are passes through acquired rays, not SIRT iterations. The basic default for preliminary reruns is 3 provisional epochs, 3 diagnostic epochs, and 8 final epochs. These defaults **have not been optimized or validated for convergence**.

Ray acquisition and final reconstruction use the **same MART** solver; geometry-only policies use MART only for final reconstruction. The geometry scorer is otherwise based on historical 04J. The reliability gate threshold and score remain heuristic, not trained statistical calibration.

## Reproduce small verified smoke (start here on low-RAM machines)

```powershell
python -m pytest -q
python experiment_05b_benchmark.py --size 4 --budget 16 --mart-epochs 8
python experiment_05b_04p.py --size 4 --angles 2 --factor 2 --phantoms branches --object-types replicated --offsets 0 --budgets 16 --seeds 271828 --noise-fractions 0 --warm-rays 12 --batch 4 --provisional-epochs 2 --diagnostic-epochs 2 --mart-epochs 2 --candidate-pool 8 --diagnostic-every 4 --output-dir results/experiment05b_04p_smoke
python experiment_05b_04qb.py --size 4 --angles 2 --factor 2 --phantoms branches --object-types replicated --offsets 0 --budgets 16 --seeds 271828 --noise-fractions 0 --warm-rays 12 --batch 4 --provisional-epochs 2 --diagnostic-epochs 2 --mart-epochs 2 --candidate-pool 8 --diagnostic-every 4 --output-dir results/experiment05b_04qb_smoke
```

The tiny 4^3 runs verify wiring; **do not** use them for confirmatory performance claims.

To run 05B-04R then 05B-04S, use the original CLI flags with `--mart-epochs`, `--provisional-epochs`, new output paths, and 05B-04S `--source-dir` pointing at the 05B-04R output. Do not mix historical 04R sequences with MART 05B-04S.

## Scientific validation checklist BEFORE manuscript revision

1. Measure MART residual, RMSE, and convergence vs 1, 2, 4, 8, 16+ epochs, varying relaxation, noise, and acquisition order. Avoid treating a SIRT iteration as equivalent computational cost.
2. Confirm acquired-only selection with oracle guards and instrumentation for all policies; zero-feedback must not read unacquired measurements.
3. Re-run *all* original 04P and 04QB prespecified phantom families, offsets, object types, seeds, noise, and budgets under fixed MART settings; compute matched paired summaries.
4. Re-run trajectories/prefix switches using newly generated MART acquisition orders. Former SIRT ray hashes cannot be reused.
5. Add the four-way 2x2 study: {SIRT/MART feedback} × {SIRT/MART final reconstruction}, with identical acquisition budgets, noise and phantom sets; clearly label comparisons.
6. Validate physically meaningful attenuation and zero-ray behavior, model mismatch, convergence, independent forward projectors, and sensitivity to data ordering.
7. Scale only after memory instrumentation and enough available physical RAM; SciPy CPU sparse matrices do not automatically leverage the GPU.
8. Rewrite manuscript after results exist. Remove old numerical claims/tables, revise pseudocode, protocol descriptions, and limitations, and clearly separate older SIRT studies from 05B MART outcomes.

### Limitations

These scripts are synthetic numerical experiments. No real scanner, dose model, physical detector, patient data, or clinical benefit is established. The original 04P/04QB code was used to port the study design, but the new solver changes acquisition orders. Small smoke results may favor feedback-off; no adaptive superiority is asserted. Timings contain repeated projector construction and are not optimized. RAM checks are screening only, not guarantees of safe peak memory. Full 04G-04O side investigations have **not all been individually ported**; they remain historical SIRT results where applicable. This package restores the **core manuscript paths** (04P/04QB) and MART trajectory/prefix follow-up (04R/04S), not every historical exploratory branch.
