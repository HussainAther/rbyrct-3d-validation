# RBYRCT-08T — Exact-versus-diagonal A-optimal ranking diagnostic

## Purpose

Directly assess the fidelity of the geometry-based diagonal covariance surrogate used in 08J/08K/08M by comparing it to the *full* linear-Gaussian posterior covariance trace-reduction score. This is an exploratory **method diagnostic**, not a new outcome validation or a justification for retuning 08M.

The exact reference is computed by the Woodbury identity in acquired-measurement space, without constructing a 32,768 × 32,768 posterior covariance matrix:

    C = τ²I − τ⁴ Hᵀ(σ²I + τ² H Hᵀ)⁻¹H
    S_exact(a) = ||Ca||² / (σ² + aᵀCa)

The diagonal surrogate implements the same 08J score and frozen parameters independently:

    D_j = [τ⁻² + σ⁻² ∑ acquired H_ij²]⁻¹
    S_diag(a) = (aᵀD²a) / (σ² + aᵀDa)

The prior and observation variances stay at their original values of 1.0. Neither score measures MART posterior uncertainty.

## Predeclared diagnostic

- Source: archived frozen 08M `acquisition_orders.csv`, read-only.
- Resolution 32³, original geometry: 4 angles and frozen tilt values.
- One representative archived object/model history per seed, since coverage and information ordering are object independent.
- Policies: `coverage` and `information_diag`.
- Acquisition seeds: 820443, 820861.
- Prefix lengths: 64, 256, 512 acquired rays.
- Pool: 16 unique candidate rays, including the next archived ray and 15 deterministic unacquired random rays.
- Metrics: Spearman score association, selected top-1 agreement, exact-score regret of diagonal selection, compute time.
- 12 pools / 192 candidate rows, no reconstructions.

## Windows PowerShell

Extract `experiment_08t.py`, `test_experiment_08t.py`, and this README directly into `rbyrct-3d-05a` root (no duplicate nested folder).

```powershell
python -m pytest test_experiment_08t.py -q
python -m pytest -q
python experiment_08t.py `
    --results-dir ..\rbyrct-results\experiment08m\frozen_first `
    --output-dir results/experiment08t/exact_vs_diagonal_first
```

Then:

```powershell
$dir = 'results/experiment08t/exact_vs_diagonal_first'
Get-Content "$dir/run_status.json"
Import-Csv "$dir/summary.csv" | Format-Table -AutoSize
```

Do not use the result to alter the frozen 08M score. This diagnostic can motivate a distinct future exploratory head-to-head 12³ MART study, after explicitly defining its protocol.

## Interpretation boundary

A strong score correlation does not imply equal ray orders. A difference in exact and diagonal rankings is not evidence that exact covariance will yield better MART reconstructions. The exact criterion is optimal only for its *specified linear-Gaussian trace objective* under fixed geometric measurements, not for nonlinear MART RMSE or clinical acquisition.
