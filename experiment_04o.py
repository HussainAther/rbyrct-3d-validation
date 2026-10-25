"""04O-A: acquired-only reliability-signal validation, NOT a new acquisition policy.

Frozen 04J acquisition choices are compared offline. An acquired-ray holdout
and split-prefix feature stability are calculated without object truth or any
unacquired measurements. Truth is used only to label final RMSE wins/losses.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,time
from collections import defaultdict
from pathlib import Path
import numpy as np
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_04i import noisy_full_projection
from experiment_04j import adaptive_order,sirt_silent,image_score,divergence
from experiment_04k import noise_seed_for
from experiment_04n import object_pair
from experiment_04m import high_resolution_matrix


def acquired_only_reliability(A, observed, ids, n, iterations=60, holdout_fraction=.2, seed=42):
    """All accesses to observed are restricted to ids. No ground truth argument."""
    ids=np.asarray(ids,dtype=np.int64)
    if len(ids)<12 or len(np.unique(ids))!=len(ids) or not 0<holdout_fraction<.5:
        raise ValueError('invalid acquired prefix or holdout')
    rng=np.random.default_rng(seed)
    perm=rng.permutation(len(ids))
    n_hold=max(2,min(len(ids)-4,int(round(len(ids)*holdout_fraction))))
    hold=ids[perm[:n_hold]];train=ids[perm[n_hold:]]
    btrain=np.asarray(observed[train]); bhold=np.asarray(observed[hold])
    model=sirt_silent(A[train],btrain,iterations)
    pred=np.asarray(A[hold]@model)
    # Divide by RMS observed amplitude, not by potentially tiny residual norms.
    normalizer=max(float(np.sqrt(np.mean(bhold*bhold))),1.e-12)
    heldout_nrmse=float(np.sqrt(np.mean((pred-bhold)**2))/normalizer)
    # Disjoint training subsets: reproducible stability proxy; both are observed.
    left=train[::2];right=train[1::2]
    f1=image_score(sirt_silent(A[left],observed[left],iterations),n)
    f2=image_score(sirt_silent(A[right],observed[right],iterations),n)
    d1=f1-f1.mean();d2=f2-f2.mean();denom=np.linalg.norm(d1)*np.linalg.norm(d2)
    stability=float(np.dot(d1,d2)/denom) if denom>1.e-12 else 0.
    return dict(heldout_nrmse=heldout_nrmse,feature_split_correlation=stability,
                feature_instability=1.-stability,n_train=len(train),n_holdout=len(hold))


def pair(rows):
    grouped=defaultdict(dict)
    for r in rows:
        key=tuple(r[k] for k in ('object_type','offset','phantom','seed','budget','noise_fraction'))
        if r['policy'] in grouped[key]:raise ValueError('duplicate policy')
        grouped[key][r['policy']]=r
    result=[]
    for key,policies in sorted(grouped.items()):
        if set(policies)!={'adaptive_feedback','feedback_off_control'}:raise ValueError('incomplete paired case')
        a=policies['adaptive_feedback'];b=policies['feedback_off_control']
        gain=(b['rmse']-a['rmse'])/max(b['rmse'],1.e-12)
        result.append(dict(**dict(zip(('object_type','offset','phantom','seed','budget','noise_fraction'),key)),
                      relative_gain=gain,adaptive_win=int(gain>0),
                      adaptive_rmse=a['rmse'],off_rmse=b['rmse']))
    return result


def attach_signals(pairs,signals):
    by_key=defaultdict(list)
    for r in signals:
        key=tuple(r[k] for k in ('object_type','offset','phantom','seed','budget','noise_fraction'))
        by_key[key].append(r)
    out=[]
    for p in pairs:
        key=tuple(p[k] for k in ('object_type','offset','phantom','seed','budget','noise_fraction'))
        vals=by_key[key]
        if not vals:raise ValueError('missing signal')
        vals=sorted(vals,key=lambda x:x['acquired'])
        out.append(dict(**p,earliest_heldout_nrmse=vals[0]['heldout_nrmse'],
                        latest_heldout_nrmse=vals[-1]['heldout_nrmse'],
                        earliest_feature_instability=vals[0]['feature_instability'],
                        latest_feature_instability=vals[-1]['feature_instability'],
                        diagnostics_prefixes=len(vals)))
    return out


def summarize(rows):
    groups=defaultdict(list)
    for r in rows:groups[(r['object_type'],r['offset'],r['budget'])].append(r)
    result=[]
    for (ob,off,budget),rr in sorted(groups.items()):
        result.append(dict(object_type=ob,offset=off,budget=budget,n=len(rr),
          wins=sum(r['adaptive_win'] for r in rr),mean_gain=float(np.mean([r['relative_gain'] for r in rr])),
          mean_heldout=float(np.mean([r['earliest_heldout_nrmse'] for r in rr])),
          mean_instability=float(np.mean([r['earliest_feature_instability'] for r in rr]))))
    return result


def associations(rows):
    # Descriptive associations, not a calibrated classifier or an independently held-out claim.
    out=[]
    for budget in sorted({r['budget'] for r in rows}):
        subset=[r for r in rows if r['budget']==budget]
        y=np.array([r['relative_gain'] for r in subset],float)
        for k in ('earliest_heldout_nrmse','latest_heldout_nrmse','earliest_feature_instability','latest_feature_instability'):
            x=np.array([r[k] for r in subset],float)
            rho=float(np.corrcoef(x,y)[0,1]) if len(x)>2 and x.std()>1.e-12 and y.std()>1.e-12 else float('nan')
            out.append(dict(budget=budget,signal=k,n=len(subset),pearson_vs_gain=rho,
                            note='exploratory correlated repeated cases; not an independent predictive validation'))
    return out


def save(path,rows):
    if not rows:return
    with open(path,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--size',type=int,default=16);p.add_argument('--angles',type=int,default=12)
    p.add_argument('--factor',type=int,default=2)
    p.add_argument('--object-types',nargs='+',choices=['replicated','subvoxel'],default=['replicated','subvoxel'])
    p.add_argument('--offsets',nargs='+',type=float,default=[0.,.15])
    p.add_argument('--budgets',nargs='+',type=int,default=[512,1024,2048])
    p.add_argument('--seeds',nargs='+',type=int,default=[104729,130363,155921])
    p.add_argument('--phantoms',nargs='+',choices=['torus','slats','beads','wedges'],default=['torus','slats','beads','wedges'])
    p.add_argument('--noise-fractions',nargs='+',type=float,default=[0.])
    p.add_argument('--warm-rays',type=int,default=128);p.add_argument('--batch',type=int,default=64)
    p.add_argument('--provisional-iterations',type=int,default=60)
    p.add_argument('--sirt-iterations',type=int,default=400)
    p.add_argument('--candidate-pool',type=int,default=64)
    p.add_argument('--holdout-fraction',type=float,default=.2)
    p.add_argument('--diagnostic-prefixes',type=int,default=3)
    p.add_argument('--output-dir',type=Path,default=Path('results/experiment04o_a'))
    a=p.parse_args(argv)
    total=len(TILTS)*a.angles*a.size*a.size
    if a.size<4 or a.angles<2 or a.factor<2 or not a.offsets or min(a.offsets)<0 or not a.budgets or min(a.budgets)<=a.warm_rays or max(a.budgets)>total or a.warm_rays<12 or a.batch<1 or a.provisional_iterations<1 or a.sirt_iterations<1 or a.candidate_pool<1 or not 0<a.holdout_fraction<.5 or a.diagnostic_prefixes<1 or not a.phantoms or not a.seeds or not a.noise_fractions or min(a.noise_fractions)<0:
        p.error('invalid 04O-A configuration')
    a.output_dir.mkdir(parents=True,exist_ok=True)
    A=system_matrix(a.size,a.angles,TILTS).tocsr()
    operators={offset:high_resolution_matrix(a.size,a.angles,TILTS,a.factor,offset) for offset in sorted(set(a.offsets))}
    objects={name:object_pair(name,a.size,a.factor) for name in a.phantoms}
    results=[];signals=[];divergences=[]
    for seed in a.seeds:
        fixed=voxel_coverage_order(A,a.size,a.angles,len(TILTS),max(a.budgets),seed,a.candidate_pool)
        for obj_type in a.object_types:
            for name in a.phantoms:
                truth,fine=objects[name][obj_type]
                for offset,M in operators.items():
                    clean=np.asarray(M@fine).ravel()
                    mismatch=float(np.linalg.norm(clean-A@truth)/max(np.linalg.norm(A@truth),1.e-12))
                    for noise in sorted(set(a.noise_fractions)):
                        observed=noisy_full_projection(clean,noise,noise_seed_for(seed,name,noise))
                        for budget in sorted(set(a.budgets)):
                            chosen,_,t_adaptive=adaptive_order(A,observed,a.size,a.angles,fixed,budget,seed,a.warm_rays,a.batch,a.provisional_iterations,a.candidate_pool,1.)
                            off,_,t_off=adaptive_order(A,observed,a.size,a.angles,fixed,budget,seed,a.warm_rays,a.batch,a.provisional_iterations,a.candidate_pool,0.)
                            meta=dict(object_type=obj_type,offset=offset,phantom=name,seed=seed,budget=budget,noise_fraction=noise)
                            divergences.append(dict(**meta,**divergence(chosen,off,a.warm_rays)))
                            for policy,ids,selection_s in [('adaptive_feedback',chosen,t_adaptive),('feedback_off_control',off,t_off)]:
                                x=sirt_silent(A[ids],observed[ids],a.sirt_iterations)
                                rmse=float(np.sqrt(np.mean((x-truth)**2)))
                                results.append(dict(**meta,policy=policy,rmse=rmse,selection_s=selection_s,relative_projection_mismatch=mismatch))
                                print(f'{obj_type:10} offset={offset:g} {name:7} seed={seed} b={budget:4} {policy:21} rmse={rmse:.6f}',flush=True)
                            # Evaluate only prefixes available *before* final budget, on the frozen adaptive trajectory.
                            for j in range(a.diagnostic_prefixes):
                                prefix=a.warm_rays+j*a.batch
                                if prefix>=budget:break
                                ids=chosen[:prefix]
                                vals=acquired_only_reliability(A,observed,ids,a.size,a.provisional_iterations,
                                    a.holdout_fraction,seed=seed+991*j)
                                signals.append(dict(**meta,acquired=prefix,**vals))
    pairs=pair(results);attached=attach_signals(pairs,signals)
    for filename,rows in [('metrics.csv',results),('signals.csv',signals),('paired_cases.csv',attached),
                          ('summary.csv',summarize(attached)),('associations.csv',associations(attached)),('divergence.csv',divergences)]:
        save(a.output_dir/filename,rows)
    (a.output_dir/'protocol.json').write_text(json.dumps(dict(experiment='04O-A',phase='exploratory reliability signal validation; selector unchanged',
       parameters={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},
       diagnostic_definition='Holdout and disjoint feature-map split on acquired prefix; never reads unacquired observations',
       label_definition='After acquisition, reconstruction RMSE relative to feedback-off using truth',
       limitations=['Uses previously explored phantom families; no heldout validation','Feature stability is not calibrated uncertainty',
                    'Same evaluation data used for signal/gain associations','Holdout validation holds out acquired rays from fitting, but rays were chosen adaptively','Subset features can be unstable simply from sparse sampling','Operator families share underlying tracing physics','Selection overhead measured separately and baseline timing not comparable']),indent=2),encoding='utf-8')
    print(f'04O-A complete: {len(results)} reconstructions, {len(pairs)} paired cases; results={a.output_dir}',flush=True)
if __name__=='__main__':main()
