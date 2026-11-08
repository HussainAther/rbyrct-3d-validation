"""05B-07 exploratory delayed MART feedback, preserving 05B-04 candidate RNG.

Only acquired ray measurements inform selection. Phantom truth is used exclusively
for offline endpoint and checkpoint evaluation. This is not confirmatory evidence.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np

from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_04m import high_resolution_matrix
from experiment_05b_04p import object_pair
from experiment_05b_adaptive import image_score, score_candidates
from experiment_05b_mart import mart_reconstruct
from experiment_05b_resources import validate_grid

POLICIES = ('coverage', 'gradient', 'capped_gradient', 'delayed_48', 'delayed_80')


def select_delayed_order(A, observed, n, angles, warm, budget, seed, *, policy,
                         warm_rays=16, batch=8, candidate_pool=16,
                         provisional_epochs=4, relaxation=.25, feature_cap=3.,
                         delay_at=None):
    """Select with the frozen score/RNG. delay_at is acquisition count at switch.

    Feedback switches on at a *batch boundary*. An offline oracle is not used.
    When strength is zero we skip MART entirely: feature=1 is exact score parity.
    """
    if policy not in POLICIES:
        raise ValueError('invalid policy')
    if not (1 <= warm_rays < budget <= A.shape[0] and batch >= 1 and candidate_pool >= 1
            and provisional_epochs >= 1 and np.isfinite(relaxation) and 0 < relaxation <= 1
            and np.isfinite(feature_cap) and feature_cap >= 1):
        raise ValueError('invalid acquisition configuration')
    if A.shape != (n*n*angles*len(TILTS), n**3):
        raise ValueError('geometry mismatch')
    if policy.startswith('delayed_'):
        switch = int(policy.split('_')[1]) if delay_at is None else delay_at
        if (not isinstance(switch, (int, np.integer)) or switch < warm_rays
                or switch >= budget or (switch-warm_rays) % batch != 0):
            raise ValueError('delay must be a full batch boundary between warm and budget')
    else:
        if delay_at is not None:
            raise ValueError('delay_at is only for delayed policies')
        switch = None
    A = A.tocsr()
    warm = np.asarray(warm[:warm_rays], dtype=np.int64)
    if (len(warm) != warm_rays or len(np.unique(warm)) != warm_rays
            or (warm < 0).any() or (warm >= A.shape[0]).any()):
        raise ValueError('invalid warm rays')
    order = list(map(int, warm))
    remaining = np.ones(A.shape[0], dtype=bool)
    remaining[warm] = False
    counts = np.asarray(A[warm].sum(axis=0)).ravel().astype(float)
    viewcounts = np.bincount(warm//(n*n), minlength=angles*len(TILTS)).astype(int)
    rng = np.random.default_rng(seed+317)
    features_flat = np.ones(A.shape[1], dtype=np.float64)
    trace = []
    start = time.perf_counter()
    while len(order) < budget:
        acquired = len(order)
        use_feedback = policy in ('gradient', 'capped_gradient') or (switch is not None and acquired >= switch)
        if use_feedback:
            ids = np.asarray(order, dtype=np.int64)
            estimate = mart_reconstruct(A[ids], observed[ids], provisional_epochs,
                                        relaxation=relaxation)
            features = image_score(estimate, n)
            if policy == 'capped_gradient':
                features = np.minimum(features, feature_cap)
        else:
            features = features_flat
        size = min(batch, budget-len(order))
        for _ in range(size):
            available = np.flatnonzero(remaining)
            candidates = rng.choice(available, size=min(candidate_pool, len(available)),
                                    replace=False)
            scores = score_candidates(A, candidates, counts, viewcounts, n, features,
                                      feedback_strength=float(use_feedback))
            high = np.max(scores)
            chosen = int(np.min(candidates[np.isclose(scores, high, rtol=1e-13, atol=1e-14)]))
            order.append(chosen)
            remaining[chosen] = False
            lo, hi = A.indptr[chosen], A.indptr[chosen+1]
            counts[A.indices[lo:hi]] += A.data[lo:hi]
            viewcounts[chosen//(n*n)] += 1
        if hasattr(observed, 'commit'):
            observed.commit(order[-size:])
        trace.append(dict(acquired_before=acquired, acquired_after=len(order),
                          policy=policy, feedback_active=int(use_feedback)))
    return np.asarray(order, dtype=np.int64), trace, time.perf_counter()-start


def run_case(A, observations, truth, n, angles, warm, seed, budget, *,
             warm_rays, batch, candidate_pool, provisional_epochs, final_epochs,
             relaxation, feature_cap, checkpoints):
    results, trajectories, selections, orders = [], [], [], {}
    for policy in POLICIES:
        order, trace, selection_s = select_delayed_order(
            A, observations, n, angles, warm, budget, seed, policy=policy,
            warm_rays=warm_rays, batch=batch, candidate_pool=candidate_pool,
            provisional_epochs=provisional_epochs, relaxation=relaxation,
            feature_cap=feature_cap)
        orders[policy] = order
        selection_rows = sum(t['feedback_active'] for t in trace)
        selections.append(dict(policy=policy, selection_s=selection_s,
                               feedback_batches=selection_rows, total_batches=len(trace)))
        for k in checkpoints:
            start = time.perf_counter()
            estimate = mart_reconstruct(A[order[:k]], observations[order[:k]],
                                        final_epochs, relaxation=relaxation)
            seconds = time.perf_counter()-start
            # Truth is only used here, *after* acquisition order is chosen.
            rmse = float(np.sqrt(np.mean((estimate-truth)**2)))
            trajectories.append(dict(policy=policy, acquired=k, rmse=rmse,
                                     reconstruction_s=seconds))
            if k == budget:
                results.append(dict(policy=policy, rmse=rmse, selection_s=selection_s,
                                    final_reconstruction_s=seconds,
                                    feedback_batches=selection_rows))
    base_rmse = next(r['rmse'] for r in results if r['policy']=='coverage')
    coverage_order = orders['coverage']
    for r in results:
        r['gain_vs_coverage'] = (base_rmse-r['rmse'])/max(base_rmse,1e-12)
        r['common_rays_with_coverage'] = len(set(map(int,orders[r['policy']])) & set(map(int,coverage_order)))
    return results, trajectories, selections, orders


def write_csv(path, records):
    if not records:
        raise ValueError('empty records')
    with path.open('w', newline='', encoding='utf-8') as out:
        writer = csv.DictWriter(out, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--size',type=int,default=8)
    ap.add_argument('--angles',type=int,default=4)
    ap.add_argument('--factor',type=int,default=2)
    ap.add_argument('--phantoms',nargs='+',choices=['branches','layers','pores','defects'],default=['branches','defects'])
    ap.add_argument('--representations',nargs='+',choices=['replicated','subvoxel'],default=['replicated'])
    ap.add_argument('--seeds',nargs='+',type=int,default=[271828,314159,577215])
    ap.add_argument('--offset',type=float,default=0.)
    ap.add_argument('--budget',type=int,default=128)
    ap.add_argument('--warm-rays',type=int,default=16)
    ap.add_argument('--batch',type=int,default=8)
    ap.add_argument('--candidate-pool',type=int,default=16)
    ap.add_argument('--provisional-epochs',type=int,default=4)
    ap.add_argument('--mart-epochs',type=int,default=16)
    ap.add_argument('--mart-relaxation',type=float,default=.25)
    ap.add_argument('--feature-cap',type=float,default=3.)
    ap.add_argument('--checkpoints',nargs='+',type=int,default=[16,48,80,112,128])
    ap.add_argument('--output-dir',type=Path,default=Path('results/experiment05b/delayed_feedback_8_first'))
    ap.add_argument('--allow-large', action='store_true')
    a = ap.parse_args(argv)
    try:
        validate_grid(a.size,a.factor,a.allow_large)
    except (ValueError,OSError) as exc:
        ap.error(str(exc))
    if (a.angles < 2 or a.warm_rays < 2 or not a.warm_rays < a.budget <= a.size*a.size*a.angles*len(TILTS)
            or min(a.batch,a.candidate_pool,a.provisional_epochs,a.mart_epochs) < 1
            or not np.isfinite(a.mart_relaxation) or not 0 < a.mart_relaxation <= 1
            or not np.isfinite(a.feature_cap) or a.feature_cap < 1
            or not np.isfinite(a.offset) or a.offset < 0):
        ap.error('invalid 05B-07 parameters')
    for k in (48,80):
        if not (a.warm_rays <= k < a.budget and (k-a.warm_rays)%a.batch == 0):
            ap.error(f'delayed_{k} requires warm <= {k} < budget and batch alignment')
    checkpoints = sorted(set(a.checkpoints + [a.warm_rays,a.budget]))
    if any(k<a.warm_rays or k>a.budget for k in checkpoints):
        ap.error('checkpoints must be within warm and budget')
    if a.output_dir.exists() and any(a.output_dir.iterdir()):
        ap.error('output directory must be empty; choose a fresh output-dir')
    A = system_matrix(a.size,a.angles,TILTS).tocsr()
    M = high_resolution_matrix(a.size,a.angles,TILTS,a.factor,a.offset)
    metrics, trajs, timings = [], [], []
    for phantom in a.phantoms:
        pairs = object_pair(phantom,a.size,a.factor)
        for representation in a.representations:
            truth, fine = pairs[representation]
            observed = np.asarray(M@fine).ravel()
            for seed in a.seeds:
                warm = voxel_coverage_order(A,a.size,a.angles,len(TILTS),a.budget,
                                            seed,a.candidate_pool)
                case_results, case_trajs, case_timings, _ = run_case(
                    A,observed,truth,a.size,a.angles,warm,seed,a.budget,
                    warm_rays=a.warm_rays,batch=a.batch,candidate_pool=a.candidate_pool,
                    provisional_epochs=a.provisional_epochs,final_epochs=a.mart_epochs,
                    relaxation=a.mart_relaxation,feature_cap=a.feature_cap,
                    checkpoints=checkpoints)
                meta = dict(phantom=phantom,representation=representation,seed=seed,
                            offset=a.offset,budget=a.budget,mart_relaxation=a.mart_relaxation)
                for rec in case_results:
                    metrics.append(dict(**meta,**rec))
                    print(f"{phantom} {representation} seed={seed} {rec['policy']:16s} "
                          f"RMSE={rec['rmse']:.6f} gain_vs_coverage={rec['gain_vs_coverage']:+.2%}",flush=True)
                trajs.extend(dict(**meta,**rec) for rec in case_trajs)
                timings.extend(dict(**meta,**rec) for rec in case_timings)
    a.output_dir.mkdir(parents=True,exist_ok=True)
    write_csv(a.output_dir/'delayed_feedback.csv',metrics)
    write_csv(a.output_dir/'reconstruction_trajectories.csv',trajs)
    write_csv(a.output_dir/'selection_timing.csv',timings)
    protocol = dict(experiment='05B-07 exploratory delayed MART feedback',
        parameters={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},
        policies=list(POLICIES), n_cases=len(metrics)//len(POLICIES),
        limitations=['Noiseless synthetic observations with original Siddon-like forward family',
                     '48 and 80 delays were selected after exploring 05B-06 data; no untouched confirmation',
                     'Seeds randomize acquisition, not independent physical phantoms',
                     'Coverage baseline skips provisional MART when feedback disabled',
                     'No clinical, physical-dose, or acquisition hardware claims',
                     'Timing includes interpreter and machine-dependent effects'])
    (a.output_dir/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    print(f'05B-07 complete: {len(metrics)} policy-case rows in {a.output_dir}')
    return metrics


if __name__ == '__main__':
    main()
