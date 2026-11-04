# RBYRCT-08I: Retrospective candidate-ranking mechanism audit

**Scope:** This is a read-only, development-only study of archived 08E and 08G candidate pools. It never performs acquisition or MART reconstruction and never changes the original source archives. It uses `audit_08h.py` (already committed at 08H) for hash verification, integrity checks, and candidate grouping.

## Research questions

1. Within each pool, do rays crossing the evaluation-only synthetic defect region systematically receive worse gradient-score ranks than non-hitting rays?
2. Does the retrospective *highest one-ray defect-improvement* candidate actually intersect the defect? (A ray-defect crossing is not sufficient or necessary for immediate RMSE improvement.)
3. When a defect-hitting candidate is available, does its best retrospective defect gain exceed the selected candidate's gain?
4. On 08G only, does split-history disagreement rank defect-intersecting candidates differently from the gradient score?

## Measures and interpretation

For each candidate pool, the script reports hit and nonhit counts, mean descending gradient-score ranks (rank 1 is highest), mean hit-minus-nonhit rank gap (positive means hits rank worse), and pairwise score-win fractions. A fraction of **0.5** indicates no hit/nonhit ranking preference among evaluated pairs; a fraction below 0.5 favors nonhit rays. It also records whether the defect-gain oracle intersects a defect, the number of hit candidates whose one-ray benefit exceeds the selected candidate's, and the best-hit versus best-nonhit immediate benefit difference. Undefined within-pool contrasts are left blank when one class is absent.

The oracle is retrospective and knows simulated truth. It is **never** a deployable policy or a guarantee about later acquisition. Scores and immediate gains are not identical scientific quantities. 08E and 08G use different development objects; summaries remain separate and first average within each object. Each condition has few independent objects, so descriptive counts and means are **not statistical evidence of general population effects**.

## Windows PowerShell instructions

Extract these three files **directly into** `rbyrct-3d-05a`, not into a nested copy. The existing `audit_08h.py` must be in that same directory.

```powershell
python -m pytest test_audit_08i.py -q
python -m pytest -q
git diff --check
```

Run against already archived source results:

```powershell
python audit_08i.py `
    --08e-dir ..\rbyrct-results\experiment08e\feedback_first `
    --08g-dir ..\rbyrct-results\experiment08g\disagreement_first `
    --output-dir ..\rbyrct-results\experiment08i\ranking_mechanism_first
```

Inspect:

```powershell
$dir = "..\rbyrct-results\experiment08i\ranking_mechanism_first"
Get-Content "$dir/audit_report.json"
Import-Csv "$dir/object_balanced_summary.csv" |
    Select-Object source,size,policy,n_objects,n_pools,pools_with_hit,pools_oracle_hit,pools_hit_beats_selected,mean_hit_minus_nonhit_rank,mean_hit_score_pairwise_win_fraction,mean_hit_defect_gain_pairwise_win_fraction |
    Format-List
```

Outputs: `audit_report.json`, `analysis_protocol.json`, `pool_rank_diagnostics.csv`, `object_balanced_summary.csv`. The output directory **must not already exist**. The script verifies the SHA-256 inventories for each source archive and rejects malformed or missing candidate histories.

## Scientific boundary

If defect-hitting candidates are ranked low but actually exhibit better one-ray defect gains, that would support the *development-only hypothesis* of ranking misalignment. If the best retrospective defect-gain candidates rarely intersect defects, then geometric intersection is a poor proxy for short-term value and the interpretation needs to change. Neither finding proves causation or validates a new selection rule. No parameters or frozen 06B/07C2 results are changed.
