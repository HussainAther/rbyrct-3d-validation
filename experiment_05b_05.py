"""05B-05 audit of frozen 05B-04 MART acquisition policies.

Descriptive, offline analysis. Acquisition is delegated unchanged to 05B-04.
No truth or candidate observations enter online selection.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import time
from pathlib import Path
import numpy as np
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_04m import high_resolution_matrix
from experiment_05b_04p import object_pair
from experiment_05b_04 import POLICIES, select_order
from experiment_05b_mart import mart_reconstruct
from experiment_05b_resources import validate_grid


def checkpoint_counts(warm_rays, budget, batch, extra=()):
    """Report the warm prefix, each acquisition batch, and the endpoint."""
    if not 1 <= warm_rays < budget or batch < 1:
        raise ValueError('invalid checkpoint geometry')
    values = set(range(warm_rays, budget + 1, batch)) | {warm_rays, budget}
    for k in extra:
        if not warm_rays <= k <= budget:
            raise ValueError('checkpoint outside acquired range')
        values.add(k)
    return sorted(values)


def prefix_geometry(A, order, n, angles):
    """Geometry-only diagnostics for an acquired prefix; never reads measurements."""
    ids = np.asarray(order, dtype=np.int64)
    if ids.size == 0 or np.any(ids < 0) or np.any(ids >= A.shape[0]):
        raise ValueError('invalid acquired prefix')
    if len(np.unique(ids)) != len(ids):
        raise ValueError('duplicate acquired ray')
    coverage = np.asarray(A[ids].sum(axis=0)).ravel().astype(float)
    touched = coverage > 0
    count = np.bincount(ids // (n*n), minlength=angles*len(TILTS))
    proportions = count[count > 0] / ids.size
    entropy = float(-np.sum(proportions * np.log(proportions)))
    max_entropy = math.log(len(count)) if len(count) > 1 else 0.
    return dict(
        acquired=len(ids),
        touched_voxel_fraction=float(np.mean(touched)),
        uncovered_voxel_fraction=float(np.mean(~touched)),
        coverage_weight_cv=float(coverage.std()/coverage.mean()) if coverage.mean() > 0 else float('nan'),
        coverage_min=float(coverage.min()),
        coverage_max=float(coverage.max()),
        sampled_views=int(np.count_nonzero(count)),
        view_entropy_normalized=entropy/max_entropy if max_entropy > 0 else 1.,
        largest_view_share=float(count.max()/ids.size),
    )


def overlap_rows(orders, checkpoints, meta):
    """Pairwise same-prefix set overlap and order divergence."""
    rows = []
    for i, left in enumerate(POLICIES):
        for right in POLICIES[i+1:]:
            for k in checkpoints:
                a, b = orders[left][:k], orders[right][:k]
                intersection = len(set(map(int, a)) & set(map(int, b)))
                union = 2*k-intersection
                rows.append(dict(**meta, acquired=k, left_policy=left, right_policy=right,
                                 common_rays=intersection, jaccard=intersection/union,
                                 set_divergence=1-intersection/k,
                                 position_disagreement=float(np.mean(a != b))))
    return rows


def evaluate_case(A, observed, truth, n, angles, warm, seed, budget, *,
                  warm_rays, batch, candidate_pool, provisional_epochs,
                  final_epochs, relaxation, feature_cap, checkpoints):
    """Run each frozen selector once; reconstruct only afterward for offline audit."""
    orders, geometry, trajectories, timings, views = {}, [], [], [], []
    meta = dict(seed=seed)
    for policy in POLICIES:
        order, _, selection_s = select_order(
            A, observed, n, angles, warm, budget, seed, policy=policy,
            warm_rays=warm_rays, batch=batch, candidate_pool=candidate_pool,
            provisional_epochs=provisional_epochs, relaxation=relaxation,
            feature_cap=feature_cap)
        if len(order) != budget or len(np.unique(order)) != budget:
            raise AssertionError(f'invalid order: {policy}')
        orders[policy] = order
        time_reconstruction = 0.
        for k in checkpoints:
            ids = order[:k]
            geom = prefix_geometry(A, ids, n, angles)
            geometry.append(dict(**meta, policy=policy, **geom))
            counts = np.bincount(ids//(n*n), minlength=angles*len(TILTS))
            for view, count in enumerate(counts):
                views.append(dict(**meta, policy=policy, acquired=k,
                                  view_index=view, ray_count=int(count)))
            start = time.perf_counter()
            estimate = mart_reconstruct(A[ids], observed[ids], final_epochs,
                                        relaxation=relaxation)
            elapsed = time.perf_counter()-start
            time_reconstruction += elapsed
            rmse = float(np.sqrt(np.mean((estimate-truth)**2)))
            residual = np.asarray(A[ids]@estimate).ravel()-np.asarray(observed[ids]).ravel()
            data_norm = max(float(np.linalg.norm(observed[ids])),1.e-12)
            trajectories.append(dict(**meta, policy=policy, acquired=k, rmse=rmse,
                                     acquired_projection_relative_residual=float(np.linalg.norm(residual)/data_norm),
                                     offline_reconstruction_s=elapsed))
        timings.append(dict(**meta, policy=policy, selection_s=selection_s,
                            all_checkpoint_reconstruction_s=time_reconstruction,
                            # Last checkpoint reconstruction cost is the endpoint budget cost.
                            final_reconstruction_s=trajectories[-1]['offline_reconstruction_s'],
                            total_selection_plus_final_s=selection_s+trajectories[-1]['offline_reconstruction_s']))
    # Policy endpoint pairs, evaluated offline with a common reconstructed error metric.
    errors = {(r['policy'],r['acquired']):r['rmse'] for r in trajectories}
    for r in trajectories:
        baseline = errors[('coverage',r['acquired'])]
        r['coverage_rmse'] = baseline
        r['gain_vs_coverage'] = (baseline-r['rmse'])/max(baseline,1.e-12)
    return dict(orders=orders, geometry=geometry, trajectories=trajectories,
                timings=timings, views=views,
                overlaps=overlap_rows(orders,checkpoints,meta))


def write_csv(path, rows):
    if not rows:
        raise ValueError(f'empty output {path}')
    with path.open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
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
    p.add_argument('--checkpoint-every',type=int,default=32,
                   help='Offline checkpoint spacing in acquired-ray counts; warm and endpoint always included')
    p.add_argument('--output-dir',type=Path,default=Path('results/experiment05b/objective_audit_8'))
    p.add_argument('--allow-large',action='store_true')
    a=p.parse_args(argv)
    try:
        validate_grid(a.size,a.factor,a.allow_large)
    except (ValueError,OSError) as exc:
        p.error(str(exc))
    if (a.angles<2 or a.warm_rays<2 or not a.warm_rays<a.budget<=a.size*a.size*a.angles*len(TILTS)
        or min(a.batch,a.candidate_pool,a.provisional_epochs,a.mart_epochs,a.checkpoint_every)<1
        or not np.isfinite(a.mart_relaxation) or not 0<a.mart_relaxation<=1
        or not np.isfinite(a.feature_cap) or a.feature_cap<1
        or not np.isfinite(a.offset) or a.offset<0):
        p.error('invalid 05B-05 configuration')
    if a.output_dir.exists() and any(a.output_dir.iterdir()):
        p.error('output directory is not empty; use a fresh directory')
    # Ensure offline checkpoints align with full acquisition batches.
    cps = checkpoint_counts(a.warm_rays,a.budget,a.batch)
    selected_cps = sorted({a.warm_rays,a.budget} | {
        k for k in range(a.warm_rays,a.budget+1,a.batch)
        if (k-a.warm_rays)%a.checkpoint_every==0})
    if not selected_cps:
        p.error('no checkpoints')
    A=system_matrix(a.size,a.angles,TILTS).tocsr()
    M=high_resolution_matrix(a.size,a.angles,TILTS,a.factor,a.offset)
    grouped={name:[] for name in ('geometry','trajectories','timings','views','overlaps')}
    for phantom in a.phantoms:
        pairs=object_pair(phantom,a.size,a.factor)
        for rep in a.representations:
            truth,fine=pairs[rep]
            observed=np.asarray(M@fine).ravel()
            for seed in a.seeds:
                warm=voxel_coverage_order(A,a.size,a.angles,len(TILTS),a.budget,seed,a.candidate_pool)
                result=evaluate_case(A,observed,truth,a.size,a.angles,warm,seed,a.budget,
                    warm_rays=a.warm_rays,batch=a.batch,candidate_pool=a.candidate_pool,
                    provisional_epochs=a.provisional_epochs,final_epochs=a.mart_epochs,
                    relaxation=a.mart_relaxation,feature_cap=a.feature_cap,checkpoints=selected_cps)
                for key in grouped:
                    for row in result[key]:
                        grouped[key].append(dict(phantom=phantom,representation=rep,offset=a.offset,**row))
                endpoint=[r for r in result['trajectories'] if r['acquired']==a.budget]
                print(f'{phantom} {rep} seed={seed}: '+', '.join(
                    f"{r['policy']}={r['rmse']:.6f}" for r in endpoint),flush=True)
    a.output_dir.mkdir(parents=True,exist_ok=True)
    names={'geometry':'prefix_geometry.csv','trajectories':'reconstruction_trajectories.csv',
           'timings':'timing.csv','views':'view_counts.csv','overlaps':'policy_overlap.csv'}
    for key,name in names.items():
        write_csv(a.output_dir/name,grouped[key])
    protocol=dict(experiment='05B-05 frozen MART acquisition objective audit',
       parameters={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},
       policies=list(POLICIES),checkpoints=selected_cps,
       limitations=['Frozen 05B-04 scoring policies; no new online acquisition rules',
       'Truth and acquired projection residuals are offline evaluation only',
       'Geometry coverage is path-weighted, not statistical uncertainty',
       'Selection runtime wall-clock is noisy and hardware-dependent',
       'Candidate RNG streams are seeded identically but diverge as policy choices diverge',
       'Single forward model family and synthetic phantoms; no physical CT claims',
       'Repeated prefixes and seeds are not independent ground-truth objects'])
    (a.output_dir/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf8')
    print(f'05B-05 complete: {len(grouped["trajectories"])} policy-checkpoint rows in {a.output_dir}')
    return grouped

if __name__=='__main__':main()
