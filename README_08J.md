# RBYRCT-08J: acquired-only diagonal-precision acquisition diagnostics

## Scope

This is a **development-only, non-deployed ranking diagnostic**. The original 08E gradient and incremental_25 selectors generate fresh acquisition histories. After each history completes, the candidate pools are evaluated retrospectively; the proposed information score sees *only acquired ray geometry*. No new sequential policy or held-out validation is claimed. Existing 06B and 07C2 frozen studies remain untouched.

## Mathematical derivation and limitations

For a **hypothetical linear model** y=A x+epsilon with independent Gaussian prior variance tau² and homoscedastic Gaussian observation noise variance sigma², the posterior precision is tau⁻² I + sigma⁻² A_H^T A_H. Its inverse is **generally not diagonal**.

For computational feasibility 08J explicitly replaces the full posterior covariance by the **inverse diagonal of that precision**:

D_j = 1 / (tau⁻² + sigma⁻² sum_{i in H} A_ij²).

For a proposed measurement row `a`, suppose the current uncertainty covariance were instead exactly `D=diag(D_j)`. The Sherman–Morrison one-step update is

D_new = D − (D a a^T D) / (sigma² + a^T D a).

The resulting **hypothetical trace reduction** is

S_info(a) = tr(D−D_new) = (a^T D² a)/(sigma² + a^T D a) >= 0.

It is exactly nonnegative for positive variances and nonnegative row squares. An all-zero row has score zero. Under repeated observations, each individual D_j decreases, but a fixed candidate's **trace-reduction score need not decrease monotonically** because its numerator and denominator change together. Do not claim monotonic ranking or actual error reduction. The score is invariant to candidate ordering (up to the same permutation), and deterministic with identical geometry and parameters.

**Crucial boundaries**: `D` is not `diag(true posterior covariance)`, the score is not calibrated uncertainty, and MART is a nonlinear algorithm for which this derivation does **not** establish realized RMSE reduction. The hypothetical rank-one update uses a *full* updated covariance even though the current approximation is diagonal; subsequently recomputing `D` by diagonal precision is a separate approximation. Fixed parameters tau²=sigma²=1 are developmental units and should not be presented as measured physical noise or tuned to prior validation outcomes. The approximation can favor geometric coverage without detecting defects.

## Inputs and information firewall

`info_score(A_acquired, A_candidates, ...)` has no argument for acquired/candidate detector readings, truth, evaluation masks, or reconstruction error. It uses only acquired geometry and prospective known ray geometry. The existing selector uses `AcquiredOnly` for gradient or incremental acquisition; only **after the entire history completes**, candidate-specific counterfactuals use unseen detector values and truth to produce retrospective labels. New object seeds are disjoint from 08E/08G and frozen 06B/07C2.

## Development design

| Parameter | Value |
| --- | --- |
| Grid sizes | 12³, 32³ |
| Objects | 2 new objects per size |
| Existing acquisition histories | gradient, incremental_25 |
| Probes | 2 per history |
| Candidate pool | 16 |
| Total histories | 8 |
| Total pools | 16 |
| Candidate rows | 256 |
| Matched model noise fraction | 0.005 |
| Retrospective MART epochs | 16 |
| Fixed score prior variance | 1.0 |
| Fixed score observation variance | 1.0 |

The test reports object-balanced regret and within-pool Spearman score correlations with retrospective one-ray benefit. This is **not** a full acquisition-policy performance experiment. Do not treat 256 candidate rows as independent replicates.

## Windows PowerShell

Extract only `experiment_08j.py`, `test_experiment_08j.py`, and `README_08J.md` to the existing `rbyrct-3d-05a` root (avoid duplicate nested folders).

```powershell
python -m pytest test_experiment_08j.py -q
python -m pytest -q
git diff --check
python experiment_08j.py `
    --output-dir results/experiment08j/information_first
```

Inspect:

```powershell
$dir = 'results/experiment08j/information_first'
Get-Content "$dir/run_status.json"
Import-Csv "$dir/object_balanced_summary.csv" |
    Select-Object size,policy,n_objects,n_pools,info_defect_regret,existing_defect_regret,info_global_regret,existing_global_regret,info_defect_spearman,gradient_defect_spearman,info_selected_defect_hit,actual_selected_defect_hit |
    Format-List
```

The experiment refuses to overwrite nonempty output directories. Results are exploratory; favorable or unfavorable scores should be preserved without retroactive tuning.

## Artifacts

- `candidate_diagnostics.csv`: each candidate's acquired-only score plus **later** truth-dependent evaluation labels.
- `pool_diagnostics.csv`: individual pool regrets, rank correlations, and oracle comparisons.
- `object_balanced_summary.csv`: pool->object->condition aggregation.
- `acquisition_manifest.csv`: original policy histories and hashes.
- `protocol.json`, `run_status.json`, `sha256.json`: provenance, completion and file hashes.
