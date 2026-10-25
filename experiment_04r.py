"""04R exploratory ray-trajectory pilot for the frozen 04P acquisition methods.

This script IMPORTS the original frozen selector; it does not modify it.
Reconstruction checkpoints and comparisons use ground truth only OFFLINE.
Run from the root of rbyrct-3d-validation in the rbyrct-3d environment.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np
import scipy

from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_04i import noisy_full_projection
from experiment_04j import adaptive_order, sirt_silent
from experiment_04m import high_resolution_matrix
from experiment_04p import object_pair


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        raise ValueError(f'No rows for {path}')
    with path.open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def hash_indices(arr):
    return hashlib.sha256(np.asarray(arr, dtype='<i8').tobytes()).hexdigest()


def make_checkpoints(warm, batch, budget):
    # Include the warm prefix, full-budget endpoint, and diagnostic cadence checkpoints.
    # Diagnostics in 04P occur every 256 acquired rays after the 128-ray warm start.
    points = {warm, budget}
    k = warm + 256
    while k < budget:
        points.add(k)
        k += 256
    return sorted(points)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--phantom', choices=['branches', 'layers', 'pores', 'defects'], default='defects')
    ap.add_argument('--size', type=int, default=16)
    ap.add_argument('--angles', type=int, default=12)
    ap.add_argument('--factor', type=int, default=2)
    ap.add_argument('--offset', type=float, default=0.0)
    ap.add_argument('--seed', type=int, default=271828)
    ap.add_argument('--budget', type=int, default=2048)
    ap.add_argument('--warm-rays', type=int, default=128)
    ap.add_argument('--batch', type=int, default=64)
    ap.add_argument('--candidate-pool', type=int, default=64)
    ap.add_argument('--provisional-iterations', type=int, default=60)
    ap.add_argument('--sirt-iterations', type=int, default=400)
    ap.add_argument('--output-dir', type=Path, default=Path('results/experiment04r_pilot'))
    args = ap.parse_args()
    if args.budget <= args.warm_rays or args.warm_rays < 12 or args.budget > args.size**2 * args.angles * len(TILTS):
        ap.error('Invalid budget/warm start for the requested geometry')
    if args.batch <= 0 or args.candidate_pool <= 0 or args.sirt_iterations <= 0 or args.provisional_iterations <= 0 or args.factor < 2 or args.offset < 0:
        ap.error('Invalid numeric argument')
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        ap.error(f'Output directory is not empty: {args.output_dir}; use a fresh directory')
    args.output_dir.mkdir(parents=True, exist_ok=True)

    A = system_matrix(args.size, args.angles, TILTS).tocsr()
    M = high_resolution_matrix(args.size, args.angles, TILTS, args.factor, args.offset)
    warm = voxel_coverage_order(A, args.size, args.angles, len(TILTS), args.budget, args.seed, args.candidate_pool)
    checkpoints = make_checkpoints(args.warm_rays, args.batch, args.budget)

    selected_rows, divergence_rows, checkpoint_rows, metric_rows = [], [], [], []
    for representation in ('replicated', 'subvoxel'):
        truth, fine = object_pair(args.phantom, args.size, args.factor)[representation]
        clean = np.asarray(M @ fine).ravel()
        noise_seed = (args.seed + int(hashlib.sha256(f'{args.phantom}:{0.:.12g}'.encode()).hexdigest()[:8], 16)) % (2**32)
        observed = noisy_full_projection(clean, 0., noise_seed)

        orders = {}
        for policy, strength in (('adaptive_feedback', 1.), ('feedback_off_control', 0.)):
            order, _, _ = adaptive_order(A, observed, args.size, args.angles, warm,
                                          args.budget, args.seed, args.warm_rays,
                                          args.batch, args.provisional_iterations,
                                          args.candidate_pool, strength)
            order = np.asarray(order, dtype=np.int64)
            if len(order) != args.budget or len(np.unique(order)) != args.budget or np.any(order < 0) or np.any(order >= A.shape[0]):
                raise AssertionError(f'Invalid ray order for {representation}/{policy}')
            if not np.array_equal(order[:args.warm_rays], np.asarray(warm)[:args.warm_rays]):
                raise AssertionError(f'Warm prefix changed for {representation}/{policy}')
            orders[policy] = order
            for pos, ray in enumerate(order):
                selected_rows.append(dict(phantom=args.phantom, representation=representation,
                                          offset=args.offset, seed=args.seed, budget=args.budget,
                                          policy=policy, acquisition_position=pos+1,
                                          ray_index=int(ray), view_index=int(ray)//(args.size**2),
                                          detector_index=int(ray)%(args.size**2),
                                          warm_start=int(pos < args.warm_rays)))
            for k in checkpoints:
                ids = order[:k]
                # Offline evaluation only: selector NEVER receives truth.
                x = sirt_silent(A[ids], observed[ids], args.sirt_iterations)
                rmse = float(np.sqrt(np.mean((np.asarray(x).ravel() - np.asarray(truth).ravel())**2)))
                checkpoint_rows.append(dict(phantom=args.phantom, representation=representation,
                                             offset=args.offset, seed=args.seed, budget=args.budget,
                                             policy=policy, acquired=k, rmse=rmse,
                                             selected_prefix_sha256=hash_indices(ids)))
                if k == args.budget:
                    metric_rows.append(dict(phantom=args.phantom, representation=representation,
                                            offset=args.offset, seed=args.seed, budget=args.budget,
                                            policy=policy, rmse=rmse))
                print(f'{representation:10s} {policy:22s} rays={k:4d} RMSE={rmse:.6f}', flush=True)

        adap = orders['adaptive_feedback']
        off = orders['feedback_off_control']
        for k in checkpoints:
            overlap = len(set(map(int, adap[:k])) & set(map(int, off[:k])))
            divergence_rows.append(dict(phantom=args.phantom, representation=representation,
                                        offset=args.offset, seed=args.seed, budget=args.budget,
                                        acquired=k, overlap=overlap,
                                        set_divergence=1-overlap/k,
                                        position_disagreement=float(np.mean(adap[:k] != off[:k]))))

    write_csv(args.output_dir/'selected_rays.csv', selected_rows)
    write_csv(args.output_dir/'prefix_divergence.csv', divergence_rows)
    write_csv(args.output_dir/'reconstruction_checkpoints.csv', checkpoint_rows)
    write_csv(args.output_dir/'final_metrics.csv', metric_rows)
    for rep in ('replicated', 'subvoxel'):
        sub = {r['policy']: r['rmse'] for r in metric_rows if r['representation'] == rep}
        gain = (sub['feedback_off_control'] - sub['adaptive_feedback']) / sub['feedback_off_control']
        print(f'FINAL {rep}: paired adaptive gain {100*gain:+.3f}%')
    protocol = dict(experiment='04R exploratory selected-ray pilot', input_study='04P',
                    design='Selected defect family and single seed; NOT independent confirmatory evidence',
                    arguments={k: str(v) if isinstance(v, Path) else v for k,v in vars(args).items()},
                    checkpoints=checkpoints, python=sys.version, platform=platform.platform(),
                    numpy=np.__version__, scipy=scipy.__version__,
                    limitations=['Exact frozen 04J adaptive selector, original 04P observation model',
                                 'No randomized causal policy switching performed',
                                 'Prefix RMSE uses synthetic truth only for offline evaluation',
                                 'Selected-ray divergence is descriptive, not a causal explanation',
                                 'Replicated and subvoxel targets differ as in original Study 1'])
    (args.output_dir/'protocol.json').write_text(json.dumps(protocol, indent=2), encoding='utf-8')
    print(f'04R outputs written to {args.output_dir}')


if __name__ == '__main__':
    main()
