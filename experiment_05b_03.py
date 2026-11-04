"""05B-03 exploratory diagnostic-versus-feedback utility, matched-prefix MART.

Uses only acquired observations when selecting or diagnosing. Synthetic truth is
used exclusively to score reconstructions after a continuation is selected.
This is not a calibrated reliability gate or a confirmatory causal estimate.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_04m import high_resolution_matrix
from experiment_05b_04p import object_pair
from experiment_05b_adaptive import adaptive_order
from experiment_05b_diagnostics import acquired_only_reliability
from experiment_05b_gate import AcquiredOnly
from experiment_05b_mart import mart_reconstruct
from experiment_05b_04s import continue_after_prefix
from experiment_05b_resources import validate_grid


def analyze_case(A, observations, truth, n, angles, warm, seed, budget,
                 warm_rays, batch, candidate_pool, provisional_epochs,
                 diagnostic_epochs, final_epochs, relaxation, switches, holdout=.2):
    """Return per-prefix paired contrasts, with no truth in decision functions."""
    references = {}
    for name, strength in (("adaptive", 1.), ("off", 0.)):
        reference, _, _ = adaptive_order(
            A, observations, n, angles, warm, budget, seed,
            warm_rays=warm_rays, batch=batch,
            provisional_epochs=provisional_epochs,
            candidate_pool=candidate_pool, feedback_strength=strength,
            mart_relaxation=relaxation,
        )
        references[name] = reference

    rows = []
    for source, reference in references.items():
        for k in switches:
            prefix = reference[:k]
            oracle = AcquiredOnly(observations)
            oracle.commit(prefix)
            diag = acquired_only_reliability(
                A, oracle, prefix, n, epochs=diagnostic_epochs,
                holdout_fraction=holdout, seed=seed + 13*k,
                mart_relaxation=relaxation,
            )
            continuations = {}
            for name, strength in (("adaptive", 1.), ("off", 0.)):
                order = continue_after_prefix(
                    A, oracle.values, n, angles, prefix, seed, budget,
                    strength, warm_rays, batch, candidate_pool,
                    provisional_epochs, mart_relaxation=relaxation,
                )
                assert np.array_equal(order[:k], prefix)
                if source == name and not np.array_equal(order, reference):
                    raise AssertionError(f"Same-policy replay mismatch: {source} at {k}")
                # Offline scoring: only now does the truth enter the computation.
                x = mart_reconstruct(A[order], observations[order], final_epochs,
                                     relaxation=relaxation)
                continuations[name] = (order, float(np.sqrt(np.mean((x-truth)**2))))
            adap_order, adap_rmse = continuations["adaptive"]
            off_order, off_rmse = continuations["off"]
            overlap = len(set(map(int, adap_order[k:])) & set(map(int, off_order[k:])))
            remaining = budget-k
            rows.append(dict(
                source_policy=source, switch_at=k, budget=budget,
                heldout_nrmse=diag['heldout_nrmse'],
                feature_split_correlation=diag['feature_split_correlation'],
                feature_instability=diag['feature_instability'],
                n_train=diag['n_train'], n_holdout=diag['n_holdout'],
                adaptive_rmse=adap_rmse, off_rmse=off_rmse,
                gain_feedback=(off_rmse-adap_rmse)/max(off_rmse, 1e-12),
                feedback_wins=int(adap_rmse < off_rmse),
                continuation_set_divergence=1-overlap/remaining,
                continuation_position_disagreement=float(np.mean(adap_order[k:] != off_order[k:])),
            ))
    return rows


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--size', type=int, default=8)
    p.add_argument('--angles', type=int, default=4)
    p.add_argument('--factor', type=int, default=2)
    p.add_argument('--phantoms', nargs='+', choices=['branches','layers','pores','defects'], default=['branches','defects'])
    p.add_argument('--representations', nargs='+', choices=['replicated','subvoxel'], default=['replicated'])
    p.add_argument('--seeds', nargs='+', type=int, default=[271828,314159])
    p.add_argument('--offset', type=float, default=0.)
    p.add_argument('--budget', type=int, default=128)
    p.add_argument('--warm-rays', type=int, default=16)
    p.add_argument('--batch', type=int, default=8)
    p.add_argument('--candidate-pool', type=int, default=16)
    p.add_argument('--switches', nargs='+', type=int, default=[32,64,96])
    p.add_argument('--provisional-epochs', type=int, default=4)
    p.add_argument('--diagnostic-epochs', type=int, default=8)
    p.add_argument('--mart-epochs', type=int, default=16)
    p.add_argument('--mart-relaxation', type=float, default=.25)
    p.add_argument('--holdout-fraction', type=float, default=.2)
    p.add_argument('--output-dir', type=Path, default=Path('results/experiment05b/diagnostic_validation'))
    p.add_argument('--allow-large', action='store_true')
    a = p.parse_args(argv)
    try:
        validate_grid(a.size, a.factor, a.allow_large)
    except (ValueError, OSError) as exc:
        p.error(str(exc))
    ray_count = a.size**2 * a.angles * len(TILTS)
    if (a.angles < 2 or a.warm_rays < 12 or not a.warm_rays < a.budget <= ray_count
            or a.batch < 1 or a.candidate_pool < 1 or a.provisional_epochs < 1
            or a.diagnostic_epochs < 1 or a.mart_epochs < 1
            or not np.isfinite(a.mart_relaxation) or not 0 < a.mart_relaxation <= 1
            or not np.isfinite(a.offset) or a.offset < 0
            or not 0 < a.holdout_fraction < .5
            or not a.switches or len(set(a.switches)) != len(a.switches)
            or any(not a.warm_rays < k < a.budget or (k-a.warm_rays)%a.batch for k in a.switches)):
        p.error('Invalid 05B-03 configuration or switch must be a batch boundary')
    if a.output_dir.exists() and any(a.output_dir.iterdir()):
        p.error('Output directory must be empty; use a new --output-dir')
    A = system_matrix(a.size, a.angles, TILTS).tocsr()
    M = high_resolution_matrix(a.size, a.angles, TILTS, a.factor, a.offset)
    results = []
    for phantom in a.phantoms:
        pairs = object_pair(phantom, a.size, a.factor)
        for rep in a.representations:
            truth, fine = pairs[rep]
            observations = np.asarray(M @ fine).ravel()
            for seed in a.seeds:
                warm = voxel_coverage_order(A, a.size, a.angles, len(TILTS),
                                            a.budget, seed, a.candidate_pool)
                rows = analyze_case(A, observations, truth, a.size, a.angles, warm,
                                    seed, a.budget, a.warm_rays, a.batch, a.candidate_pool,
                                    a.provisional_epochs, a.diagnostic_epochs,
                                    a.mart_epochs, a.mart_relaxation, a.switches,
                                    a.holdout_fraction)
                for row in rows:
                    results.append(dict(phantom=phantom, representation=rep, seed=seed,
                                        relaxation=a.mart_relaxation, **row))
                    print(f"{phantom} {rep} seed={seed} {row['source_policy']} "
                          f"prefix={row['switch_at']} holdout={row['heldout_nrmse']:.3f} "
                          f"feature_r={row['feature_split_correlation']:.3f} "
                          f"feedback_gain={row['gain_feedback']:+.3%}", flush=True)
    a.output_dir.mkdir(parents=True, exist_ok=True)
    with (a.output_dir/'matched_prefix_diagnostics.csv').open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f, fieldnames=list(results[0]));writer.writeheader();writer.writerows(results)
    protocol = dict(experiment='05B-03 exploratory matched-prefix diagnostic validation',
                    parameters={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},
                    n_rows=len(results),
                    interpretation='Gain is an offline paired counterfactual simulation difference, not causal clinical evidence.',
                    limitations=['Single synthetic ray-tracer family', 'Noiseless data',
                                 'Repeated prefixes within same phantom/seed are dependent',
                                 'Do not calibrate thresholds and evaluate on same cases',
                                 'No guarantee either diagnostic predicts acquisition gain'])
    (a.output_dir/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf8')
    print(f"05B-03 complete: {len(results)} prefix comparisons in {a.output_dir}")
    return results


if __name__ == '__main__':
    main()
