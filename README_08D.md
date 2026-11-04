# RBYRCT-08D — Read-only acquisition-path and defect-intersection diagnostic

**Scope:** Analyze the completed, archived **08C exploratory** ray histories. No new acquisition, no MART reruns, no policy changes, no tuning, and no inference of clinical detection performance.

## Requirements

Place `audit_08d.py`, `test_audit_08d.py`, and this README in the root of your existing `rbyrct-3d-05a` repository. The script imports your existing `experiment_04b`, `experiment_04g`, and `experiment_07c_preflight` modules to regenerate the exact ray geometry and evaluation-only defect masks. Requires `numpy`, `scipy`, `pytest` (already in the project).

The 08C results were moved to `..\rbyrct-results\experiment08c\exploratory_first` in the preceding workflow. Verify the path if your folder layout differs.

## Windows PowerShell

```powershell
python -m pytest test_audit_08d.py -q
python -m pytest -q
git diff --check

python audit_08d.py `
    --results-dir ..\rbyrct-results\experiment08c\exploratory_first `
    --output-dir ..\rbyrct-results\experiment08d\path_diagnostic_first
```

Outputs, all **outside** the original 08C data folder:

- `audit_report.json`: PASS/error verdict, counts, verification limits.
- `path_metrics.csv`: one record per completed reconstruction checkpoint and policy, reporting raw defect intersections, total ray path fraction through defects, coverage coefficient of variation, defect voxel coverage, ray-order overlap and original RMSE.
- `paired_differences.csv`: policy-minus-coverage contrasts within each size × object × forward model × budget.
- `object_level_differences.csv`: averages over the two forward models **within each object**.
- `descriptive_summary.csv`: object-balanced descriptive averages and Spearman correlations (no p-values).

The script verifies original `sha256.json` file digests, complete status, original ray-order checkpoint fingerprints, exact index sequences and unique ray IDs, regenerated defect-mask hashes, and original saved overlap counts. It refuses to overwrite an existing output directory or write under the original 08C folder.

**Interpretation:** `defect_hit_fraction` is the share of acquired rays with any positive matrix-path overlap with the known evaluation-only defect mask. `defect_path_fraction` is the fraction of *summed path length* through defect-mask voxels among all acquired rays. Neither is a measure of the amount of detected defect signal. The coefficient of variation uses path-length-weighted voxel coverage. Overlap is set-based, unlike ordered history fingerprints.

**Cautions:** The original 08C objects are exploratory, the effective unit of replication is the synthetic object (four per resolution), and post-hoc associations cannot show that a particular path pattern *caused* better or worse reconstruction. Values are geometry dependent; do not compare raw fractions across resolutions as if all else were controlled. Defect masks are regenerated for *post-acquisition evaluation only*. This report does not claim a new beneficial acquisition rule.

### After review

If all checks pass, commit the three source files while preserving original experiment results separately. Do not add the `experiment08d` outputs to the source repository unless deliberately versioning reports.
