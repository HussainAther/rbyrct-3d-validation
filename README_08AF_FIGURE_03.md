# RBYRCT-08AF — Figure 3, frozen 08M primary evidence

Use this package **from the Windows repo root**. Extract the two `.py` files and this README directly into `C:\Users\shuss\Downloads\rbyrct-3d-05a`.

This script reads from frozen 08M and independently replayed 08Q only. It never modifies those directories, generates phantoms, selects rays, or runs MART.

## Check installation

```powershell
conda activate rbyrct-3d
python -m pip show matplotlib pandas numpy
python -m pytest test_figure_03_08m_primary.py -q
```

## Generate Figure 3

```powershell
python figure_03_08m_primary.py `
    --08m-dir ..\rbyrct-results\experiment08m\frozen_first `
    --08q-dir ..\rbyrct-results\experiment08q\full_replay_first `
    --output-dir figures\08af\figure03_first
```

The output directory must not exist, to avoid accidental overwriting. If rerunning, use `figure03_second` or another new path.

## Outputs

- `Figure_03_08M_primary_evidence.pdf` — vector manuscript figure
- `Figure_03_08M_primary_evidence.svg` — editable vector
- `Figure_03_08M_primary_evidence.png` — 600-dpi preview
- `figure_03_object_values.csv` — every plotted independent object value
- `figure_03_manifest.json` — evidence classification, comparison definition, source hashes, and checks

## Scientific choices

- Primary 08M endpoint **2,048 rays** and **information_diag vs coverage** only.
- Two panels: global and defect-region paired fractional RMSE gain, with zero reference and mean.
- All **eight** independent phantom objects plotted, in ascending object-seed order, not sorted by measured gains.
- Two acquisition seeds × two model conditions are averaged *within* each independent object, so n=8, not n=32.
- Figures use no bootstrapped intervals; individual observations are visible.
- The plot generator recomputes means and object win counts and compares 08M object values with 08Q replayed values before exporting.
- This is a figure production and saved-output agreement check, not another reconstruction audit.

## Inspect

```powershell
Get-Content figures\08af\figure03_first\figure_03_manifest.json
Start-Process figures\08af\figure03_first\Figure_03_08M_primary_evidence.png
```

Record the output figure files and figure-manifest hash in your manuscript or publication provenance ledger. Do not overwrite the frozen 08M or 08Q archives.
