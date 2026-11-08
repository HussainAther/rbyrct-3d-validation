# 08AJ-CV: Complete-view geometry-only comparator (draft, not locked)

## Purpose

Provide a constrained *simulated* parallel-beam comparator that selects **entire n x n detector views**. The ray catalogue uses the original `experiment_04b.system_matrix` indexing: tilt-major, azimuth, detector row, detector column. Unlike the prior 08AJ-B individual-ray baselines, this comparator never acquires a partial view.

This is **not** proof of physical scanner executability: gantry movement, detector readout, photon-count noise, exposure time, control constraints, and radiation dose have not been modeled.

## Selection rule

A view is one (tilt, azimuth) pair with n² consecutive ray IDs. First select the zero-nearest tilt and first azimuth. Then greedily select an unchosen catalogue direction that maximizes the minimum angular distance `acos(abs(dot(d_i, d_j)))` from previously chosen directions (smallest catalogue index wins ties). Emit **all n² detector rays** for each view in source row/column order. This is a reproducible discrete geometric heuristic, not optimal-view design.

Only budgets divisible by n² are legal. In particular:

- 32³ at 2,048 rays = **2 complete views** (feasible)
- 32³ at 4,096 rays = **4 complete views** (feasible)
- 64³ at 2,048 rays = **INFEASIBLE** (one view needs 4,096 rays)
- 64³ at 4,096 rays = **1 complete view** (feasible but angularly very limited)

No rounding up/down or fractional detector view is silently performed.

## Setup / Windows PowerShell

Extract `experiment_08aj_c_view.py`, `test_experiment_08aj_c_view.py`, and this README into the repository root.

```powershell
python -m pytest test_experiment_08aj_c_view.py -q
python experiment_08aj_c_view.py --size 32 --budget 2048 --output-dir results\experiment08aj_c_view\view32_2048_first
python experiment_08aj_c_view.py --size 32 --budget 4096 --output-dir results\experiment08aj_c_view\view32_4096_first
python experiment_08aj_c_view.py --size 64 --budget 2048 --output-dir results\experiment08aj_c_view\view64_2048_infeasible
python experiment_08aj_c_view.py --size 64 --budget 4096 --output-dir results\experiment08aj_c_view\view64_4096_first
```

The 64³/2048 case **completes with verdict `INFEASIBLE` by design**, not `PASS`; the output contains a reason, no `.npy` acquisition history, and should not be interpreted as an engineering failure. Each command refuses to overwrite an existing output directory.

To inspect:

```powershell
Get-Content results\experiment08aj_c_view\view32_2048_first\view_report.json
Get-Content results\experiment08aj_c_view\view64_2048_infeasible\run_status.json
```

## Scientific design decision required before 08AJ lock

The new 32³ comparator is an extremely sparse-angle complete-view baseline (only two views at 2,048 rays). It tests a distinct feasible **block-selection constraint**, not a statistically fair surrogate for typical clinical CT. It should be a *secondary, constraint-aware comparison*, not the default 08AJ primary comparator without stronger motivation. Existing primary individual-ray policy designs and the 64³ single-ray pilot have different admissible acquisition actions. 64³ full views cannot be compared at 2,048 rays; a separate >=4,096-ray comparison would need its own preregistered budget and interpretation. More candidate views/realistic scanner trajectories would require a fresh prospective protocol, not relabeling this 12-view catalogue.

## Reproducibility and limits

Reports contain the exact selected view IDs, full detector ray order hash (little-endian signed int64), per-view ray counts, and SHA-256 file manifest. No phantom generator, intensities, reconstruction, RMSE, or noise values are accessed. This engineering artifact must not be presented as scientific validation or a locked 08AJ-C protocol.
