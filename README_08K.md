# RBYRCT-08K — Exploratory sequential information acquisition

**Development only; not held-out validation.** This package adds a fourth real sequential acquisition policy to 08C's unchanged reconstruction comparison. The existing coverage, gradient, and incremental_25 selectors are called without modification. The new policy is named `information_diag`.

## Scientific question

Does 08J's geometry-only diagonal precision score improve **complete acquired-only sequential MART reconstruction** at equal ray counts, or did its retrospective candidate-ranking improvement fail to translate into an acquisition-policy advantage?

## Information score and limitations

Let `A_H` contain the known rows of already acquired rays. With fixed model values `prior_variance=1`, `observation_variance=1`, calculate

```
D_j = 1/(1/prior_variance + sum_{i in H}(A_ij**2)/observation_variance)
S(a) = sum_j(a_j**2 * D_j**2) / (observation_variance + sum_j(a_j**2 * D_j))
```

`D` is the inverse of a **diagonal approximate precision**. It is *not* the diagonal of the exact posterior covariance; it is not calibrated MART uncertainty. The new selector updates its diagonal precision surrogate after every selected ray, draws candidate pools with the existing deterministic `seed+317` procedure, and commits selected ray IDs after each batch. It does **not** index the detector observations when selecting, nor access phantom, mask, candidate responses, or unmeasured detector values. This geometry-only behavior also means it cannot adapt to actual intensity values; interpret this as a geometry-aware information-design comparison, not a measurement-feedback breakthrough.

## Prespecified exploratory configuration

- Resolution: 12³ and 32³, four views and the existing tilt set.
- Fresh object seeds: 12³ `810201, 810202`; 32³ `810301, 810302`.
- Forward models: `same`, `independent`; matched noise generation from 08C.
- Policies: `coverage`, `gradient`, `incremental_25`, `information_diag`.
- Budgets/checkpoints: 12³ `144/288`; 32³ `512/1024`.
- Warm rays: 12³ `24`; 32³ `64`.
- Batches: 12³ `16`; 32³ `32`; candidate pool `16`.
- Original gradient provisional MART: `2` epochs; final MART for all policies `16` epochs; relaxation `.25`.
- Evaluation-only whole-volume, defect-region, nondefect RMSE; report paired gains versus the coverage policy.
- **32 acquisition histories, 64 checkpoint reconstructions.** Object, not checkpoint or ray, is the independent replication unit. Just two objects per size; treat outcomes as descriptive only.

No parameter grid search, retroactive tuning, or new success gate. In particular, 08K may not reuse reserved 06B/07C2/08C or 08J object seeds. The information policy is allowed to differ from 08J's single-state ranking because the entire acquisition history changes after each decision.

## Windows commands

Extract **only** `experiment_08k.py`, `test_experiment_08k.py`, `README_08K.md` directly into your existing `rbyrct-3d-05a` repository root. Avoid a nested duplicate test directory.

```powershell
python -m pytest test_experiment_08k.py -q
python -m pytest -q
git diff --check
python experiment_08k.py --output-dir results/experiment08k/information_sequential_first
```

Read the results:

```powershell
$dir = "results/experiment08k/information_sequential_first"
Get-Content "$dir/run_status.json"
Import-Csv "$dir/aggregate_summary.csv" | Format-List size,acquired,policy,n_objects,mean_global_gain,mean_defect_gain,object_global_wins,object_defect_wins
```

The runner writes `protocol.json`, `environment.json`, `object_manifest.csv`, per-ray `acquisition_orders.csv`, per-checkpoint `prefix_reconstructions.csv`, `object_level_summary.csv`, `aggregate_summary.csv`, `run_status.json`, and `sha256.json`. Do not interpret partial outputs as completed. It refuses to overwrite prior output folders.

## Interpretive boundaries

1. The information score compares geometry-based hypothetical trace reduction under a diagonal Gaussian proxy, **not** actual Bayesian information gain or a MART theorem.
2. Stronger retrospective ranking in 08J is not evidence of improved final trajectories in 08K.
3. No physical-dose reduction, clinical validity, statistical significance, or independent confirmation is claimed.
4. Preserve all unfavorable outcomes; if promising, design a **new independently seeded frozen** evaluation instead of retuning 08K until it wins.
