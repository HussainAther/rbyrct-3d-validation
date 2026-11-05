"""08Z: prospective exploratory spatial-sensitivity intervention on exact Gaussian A-optimal ray ranking.

Prespecified alpha=0.25; selection is geometry-only. This is not a MART
posterior, causal proof, independent replication, or retuning of frozen 08M.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix

from experiment_08u import (append_cholesky, score_full_from_cholesky,
    select_full, geometry, order_sha256, write_csv,
    PRIOR_VARIANCE, OBSERVATION_VARIANCE)

SIZE=12
ANGLES=4
FACTOR=2
OBJECT_SEEDS=(910201, 910202, 910203, 910204)  # distinct from 08U, 08M, and 08K
ACQUISITION_SEED=910411
MODELS=('same','independent')
POLICIES=('coverage','information_diag','information_full','full_spatial_balanced')
BUDGET=288
CHECKPOINTS=(144,288)
WARM=24
BATCH=16
POOL=16
ALPHA=0.25   # FIXED before outcome inspection; no outcome-based tuning
EPOCHS=16
RELAXATION=.25
NOISE_FRACTION=.005
OFFSET=.15
STEP=.25


def normalized(values):
    """Fixed min-max scaling on one candidate pool; constants become zeros."""
    x=np.asarray(values,dtype=float)
    if x.ndim!=1 or not len(x) or not np.all(np.isfinite(x)):
        raise ValueError('invalid values')
    span=float(x.max()-x.min())
    if span<=1e-14*max(1.,float(np.abs(x).max())):
        return np.zeros_like(x)
    return (x-x.min())/span


def spatial_novelty(A, candidate, cumulative_sensitivity):
    """Negative mean previously acquired |A|-weighted sensitivity along a ray.

    N(a) = -sum_j |a_j| w_j / sum_j |a_j|, w_j=sum_{i acquired}|A_ij|.
    The normalized positive form is a per-pool geometric reward for rays
    reaching voxels with low prior weighted measurement sensitivity.
    """
    rows=A[np.asarray(candidate,dtype=np.int64)].tocsr()
    current=np.asarray(cumulative_sensitivity,dtype=float)
    if current.shape!=(A.shape[1],) or not np.all(np.isfinite(current)) or np.any(current<0):
        raise ValueError('invalid sensitivity state')
    weights=rows.copy()
    weights.data=np.abs(weights.data)
    mass=np.asarray(weights.sum(axis=1)).ravel()
    if np.any(mass<=0):
        raise ValueError('empty ray path')
    return -np.asarray(weights@current).ravel()/mass


def spatial_blend(full_scores, novelty, alpha=ALPHA):
    """Pool-wise normalized exact Gaussian score plus spatial novelty.

    Alpha=0 returns the unmodified full score exactly to preserve tie semantics.
    """
    if not (np.isfinite(alpha) and 0<=alpha<=1):
        raise ValueError('invalid alpha')
    full=np.asarray(full_scores,dtype=float)
    novel=np.asarray(novelty,dtype=float)
    if full.ndim!=1 or novel.shape!=full.shape or not len(full) or not np.all(np.isfinite(novel)):
        raise ValueError('invalid score shapes')
    return full.copy() if alpha==0 else (1-alpha)*normalized(full)+alpha*normalized(novel)


def sensitivity_gini(A, selected):
    """Inequality of cumulative absolute system-matrix coefficients across voxels."""
    rows=A[np.asarray(selected,dtype=np.int64)].tocsr().copy()
    rows.data=np.abs(rows.data)
    w=np.asarray(rows.sum(axis=0)).ravel()
    if not np.all(np.isfinite(w)) or np.any(w<0):
        raise ValueError('invalid sensitivity')
    if not len(w) or np.sum(w)==0:
        return 0.0
    sorted_w=np.sort(w)
    n=len(sorted_w)
    return float((2*np.dot(np.arange(1,n+1),sorted_w)/(n*sorted_w.sum()))-(n+1)/n)


def select_full_spatial(A, observations, warm_order, budget, seed, *, size=SIZE,
                        alpha=ALPHA, warm_rays=WARM, batch=BATCH, candidate_pool=POOL,
                        prior_variance=PRIOR_VARIANCE, observation_variance=OBSERVATION_VARIANCE):
    """Gaussian A-optimality with fixed spatial anti-concentration reward.

    Candidate pools, warm ray IDs, Cholesky updates and the RNG convention
    match 08U. The policy is geometry-only; measured data are never read.
    """
    A=A.tocsr()
    if not(np.isfinite(alpha) and 0<=alpha<=1 and size>=2 and 0<warm_rays<budget<=A.shape[0]
           and batch>=1 and candidate_pool>=1):
        raise ValueError('invalid protocol')
    warm=np.asarray(warm_order[:warm_rays],dtype=np.int64)
    if len(warm)!=warm_rays or len(set(map(int,warm)))!=warm_rays or np.any(warm<0) or np.any(warm>=A.shape[0]):
        raise ValueError('invalid warm order')
    selected=[]
    lower=np.zeros((0,0),dtype=float)
    remaining=np.ones(A.shape[0],dtype=bool)
    remaining[warm]=False
    weights=A.copy()
    weights.data=np.abs(weights.data)
    sensitivity=np.zeros(A.shape[1],dtype=float)
    for rid in warm:
        lower=append_cholesky(A,selected,lower,int(rid),prior_variance=prior_variance,
                              observation_variance=observation_variance)
        selected.append(int(rid))
        sensitivity+=weights.getrow(int(rid)).toarray().ravel()
    rng=np.random.default_rng(seed+317)
    started=time.perf_counter()
    while len(selected)<budget:
        chosen=[]
        for _ in range(min(batch,budget-len(selected))):
            available=np.flatnonzero(remaining)
            candidate=np.asarray(rng.choice(available,size=min(candidate_pool,len(available)),replace=False),dtype=np.int64)
            full=score_full_from_cholesky(A,selected,lower,candidate,
                prior_variance=prior_variance,observation_variance=observation_variance)
            novelty=spatial_novelty(A,candidate,sensitivity)
            ranks=spatial_blend(full,novelty,alpha)
            ties=np.flatnonzero(np.isclose(ranks,np.max(ranks),rtol=1e-13,atol=1e-14))
            rid=int(min(candidate[ties]))
            lower=append_cholesky(A,selected,lower,rid,prior_variance=prior_variance,
                                  observation_variance=observation_variance)
            remaining[rid]=False
            selected.append(rid)
            sensitivity+=weights.getrow(rid).toarray().ravel()
            chosen.append(rid)
        if hasattr(observations,'commit'):
            observations.commit(chosen)
    return np.asarray(selected,dtype=np.int64),time.perf_counter()-started


def make_orders(A,coverage,seed,observations=None):
    from experiment_08k import select_information
    orders={'coverage':np.asarray(coverage,dtype=np.int64)}
    times={'coverage':0.}
    diag,_,t=select_information(A,observations,SIZE,ANGLES,coverage,BUDGET,seed,
        warm_rays=WARM,batch=BATCH,candidate_pool=POOL)
    orders['information_diag']=diag;times['information_diag']=t
    full,t=select_full(A,observations,coverage,BUDGET,seed,warm_rays=WARM,batch=BATCH,candidate_pool=POOL)
    orders['information_full']=full;times['information_full']=t
    spatial,t=select_full_spatial(A,observations,coverage,BUDGET,seed)
    orders['full_spatial_balanced']=spatial;times['full_spatial_balanced']=t
    for p,order in orders.items():
        if len(order)!=BUDGET or len(set(map(int,order)))!=BUDGET or not np.array_equal(order[:WARM],coverage[:WARM]):
            raise RuntimeError('bad order '+p)
    return orders,times


def geometry_and_coverage():
    from experiment_04h import voxel_coverage_order
    from experiment_04g import TILTS
    A=geometry(SIZE)
    seed=ACQUISITION_SEED+SIZE
    coverage=np.asarray(voxel_coverage_order(A,SIZE,ANGLES,len(TILTS),BUDGET,seed,POOL),dtype=np.int64)
    return A,coverage,seed


def preflight(output_dir):
    out=Path(output_dir)
    if out.exists(): raise FileExistsError('refusing to overwrite earlier results')
    A,coverage,seed=geometry_and_coverage()
    orders,times=make_orders(A,coverage,seed)
    zero,_=select_full_spatial(A,None,coverage,BUDGET,seed,alpha=0.)
    repeat,_=select_full_spatial(A,None,coverage,BUDGET,seed)
    if not np.array_equal(zero,orders['information_full']): raise RuntimeError('alpha=0 does not recover exact selector')
    if not np.array_equal(repeat,orders['full_spatial_balanced']): raise RuntimeError('non-deterministic intervention')
    gini={p:{str(k):sensitivity_gini(A,o[:k]) for k in CHECKPOINTS} for p,o in orders.items()}
    reduced={str(k):gini['full_spatial_balanced'][str(k)]<gini['information_full'][str(k)] for k in CHECKPOINTS}
    active=bool(not np.array_equal(orders['information_full'],orders['full_spatial_balanced']) and all(reduced.values()))
    report=dict(complete=active,engineering_only=True,alpha=ALPHA,size=SIZE,budget=BUDGET,
        warm=WARM,batch=BATCH,pool=POOL,object_truth_accessed=False,
        intervention_changes_order=not np.array_equal(orders['information_full'],orders['full_spatial_balanced']),
        spatial_gini_reduced_at_checkpoints=reduced,weighted_sensitivity_gini=gini,
        alpha_zero_equals_full=True,intervention_deterministic=True,
        order_sha256={p:order_sha256(o) for p,o in orders.items()},selection_seconds=times,
        note='Spatial novelty is geometric; mean-sensitivity penalty is not an optimization of Gini, and full covariance is Gaussian, not MART posterior.')
    out.mkdir(parents=True)
    (out/'preflight.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,indent=2))
    if not active:
        raise RuntimeError('08Z spatial Gini gate failed; preserve output and do not run reconstructions')
    return report


def object_aggregate(rows):
    objects=[]
    for oid in sorted({r['object_id'] for r in rows}):
        for k in CHECKPOINTS:
            for policy in POLICIES:
                z=[r for r in rows if (r['object_id'],r['acquired'],r['policy'])==(oid,k,policy)]
                if len(z)!=len(MODELS): raise ValueError('missing object-model conditions')
                objects.append(dict(object_id=oid,acquired=k,policy=policy,
                    n_models=len(z),mean_global_gain=float(np.mean([r['gain_vs_coverage'] for r in z])),
                    mean_defect_gain=float(np.mean([r['defect_gain_vs_coverage'] for r in z])),
                    mean_global_rmse=float(np.mean([r['global_rmse'] for r in z])),
                    mean_defect_rmse=float(np.mean([r['defect_region_rmse'] for r in z]))))
    return objects


def run(output_dir,preflight_dir):
    pre=Path(preflight_dir)/'preflight.json'
    if not pre.is_file():raise FileNotFoundError('successful 08Z preflight required')
    pf=json.loads(pre.read_text(encoding='utf8'))
    if not(pf.get('complete') and pf.get('intervention_deterministic') and pf.get('alpha_zero_equals_full')
           and pf.get('intervention_changes_order') and set(pf.get('spatial_gini_reduced_at_checkpoints',{}))==set(map(str,CHECKPOINTS)) and all(pf['spatial_gini_reduced_at_checkpoints'].values()) and pf.get('alpha')==ALPHA and pf.get('size')==SIZE and pf.get('budget')==BUDGET):
        raise ValueError('invalid 08Z preflight or inactive intervention')
    out=Path(output_dir)
    if out.exists():raise FileExistsError('refusing to overwrite earlier results')
    A,coverage,seed=geometry_and_coverage()
    orders,times=make_orders(A,coverage,seed)
    hashes={p:order_sha256(o) for p,o in orders.items()}
    if hashes!=pf['order_sha256']:raise RuntimeError('preflight ray ordering changed')
    from experiment_04g import TILTS
    from experiment_04qa import project
    from experiment_05b_08b import nonnegative_noisy_measurements
    from experiment_05b_mart import mart_reconstruct
    from experiment_06b import defect_phantom
    from experiment_07c_preflight import defect_support, error_metrics
    out.mkdir(parents=True)
    protocol=dict(stage='08Z prespecified exploratory intervention; not held-out validation',
        size=SIZE,object_seeds=OBJECT_SEEDS,acquisition_seed=seed,models=MODELS,policies=POLICIES,
        budget=BUDGET,checkpoints=CHECKPOINTS,warm=WARM,batch=BATCH,pool=POOL,
        spatial_novelty_weight=ALPHA,score_normalization='per-pool min-max',
        spatial_reward='negative path-length-weighted prior absolute voxel sensitivity',geometry_only=True,
        final_epochs=EPOCHS,relaxation=RELAXATION,noise_fraction=NOISE_FRACTION,
        claim='exploratory spatial-sensitivity intervention; no causal or significance claim')
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n',encoding='utf8')
    (out/'environment.json').write_text(json.dumps(dict(python=sys.version,platform=platform.platform(),numpy=np.__version__),indent=2)+'\n',encoding='utf8')
    write_csv(out/'acquisition_orders.csv',[dict(policy=p,acquired_index=i+1,ray_id=int(ray),order_sha256=hashes[p])
        for p in POLICIES for i,ray in enumerate(orders[p])])
    records=[];manifest=[]
    def status(complete=False):
        (out/'run_status.json').write_text(json.dumps(dict(complete=complete,completed_reconstructions=len(records),
            expected_reconstructions=len(OBJECT_SEEDS)*len(MODELS)*len(POLICIES)*len(CHECKPOINTS)),indent=2)+'\n',encoding='utf8')
    status()
    try:
        for obj_seed in OBJECT_SEEDS:
            truth,fine,desc=defect_phantom(SIZE,FACTOR,obj_seed)
            mask,maskinfo=defect_support(SIZE,FACTOR,obj_seed)
            oid=f'defect_dev_{obj_seed}'
            manifest.append(dict(object_id=oid,seed=obj_seed,n_defects=desc['n_defects'],
                mask_voxels=maskinfo['mask_voxels'],mask_sha256=maskinfo['mask_sha256'],
                truth_sha256=hashlib.sha256(np.asarray(truth,dtype='<f8').tobytes()).hexdigest()))
            for mi,model in enumerate(MODELS):
                clean=np.asarray(A@truth).ravel() if model=='same' else np.asarray(project(fine,SIZE,ANGLES,TILTS,
                    factor=FACTOR,offset=OFFSET,step=STEP,mode='linear')).ravel()
                measured=nonnegative_noisy_measurements(clean,NOISE_FRACTION,(obj_seed*37+mi*100003+17011)%(2**32))
                rows=[]
                for policy in POLICIES:
                    order=orders[policy]
                    for k in CHECKPOINTS:
                        start=time.perf_counter()
                        recon=mart_reconstruct(A[order[:k]],measured[order[:k]],EPOCHS,relaxation=RELAXATION)
                        metrics=error_metrics(recon,truth,mask)
                        rows.append(dict(object_id=oid,object_seed=obj_seed,model=model,policy=policy,acquired=k,
                            **metrics,gain_vs_coverage=0.,defect_gain_vs_coverage=0.,
                            nondefect_gain_vs_coverage=0.,order_sha256=order_sha256(order[:k]),
                            selection_seconds=times[policy],reconstruction_seconds=time.perf_counter()-start))
                    print(f'08Z object={obj_seed} model={model:11s} policy={policy:22s} rays={BUDGET}',flush=True)
                for row in rows:
                    ref=next(r for r in rows if r['policy']=='coverage' and r['acquired']==row['acquired'])
                    for metric,key in [('global_rmse','gain_vs_coverage'),('defect_region_rmse','defect_gain_vs_coverage'),
                                       ('nondefect_rmse','nondefect_gain_vs_coverage')]:
                        row[key]=(ref[metric]-row[metric])/max(ref[metric],1e-12)
                records.extend(rows)
                status()
    except BaseException:
        status(False)
        raise
    write_csv(out/'prefix_reconstructions.csv',records)
    write_csv(out/'object_manifest.csv',manifest)
    objects=object_aggregate(records)
    write_csv(out/'object_level_summary.csv',objects)
    summary=[]
    for k in CHECKPOINTS:
        for p in POLICIES:
            z=[r for r in objects if r['acquired']==k and r['policy']==p]
            summary.append(dict(size=SIZE,acquired=k,policy=p,n_objects=len(z),
                mean_global_gain=float(np.mean([r['mean_global_gain'] for r in z])),
                mean_defect_gain=float(np.mean([r['mean_defect_gain'] for r in z])),
                object_global_wins=sum(r['mean_global_gain']>0 for r in z),
                object_defect_wins=sum(r['mean_defect_gain']>0 for r in z)))
    write_csv(out/'aggregate_summary.csv',summary)
    compare=[]
    for k in CHECKPOINTS:
        for oid in sorted({r['object_id'] for r in objects}):
            z={r['policy']:r for r in objects if r['acquired']==k and r['object_id']==oid}
            compare.append(dict(object_id=oid,acquired=k,
                spatial_minus_full_global_rmse=z['full_spatial_balanced']['mean_global_rmse']-z['information_full']['mean_global_rmse'],
                spatial_minus_full_defect_rmse=z['full_spatial_balanced']['mean_defect_rmse']-z['information_full']['mean_defect_rmse'],
                spatial_better_global=int(z['full_spatial_balanced']['mean_global_rmse']<z['information_full']['mean_global_rmse']),
                spatial_better_defect=int(z['full_spatial_balanced']['mean_defect_rmse']<z['information_full']['mean_defect_rmse'])))
    write_csv(out/'spatial_vs_full_object.csv',compare)
    geom=[]
    for k in CHECKPOINTS:
        for p in POLICIES:
            order=orders[p][:k]
            geom.append(dict(policy=p,acquired=k,detector_entropy=detector_entropy(order),
                detector_bins_visited=int(np.unique(order%(SIZE*SIZE)).size),
                weighted_sensitivity_gini=sensitivity_gini(A,order),
                visited_voxel_fraction=float(np.mean(np.asarray((A[order].copy().sign()!=0).sum(axis=0)).ravel()>0)),
                overlap_with_full=float(len(set(order)&set(orders['information_full'][:k]))/k)))
    write_csv(out/'geometry_summary.csv',geom)
    status(True)
    hashes_out={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()}
    (out/'sha256.json').write_text(json.dumps(hashes_out,indent=2)+'\n',encoding='utf8')
    print(json.dumps(json.loads((out/'run_status.json').read_text(encoding='utf8')),indent=2))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    mode=ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight',action='store_true')
    mode.add_argument('--run',action='store_true')
    ap.add_argument('--output-dir',required=True)
    ap.add_argument('--preflight-dir')
    args=ap.parse_args()
    if args.preflight:preflight(args.output_dir)
    else:
        if not args.preflight_dir:ap.error('--run requires --preflight-dir')
        run(args.output_dir,args.preflight_dir)

if __name__=='__main__':main()
