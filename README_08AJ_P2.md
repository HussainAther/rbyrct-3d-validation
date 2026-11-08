# 08AJ-P2: one-volume 64³ MART engineering pilot

**Purpose:** Test feasibility of one 64³ MART reconstruction at 2,048 acquired rays using the **unchanged** 08AJ-P acquisition-order algorithm and the existing 05B MART kernel. Engineering-only, not an accuracy comparison, confirmatory study, physical tomography test or dose demonstration.

## Inputs and controls

- Prior successful 08AJ-P directory `results/experiment08aj_p/geometry64_first` must exist, especially `order_fingerprints.json`. The pilot regenerates the same diagonal order from the same seed and **refuses** a hash mismatch.
- 64³, 4 azimuths, original three tilts, 49,152 candidate rays; 2,048 selected; warm 64, batch 32, candidate pool 16, seed 930011.
- One **fixed** `experiment_04b.phantom_3d(64)` phantom, **matched forward model only**, deterministic Gaussian-perturbed nonnegative measurements (`fraction=.005`, seed 930021). This avoids the heavy 128³ independent forward projector in an engineering pilot.
- `experiment_05b_mart.mart_reconstruct` unchanged; 16 epochs, relaxation .25, initial .3.
- Output records timings, before/after memory and Windows `psutil.peak_wset` if available, finite positive reconstruction, a single projection residual for numerical sanity, voxel and order hashes. It reports **no phantom RMSE or policy gain**, deliberately.
- No overwrite, no changes to historic source, no modification of frozen 08M/08AC.

## On your Windows PowerShell environment

Extract these three files into the existing `rbyrct-3d-05a` repository root:

```powershell
python -m pytest test_experiment_08aj_p2.py -q
python experiment_08aj_p2.py `
  --preflight-dir results\experiment08aj_p\geometry64_first `
  --output-dir results\experiment08aj_p2\pilot64_first
Get-Content results\experiment08aj_p2\pilot64_first\run_status.json
Get-Content results\experiment08aj_p2\pilot64_first\pilot_report.json
```

Only run against a **new** output directory. On failure, keep the partial directory and the traceback; do not repeatedly run over it. If peak working set is unavailable, report this rather than treating sampled RSS as peak. If the peak memory gate is exceeded, preserve the result as a resource feasibility finding.

Before scientific 08AJ validation, implement and verify conventional/stratified controls, design object families, and freeze the prospective primary comparison. **A positive residual, a finite reconstruction, or a fast runtime does not establish a reconstruction-quality benefit.**
