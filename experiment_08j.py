"""RBYRCT-08J: acquired-geometry diagonal-precision information score.

DEVELOPMENT ONLY. Acquired-only score; same frozen 08E gradient and incremental_25
selectors are used to generate histories. No new policy is deployed. The diagonal
covariance is a surrogate, not MART posterior uncertainty. Counterfactual labels
are evaluated only after each full history is fixed.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

from experiment_08e import (acquire_with_probes, retrospective, score_rank,
    _sha, ANGLES, POLICIES, RELAXATION, NOISE_FRACTION, FINAL_EPOCHS)

OBJECT_SEEDS={12:(809701,809702),32:(809801,809802)}
ACQUISITION_SEED=809911
CONFIGS={12:dict(budget=144,warm=24,batch=16,pool=16,epochs=2,probes=(24,88)),
         32:dict(budget=512,warm=64,batch=32,pool=16,epochs=2,probes=(64,320))}
# Explicit fixed, dimensionless model parameters, not fitted to 06B/07C2/08E-08I gains.
PRIOR_VARIANCE=1.0
OBSERVATION_VARIANCE=1.0


def diagonal_precision(A_acquired, *, prior_variance=PRIOR_VARIANCE,
                       observation_variance=OBSERVATION_VARIANCE):
    """D_j = (tau^-2 + sum_i A_ij^2 / sigma^2)^-1.

    This is inverse diagonal approximate precision, not diag[(A^T A+...)^-1].
    Only acquired geometry is accepted; no truth or candidate measurements.
    """
    from scipy import sparse
    if not sparse.issparse(A_acquired):
        raise TypeError('acquired geometry must be sparse')
    if A_acquired.ndim != 2 or A_acquired.shape[0] < 1 or A_acquired.shape[1] < 1:
        raise ValueError('empty acquired geometry')
    if not (np.isfinite(prior_variance) and prior_variance>0 and
            np.isfinite(observation_variance) and observation_variance>0):
        raise ValueError('variances must be finite and positive')
    a=A_acquired.tocsr(copy=True)
    if not np.isfinite(a.data).all():
        raise ValueError('nonfinite geometry')
    a.data **= 2
    fisher=np.asarray(a.sum(axis=0)).ravel()/observation_variance
    d=1.0/(1.0/prior_variance+fisher)
    if not np.isfinite(d).all() or (d<=0).any():
        raise ArithmeticError('invalid diagonal precision proxy')
    return d


def info_score(A_acquired, A_candidates, *, prior_variance=PRIOR_VARIANCE,
               observation_variance=OBSERVATION_VARIANCE):
    """Trace reduction for a hypothetical diagonal D updated by one candidate.

    S(a)=sum_j a_j^2 D_j^2 / (sigma^2 + sum_j a_j^2 D_j).
    Formula follows Sherman-Morrison for D' = D-Daa^TD/(sigma^2+a^TDa).
    Strictly a rank-one update of the assumed D, NOT a MART improvement guarantee.
    """
    from scipy import sparse
    if not sparse.issparse(A_candidates):
        raise TypeError('candidate geometry must be sparse')
    if A_candidates.ndim != 2 or A_candidates.shape[0] < 1 or A_acquired.shape[1]!=A_candidates.shape[1]:
        raise ValueError('invalid candidate geometry')
    d=diagonal_precision(A_acquired,prior_variance=prior_variance,
                         observation_variance=observation_variance)
    c=A_candidates.tocsr(copy=True)
    if not np.isfinite(c.data).all():
        raise ValueError('nonfinite candidate geometry')
    c.data **= 2
    numerator=np.asarray(c@(d*d)).ravel()
    denominator=observation_variance+np.asarray(c@d).ravel()
    result=numerator/denominator
    if not np.isfinite(result).all() or (result<0).any():
        raise ArithmeticError('invalid information proxy')
    return result


def _spearman(x,y):
    from scipy.stats import rankdata
    x=np.asarray(x,dtype=float);y=np.asarray(y,dtype=float)
    if len(x)<2 or x.shape!=y.shape or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError('invalid ranking vectors')
    xx=rankdata(x);yy=rankdata(y)
    if np.std(xx)==0 or np.std(yy)==0:return float('nan')
    return float(np.corrcoef(xx,yy)[0,1])


def summarize(rows):
    """Pool -> object -> condition. Never count individual rays as replicates."""
    out=[]; poolrows=[]
    for n in sorted(set(int(r['size']) for r in rows)):
        for policy in POLICIES:
            pools={}
            for r in rows:
                if int(r['size'])==n and r['policy']==policy:
                    pools.setdefault((int(r['object_seed']),int(r['acquired_before'])),[]).append(r)
            if not pools:continue
            for (obj,prefix),p in sorted(pools.items()):
                ids=np.array([int(r['candidate_ray']) for r in p]);
                if len(set(ids))!=len(ids) or sum(int(r['chosen']) for r in p)!=1:
                    raise ValueError('invalid candidate pool or selected candidate')
                scores=np.array([float(r['info_score']) for r in p]);grad=np.array([float(r['gradient_score']) for r in p]);
                dg=np.array([float(r['one_ray_defect_gain']) for r in p]);gg=np.array([float(r['one_ray_global_gain']) for r in p]);
                best=int(score_rank(scores,ids)[0]);actual=int(np.argmax([int(r['chosen']) for r in p]));
                poolrows.append(dict(size=n,policy=policy,object_seed=obj,acquired_before=prefix,
                    n_candidates=len(p),info_defect_regret=float(max(dg)-dg[best]),
                    existing_defect_regret=float(max(dg)-dg[actual]),
                    info_global_regret=float(max(gg)-gg[best]),
                    existing_global_regret=float(max(gg)-gg[actual]),
                    info_defect_spearman=_spearman(scores,dg),
                    gradient_defect_spearman=_spearman(grad,dg),
                    info_global_spearman=_spearman(scores,gg),
                    info_selected_defect_hit=int(p[best]['defect_hit']),
                    actual_selected_defect_hit=int(p[actual]['defect_hit']),
                    info_matches_existing=int(best==actual)))
            these=[p for p in poolrows if p['size']==n and p['policy']==policy]
            object_rows=[]
            for obj in sorted(set(r['object_seed'] for r in these)):
                group=[r for r in these if r['object_seed']==obj]
                keys=[k for k in group[0] if k not in ('size','policy','object_seed','acquired_before','n_candidates')]
                object_rows.append({k:float(np.mean([r[k] for r in group if np.isfinite(r[k])])) if any(np.isfinite(r[k]) for r in group) else float('nan') for k in keys})
            out.append(dict(size=n,policy=policy,n_objects=len(object_rows),n_pools=len(these),
                **{k:float(np.mean([r[k] for r in object_rows if np.isfinite(r[k])])) if any(np.isfinite(r[k]) for r in object_rows) else float('nan') for k in object_rows[0]}))
    return out,poolrows


def write_csv(path,rows):
    if not rows:raise ValueError('no rows')
    with Path(path).open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def run(output_dir, *, configs=CONFIGS, object_seeds=OBJECT_SEEDS,
        acquisition_seed=ACQUISITION_SEED, prior_variance=PRIOR_VARIANCE,
        observation_variance=OBSERVATION_VARIANCE):
    """Fresh 08J development histories, score after acquisition, then evaluate."""
    from experiment_04b import system_matrix
    from experiment_04g import TILTS
    from experiment_04h import voxel_coverage_order
    from experiment_05b_gate import AcquiredOnly
    from experiment_05b_08b import nonnegative_noisy_measurements
    from experiment_06b import defect_phantom
    from experiment_07c_preflight import defect_support
    root=Path(output_dir)
    if root.exists() and any(root.iterdir()):raise FileExistsError('output exists; no overwrite')
    if not configs or set(configs)!=set(object_seeds) or not set(configs).issubset({12,32}):
        raise ValueError('invalid sizes')
    reserved={808701,808702,808801,808802,809101,809102,809201,809202}
    seeds=[int(s) for v in object_seeds.values() for s in v]
    if len(seeds)!=len(set(seeds)) or any(s in reserved or 2077001<=s<=2132434 for s in seeds):
        raise ValueError('study seeds reused')
    # Validate score parameters before creating output directory.
    from scipy import sparse
    info_score(sparse.csr_matrix([[1.]]),sparse.csr_matrix([[1.]]),
               prior_variance=prior_variance,observation_variance=observation_variance)
    root.mkdir(parents=True,exist_ok=True)
    rows=[];manifest=[]
    for n in sorted(configs):
        cfg=configs[n]
        A=system_matrix(n,ANGLES,TILTS).tocsr();seed=acquisition_seed+n
        warm=voxel_coverage_order(A,n,ANGLES,len(TILTS),cfg['budget'],seed,cfg['pool'])
        for obj in object_seeds[n]:
            truth,_,_=defect_phantom(n,2,int(obj))
            mask,meta=defect_support(n,2,int(obj))
            measurements=nonnegative_noisy_measurements(np.asarray(A@truth).ravel(),NOISE_FRACTION,
                                    (int(obj)*37+17011)%(2**32))
            for policy in POLICIES:
                gate=AcquiredOnly(measurements);gate.commit(warm[:cfg['warm']])
                order,snapshots=acquire_with_probes(A,gate,n,TILTS,warm,cfg,seed,policy)
                if gate.allowed!=set(map(int,order)):
                    raise AssertionError('acquired-only violation')
                # Acquire entire history first; retrospective may see hidden truth,
                # but the information score is computed using ONLY acquired geometry.
                retrospective_rows=retrospective(A,snapshots,measurements,truth,mask,FINAL_EPOCHS)
                for snap in snapshots:
                    ids=np.asarray(snap['acquired_ids'],dtype=int);cands=np.asarray(snap['candidates'],dtype=int)
                    score=info_score(A[ids],A[cands],prior_variance=prior_variance,
                                     observation_variance=observation_variance)
                    byid={int(r['candidate_ray']):r for r in retrospective_rows if int(r['acquired_before'])==len(ids)}
                    if len(byid)!=len(cands):raise AssertionError('candidate/label alignment mismatch')
                    for ray,ss in zip(cands,score):
                        row=dict(byid[int(ray)]);row.update(size=n,object_seed=int(obj),info_score=float(ss))
                        rows.append(row)
                manifest.append(dict(size=n,object_seed=int(obj),policy=policy,acquired=len(order),
                    order_sha256=_sha(order),probes=len(snapshots),evaluated_candidates=len(retrospective_rows),
                    mask_sha256=meta['mask_sha256']))
                print(f'08J {n}^3 object={obj} policy={policy} candidates={len(retrospective_rows)}',flush=True)
    write_csv(root/'candidate_diagnostics.csv',rows)
    write_csv(root/'acquisition_manifest.csv',manifest)
    summary,pools=summarize(rows)
    write_csv(root/'pool_diagnostics.csv',pools)
    write_csv(root/'object_balanced_summary.csv',summary)
    (root/'protocol.json').write_text(json.dumps(dict(stage='08J acquired-only diagonal-precision proxy (development-only)',
        sizes=sorted(configs),object_seeds=object_seeds,configs=configs,acquisition_seed=acquisition_seed,
        prior_variance=prior_variance,observation_variance=observation_variance,
        approximation='inverse diagonal precision; not true covariance or MART posterior',
        score='(a^T D^2 a)/(sigma2 + a^T D a)',
        baseline_policies=POLICIES,truth_access='ONLY retrospective after acquisition finished',
        limitations=['No new adaptive policy deployed','No calibrated uncertainty claim',
            'Two development objects per scale','One-ray retrospective regret not cumulative benefit',
            'No frozen 06B/07C2 results or object seeds used in tuning']),indent=2)+'\n')
    (root/'run_status.json').write_text(json.dumps(dict(complete=True,histories=len(manifest),
        pools=len(pools),candidate_rows=len(rows)),indent=2)+'\n')
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.iterdir()) if p.is_file()}
    (root/'sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,default=Path('results/experiment08j/information_first'))
    args=p.parse_args()
    print(json.dumps(run(args.output_dir),indent=2,allow_nan=True))

if __name__=='__main__':main()
