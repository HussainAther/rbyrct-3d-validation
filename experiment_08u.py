"""08U: exploratory sequential full-covariance versus diagonal A-optimal ray ordering.

Uses the same 12^3 geometry, seeded defects, measurement process, and final MART
reconstruction as the established 08K framework. This is NOT held-out validation.
The exact score is exact for an assumed Gaussian model, not MART uncertainty.
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
from scipy.linalg import solve_triangular
# Runtime project imports are deliberately deferred. Pure Gaussian-kernel tests
# can run independently; the integrated Windows study uses the full repo.
PRIOR_VARIANCE = 1.0
OBSERVATION_VARIANCE = 1.0


SIZE = 12
ANGLES = 4
FACTOR = 2
OBJECT_SEEDS = (880201, 880202, 880203)  # new, exploratory, not 08M seeds
ACQUISITION_SEED = 880411
MODELS = ('same', 'independent')
POLICIES = ('coverage', 'information_diag', 'information_full')
BUDGET = 288
CHECKPOINTS = (144, 288)
WARM = 24
BATCH = 16
POOL = 16
FINAL_EPOCHS = 16
RELAXATION = .25
NOISE_FRACTION = .005
OFFSET = .15
STEP = .25


def order_sha256(order):
    return hashlib.sha256(np.asarray(order, dtype='<i8').tobytes()).hexdigest()


def write_csv(path, rows):
    if not rows:
        raise ValueError(f'empty output: {path}')
    with Path(path).open('w', encoding='utf8', newline='') as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def score_full_from_cholesky(A, selected, lower, candidates, *, prior_variance=PRIOR_VARIANCE, observation_variance=OBSERVATION_VARIANCE):
    """Full Gaussian one-step A-optimal trace reduction on a candidate pool.

    Covariance C = tau2 I - tau2**2 H.T (sigma2 I + tau2 H H.T)^-1 H.
    Scores = ||C a||**2 / (sigma2 + a.T C a). Full voxel covariance
    is never constructed; selected-row covariance is Cholesky factored.
    """
    A=A.tocsr()
    ids=np.asarray(selected,dtype=np.int64)
    cand=np.asarray(candidates,dtype=np.int64)
    if ids.ndim!=1 or cand.ndim!=1 or not len(cand) or len(set(cand.tolist()))!=len(cand):
        raise ValueError('bad candidate list')
    if np.any(ids<0) or np.any(ids>=A.shape[0]) or np.any(cand<0) or np.any(cand>=A.shape[0]):
        raise ValueError('ray id out of bounds')
    if not (prior_variance>0 and observation_variance>0 and np.isfinite(prior_variance) and np.isfinite(observation_variance)):
        raise ValueError('invalid variances')
    Q=A[cand].T.toarray()  # voxels x pool; small bounded candidate pool
    if len(ids):
        H=A[ids]
        if lower.shape!=(len(ids),len(ids)):
            raise ValueError('Cholesky dimension mismatch')
        rhs=np.asarray(H@Q)
        x=solve_triangular(lower,rhs,lower=True,check_finite=False)
        x=solve_triangular(lower.T,x,lower=False,check_finite=False)
        CQ=prior_variance*Q-(prior_variance**2)*np.asarray(H.T@x)
    else:
        CQ=prior_variance*Q
    numer=np.einsum('ij,ij->j',CQ,CQ)
    denom=observation_variance+np.einsum('ij,ij->j',Q,CQ)
    if np.any(denom<=0) or not np.all(np.isfinite(numer/denom)):
        raise ArithmeticError('unstable full-covariance scores')
    return numer/denom


def append_cholesky(A, selected, lower, ray, *, prior_variance=PRIOR_VARIANCE, observation_variance=OBSERVATION_VARIANCE):
    """Extend Cholesky of sigma2 I + tau2 H H.T by one acquired row."""
    A=A.tocsr()
    ids=np.asarray(selected,dtype=np.int64)
    if ray<0 or ray>=A.shape[0] or ray in set(ids.tolist()):
        raise ValueError('duplicate/invalid acquisition')
    if lower.shape!=(len(ids),len(ids)):
        raise ValueError('Cholesky dimension mismatch')
    a=A[ray]
    diag=observation_variance+prior_variance*float(a.multiply(a).sum())
    if len(ids):
        cross=prior_variance*(A[ids]@a.T).toarray().ravel()
        v=solve_triangular(lower,cross,lower=True,check_finite=False)
        resid=diag-float(v@v)
    else:
        v=np.empty(0,dtype=float)
        resid=diag
    if resid<=0 or not np.isfinite(resid):
        raise ArithmeticError('Cholesky update nonpositive residual')
    new=np.zeros((len(ids)+1,len(ids)+1),dtype=float)
    new[:len(ids),:len(ids)]=lower
    new[-1,:-1]=v
    new[-1,-1]=np.sqrt(resid)
    return new


def select_full(A, observations, warm_order, budget, seed, *, warm_rays=WARM, batch=BATCH, candidate_pool=POOL,
                prior_variance=PRIOR_VARIANCE, observation_variance=OBSERVATION_VARIANCE):
    """Acquire rays using full-covariance Gaussian score with an incremental factor.

    Candidate sampling/tie resolution matches 08K's geometry-only information
    selector. No read of the observation object, except committing selected IDs.
    """
    A=A.tocsr()
    if not (0<warm_rays<budget<=A.shape[0] and batch>=1 and candidate_pool>=1):
        raise ValueError('invalid acquisition budget')
    warm=np.asarray(warm_order[:warm_rays],dtype=np.int64)
    if len(warm)!=warm_rays or len(set(warm.tolist()))!=warm_rays or np.any(warm<0) or np.any(warm>=A.shape[0]):
        raise ValueError('invalid warm rays')
    remaining=np.ones(A.shape[0],dtype=bool);remaining[warm]=False
    selected=[];lower=np.zeros((0,0),dtype=float)
    for ray in warm:
        lower=append_cholesky(A,selected,lower,int(ray),prior_variance=prior_variance,observation_variance=observation_variance)
        selected.append(int(ray))
    rng=np.random.default_rng(seed+317)
    start=time.perf_counter()
    while len(selected)<budget:
        block=min(batch,budget-len(selected))
        chosen_block=[]
        for _ in range(block):
            available=np.flatnonzero(remaining)
            candidates=np.asarray(rng.choice(available,size=min(candidate_pool,len(available)),replace=False),dtype=np.int64)
            values=score_full_from_cholesky(A,selected,lower,candidates,
                prior_variance=prior_variance,observation_variance=observation_variance)
            winning=np.flatnonzero(np.isclose(values,np.max(values),rtol=1e-13,atol=1e-14))
            ray=int(min(candidates[winning]))
            lower=append_cholesky(A,selected,lower,ray,prior_variance=prior_variance,observation_variance=observation_variance)
            selected.append(ray);chosen_block.append(ray);remaining[ray]=False
        if hasattr(observations,'commit'):
            observations.commit(chosen_block)
    return np.asarray(selected,dtype=np.int64),time.perf_counter()-start


def geometry(size=SIZE):
    from experiment_04b import system_matrix
    from experiment_04g import TILTS
    A=system_matrix(size,ANGLES,TILTS).tocsr()
    if A.shape!=(size*size*ANGLES*len(TILTS),size**3):
        raise ValueError('geometry shape mismatch')
    return A


def make_orders(A, coverage, budget, seed, *, warm, batch, pool, observations=None):
    # For engineering-only preflight, no measurements are supplied to any selector.
    orders={'coverage':np.asarray(coverage,dtype=np.int64)}
    times={'coverage':0.}
    from experiment_08k import select_information
    d,_,dt=select_information(A,observations,SIZE,ANGLES,coverage,budget,seed,
        warm_rays=warm,batch=batch,candidate_pool=pool)
    orders['information_diag']=d;times['information_diag']=dt
    f,ft=select_full(A,observations,coverage,budget,seed,warm_rays=warm,batch=batch,candidate_pool=pool)
    orders['information_full']=f;times['information_full']=ft
    for name,order in orders.items():
        if len(order)!=budget or len(set(map(int,order)))!=budget or not np.array_equal(order[:warm],coverage[:warm]):
            raise RuntimeError(f'invalid ordering: {name}')
    return orders,times


def preflight(output_dir, *, size=SIZE, budget=BUDGET, warm=WARM, batch=BATCH, pool=POOL):
    if size!=SIZE or budget!=BUDGET or warm!=WARM or batch!=BATCH or pool!=POOL:
        raise ValueError('production preflight settings must match 08U')
    out=Path(output_dir)
    if out.exists(): raise FileExistsError('refusing to overwrite previous results')
    A=geometry(size)
    seed=ACQUISITION_SEED+size
    from experiment_04h import voxel_coverage_order
    from experiment_04g import TILTS
    coverage=np.asarray(voxel_coverage_order(A,size,ANGLES,len(TILTS),budget,seed,pool),dtype=np.int64)
    orders,times=make_orders(A,coverage,budget,seed,warm=warm,batch=batch,pool=pool)
    # Determinism check: repeat exact selector and compare full integer ray history.
    repeat,repeat_t=select_full(A,None,coverage,budget,seed,warm_rays=warm,batch=batch,candidate_pool=pool)
    if not np.array_equal(orders['information_full'],repeat):raise RuntimeError('non-deterministic exact acquisition')
    report=dict(complete=True,engineering_only=True,ray_budget=budget,size=size,select_seconds=times,
        exact_repeat_seconds=repeat_t,exact_deterministic=True,
        order_sha256={p:order_sha256(v) for p,v in orders.items()},
        diagonal_equals_exact=bool(np.array_equal(orders['information_diag'],orders['information_full'])),
        full_equals_coverage=bool(np.array_equal(orders['information_full'],orders['coverage'])),
        information_score='full-covariance Gaussian A-optimal; not MART posterior',
        note='No phantoms, detector measurements, reconstructions, or truth used.')
    out.mkdir(parents=True)
    (out/'preflight.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,indent=2),flush=True)
    return report


def object_summary(rows):
    out=[]
    for oid in sorted({r['object_id'] for r in rows}):
        for k in CHECKPOINTS:
            for policy in POLICIES:
                subset=[r for r in rows if r['object_id']==oid and r['acquired']==k and r['policy']==policy]
                if len(subset)!=len(MODELS): raise RuntimeError('incomplete object conditions')
                out.append(dict(object_id=oid,acquired=k,policy=policy,n_models=len(subset),
                    mean_global_gain=float(np.mean([r['gain_vs_coverage'] for r in subset])),
                    mean_defect_gain=float(np.mean([r['defect_gain_vs_coverage'] for r in subset])),
                    mean_global_rmse=float(np.mean([r['global_rmse'] for r in subset])),
                    mean_defect_rmse=float(np.mean([r['defect_region_rmse'] for r in subset]))))
    return out


def run(output_dir, preflight_dir):
    pre=Path(preflight_dir)/'preflight.json'
    if not pre.is_file():raise FileNotFoundError('08U engineering preflight must complete first')
    engineering=json.loads(pre.read_text(encoding='utf8'))
    if not engineering.get('complete') or not engineering.get('exact_deterministic') or engineering.get('ray_budget')!=BUDGET or engineering.get('size')!=SIZE:
        raise ValueError('invalid 08U preflight')
    out=Path(output_dir)
    if out.exists():raise FileExistsError('refusing to overwrite previous results')
    A=geometry()
    seed=ACQUISITION_SEED+SIZE
    from experiment_04h import voxel_coverage_order
    from experiment_04g import TILTS
    from experiment_04qa import project
    from experiment_05b_08b import nonnegative_noisy_measurements
    from experiment_05b_mart import mart_reconstruct
    from experiment_06b import defect_phantom
    from experiment_07c_preflight import defect_support, error_metrics
    coverage=np.asarray(voxel_coverage_order(A,SIZE,ANGLES,len(TILTS),BUDGET,seed,POOL),dtype=np.int64)
    # Geometry-based ordering is object-independent; compute once, reuse for all phantoms.
    orders,times=make_orders(A,coverage,BUDGET,seed,warm=WARM,batch=BATCH,pool=POOL)
    hashes={p:order_sha256(v) for p,v in orders.items()}
    if hashes!=engineering['order_sha256']:
        raise RuntimeError('acquisition orders differ from engineering preflight')
    out.mkdir(parents=True)
    cfg=dict(stage='08U exploratory; results known only after run, NOT independent validation',
        size=SIZE,object_seeds=list(OBJECT_SEEDS),acquisition_seed=seed,
        models=list(MODELS),policies=list(POLICIES),budget=BUDGET,checkpoints=list(CHECKPOINTS),
        warm=WARM,batch=BATCH,pool=POOL,prior_variance=PRIOR_VARIANCE,
        observation_variance=OBSERVATION_VARIANCE,final_epochs=FINAL_EPOCHS,
        relaxation=RELAXATION,noise_fraction=NOISE_FRACTION,
        geometric_full_score='exact one-step linear-Gaussian A-optimal score, not MART posterior',
        independent_objects=len(OBJECT_SEEDS),primary_claim='none: descriptive development study',
        geometry_only=True)
    (out/'protocol.json').write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf8')
    (out/'environment.json').write_text(json.dumps(dict(python=sys.version,platform=platform.platform(),numpy=np.__version__),indent=2)+'\n')
    allorders=[dict(policy=p,acquired_index=i+1,ray_id=int(ray),order_sha256=hashes[p]) for p in POLICIES for i,ray in enumerate(orders[p])]
    write_csv(out/'acquisition_orders.csv',allorders)
    rows=[];manifest=[]
    (out/'run_status.json').write_text(json.dumps(dict(complete=False,completed_reconstructions=0))+'\n')
    try:
        for obj_seed in OBJECT_SEEDS:
            truth,fine,description=defect_phantom(SIZE,FACTOR,obj_seed)
            mask,maskinfo=defect_support(SIZE,FACTOR,obj_seed)
            oid=f'defect_dev_{obj_seed}'
            manifest.append(dict(object_id=oid,object_seed=obj_seed,
                n_defects=description['n_defects'],mask_voxels=maskinfo['mask_voxels'],
                mask_sha256=maskinfo['mask_sha256'],truth_sha256=hashlib.sha256(np.asarray(truth,dtype='<f8').tobytes()).hexdigest()))
            for mi,model in enumerate(MODELS):
                clean=np.asarray(A@truth).ravel() if model=='same' else np.asarray(project(fine,SIZE,ANGLES,TILTS,factor=FACTOR,offset=OFFSET,step=STEP,mode='linear')).ravel()
                measured=nonnegative_noisy_measurements(clean,NOISE_FRACTION,(obj_seed*37+mi*100003+17011)%(2**32))
                condition=[]
                for policy in POLICIES:
                    order=orders[policy]
                    for k in CHECKPOINTS:
                        begin=time.perf_counter()
                        recon=mart_reconstruct(A[order[:k]],measured[order[:k]],FINAL_EPOCHS,relaxation=RELAXATION)
                        elapsed=time.perf_counter()-begin
                        metrics=error_metrics(recon,truth,mask)
                        condition.append(dict(object_id=oid,object_seed=obj_seed,model=model,policy=policy,
                            acquired=k,**metrics,gain_vs_coverage=0.,defect_gain_vs_coverage=0.,
                            nondefect_gain_vs_coverage=0.,order_sha256=order_sha256(order[:k]),
                            selection_seconds=times[policy],reconstruction_seconds=elapsed))
                    print(f'08U object={obj_seed} model={model:11s} policy={policy:17s} ray_budget={BUDGET}',flush=True)
                for r in condition:
                    ref=next(x for x in condition if x['policy']=='coverage' and x['acquired']==r['acquired'])
                    for metric,key in [('global_rmse','gain_vs_coverage'),('defect_region_rmse','defect_gain_vs_coverage'),('nondefect_rmse','nondefect_gain_vs_coverage')]:
                        r[key]=(ref[metric]-r[metric])/max(ref[metric],1e-12)
                rows.extend(condition)
                (out/'run_status.json').write_text(json.dumps(dict(complete=False,completed_reconstructions=len(rows)),indent=2)+'\n')
    except BaseException:
        (out/'run_status.json').write_text(json.dumps(dict(complete=False,completed_reconstructions=len(rows),message='interrupted; preserve directory'),indent=2)+'\n')
        raise
    write_csv(out/'prefix_reconstructions.csv',rows)
    write_csv(out/'object_manifest.csv',manifest)
    objects=object_summary(rows);write_csv(out/'object_level_summary.csv',objects)
    aggregate=[]
    for k in CHECKPOINTS:
        for p in POLICIES:
            subset=[r for r in objects if r['acquired']==k and r['policy']==p]
            aggregate.append(dict(size=SIZE,acquired=k,policy=p,n_objects=len(subset),
                mean_global_gain=float(np.mean([r['mean_global_gain'] for r in subset])),
                mean_defect_gain=float(np.mean([r['mean_defect_gain'] for r in subset])),
                object_global_wins=sum(r['mean_global_gain']>0 for r in subset),
                object_defect_wins=sum(r['mean_defect_gain']>0 for r in subset)))
    write_csv(out/'aggregate_summary.csv',aggregate)
    comparisons=[]
    for k in CHECKPOINTS:
        for oid in sorted({r['object_id'] for r in objects}):
            z={r['policy']:r for r in objects if r['object_id']==oid and r['acquired']==k}
            comparisons.append(dict(object_id=oid,acquired=k,
                full_minus_diagonal_global_rmse=z['information_full']['mean_global_rmse']-z['information_diag']['mean_global_rmse'],
                full_minus_diagonal_defect_rmse=z['information_full']['mean_defect_rmse']-z['information_diag']['mean_defect_rmse'],
                full_better_global=int(z['information_full']['mean_global_rmse']<z['information_diag']['mean_global_rmse']),
                full_better_defect=int(z['information_full']['mean_defect_rmse']<z['information_diag']['mean_defect_rmse'])))
    write_csv(out/'full_vs_diagonal_object.csv',comparisons)
    status=dict(complete=True,completed_reconstructions=len(rows),objects=len(OBJECT_SEEDS),
        models=len(MODELS),policies=len(POLICIES),checkpoints=len(CHECKPOINTS),
        interpretation='exploratory; no preregistered significance claim')
    (out/'run_status.json').write_text(json.dumps(status,indent=2)+'\n')
    digest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()}
    (out/'sha256.json').write_text(json.dumps(digest,indent=2)+'\n')
    print(json.dumps(status,indent=2),flush=True)
    return status


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_mutually_exclusive_group(required=True)
    sub.add_argument('--preflight',action='store_true')
    sub.add_argument('--run',action='store_true')
    p.add_argument('--output-dir',required=True)
    p.add_argument('--preflight-dir')
    args=p.parse_args()
    if args.preflight:
        preflight(args.output_dir)
    else:
        if not args.preflight_dir:p.error('--run requires --preflight-dir')
        run(args.output_dir,args.preflight_dir)

if __name__=='__main__': main()
