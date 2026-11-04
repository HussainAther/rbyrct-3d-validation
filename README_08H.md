# RBYRCT-08H — Candidate availability, ranking and geometric opportunity audit

**Read-only, retrospective, development-only.** This analysis consumes the **completed 08E and 08G** archives. It does not rerun acquisition, MART reconstruction or phantom creation. It does not use defect masks or truth to select any ray. All defect-hit and one-ray-gain labels were recorded **after acquisition** in the source experiments.

## Scientific question

The preceding work found that the adaptive acquisition methods tended to intersect fewer localized defects and that their selected rays often missed stronger retrospective one-ray improvements. **08H separates candidate availability from ranking.** In each archived probe pool, it asks:

1. Does *any* candidate ray intersect the evaluation-defined defect mask? If not, the ranking algorithm cannot select a defect-intersecting ray from that pool.
2. When such candidates are available, did the **actual selected** ray (or highest-scoring gradient ray) miss them?
3. How much *immediate, retrospective* improvement was available from the best defect-RMSE and global-RMSE candidates? How much did the actual selected ray miss? How much opportunity did the guard exclude?
4. How geometrically similar are the candidate ray paths, according to nonnegative row cosine similarity of the known sparse projection matrix? Does the selected ray differ in overlap from the retrospectively best-defect ray?

The source experiments were **not paired**: 08E and 08G have different object seeds and acquisition histories. Outputs are grouped by **source × resolution × policy**, and means are computed **within object first**, then across the two development objects. Pools are nested within objects, not additional independent samples.

### Key definitions

- `has_defect_candidate`: at least one candidate in the pool has `defect_hit=1` (retrospective evaluation only).
- `hit_missed_when_available`: the pool has a defect-hit candidate, but the **actual selected** ray has `defect_hit=0`.
- `missed_given_available`: number of missed-hit pools divided by number of pools with any defect-hit candidate. Blank/`None` when no such pools exist; **not zero**.
- `defect_oracle_gain`: highest retrospective one-ray relative defect-RMSE improvement among the actual candidate pool, without knowing the truth at selection time. A **diagnostic upper bound on the one-step candidate benefit**, not a deployable policy or a guarantee of future trajectory quality.
- `defect_regret`: best retrospective defect gain minus selected ray's gain. `global_regret` analogously.
- `defect_guard_exclusion_gap`: best full-pool defect gain minus best gain among eligible candidates. It measures potential one-step opportunity excluded by the guard, not the actual causal effect of guarding.
- `mean_pairwise_cosine`: mean off-diagonal nonnegative row cosine of ray path-length vectors. Higher means paths are more geometrically overlapping. `pool_path_diversity = 1 - mean_pairwise_cosine`. These are **descriptive geometry scores**, not Fisher information or reconstruction conditioning.

## Windows PowerShell

Extract only these three files **directly into** `C:\Users\shuss\Downloads\rbyrct-3d-05a` (do not leave a second nested `test_audit_08h.py` directory, which can cause a pytest import mismatch).

```powershell
python -m pytest test_audit_08h.py -q
python -m pytest -q
git diff --check
```

The 08E and 08G studies were previously archived under `..\rbyrct-results`. Run:

```powershell
python audit_08h.py `
    --08e-dir ..\rbyrct-results\experiment08e\feedback_first `
    --08g-dir ..\rbyrct-results\experiment08g\disagreement_first `
    --output-dir ..\rbyrct-results\experiment08h\candidate_diagnostic_first
```

The default command includes sparse projection-matrix geometry, using existing `experiment_04b`, `experiment_04g`, and `experiment_08e` modules. If these dependencies are unavailable, `--no-geometry` runs the candidate-availability, ranking and oracle analysis alone and leaves geometric statistics blank. **Do not substitute the geometry-free output for a full geometric audit.**

Inspect results:

```powershell
$dir = '..\rbyrct-results\experiment08h\candidate_diagnostic_first'
Get-Content "$dir/audit_report.json"
Import-Csv "$dir/object_balanced_summary.csv" |
    Select-Object source,size,policy,n_objects,n_pools,pools_with_hits,pools_with_hit_missed,missed_given_available,mean_defect_regret,mean_global_regret,mean_pool_path_diversity |
    Format-List
```

Files written **only** under the new 08H output directory:

- `audit_report.json` — verdict, verified hashes and limitations.
- `pool_diagnostics.csv` — each candidate pool with actual selection, oracle, defect availability, and optional path diversity.
- `object_balanced_summary.csv` — development-object-balanced summaries **within each archive**, never combined as matched runs.
- `analysis_protocol.json` — definitions and scope.

`audit_08h.py` verifies each source archive's SHA-256 inventory, completion status, recorded manifest counts, candidate uniqueness, eligibility and selection. It refuses to overwrite an existing 08H output directory or write inside a source archive. It does **not** independently re-simulate physics or verify MART correctness. The full Windows archives have **not** been run through this tool here; the Windows result is needed for an 08H scientific interpretation.

## Reporting guidance

Interpret all findings as exploratory and retrospective. Even if a defect-hit candidate exists, that candidate may have **worse** one-ray defect benefit. Geometric intersection is not equivalent to useful independent information. A retrospective one-ray oracle is not an operational objective because it relies on unavailable simulated truth. Do not use any 08E/08G outcome to retune a supposedly held-out test, and do not claim clinical readiness, dose saving or statistically independent candidate-level replication.
