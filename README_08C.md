# RBYRCT-08C: Exploratory reconstruction-quality comparison

**Scope:** Development-only, synthetic localized-defect MART tomography. This is **not** independent validation, a clinical experiment, a dose study, or a claim of improved imaging. Frozen 06B/07C2 study objects and results are not used for tuning.

## Design (locked in the default runner)

- Grid sizes: **12³ and 32³**; four new object seeds per size (eight objects total).
- Forward models: matched (`same`) and independent trilinear (`independent`); one deterministic acquisition seed per size.
- Policies: `coverage`, `gradient`, `incremental_25`, with the **unchanged 08B** acquired-only selector, `lambda=0.25`.
- 12³: 24 warm rays, 288 total, checkpoints **144 and 288**; batch 16, pool 16.
- 32³: 64 warm rays, 1,024 total, checkpoints **512 and 1,024**; batch 32, pool 16.
- Provisional MART: 2 epochs, relaxation 0.25. Final MART: **16 epochs** for all policies/checkpoints. Noise fraction 0.005.
- **48 acquisition histories**, **96 checkpoint reconstructions** total.
- Outcomes: whole-volume, evaluation-only defect-region and nondefect-region RMSE; paired percent gain vs coverage; individual object summaries and descriptive averages. No prespecified success test or selected primary endpoint.
- **No hyperparameter sweep**. If development results motivate a new rule, that is a new version and requires fresh held-out validation later.

## Windows PowerShell

Unzip the three files into the existing `rbyrct-3d-05a` directory. Then:

```powershell
python -m pytest test_experiment_08c.py -q
python -m pytest -q
git diff --check
python experiment_08c.py --output-dir results/experiment08c/exploratory_first
```

After completion:

```powershell
$dir = 'results/experiment08c/exploratory_first'
Get-Content "$dir/run_status.json"
Import-Csv "$dir/aggregate_summary.csv" | Format-Table -AutoSize
Import-Csv "$dir/object_level_summary.csv" | Format-Table -AutoSize
```

The script refuses to overwrite existing output. It saves each completed `(size, object, model)` set of six checkpoint-policy rows. If interrupted, `run_status.json` marks it incomplete. **Do not interpret partial outputs as a completed experiment.**

`acquisition_orders.csv` records acquired ray IDs for a later independent audit; `guard_batch_audit.csv` records restriction/intervention statistics; `object_manifest.csv` includes truth/mask hashes. `sha256.json` hashes all completed output files except itself. Object ground truth and masks are created outside selectors and used only to evaluate reconstructed images; the `AcquiredOnly` gate restricts measurement reads.

**Caveats:** 12³ and 32³ configurations have different budgets, so comparison of raw gain across resolutions is descriptive, not a controlled attribution to resolution. Guard activity is not synonymous with imaging benefit. These development objects must not become future independent validation objects.
