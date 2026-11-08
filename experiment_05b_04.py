"""05B-04 exploratory acquired-only candidate-score ablation for MART-RBYRCT.

A policy comparison, NOT a validated improvement or calibrated uncertainty model.
The existing 05B selectors and all historical 04 experiments are unchanged.
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
from experiment_05b_adaptive import image_score, score_candidates, adaptive_order
from experiment_05b_mart import mart_reconstruct
from experiment_05b_resources import validate_grid

POLICIES = ('gradient', 'coverage', 'capped_gradient', 'projection_disagreement')


def select_order(A, observed, n, angles, warm, budget, seed, *, policy,
                 warm_rays=16, batch=8, candidate_pool=16, provisional_epochs=4,
                 relaxation=.25, feature_cap=3.):
    """Select rays using only projections belonging to already acquired IDs.

    For comparison, preserve 05B candidate RNG seed/draws and tie-breaking.
    The prediction-disagreement heuristic is based on two disjoint, acquired-only
    MART fits; it does not consume any candidate observation.
    """
    if policy not in POLICIES:
        raise ValueError('unsupported policy')
    if (not 1 <= warm_rays < budget <= A.shape[0] or batch < 1 or candidate_pool < 1
            or provisional_epochs < 1 or not np.isfinite(relaxation)
            or not 0 < relaxation <= 1 or not np.isfinite(feature_cap) or feature_cap < 1):
        raise ValueError('invalid 05B-04 parameters')
    if n**3 != A.shape[1] or A.shape[0] != n*n*angles*len(TILTS):
        raise ValueError('geometry mismatch')
    warm = np.asarray(warm[:warm_rays], dtype=np.int64)
    if (len(warm) != warm_rays or len(np.unique(warm)) != warm_rays
            or np.any(warm < 0) or np.any(warm >= A.shape[0])):
        raise ValueError('invalid warm prefix')
    A = A.tocsr()
    order = list(map(int, warm))
    remaining = np.ones(A.shape[0], dtype=bool)
    remaining[warm] = False
    counts = np.asarray(A[warm].sum(axis=0)).ravel().astype(float)
    viewcounts = np.bincount(warm//(n*n), minlength=angles*len(TILTS)).astype(int)
    rng = np.random.default_rng(seed+317)
    trace = []
    start = time.perf_counter()
    while len(order) < budget:
        acquired = np.asarray(order, dtype=np.int64)
        # No information from unacquired candidate observations enters these fits.
        if policy in ('gradient', 'capped_gradient'):
            estimate = mart_reconstruct(A[acquired], observed[acquired], provisional_epochs,
                                        relaxation=relaxation)
            features = image_score(estimate, n)
            if policy == 'capped_gradient':
                features = np.minimum(features, feature_cap)
        elif policy == 'projection_disagreement':
            if len(acquired) < 2:
                raise ValueError('disagreement requires >= 2 acquired rays')
            # Alternating rows are disjoint and depend only on past acquisition order.
            left, right = acquired[::2], acquired[1::2]
            xleft = mart_reconstruct(A[left], observed[left], provisional_epochs,
                                      relaxation=relaxation)
            xright = mart_reconstruct(A[right], observed[right], provisional_epochs,
                                       relaxation=relaxation)
        chosen_in_batch = min(batch, budget-len(order))
        for _ in range(chosen_in_batch):
            available = np.flatnonzero(remaining)
            candidates = rng.choice(available, size=min(candidate_pool, len(available)),
                                    replace=False)
            if policy == 'coverage':
                scores = score_candidates(A, candidates, counts, viewcounts, n,
                                          np.ones(A.shape[1]), feedback_strength=0.)
            elif policy in ('gradient', 'capped_gradient'):
                scores = score_candidates(A, candidates, counts, viewcounts, n, features,
                                          feedback_strength=1.)
            else:
                # Apply the same geometry/coverage weighting to candidate disagreement.
                # Mean-normalization is candidate-set local; no calibration claim.
                geom = score_candidates(A, candidates, counts, viewcounts, n,
                                        np.ones(A.shape[1]), feedback_strength=0.)
                predictions = np.asarray(A[candidates] @ (xleft-xright)).ravel()
                discrepancy = np.abs(predictions)
                # Normalize by typical *acquired* forward projection amplitude.
                # This avoids direct use of unacquired measurements.
                scale = max(float(np.sqrt(np.mean(np.asarray(observed[acquired])**2))), 1.e-12)
                scores = geom * (1. + discrepancy/scale)
            high = np.max(scores)
            chosen = int(np.min(candidates[np.isclose(scores, high,
                                                        rtol=1.e-13, atol=1.e-14)]))
            order.append(chosen)
            remaining[chosen] = False
            lo, hi = A.indptr[chosen], A.indptr[chosen+1]
            counts[A.indices[lo:hi]] += A.data[lo:hi]
            viewcounts[chosen//(n*n)] += 1
        if hasattr(observed, "commit"):
            observed.commit(order[-chosen_in_batch:])
        trace.append(dict(acquired=len(order), policy=policy,
                          next_batch_size=chosen_in_batch))
    return np.asarray(order,dtype=np.int64), trace, time.perf_counter()-start


def run_case(A, observations, truth, n, angles, warm, seed, budget, *,
             warm_rays, batch, candidate_pool, provisional_epochs, final_epochs,
             relaxation, feature_cap):
    outcomes = []
    orders = {}
    for policy in POLICIES:
        order, _, selection_s = select_order(
            A, observations, n, angles, warm, budget, seed, policy=policy,
            warm_rays=warm_rays, batch=batch, candidate_pool=candidate_pool,
            provisional_epochs=provisional_epochs, relaxation=relaxation,
            feature_cap=feature_cap)
        # Ground truth appears only here in the *offline* evaluation.
        start = time.perf_counter()
        estimate = mart_reconstruct(A[order], observations[order], final_epochs,
                                    relaxation=relaxation)
        reconstruction_s = time.perf_counter()-start
        rmse = float(np.sqrt(np.mean((estimate-truth)**2)))
        orders[policy] = order
        outcomes.append(dict(policy=policy, rmse=rmse, selection_s=selection_s,
                             reconstruction_s=reconstruction_s))
    base = next(x['rmse'] for x in outcomes if x['policy']=='coverage')
    for result in outcomes:
        result['gain_vs_coverage'] = (base-result['rmse'])/max(base,1.e-12)
        result['same_order_as_coverage'] = int(np.array_equal(
            orders[result['policy']], orders['coverage']))
    return outcomes, orders


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--size',type=int,default=8)
    p.add_argument('--angles',type=int,default=4)
    p.add_argument('--factor',type=int,default=2)
    p.add_argument('--phantoms',nargs='+',choices=['branches','layers','pores','defects'],default=['branches','defects'])
    p.add_argument('--representations',nargs='+',choices=['replicated','subvoxel'],default=['replicated'])
    p.add_argument('--seeds',nargs='+',type=int,default=[271828,314159,577215])
    p.add_argument('--offset',type=float,default=0.)
    p.add_argument('--budget',type=int,default=128)
    p.add_argument('--warm-rays',type=int,default=16)
    p.add_argument('--batch',type=int,default=8)
    p.add_argument('--candidate-pool',type=int,default=16)
    p.add_argument('--provisional-epochs',type=int,default=4)
    p.add_argument('--mart-epochs',type=int,default=16)
    p.add_argument('--mart-relaxation',type=float,default=.25)
    p.add_argument('--feature-cap',type=float,default=3.)
    p.add_argument('--output-dir',type=Path,default=Path('results/experiment05b/score_ablation_8'))
    p.add_argument('--allow-large',action='store_true')
    a = p.parse_args(argv)
    try:
        validate_grid(a.size,a.factor,a.allow_large)
    except (ValueError,OSError) as exc:
        p.error(str(exc))
    if (a.angles<2 or a.warm_rays<2 or not a.warm_rays<a.budget<=a.size*a.size*a.angles*len(TILTS)
            or min(a.batch,a.candidate_pool,a.provisional_epochs,a.mart_epochs)<1
            or not np.isfinite(a.mart_relaxation) or not 0<a.mart_relaxation<=1
            or not np.isfinite(a.feature_cap) or a.feature_cap<1
            or not np.isfinite(a.offset) or a.offset<0):
        p.error('invalid 05B-04 configuration')
    if a.output_dir.exists() and any(a.output_dir.iterdir()):
        p.error('output directory is not empty; use a fresh directory')
    A = system_matrix(a.size,a.angles,TILTS).tocsr()
    M = high_resolution_matrix(a.size,a.angles,TILTS,a.factor,a.offset)
    results=[]
    for phantom in a.phantoms:
        pairs=object_pair(phantom,a.size,a.factor)
        for rep in a.representations:
            truth,fine = pairs[rep]
            observations=np.asarray(M@fine).ravel()
            for seed in a.seeds:
                warm=voxel_coverage_order(A,a.size,a.angles,len(TILTS),a.budget,
                                          seed,a.candidate_pool)
                outcomes,_=run_case(A,observations,truth,a.size,a.angles,warm,seed,a.budget,
                                    warm_rays=a.warm_rays,batch=a.batch,candidate_pool=a.candidate_pool,
                                    provisional_epochs=a.provisional_epochs,final_epochs=a.mart_epochs,
                                    relaxation=a.mart_relaxation,feature_cap=a.feature_cap)
                for out in outcomes:
                    row=dict(phantom=phantom,representation=rep,seed=seed,offset=a.offset,
                             budget=a.budget,mart_relaxation=a.mart_relaxation,**out)
                    results.append(row)
                    print(f"{phantom} {rep} seed={seed} {out['policy']:23s} "
                          f"RMSE={out['rmse']:.6f} gain_vs_coverage={out['gain_vs_coverage']:+.2%}",
                          flush=True)
    a.output_dir.mkdir(parents=True,exist_ok=True)
    with (a.output_dir/'score_ablation.csv').open('w',newline='',encoding='utf8') as fh:
        w=csv.DictWriter(fh,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
    protocol=dict(experiment='05B-04 exploratory acquired-only score ablation',
                  parameters={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},
                  policies=list(POLICIES),n_rows=len(results),
                  limitations=['One synthetic forward-model family; not independent physical CT',
                               'Noiseless measurement data','Multiple seeds are acquisition randomizations, not independent phantoms',
                               'No held-out confirmatory dataset','Disagreement is heuristic, not calibrated uncertainty',
                               'Candidate pool and tie-breaking frozen across policies; paths diverge',
                               'Final RMSE uses truth offline only'])
    (a.output_dir/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf8')
    print(f'05B-04 complete: {len(results)} policy-case rows in {a.output_dir}')
    return results

if __name__=='__main__':
    main()
