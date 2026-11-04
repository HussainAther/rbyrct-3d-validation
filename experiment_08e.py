"""RBYRCT-08E: prospective DEVELOPMENT-ONLY recording of actual candidate scores.

Exact acquisition decision logic of 08B is copied with observation gating. Ground
truth, defect masks, candidate detector intensities, and RMSE are not accessed
by the selector; they are used only AFTER all acquisition orders are fixed.
This does NOT reconstruct historical 08C candidate pools, nor establish causality.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import platform
import sys
from pathlib import Path
import numpy as np

ANGLES=4
ACQUISITION_SEED=808911
OBJECT_SEEDS={12:(808701,808702),32:(808801,808802)}
CONFIGS={12:dict(budget=144,warm=24,batch=16,pool=16,epochs=2,probes=(24,88)),
         32:dict(budget=512,warm=64,batch=32,pool=16,epochs=2,probes=(64,320))}
POLICIES=('gradient','incremental_25')
RELAXATION=.25
LAMBDA=.25
FINAL_EPOCHS=16
NOISE_FRACTION=.005


def score_rank(scores, ids):
    """Stable rank: descending score then ascending ray ID."""
    s=np.asarray(scores,dtype=float); ids=np.asarray(ids,dtype=np.int64)
    if s.ndim!=1 or ids.ndim!=1 or not len(s) or s.shape!=ids.shape or not np.isfinite(s).all() or len(set(ids.tolist()))!=len(ids):
        raise ValueError('invalid candidate scores/IDs')
    return np.lexsort((ids,-s))


def contrast(a,b):
    """Nonparametric Pearson coefficient, NaN for degenerate cases."""
    a=np.asarray(a,dtype=float); b=np.asarray(b,dtype=float)
    if a.ndim!=1 or a.shape!=b.shape or len(a)<2 or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('invalid paired data')
    ac=a-a.mean();bc=b-b.mean();den=float(np.linalg.norm(ac)*np.linalg.norm(bc))
    return float(np.dot(ac,bc)/den) if den>1e-15 else float('nan')


def row_geometry(A, ray, coverage, mask):
    """Geometry-only evaluations; mask is NEVER called by selection."""
    lo,hi=A.indptr[ray:ray+2]; v=A.indices[lo:hi]; w=A.data[lo:hi]
    total=float(w.sum());hit=float(w[mask[v]].sum())
    redundancy=float(np.dot(w,coverage[v])/max(total,1e-12))
    return int(hit>0),float(hit/max(total,1e-12)),redundancy


def _sha(order):
    return hashlib.sha256(np.asarray(order,dtype='<i8').tobytes()).hexdigest()


def acquire_with_probes(A, oracle, n, tilts, warm_order, cfg, seed, policy):
    """08B policy logic + passive candidate logging at fixed acquisition states.

    Evaluation state is deliberately absent from the signature. Snapshot
    records are copied; retrospective analysis occurs after this returns.
    """
    from experiment_05b_adaptive import score_candidates, image_score
    from experiment_05b_mart import mart_reconstruct
    from experiment_08a import incremental_variance, incremental_eligibility
    if policy not in POLICIES:raise ValueError('unsupported policy')
    A=A.tocsr();budget=cfg['budget'];warm=cfg['warm'];batch=cfg['batch'];pool=cfg['pool']
    if not(0<warm<budget<=A.shape[0] and 0<batch and pool>=2 and cfg['epochs']>=1):
        raise ValueError('bad experiment configuration')
    initial=np.asarray(warm_order[:warm],dtype=np.int64)
    if len(initial)!=warm or len(np.unique(initial))!=warm:raise ValueError('bad warm history')
    order=list(map(int,initial));remaining=np.ones(A.shape[0],dtype=bool);remaining[initial]=False
    counts=np.asarray(A[initial].sum(axis=0)).ravel().astype(float)
    views=np.bincount(initial//(n*n),minlength=ANGLES*len(tilts)).astype(int)
    rng=np.random.default_rng(seed+317)
    snapshots=[];selected_probe_count=0
    while len(order)<budget:
        acquired=np.asarray(order,dtype=np.int64)
        x=mart_reconstruct(A[acquired],oracle[acquired],cfg['epochs'],relaxation=RELAXATION)
        features=image_score(x,n)
        b=min(batch,budget-len(order));batch_selected=[]
        for _ in range(b):
            before=len(order)
            available=np.flatnonzero(remaining)
            cand=np.asarray(rng.choice(available,size=min(pool,len(available)),replace=False),dtype=np.int64)
            cv=score_candidates(A,cand,counts,views,n,np.ones(A.shape[1]),feedback_strength=0.)
            gs=score_candidates(A,cand,counts,views,n,features,feedback_strength=1.)
            if not np.isfinite(cv).all() or not np.isfinite(gs).all():raise ArithmeticError('nonfinite selection score')
            tie=np.flatnonzero(np.isclose(cv,cv.max(),rtol=1e-13,atol=1e-14))
            ref=int(min(tie,key=lambda j:int(cand[j])))
            if policy=='gradient': eligible=np.ones(len(cand),dtype=bool)
            else:
                delta=incremental_variance(A,cand,counts)
                eligible,_,_=incremental_eligibility(delta,ref,LAMBDA)
            best=float(gs[eligible].max())
            best_positions=np.flatnonzero(eligible&np.isclose(gs,best,rtol=1e-13,atol=1e-14))
            pos=int(min(best_positions,key=lambda j:int(cand[j])))
            chosen=int(cand[pos]);batch_selected.append(chosen)
            if before in cfg['probes']:
                # Candidate scores, counts and pre-decision IDs only. NO outcomes.
                snapshots.append(dict(policy=policy,acquired_before=before,acquired_ids=acquired.copy(),
                    candidates=cand.copy(),scores=np.asarray(gs,dtype=float).copy(),
                    coverage=counts.copy(),eligible=eligible.copy(),chosen_ray=chosen,
                    reference_ray=int(cand[ref])))
                selected_probe_count+=1
            order.append(chosen);remaining[chosen]=False
            lo,hi=A.indptr[chosen:chosen+2]
            counts[A.indices[lo:hi]]+=A.data[lo:hi]
            views[chosen//(n*n)]+=1
        oracle.commit(batch_selected)
    if selected_probe_count!=len(cfg['probes']):
        raise AssertionError(f'probe count mismatch: {selected_probe_count} vs {len(cfg["probes"])}')
    if oracle.allowed!=set(order) or len(set(order))!=budget:raise AssertionError('acquisition integrity')
    return np.asarray(order,dtype=np.int64),snapshots


def retrospective(A, snapshots, oracle_values, truth, mask, final_epochs=FINAL_EPOCHS):
    """Only run after acquisition is fixed. Evaluates counterfactual one-ray MART.

    Candidate detector values are intentionally accessed here, never in the
    acquisition selector. No counterfactual outcomes are fed back into policy.
    """
    from experiment_05b_mart import mart_reconstruct
    from experiment_07c_preflight import error_metrics
    mask=np.asarray(mask,dtype=bool)
    if mask.shape!=(A.shape[1],):raise ValueError('bad evaluation mask')
    rows=[]
    for snap in snapshots:
        ids=snap['acquired_ids'];cand=snap['candidates'];scores=snap['scores']
        coverage=snap['coverage'];rank=score_rank(scores,cand)
        baseline=mart_reconstruct(A[ids],oracle_values[ids],final_epochs,relaxation=RELAXATION)
        base=error_metrics(baseline,truth,mask)
        for j in range(len(cand)):
            ray=int(cand[j]);new_ids=np.concatenate((ids,[ray]))
            improved=mart_reconstruct(A[new_ids],oracle_values[new_ids],final_epochs,relaxation=RELAXATION)
            new=error_metrics(improved,truth,mask)
            hit,fraction,redundancy=row_geometry(A,ray,coverage,mask)
            rows.append(dict(policy=snap['policy'],acquired_before=int(snap['acquired_before']),
                candidate_ray=ray,gradient_score=float(scores[j]),score_rank=int(np.where(rank==j)[0][0])+1,
                eligible=int(snap['eligible'][j]),chosen=int(ray==snap['chosen_ray']),
                reference=int(ray==snap['reference_ray']),defect_hit=hit,defect_path_fraction=fraction,
                prior_path_coverage=redundancy,
                one_ray_global_gain=(base['global_rmse']-new['global_rmse'])/max(base['global_rmse'],1e-12),
                one_ray_defect_gain=(base['defect_region_rmse']-new['defect_region_rmse'])/max(base['defect_region_rmse'],1e-12)))
    return rows


def _write_csv(path, rows):
    if not rows:raise ValueError('no diagnostic rows')
    with path.open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def run(output_dir):
    # Lazy imports keep pure audit math independently testable.
    from experiment_04b import system_matrix
    from experiment_04g import TILTS
    from experiment_04h import voxel_coverage_order
    from experiment_05b_gate import AcquiredOnly
    from experiment_05b_08b import nonnegative_noisy_measurements
    from experiment_06b import defect_phantom
    from experiment_07c_preflight import defect_support
    out=Path(output_dir)
    if out.exists() and any(out.iterdir()):raise FileExistsError('refusing to overwrite diagnostics')
    out.mkdir(parents=True,exist_ok=True)
    protocol=dict(stage='08E development-only instrumented candidate ranking and retrospective one-ray sensitivity',
        object_seeds=OBJECT_SEEDS,configs=CONFIGS,acquisition_seed=ACQUISITION_SEED,
        models=['same'],policies=POLICIES,lambda_incremental=LAMBDA,
        acquisition_gate='AcquiredOnly; committed after each batch',
        evaluation='counterfactual unacquired observations, truth, and defect mask accessed ONLY after acquisition order complete',
        warnings=['Not a historical replay of 08C candidate sets','Counterfactual one-ray MART comparison is not causal performance validation',
                  'Two development objects per resolution; do not infer statistical significance'])
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n',encoding='utf8')
    rows=[];manifest=[]
    for n in (12,32):
        cfg=CONFIGS[n];A=system_matrix(n,ANGLES,TILTS).tocsr();seed=ACQUISITION_SEED+n
        warm_order=voxel_coverage_order(A,n,ANGLES,len(TILTS),cfg['budget'],seed,cfg['pool'])
        for obj_seed in OBJECT_SEEDS[n]:
            truth,_,_=defect_phantom(n,2,obj_seed)
            mask,mi=defect_support(n,2,obj_seed)
            measured=nonnegative_noisy_measurements(np.asarray(A@truth).ravel(),NOISE_FRACTION,(obj_seed*37+17011)%(2**32))
            for policy in POLICIES:
                gate=AcquiredOnly(measured);gate.commit(warm_order[:cfg['warm']])
                order,snapshots=acquire_with_probes(A,gate,n,TILTS,warm_order,cfg,seed,policy)
                # IMPORTANT: all acquisition decisions are complete by this point.
                diag=retrospective(A,snapshots,measured,truth,mask)
                for r in diag:r.update(size=n,object_seed=obj_seed)
                rows.extend(diag)
                manifest.append(dict(size=n,object_seed=obj_seed,policy=policy,acquired=len(order),
                    order_sha256=_sha(order),probes=len(snapshots),evaluated_candidates=len(diag),
                    mask_sha256=mi['mask_sha256']))
                print(f'08E {n}^3 object={obj_seed} policy={policy} candidates={len(diag)}',flush=True)
    _write_csv(out/'candidate_probes.csv',rows);_write_csv(out/'acquisition_manifest.csv',manifest)
    summaries=[]
    for n in (12,32):
        for policy in POLICIES:
            group=[r for r in rows if r['size']==n and r['policy']==policy]
            summaries.append(dict(size=n,policy=policy,n_candidates=len(group),
                mean_defect_hit_fraction=float(np.mean([r['defect_hit'] for r in group])),
                score_vs_hit_corr=contrast([r['gradient_score'] for r in group],[r['defect_hit'] for r in group]),
                score_vs_redundancy_corr=contrast([r['gradient_score'] for r in group],[r['prior_path_coverage'] for r in group]),
                score_vs_one_ray_global_corr=contrast([r['gradient_score'] for r in group],[r['one_ray_global_gain'] for r in group]),
                score_vs_one_ray_defect_corr=contrast([r['gradient_score'] for r in group],[r['one_ray_defect_gain'] for r in group]),
                mean_one_ray_defect_gain=float(np.mean([r['one_ray_defect_gain'] for r in group]))))
    _write_csv(out/'descriptive_summary.csv',summaries)
    (out/'run_status.json').write_text(json.dumps(dict(complete=True,probed_candidate_rows=len(rows),
          runs=len(manifest),evaluation_only_confirmed=True),indent=2)+'\n',encoding='utf8')
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()}
    (out/'sha256.json').write_text(json.dumps(hashes,indent=2)+'\n',encoding='utf8')
    return summaries


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,default=Path('results/experiment08e/feedback_first'))
    args=p.parse_args();print(json.dumps(run(args.output_dir),indent=2,allow_nan=True))

if __name__=='__main__':main()
