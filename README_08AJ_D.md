# RBYRCT 08AJ-D — prospective design package (DRAFT; not frozen)

## What is in this ZIP

- `experiment_08aj_d.py` — deterministic candidate phantom generators, 24-object seed manifest, proposed analysis/endpoint specification and source fingerprints.
- `experiment_08aj_d_analysis.py` — testable function for object-level paired primary analysis of **future** 32³ results. No actual outcome data are included.
- `test_experiment_08aj_d.py` — eight tests including phantom determinism, different families and rejection of missing/duplicate RMSE observations.
- `README_08AJ_D.md` — instructions and unresolved protocol decisions.

**Copy these four files into the root of `rbyrct-3d-05a`, alongside the 08AJ-B/C code and existing experimental modules.** Do not change archived 08M, 08AC or 08AD outputs.

## Commands (PowerShell)

```powershell
python -m pytest test_experiment_08aj_d.py -q
python experiment_08aj_d.py `
  --output-dir results\experiment08aj_d\design_draft_first
Get-Content results\experiment08aj_d\design_draft_first\run_status.json
```

Expected status is `DRAFT_PASS` with 24 proposed phantom objects, `no_outcome_data: true` and `frozen: false`. This is **not** a confirmatory experiment. Source fingerprints cover candidate implementation modules. Note that the source archive used to build this ZIP may differ from your local working tree; the report uses **your local files**.

## Primary analysis proposed

- 32³; 8 objects per family for 3 independent generator families; 24 total.
- Primary comparison: diagonal information versus uniform multiscale at 2048 selected rays.
- Two acquisition seeds and two matched/independent forward-model conditions are paired within each object.
- Paired condition gain `1 - RMSE(diag)/RMSE(uniform)`; average four condition gains **within each object**; grand mean of 24 object gains.
- Proposed 95% percentile bootstrap resamples eight objects within each family with replacement, 20,000 replicates, seed 941007. Inferential criterion is positive lower 95% CI bound; effect size and power/precision remain to be justified.
- Additional policies and endpoints are secondary; no claims from comparisons before lock.

## Unresolved blockers (do not freeze yet)

1. The three generators are proposed computational cases. Validate novelty and physical relevance, and check distinctness against historical experiments.
2. The new generators do not yet have a verified independent fine-grid forward-model adapter for each family; matched-only results cannot stand in for the declared two-model design.
3. Build, unit-test, and resource-gate the future 08AJ runner that uses the unchanged information selector and all baselines under the identical geometry and budgets. Do not run outcomes before the protocol is locked.
4. Specify exact noise-seed mapping, failure/timeout policy, resource gates, and source-lock hashes covering the future runner.
5. Document sample-size/precision rationale, bootstrap assumptions, practical relevance threshold and final candidate-baseline applicability.
6. Review design, freeze and **commit** the final locked protocol and sources before any confirmatory outcome runs.

The draft utility intentionally refuses `--freeze`, protecting against accidentally calling a partially specified design 'prespecified'. `experiment_08aj_d_analysis.py` is an import-only specification and cannot automatically consume reconstructed results from a nonlocked run.

## Scientific limitations

These are synthetic voxel fields and a simulated parallel-beam ray catalogue. No physical scanner, dose model, physical CT study, clinical suitability, or detector-response adaptation is established. A complete-view comparator at 2048 rays comprises only two 32³ detector views; label it as an acquisition-constraint contrast, not a straightforward like-for-like conventional full-angle baseline.
