"""RBYRCT-08G: defect-agnostic split-history disagreement ranking diagnostic.

DEVELOPMENT ONLY. Existing 08E gradient and incremental-guard acquisition histories
are unchanged. Candidate-ray measurements, phantom truth and evaluation masks never
enter disagreement_score. One-ray gains are measured retrospectively after all
acquisition decisions. No result constitutes a new validated acquisition policy.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

from experiment_08e import (acquire_with_probes, retrospective, score_rank,
                            _sha, ANGLES, POLICIES, RELAXATION,
                            NOISE_FRACTION, FINAL_EPOCHS)

# New development objects and acquisition seed, disjoint from 08E, 08C, 07C2.
OBJECT_SEEDS = {12:(809101,809102), 32:(809201,809202)}
ACQUISITION_SEED = 809311
CONFIGS = {12:dict(budget=144,warm=24,batch=16,pool=16,epochs=2,probes=(24,88)),
           32:dict(budget=512,warm=64,batch=32,pool=16,epochs=2,probes=(64,320))}
SPLIT_EPOCHS = 8


def disagreement_score(A_acquired, y_acquired, A_candidate, *, epochs=SPLIT_EPOCHS,
                       relaxation=RELAXATION, reconstruct=None):
    """A scalar acquired-only uncertainty proxy, per candidate ray.

    Split acquired rays by deterministic acquisition-time parity. Two independent
    MART fits produce x_even/x_odd; score_i = |a_i (x_even-x_odd)| / ||a_i||_1.
    No candidate measurement y_i is accepted or accessed. This is disagreement,
    NOT a calibrated uncertainty or expected-error-reduction certificate.
    """
    if reconstruct is None:
        from experiment_05b_mart import mart_reconstruct as reconstruct
    y=np.asarray(y_acquired,dtype=float)
    if (A_acquired.shape[0]!=len(y) or len(y)<4 or not np.isfinite(y).all()
            or A_acquired.shape[1]!=A_candidate.shape[1] or A_candidate.shape[0]<1
            or int(epochs)!=epochs or epochs<1 or not np.isfinite(relaxation)
            or not (0<relaxation<=1)):
        raise ValueError('invalid acquired history, geometry or reconstruction configuration')
    a=A_acquired.tocsr(); c=A_candidate.tocsr()
    p=np.arange(len(y))%2==0
    x0=np.asarray(reconstruct(a[p],y[p],int(epochs),relaxation=relaxation),dtype=float).ravel()
    x1=np.asarray(reconstruct(a[~p],y[~p],int(epochs),relaxation=relaxation),dtype=float).ravel()
    if x0.shape!=(a.shape[1],) or x1.shape!=(a.shape[1],) or not np.isfinite(x0).all() or not np.isfinite(x1).all():
        raise ArithmeticError('nonfinite split reconstruction')
    lengths=np.asarray(np.abs(c).sum(axis=1)).ravel()
    numerator=np.abs(np.asarray(c@(x0-x1)).ravel())
    score=numerator/np.maximum(lengths,1e-12)
    if not np.isfinite(score).all():raise ArithmeticError('nonfinite disagreement scores')
    return score


def _spearman(a,b):
    """Within-pool Spearman without scipy; omit degenerate vectors (NaN)."""
    from scipy.stats import rankdata
    x=np.asarray(a,dtype=float);y=np.asarray(b,dtype=float)
    if len(x)<2 or len(x)!=len(y) or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError('invalid ranking data')
    rx=rankdata(x);ry=rankdata(y)
    if np.std(rx)==0 or np.std(ry)==0:return float('nan')
    return float(np.corrcoef(rx,ry)[0,1])


def summarize(rows):
    """Aggregate FIRST within object to avoid pseudo-replicating candidates."""
    result=[]
    for n in (12,32):
        for policy in POLICIES:
            groups={}
            for r in rows:
                if r['size']==n and r['policy']==policy:
                    key=(r['object_seed'],r['acquired_before'])
                    groups.setdefault(key,[]).append(r)
            poolrows=[]
            for (obj,prefix),pool in groups.items():
                dis=np.array([r['disagreement_score'] for r in pool])
                grad=np.array([r['gradient_score'] for r in pool])
                gg=np.array([r['one_ray_global_gain'] for r in pool])
                dg=np.array([r['one_ray_defect_gain'] for r in pool])
                ids=np.array([r['candidate_ray'] for r in pool],dtype=np.int64)
                ranked=score_rank(dis,ids)
                pick=int(ranked[0]); actual=[i for i,r in enumerate(pool) if r['chosen']==1]
                if len(actual)!=1:raise AssertionError('not one actual selection')
                chosen=actual[0]
                poolrows.append(dict(object_seed=obj,acquired_before=prefix,
                    disagreement_defect_regret=float(dg.max()-dg[pick]),
                    gradient_selected_defect_regret=float(dg.max()-dg[chosen]),
                    disagreement_global_regret=float(gg.max()-gg[pick]),
                    gradient_selected_global_regret=float(gg.max()-gg[chosen]),
                    disagreement_score_vs_defect_spearman=_spearman(dis,dg),
                    gradient_score_vs_defect_spearman=_spearman(grad,dg),
                    disagreement_score_vs_global_spearman=_spearman(dis,gg),
                    disagreement_selected_defect_hit=int(pool[pick]['defect_hit']),
                    actual_selected_defect_hit=int(pool[chosen]['defect_hit']),
                    same_selected_ray=int(pick==chosen)))
            if not poolrows:raise ValueError('no candidate pools')
            objrows=[]
            for obj in sorted(set(r['object_seed'] for r in poolrows)):
                part=[r for r in poolrows if r['object_seed']==obj]
                objrows.append({k:float(np.mean([r[k] for r in part if np.isfinite(r[k])]))
                    if any(np.isfinite(r[k]) for r in part) else float('nan')
                    for k in poolrows[0] if k not in ('object_seed','acquired_before')})
            result.append(dict(size=n,policy=policy,n_objects=len(objrows),n_pools=len(poolrows),
                **{k:float(np.mean([r[k] for r in objrows if np.isfinite(r[k])]))
                     if any(np.isfinite(r[k]) for r in objrows) else float('nan')
                   for k in objrows[0]}))
    return result


def _write(path, rows):
    if not rows:raise ValueError('empty CSV')
    with open(path,'w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def run(output_dir, *, configs=CONFIGS, object_seeds=OBJECT_SEEDS,
        acquisition_seed=ACQUISITION_SEED):
    """New development diagnostic, original 08E policy decisions unchanged."""
    from experiment_04b import system_matrix
    from experiment_04g import TILTS
    from experiment_04h import voxel_coverage_order
    from experiment_05b_gate import AcquiredOnly
    from experiment_05b_08b import nonnegative_noisy_measurements
    from experiment_06b import defect_phantom
    from experiment_07c_preflight import defect_support
    root=Path(output_dir)
    if root.exists() and any(root.iterdir()):raise FileExistsError('output already contains files')
    if not set(configs).issubset({12,32}) or set(configs)!=set(object_seeds):raise ValueError('bad sizes')
    # Prevent inadvertent mixing with previous studies.
    reserved={808701,808702,808801,808802,808401,808402,808403,808404,808501,808502,808503,808504}
    flat=[int(x) for seeds in object_seeds.values() for x in seeds]
    if any(x in reserved or 2077001<=x<=2132434 for x in flat) or len(flat)!=len(set(flat)):
        raise ValueError('object seeds overlap previous study')
    root.mkdir(parents=True,exist_ok=True)
    rows=[];manifest=[]
    for n in sorted(configs):
        cfg=configs[n];A=system_matrix(n,ANGLES,TILTS).tocsr();seed=acquisition_seed+n
        warm=voxel_coverage_order(A,n,ANGLES,len(TILTS),cfg['budget'],seed,cfg['pool'])
        for obj in object_seeds[n]:
            truth,_,_=defect_phantom(n,2,int(obj))
            mask,meta=defect_support(n,2,int(obj))
            measured=nonnegative_noisy_measurements(np.asarray(A@truth).ravel(),NOISE_FRACTION,
                                                     (int(obj)*37+17011)%(2**32))
            for policy in POLICIES:
                gate=AcquiredOnly(measured);gate.commit(warm[:cfg['warm']])
                order,snapshots=acquire_with_probes(A,gate,n,TILTS,warm,cfg,seed,policy)
                if gate.allowed!=set(map(int,order)):raise AssertionError('acquired-only commit mismatch')
                # Only after acquisition is fully frozen: retrospective labels.
                retrospective_rows=retrospective(A,snapshots,measured,truth,mask,final_epochs=FINAL_EPOCHS)
                for snapshot in snapshots:
                    acquired=snapshot['acquired_ids'];cand=snapshot['candidates']
                    # Here the ONLY passed measurements are indexed by acquired IDs.
                    score=disagreement_score(A[acquired],measured[acquired],A[cand])
                    matched=[r for r in retrospective_rows if int(r['acquired_before'])==len(acquired)]
                    if len(matched)!=len(cand):raise AssertionError('probe mismatch')
                    by_id={int(r['candidate_ray']):r for r in matched}
                    for ray,value in zip(cand,score):
                        r=dict(by_id[int(ray)]);r.update(size=n,object_seed=int(obj),
                            disagreement_score=float(value))
                        rows.append(r)
                manifest.append(dict(size=n,object_seed=int(obj),policy=policy,
                    acquired=len(order),order_sha256=_sha(order),probes=len(snapshots),
                    n_candidates=len(retrospective_rows),mask_sha256=meta['mask_sha256']))
                print(f'08G {n}^3 object={obj} policy={policy} candidates={len(retrospective_rows)}',flush=True)
    _write(root/'candidate_diagnostics.csv',rows)
    _write(root/'acquisition_manifest.csv',manifest)
    summary=summarize(rows)
    _write(root/'object_balanced_summary.csv',summary)
    (root/'protocol.json').write_text(json.dumps(dict(stage='08G defect-agnostic disagreement score, retrospective development analysis',
        object_seeds=object_seeds,configs=configs,acquisition_seed=acquisition_seed,
        acquisition_policies=list(POLICIES),score='abs(A_ray@(MART_even-MART_odd))/L1_path',
        score_split_epochs=SPLIT_EPOCHS,retrospective_epochs=FINAL_EPOCHS,
        safeguards=['fixed 08E policy selection unchanged','disagreement computed solely from acquired measurements and geometry',
                    'truth/mask/candidate detector values accessed only after acquisition completes',
                    'new object seeds; no frozen validation reuse'],
        limitations=['No deployable policy or held-out accuracy claim','Two-object development study per resolution',
                     'Split disagreement not necessarily calibrated uncertainty','Local one-ray counterfactuals do not predict policy trajectories']),indent=2)+'\n')
    (root/'run_status.json').write_text(json.dumps(dict(complete=True,candidate_rows=len(rows),histories=len(manifest),pools=len(rows)//16),indent=2)+'\n')
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.iterdir()) if p.is_file()}
    (root/'sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,default=Path('results/experiment08g/disagreement_first'))
    args=p.parse_args()
    print(json.dumps(run(args.output_dir),indent=2,allow_nan=True))

if __name__=='__main__':main()
