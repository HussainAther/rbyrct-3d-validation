# RBYRCT-08A — Scale-aware incremental coverage: mathematical and geometry-only development

**Status: exploratory method development, not prospective reconstruction validation.** This stage does not use the frozen 07C2 truth, masks, measurements, outcomes, or acquisition histories, and cannot establish improved defect imaging.

## Motivation

The frozen 06A guard uses total prospective voxel path-length variance. With coverage vector `c` and a candidate ray's nonnegative sparse path-length vector `w`, let

- `C(c) = Var(c)` (population variance across `N=n³` voxels)
- `C(c+w) = Var(c+w)`
- old guard: `C(c+w_i) <= (1 + eta) C(c+w_ref)`, with `eta=0.05`; the coverage reference is the highest-scoring candidate under the original feedback-off geometry scorer, not the minimum-variance candidate.

The difference between candidates can become small compared with the accumulated `C`, making a fixed 5% tolerance nonbinding.

## Derivation and numerical implementation

Define the *incremental* coverage-variance change:

`Delta_i = C(c+w_i)-C(c)`.

Expanding the population variance gives the numerically stable exact identity

`Delta_i = (2/N) (c-mean(c)) dot w_i + (1/N) (w_i dot w_i) - (sum(w_i)/N)^2`.

Only the nonzero entries of `w_i` must be visited. `Delta_i` can be negative because some measurements reduce imbalance. The implementation does not subtract two large, nearly equal variances to obtain this delta.

**Developmental proposed guard:** within the same frozen candidate pool `P`, compute `Delta_min`, `Delta_max`, and `Delta_ref` for the *same original* coverage-reference candidate; admit candidate `i` when

`Delta_i <= Delta_ref + lambda*(Delta_max - Delta_min)`, with exploratory `lambda=0.25`.

`lambda` is a fraction of the **observed candidate spread**, not a percentage of total accumulated variance. This is a *pool-relative scale normalization*, not a proof of dimension/resolution-independent geometric quality. The choice 0.25 is an initial diagnostic value, not tuned to RMSE. No new acquisition policy is run at this stage.

### Proven properties and limitations

1. The coverage reference is always admissible by definition, so the eligible set is nonempty.
2. `lambda=0` admits all candidates no worse in incremental variance than the reference (not only the reference). `lambda=1` admits everyone. The admissible sets are nested as `lambda` increases.
3. If **both coverage and ray weights** are scaled by any positive constant, all `Delta` scores scale quadratically and the eligible set is unchanged, apart from floating-point effects.
4. If the candidate deltas are identical, all are admitted. If the reference is the largest delta, all are admitted even at `lambda=0`; a guard cannot be guaranteed to bind.
5. The candidate-range denominator depends on the random candidate pool; results may be noisy at small pool sizes. Small or zero spreads require explicit numerical care.
6. This rule does not guarantee monotonically decreasing coverage variance, nor improved reconstruction accuracy, nor fewer rays/dose.
7. The reference remains the ORIGINAL coverage-only scorer, which is not necessarily the minimum-variance candidate. Changing that definition would be another methodological intervention.
8. This stage is strictly geometry-only; future tests of acquired-only gating must precede any reconstruction comparison.

## Files

- `experiment_08a.py`: stable incremental-delta evaluator and two-guard geometry diagnostics.
- `test_experiment_08a.py`: exact-identity, invariance, admissibility, validation and smoke tests.
- `README_08A.md`: derivation and study boundaries.

## Windows PowerShell

Extract the three files into your `rbyrct-3d-05a` repository. Then:

```powershell
python -m pytest test_experiment_08a.py -q
python -m pytest -q
git diff --check
python experiment_08a.py --output-dir results/experiment08a/geometry_first
```

The diagnostic creates **new geometry-only coverage histories** with seed `808001` at 12³ and 32³. It evaluates eight deterministic candidate pools per prefix using 16 candidates each. The four 12³ prefixes are 24/144/288/576; 32³ prefixes are 64/1024/2048/4096. It intentionally does not load `results/experiment07c2` or the archived results. No object simulation, no ray acquisition, no MART reconstruction, no accuracy evaluation. The output folder must be empty/nonexistent.

Inspect output:

```powershell
$dir = 'results/experiment08a/geometry_first'
Import-Csv "$dir/summary.csv" | Format-Table -AutoSize
Get-Content "$dir/protocol.json"
```

Save outputs outside the source tree and commit **code only** after review. A subsequent 08B phase should implement the new acquisition selector behind acquired-only gates, demonstrate invariants, and use *new development-only* phantoms. Any future frozen validation must use fresh held-out object seeds.
