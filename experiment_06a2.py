"""RBYRCT-06A2: bounded 8^3 coverage-guard development evaluation.

Exploratory, NOT held-out evidence. 06A2 uses deterministic 05B-04P development
phantoms only. The baseline scorer, MART, and guard implementation are unchanged.
Truth and full simulated measurements are used only for OFFLINE evaluation;
online selection is enforced by AcquiredOnly.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_04m import high_resolution_matrix
from experiment_05b_04 import select_order
from experiment_05b_04p import object_pair
from experiment_05b_gate import AcquiredOnly
from experiment_05b_mart import mart_reconstruct
from experiment_06a import acquire_guarded

# Development settings chosen before 06A2 evaluation, not from held-out outcomes.
SIZE = 8
ANGLES = 4
FACTOR = 2
FAMILIES = ('branches', 'layers', 'defects')
REPRESENTATIONS = ('replicated', 'subvoxel')
SEEDS = (271828, 314159)
POLICIES = ('coverage', 'gradient', 'strict', 'guarded_05')
BUDGET = 128
WARM_RAYS = 16
BATCH = 8
POOL = 16
PROVISIONAL_EPOCHS = 4
FINAL_EPOCHS = 16
RELAXATION = .25
OFFSET = 0.


def ray_digest(order):
    return hashlib.sha256(np.asarray(order, dtype='<i8').tobytes()).hexdigest()


def write_rows(path, rows):
    if not rows:
        raise ValueError('no records to write')
    with path.open('w', newline='', encoding='utf8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_case(A, observed, truth, warm, *, seed, n=SIZE, angles=ANGLES,
             budget=BUDGET, warm_rays=WARM_RAYS, batch=BATCH,
             candidate_pool=POOL, provisional_epochs=PROVISIONAL_EPOCHS,
             final_epochs=FINAL_EPOCHS, relaxation=RELAXATION):
    """Four matched acquisitions, with acquired-only oracle per policy."""
    if len(warm) < warm_rays or len(set(map(int, warm[:warm_rays]))) != warm_rays:
        raise ValueError('invalid warm prefix')
    results, audits, orders = [], [], {}
    for policy in POLICIES:
        oracle = AcquiredOnly(observed)
        oracle.commit(warm[:warm_rays])
        if policy in ('coverage', 'gradient'):
            order, trace, selection_s = select_order(
                A, oracle, n, angles, warm, budget, seed, policy=policy,
                warm_rays=warm_rays, batch=batch, candidate_pool=candidate_pool,
                provisional_epochs=provisional_epochs, relaxation=relaxation)
        else:
            eta = 0. if policy == 'strict' else .05
            order, trace, selection_s = acquire_guarded(
                A, oracle, n, angles, warm, budget, seed, eta=eta,
                warm_rays=warm_rays, batch=batch, candidate_pool=candidate_pool,
                provisional_epochs=provisional_epochs, relaxation=relaxation)
            audits.extend(dict(policy=policy, **item) for item in trace)
        if len(order) != budget or len(np.unique(order)) != budget:
            raise AssertionError('nonunique or incomplete ray order')
        if not np.array_equal(order[:warm_rays], warm[:warm_rays]):
            raise AssertionError('warm prefix differs')
        if len(oracle.allowed) != budget:
            raise AssertionError('measurement acquisition was not fully committed')
        start = time.perf_counter()
        reconstruction = mart_reconstruct(A[order], observed[order], final_epochs,
                                           relaxation=relaxation)
        reconstruction_s = time.perf_counter() - start
        if not np.isfinite(reconstruction).all() or (reconstruction <= 0).any():
            raise AssertionError('invalid MART reconstruction')
        rmse = float(np.sqrt(np.mean((reconstruction-truth)**2)))
        orders[policy] = order
        results.append(dict(policy=policy, rmse=rmse, selection_s=selection_s,
                            reconstruction_s=reconstruction_s,
                            ray_order_sha256=ray_digest(order),
                            unique_rays=len(np.unique(order)),
                            acquired_only_verified=1))
    coverage = orders['coverage']
    base_rmse = next(row['rmse'] for row in results if row['policy'] == 'coverage')
    for row in results:
        row['gain_vs_coverage'] = (base_rmse - row['rmse']) / max(base_rmse, 1.e-12)
        row['shared_with_coverage'] = int(np.intersect1d(coverage, orders[row['policy']]).size)
        row['exact_coverage_order'] = int(np.array_equal(coverage, orders[row['policy']]))
    return results, audits, orders


def run_development(output_dir, *, size=SIZE, angles=ANGLES, factor=FACTOR,
                    families=FAMILIES, representations=REPRESENTATIONS,
                    seeds=SEEDS, budget=BUDGET, warm_rays=WARM_RAYS,
                    batch=BATCH, candidate_pool=POOL,
                    provisional_epochs=PROVISIONAL_EPOCHS,
                    final_epochs=FINAL_EPOCHS, relaxation=RELAXATION):
    """Runner allows tiny test fixtures; CLI is frozen to 8^3 design."""
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError('refusing to overwrite nonempty output directory')
    if (size < 4 or angles < 2 or factor < 2 or not families or not representations
        or not seeds or warm_rays < 2 or not warm_rays < budget <= size*size*angles*len(TILTS)
        or min(batch, candidate_pool, provisional_epochs, final_epochs) < 1
        or not np.isfinite(relaxation) or not 0 < relaxation <= 1):
        raise ValueError('invalid configuration')
    if set(families) - set(FAMILIES) or set(representations) - set(REPRESENTATIONS):
        raise ValueError('development-object allowlist violated')
    output_dir.mkdir(parents=True, exist_ok=True)
    A = system_matrix(size, angles, TILTS).tocsr()
    M = high_resolution_matrix(size, angles, TILTS, factor, OFFSET)
    raw, batch_rows = [], []
    for family in families:
        variants = object_pair(family, size, factor)
        for representation in representations:
            truth, fine = variants[representation]
            observed = np.asarray(M @ fine).ravel()
            for seed in seeds:
                warm = voxel_coverage_order(A, size, angles, len(TILTS), budget,
                                            seed, candidate_pool)
                outcomes, audits, _ = run_case(
                    A, observed, truth, warm, seed=seed, n=size, angles=angles,
                    budget=budget, warm_rays=warm_rays, batch=batch,
                    candidate_pool=candidate_pool,
                    provisional_epochs=provisional_epochs,
                    final_epochs=final_epochs, relaxation=relaxation)
                for row in outcomes:
                    raw.append(dict(family=family, representation=representation,
                                    acquisition_seed=seed, budget=budget, **row))
                    print(f"{family:8s} {representation:10s} seed={seed} "
                          f"{row['policy']:12s} RMSE={row['rmse']:.6f} "
                          f"gain={row['gain_vs_coverage']:+.2%}", flush=True)
                for audit in audits:
                    batch_rows.append(dict(family=family,
                                           representation=representation,
                                           acquisition_seed=seed, **audit))
    write_rows(output_dir/'development_cases.csv', raw)
    write_rows(output_dir/'guard_batch_audit.csv', batch_rows)
    groups = defaultdict(list)
    for row in raw:
        groups[(row['family'], row['representation'], row['policy'])].append(row)
    summaries = []
    for (family, rep, policy), rows in sorted(groups.items()):
        gains = np.asarray([r['gain_vs_coverage'] for r in rows], dtype=float)
        summaries.append(dict(family=family, representation=rep, policy=policy,
                              n_acquisition_seeds=len(rows),
                              mean_gain_vs_coverage=float(gains.mean()),
                              wins=int((gains > 0).sum()),
                              mean_shared_rays=float(np.mean([r['shared_with_coverage'] for r in rows])),
                              mean_selection_s=float(np.mean([r['selection_s'] for r in rows]))))
    write_rows(output_dir/'development_summary.csv', summaries)
    protocol = dict(experiment='RBYRCT-06A2 development comparison',
        stage='exploratory only; no held-out 06B objects',
        size=size, angles=angles, tilts=list(map(float, TILTS)), factor=factor,
        families=list(families), representations=list(representations),
        seeds=list(seeds), policies=list(POLICIES), budget=budget,
        warm_rays=warm_rays, batch=batch, candidate_pool=candidate_pool,
        provisional_epochs=provisional_epochs, final_epochs=final_epochs,
        mart_relaxation=relaxation, geometric_offset=OFFSET,
        noise_fraction=0.0, guard_eta={'strict':0., 'guarded_05':.05},
        primary_development_metric='paired final RMSE gain relative to coverage',
        no_tuning_sweep=True, no_heldout_validation=True,
        independence_caveat='fixed analytic phantom families; acquisition seeds are not new objects',
        stop_rule='one bounded development comparison; then assess before any held-out 06B')
    (output_dir/'protocol.json').write_text(json.dumps(protocol, indent=2)+'\n', encoding='utf8')
    return raw, summaries, batch_rows


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path,
                   default=Path('results/experiment06a2/development_first'))
    a = p.parse_args(argv)
    raw, summary, batches = run_development(a.output_dir)
    print(f'06A2 complete: {len(raw)} policy cases, {len(summary)} summary rows, '
          f'{len(batches)} guard-batch records; output={a.output_dir}')


if __name__ == '__main__':
    main()
