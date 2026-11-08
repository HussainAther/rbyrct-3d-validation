# RBYRCT-08AA — independent saved-output audit of 08Z

**Purpose:** Validate the preserved 08Z saved tables and acquisition orders **without importing `experiment_08z`**, rerunning MART, changing acquisition policies, or modifying source archives. 08Z used four new 12³ development phantoms, 4 policies, 2 forward-model conditions, and 2 acquisition checkpoints (64 saved reconstruction rows). The first 08Z attempt completed the MART calculations but crashed while generating a geometry table; the second attempt completed successfully after a missing reporting-function import was fixed.

## Exactly what the audit verifies

- SHA-256 digest of every file listed in the *completed* 08Z archive's `sha256.json`, including `run_status.json` and reconstruction CSVs.
- Original engineering preflight success and its approved full acquisition-order fingerprints; detector ordering and the fixed 0.25 intervention weight remain unchanged.
- Four complete, unique, valid 288-ray acquisition histories and the independently calculated little-endian int64 SHA-256 hash of every 144/288-ray prefix.
- Exactly 64 unique object × forward-model × policy × budget reconstruction records; nonnegative, finite whole-volume/defect/nondefect RMSE fields.
- All archived gains against the matched coverage baseline recalculated from the raw saved RMSE values, with no reuse of the 08Z aggregation functions.
- All 32 object-level rows, 8 aggregate rows, and 8 spatial-versus-full paired comparisons independently recomputed, including object win counts.
- Spatial geometry metrics independently recomputed from the repository's system matrix: weighted-sensitivity Gini, detector-position entropy, detector bins, voxel visitation, and intersection fraction with full-covariance ordering.
- Checks that the archived four-object manifest identifies the expected object seeds and structurally valid hashes (without claiming to regenerate object truth).
- First versus second reconstruction archive: same protocol, orders, saved RMSE/gain values, object manifest and summaries. Reconstruction CSV timing fields may differ between executions; the audit *ignores only* timing fields for that comparison.
- Read-only behavior for both archived attempts, creating all outputs in a new audit folder.

## Run in PowerShell (from repository root)

Extract exactly `experiment_08aa.py`, `test_experiment_08aa.py`, and `README_08AA.md` directly into `C:\Users\shuss\Downloads\rbyrct-3d-05a` (not a duplicate nested folder).

```powershell
python -m pytest test_experiment_08aa.py -q
python -m pytest -q
git diff --check
```

If 08Z has **already been archived** under `..\rbyrct-results\experiment08z`:

```powershell
python experiment_08aa.py `
    --preflight-dir ..\rbyrct-results\experiment08z\engineering_first `
    --failed-dir ..\rbyrct-results\experiment08z\reconstruction_first `
    --complete-dir ..\rbyrct-results\experiment08z\reconstruction_second `
    --output-dir results/experiment08aa/audit_first
```

If 08Z is **still inside the repository**, replace `..\rbyrct-results\experiment08z` with `results\experiment08z` in the three source-directory arguments above. Do not overwrite any existing output directory; use `audit_second` for an intentional retry.

Read the findings:

```powershell
$dir = 'results/experiment08aa/audit_first'
Get-Content "$dir/audit_report.json"
Import-Csv "$dir/independently_recomputed_summary.csv" | Format-Table -AutoSize
Import-Csv "$dir/first_vs_second.csv" | Format-Table -AutoSize
```

A successful report requires `complete: true`, an empty `errors` array, `preflight_verified: true`, and `failed_attempt_compared: true`. The program raises an error after writing a failed report if any consistency check fails. **Do not commit or archive a failing audit as a passing audit.**

Once the audit passes, commit the code and preserve the results:

```powershell
git add experiment_08aa.py test_experiment_08aa.py README_08AA.md
git diff --cached --check
git commit -m "Add independent 08Z saved-output and provenance audit"
Move-Item 'results/experiment08aa' '..\rbyrct-results\'
git restore -- ':(glob)__pycache__/*.pyc'
git status --short
```

## Limits: what this **cannot** prove

The 08Z archive does not preserve the actual reconstructed voxel arrays, so this audit cannot independently verify a reconstruction against phantom truth or independently replay the MART kernel. It verifies the **internal integrity and arithmetic of the saved result tables**, not their underlying voxel-space accuracy. The geometry computation also shares the original repository's system-matrix implementation, so it is not a separate physical-model replication. Four objects are exploratory development examples; the two forward-model conditions are paired within each object, not eight independent observations. Do not interpret audit success as statistical significance, validated clinical benefit, or evidence that one regularization policy generalizes to different acquisition geometries. Stronger follow-up work should include a voxel-level MART replay, multiple geometries, larger held-out objects, and competitive published baselines.
