# RBYRCT 05B-11 Stage 2 - frozen 12-cubed study

This add-on uses existing `experiment_05b_11.py` and prior 05B dependencies unchanged.
No new acquisition scores, solver tuning, or SIRT comparisons.

## Frozen protocol

- 12 x 12 x 12 coarse MART reconstruction; factor-two fine-grid generator.
- Four new phantom families x two independent parameter seeds each: eight objects; **not** the Stage 1 pilot objects.
- Two acquisition RNG seeds (104729, 130363) x two measurement models (`same` and trilinear `independent`, offset 0.15, midpoint step 0.25), with 0.005 RMS Gaussian noise clipped at zero.
- Three policies: `coverage`, `gradient`, `delayed_48`. All use the **same** MART implementation; delayed activation occurs at 48 *absolute* acquired rays.
- 576 acquired rays; nested reconstructed checkpoints 144, 288, 576; warm 36, batch 12, candidate pool 24.
- Provisional MART 4 epochs; final MART 16 epochs; relaxation 0.25. No parameter tuning based on results.
- Primary outcome: object-balanced mean paired RMSE gain vs coverage at **288 rays**. Secondary outcomes: 144/576 gains, family heterogeneity, worst-object deficits, threshold 0.10 crossing at saved checkpoints only, timing.
- The eight structural objects are the replication units; two seeds, two models and checkpoints are repeated conditions. No population-significance claims.

## Install (PowerShell, conda environment rbyrct-3d)

Copy `experiment_05b_11_stage2.py`, `test_experiment_05b_11_stage2.py`, and `README_05B11_STAGE2.md` directly to the `rbyrct-3d-05a` repository root. Do **not** leave duplicate test-module copies in a nested extracted directory.

```powershell
python -m pytest test_experiment_05b_11_stage2.py -q
python -m pytest -q
git diff --check
```

Expected: 5 new tests, 139 total tests if the original 134-test repository is otherwise unchanged. These are fast unit tests and a reduced-scale smoke test; **they do not execute the full study**.

## Frozen production run

```powershell
python experiment_05b_11_stage2.py `
    --output-dir results/experiment05b/stage2_11_frozen_first
```

The script refuses a nonempty destination and accepts **no parameter overrides**. Output includes `protocol.json`, `environment.txt`, `object_manifest.csv`, `acquisition_orders.csv`, `prefix_reconstructions.csv`, `matched_cases.csv`, `object_level_summary.csv`, `threshold_crossings.csv`, `timing.csv`, `study_status.json`, and `run_manifest.sha256`.

Anticipated outputs: 8 objects x 2 models x 2 seeds x 3 policies = **96 full acquisition histories**, 96 x 3 checkpoints = **288 reconstruction rows**; 55,296 ray-order rows (96 x 576); 96 rows at the 288-ray primary endpoint. This is a computational estimate, not a runtime promise.

### After finishing

```powershell
Get-Content results/experiment05b/stage2_11_frozen_first/study_status.json
Import-Csv results/experiment05b/stage2_11_frozen_first/object_level_summary.csv |
    Format-Table object_id, policy, mean_relative_gain -AutoSize
```

Commit **only** the three added source/README files after tests pass. Leave generated results in your ignored `results/` directory. Preserve the full CSVs and manifest for later archive/publication. Do not edit policies after inspecting the outcomes.

### Scientific boundaries

A favorable conditional result is not proof of universal adaptivity or clinical CT savings. A negative result is useful evidence about this frozen selector. `selection_s` covers the full acquisition history; it is repeated beside checkpoint-specific reconstruction times and must not be summed over checkpoints. Threshold `.10` is a coarse, **checkpoint-censored** descriptive measure, not a precise ray-savings estimate.
