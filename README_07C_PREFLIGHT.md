# RBYRCT-07C-P: bounded 32^3 preflight (engineering only)

## Purpose and scientific boundaries

This is **not** the frozen 07C 32^3 accuracy validation. It is a **single deterministic feasibility preflight** using the existing 07B/06A/06B code paths. Do not use its output to select a favorable reconstruction budget or to assert measurement efficiency or defect-detection gains.

The preflight:

1. Builds the existing 32^3 sparse ray system (4 azimuths, 3 tilts; 12,288 candidate rays).
2. Computes **one common 4,096-ray coverage order**, then profiles **1,024 rays** for coverage, original gradient and guarded 5% selectors. The common full 4,096-ray coverage-order time is included in every 1,024-ray selector's `total_selection_s`: this deliberately charges all policies for that preparatory computation and is **not** an optimized 1,024-ray-only coverage timing.
3. Verifies unique acquired rays, acquired-only observation access, strictly positive finite MART output, and reports process memory, final sparse matrix bytes, timings, and SHA-256 ray-order hashes.
4. Profiles **4,096 rays for coverage-only**, including a final MART solve. **Gradient and guarded acquisition at 2,048 or 4,096 rays are not executed**, and their feasibility must not be inferred from this run.
5. Defines, but **does not evaluate reconstruction accuracy with**, a ground-truth defect-region mask for use in a future protocol.

A profiler may show differing timings under Windows versus Linux or even between repeated runs on one machine. Windows `psutil` reports the OS peak working set; on Linux the maximum RSS is reported by `resource`. This is a process-level peak, not a model of memory needed for larger studies. The final CSR matrix bytes exclude temporary list allocations.

## Dependencies

The existing `rbyrct-3d-05a` repository with `experiment_04b`, `experiment_04g`, `experiment_04h`, `experiment_05b_04`, `experiment_05b_gate`, `experiment_05b_mart`, `experiment_06a`, `experiment_06b`, `experiment_07b` and their usual NumPy/SciPy dependencies; `psutil` is recommended for Windows memory reporting.

## Install and run in PowerShell

Unzip these three files into `C:\Users\shuss\Downloads\rbyrct-3d-05a`:

- `experiment_07c_preflight.py`
- `test_experiment_07c_preflight.py`
- `README_07C_PREFLIGHT.md`

```powershell
python -m pytest test_experiment_07c_preflight.py -q
python -m pytest -q
git diff --check

python experiment_07c_preflight.py `
    --output-dir results/experiment07c/preflight_32_first

$dir = "results/experiment07c/preflight_32_first"
Get-Content "$dir/profile.json"
Import-Csv "$dir/policy_timing.csv" |
    Format-Table budget,policy,total_selection_s,final_mart_s,peak_so_far_bytes -AutoSize
Get-Content "$dir/defect_metric_definition.json"
```

The experiment refuses to overwrite nonempty output directories. Run again only in a new destination and preserve the first run.

## Data products

- `protocol.json`: fixed engineering settings and scope
- `profile.json`: matrix dimensions, nonzeros, build time, memory, covered budgets
- `policy_timing.csv`: ray-order hashes and measurements for the four workloads
- `defect_metric_definition.json`: deterministic example of the proposed *evaluation-only* defect support mask
- `environment.json`: Python, OS and NumPy metadata

## Defect metric proposed for a subsequent frozen accuracy protocol

The original seeded 06B `defect_phantom` is reconstructed at 32^3 using factor-two fine-volume generation. For each new independent object seed, independently regenerate the **undefected host** using the same host/texture draws; let `delta = max(host_only_coarse - defective_truth_coarse, 0)`.

The **ground-truth evaluation mask** is `delta >= max(0.01, 0.08 * delta.max())`. It is determined from known synthetic truth **only after acquisition**, and must **never** be passed to coverage, gradient, guarded selection, reconstruction, tuning, or stopping logic. The proposed primary error metrics are whole-volume RMSE and defect-mask RMSE; nondefect RMSE is a guardrail. Mask dimensions and fraction must be reported per object. Thresholds were selected to make a reproducible definition, **not** to optimize a gain. The mask definition is not a defect-detection metric: that would need a separately prespecified detection algorithm and operating point.

The preflight sample uses generator seed `707001` solely to confirm that this definition yields a nonempty mask; do not reuse this seed as a supposedly untouched test object without explicitly accounting for this exposure.

## After this preflight

Before freezing 07C proper, review Windows process memory and runtime measurements and choose an affordable **fixed** design for new 32^3 localized-defect volumes. A natural candidate checkpoint schedule is 1,024 / 2,048 / 4,096 acquired rays, with a prespecified primary checkpoint and all three methods evaluated there; **but this package does not assert those adaptive 4,096-ray runs are feasible**, and does not freeze a 07C accuracy study. No 07C accuracy claims should enter the manuscript until a prospective independently audited study is executed.

## Local verification of this ZIP

Five new tests passed. In the available local repository snapshot, the full suite passed **164/164**. A complete preflight also ran on Linux, producing 1,024-ray coverage/gradient/guarded timings and a 4,096-ray coverage-only reconstruction. Your Windows timing/memory report is the relevant measurement for your hardware.
