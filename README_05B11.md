# 05B-11 — Stage 1 feasibility pilot (12³)

This package implements **only Stage 1** of `RBYRCT_05B11_Bounded_Protocol.md`.
It adds `experiment_05b_11.py` and `test_experiment_05b_11.py` to the
existing `experiment-05b-mart-restoration` repository. It does **not** run Stage 2,
change MART, optimize policy settings, or replace any prior result.

The frozen defaults are: two *new* objects (inclusions, laminae), 12³ coarse
volume, factor-two fine object, 4 azimuths × 3 tilts, 1,728 candidate rays;
`same` forward operator, additive Gaussian noise 0.005 × RMS(clean) and
nonnegative clipping; one acquisition seed; coverage, gradient, delayed-48;
288 selected rays with 144- and 288-ray checkpoints; warm36, batch12, pool24;
provisional 4 MART epochs, final 16 epochs, relaxation 0.25. Delayed-48
switches after 48 absolute rays, not 48% of budget.

## Install (PowerShell, from `C:\Users\shuss\Downloads\rbyrct-3d-05a`)

Extract ZIP into the **repository root**, with no nested directory.

```powershell
python -m pytest test_experiment_05b_11.py -q
python -m pytest -q
git diff --check
python experiment_05b_11.py `
  --output-dir results/experiment05b/feasibility_11_pilot_first
```

For basic timing and resource monitoring, run separately before/after:

```powershell
Get-CimInstance Win32_OperatingSystem | Select-Object FreePhysicalMemory,TotalVisibleMemorySize
```

## Outputs
`protocol.json`, `environment.txt`, `object_manifest.csv`, `acquisition_orders.csv`,
`prefix_reconstructions.csv`, `timing.csv`, `engineering_status.json`,
`run_manifest.sha256`. Output directory must not already contain files.

Do **not** interpret better pilot RMSE as a license to change the 05B-11
protocol. Pilot pass/fail concerns finite results, validated acquired-only access,
ray history consistency, adequate memory and feasible execution time. The
script verifies all numerical integrity checks; **the user must evaluate runtime
and available RAM** before authorizing Stage 2.

A test-only smoke example is executed by the unit tests on a tiny grid and
is not evidence for the 12³ study. This script does not calculate external
hardware-independent memory peak or choose an acceptable runtime threshold.

## Scientific caution
A coherent 3D MART architecture does not imply that gradient-guided acquisition
has demonstrated superiority to coverage-only. Any stage-2 comparison must
retain object-level statistical units and be frozen before viewing its outcomes.
