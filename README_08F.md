# RBYRCT-08F — Read-only within-pool ranking and regret audit

## Purpose
Analyze **existing 08E retrospective candidate records**. No MART reconstructions, candidate acquisitions, policy changes, or access to unmeasured detector data during selection occur in 08F. The 08E archive's `chosen` and `eligible` columns permit actual selected-ray regret computations. Results are **development-only descriptive diagnostics**.

## Installation
Extract **only** `audit_08f.py`, `test_audit_08f.py`, and `README_08F.md` into the top level of `rbyrct-3d-05a`. Do not retain a second nested extraction directory that duplicates the test module.

## Windows PowerShell
```powershell
python -m pytest test_audit_08f.py -q
python -m pytest -q
git diff --check

python audit_08f.py `
    --results-dir ..\rbyrct-results\experiment08e\feedback_first `
    --output-dir ..\rbyrct-results\experiment08f\ranking_first

$dir = "..\rbyrct-results\experiment08f\ranking_first"
Get-Content "$dir/audit_report.json"
Import-Csv "$dir/object_balanced_summary.csv" |
    Select-Object size,policy,n_objects,n_pools,mean_defect_regret_all,mean_global_regret_all,mean_defect_restriction_gap,mean_within_pool_score_defect_spearman |
    Format-List
```

If the `experiment08e` directory was archived under a different name, locate `candidate_probes.csv` and `sha256.json` and supply that folder. The input directory must contain the **unaltered** 08E output, including `sha256.json`.

08F checks 08E file digests, manifest and status counts, pool membership, unique ray IDs, exactly one selected and reference ray per pool, eligibility, finite scores and gains, and stored score ranks. It refuses to overwrite results and writes **only** to a separate new output directory.

## Metrics
For each recorded candidate pool (16 candidates in the intended 08E protocol):

- **Defect/global all-candidate regret:** `max(all candidate one-ray gains) - selected ray's one-ray gain`.
- **Eligible-only regret:** `max(eligible candidate gains) - selected gain`.
- **Guard restriction gap:** `max(all candidate gains) - max(eligible candidate gains)`. The identity `all regret = eligible regret + restriction gap` holds up to floating-point error.
- **Ranking:** descending feedback score, ties broken by smallest ray ID; top-score/best-gain agreement; within-pool midrank Spearman correlations, omitted for degenerate pools.
- **Defect hits:** selected ray's evaluation-only defect intersection versus overall candidate-pool intersection fraction.
- **Aggregates:** average each metric across probe pools **within each object**, then average across objects within resolution/policy. Candidate rows/pools must not be treated as independent scientific replicates.

Values in `*_gain`, `*_regret*` and `*_restriction_gap` are **relative RMSE fractions**, not raw RMSE or physical dose. For example, a regret of 0.01 is **one percentage point of normalized one-ray RMSE improvement**, not necessarily a one-percent change in final reconstruction error.

## Files written
- `audit_report.json`: integrity verdict, scope and limitations.
- `analysis_protocol.json`: precisely defined calculations.
- `pool_regret.csv`: one row per actual probe pool.
- `object_balanced_summary.csv`: four resolution/policy rows in the intended 08E protocol.

## Interpretation limits
- Counterfactual one-ray benefits were computed in 08E after acquisition from *simulation truth and unacquired ray intensities*. They are legal **only for post-hoc evaluation**, not for selection.
- One-ray regret does not establish that choosing another ray would improve the entire future acquisition trajectory.
- The two policies follow different acquired histories, so their probe pools and provisional reconstructions differ; comparisons are descriptive, not same-state controlled ablations.
- There are just **two development objects per resolution**. No significance claims or favorable independent validation.
- The audit does not independently rerun MART or verify that 08E's saved counterfactual gains are numerically correct; it verifies file hashes and internal consistency of the recorded data.
- Existing frozen 06B and 07C2 results remain unchanged.

## Closeout (after reviewing results)
```powershell
git add audit_08f.py test_audit_08f.py README_08F.md
git diff --cached --check
git commit -m "Add read-only within-pool MART feedback regret audit"
git restore -- ":(glob)__pycache__/*.pyc"
git status --short
```
