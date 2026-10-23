"""04N: frozen 04J adaptive-policy failure-mechanism controls after 04M.

Separates subvoxel object differences from forward-grid discretization,
then evaluates a fixed ray-origin-offset severity sweep. Truth is used only
for after-the-fact scoring; no oracle truth enters ray selection.
"""
from __future__ import annotations
import argparse, csv, json, time, hashlib
from collections import defaultdict
from pathlib import Path
import numpy as np
from experiment_04b import system_matrix
from experiment_04g import TILTS, policies
from experiment_04h import voxel_coverage_order, coverage
from experiment_04i import noisy_full_projection
from experiment_04j import adaptive_order, sirt_silent, divergence, image_score
from experiment_04k import new_phantoms, noise_seed_for
from experiment_04m import high_resolution_matrix, downsample_average

POLICIES=('adaptive_feedback','feedback_off_control','voxel_coverage_greedy','random','geometry_balanced')

def replicate_coarse(coarse, factor):
    if factor < 2 or coarse.ndim != 3 or len(set(coarse.shape))!=1:
        raise ValueError('requires cubic volume and factor >=2')
    return np.repeat(np.repeat(np.repeat(coarse,factor,axis=0),factor,axis=1),factor,axis=2)

def object_pair(name,n,factor):
    # Exactly replicated coarse object isolates operator-grid changes.
    coarse=new_phantoms(n)[name]
    fine_rep=replicate_coarse(coarse,factor)
    # Analytic fine phantom adds subvoxel content; target = block-averaged fine object.
    fine_native=new_phantoms(n*factor)[name]
    return {'replicated':(coarse.ravel(),fine_rep.ravel()),
            'subvoxel':(downsample_average(fine_native,factor).ravel(),fine_native.ravel())}

def write_csv(path,rows):
    if not rows:return
    with Path(path).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def paired_summary(rows):
    cases=defaultdict(dict)
    for r in rows:
        k=(r['object_type'],r['offset'],r['phantom'],r['seed'],r['budget'],r['noise_fraction'])
        if r['policy'] in cases[k]:raise ValueError('duplicate policy case')
        cases[k][r['policy']]=float(r['rmse'])
    out=[]
    for k,p in sorted(cases.items()):
        if set(p)!=set(POLICIES): raise ValueError(f'incomplete case: {k}')
        for comp in POLICIES[1:]:
            base=p[comp];adaptive=p['adaptive_feedback']
            out.append(dict(object_type=k[0],offset=k[1],phantom=k[2],seed=k[3],budget=k[4],noise_fraction=k[5],
                            comparator=comp,adaptive_rmse=adaptive,comparator_rmse=base,
                            relative_gain=(base-adaptive)/max(base,1e-12),win=int(adaptive<base)))
    group=defaultdict(list)
    for r in out:group[(r['object_type'],r['offset'],r['budget'],r['comparator'])].append(r['relative_gain'])
    summ=[dict(object_type=o,offset=d,budget=b,comparator=c,n=len(v),wins=sum(x>0 for x in v),
               mean_gain=float(np.mean(v)),median_gain=float(np.median(v))) for (o,d,b,c),v in sorted(group.items())]
    return out,summ

def selection_feature_diagnostics(A, observations, truth, n, order, warm, batch, iterations):
    # Post-hoc audit: reconstruct only from acquired prefix; truth used only
    # to compute agreement / error, never passed into adaptive_order.
    gt=image_score(truth,n)
    result=[]
    for prefix in range(warm,min(len(order),warm+3*batch)+1,batch):
        ids=order[:prefix]
        est=sirt_silent(A[ids],observations[ids],iterations)
        feat=image_score(est,n)
        gt_center=gt-gt.mean();f_center=feat-feat.mean()
        denom=np.linalg.norm(gt_center)*np.linalg.norm(f_center)
        corr=float(np.dot(gt_center,f_center)/denom) if denom>1e-12 else 0.
        result.append(dict(acquired=prefix,provisional_rmse=float(np.sqrt(np.mean((est-truth)**2))),
                           feature_pearson=corr,feature_std=float(feat.std())))
    return result

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--size',type=int,default=16);p.add_argument('--angles',type=int,default=12)
    p.add_argument('--factor',type=int,default=2)
    p.add_argument('--object-types',nargs='+',choices=['replicated','subvoxel'],default=['replicated','subvoxel'])
    p.add_argument('--offsets',nargs='+',type=float,default=[0.,0.05,0.15,0.30])
    p.add_argument('--budgets',nargs='+',type=int,default=[512,1024,2048])
    p.add_argument('--seeds',nargs='+',type=int,default=[104729,130363,155921])
    p.add_argument('--phantoms',nargs='+',choices=['torus','slats','beads','wedges'],default=['torus','slats','beads','wedges'])
    p.add_argument('--noise-fractions',nargs='+',type=float,default=[0.])
    p.add_argument('--warm-rays',type=int,default=128);p.add_argument('--batch',type=int,default=64)
    p.add_argument('--provisional-iterations',type=int,default=60)
    p.add_argument('--sirt-iterations',type=int,default=400)
    p.add_argument('--candidate-pool',type=int,default=64)
    p.add_argument('--output-dir',type=Path,default=Path('results/experiment04n'))
    a=p.parse_args(argv)
    n_rays=len(TILTS)*a.angles*a.size*a.size
    if (a.size<4 or a.factor<2 or a.angles<2 or not a.offsets or min(a.offsets)<0 or not a.budgets
        or min(a.budgets)<=a.warm_rays or max(a.budgets)>n_rays or a.warm_rays<1 or a.batch<1 or
        a.provisional_iterations<1 or a.sirt_iterations<1 or a.candidate_pool<1 or
        not a.phantoms or not a.seeds or not a.noise_fractions or min(a.noise_fractions)<0):
        p.error('invalid 04N configuration')
    a.output_dir.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter();A=system_matrix(a.size,a.angles,TILTS).tocsr()
    operators={}
    for offset in sorted(set(a.offsets)):
        ts=time.perf_counter()
        operators[offset]=high_resolution_matrix(a.size,a.angles,TILTS,a.factor,offset)
        print(f'04N fine offset={offset:g}: nnz={operators[offset].nnz} built_s={time.perf_counter()-ts:.2f}',flush=True)
    print(f'04N coarse={A.shape} setup_s={time.perf_counter()-started:.2f}',flush=True)
    metrics=[];diagnostics=[];divergences=[];features=[];times=[]
    objects={pname:object_pair(pname,a.size,a.factor) for pname in a.phantoms}
    maxbudget=max(a.budgets)
    for seed in a.seeds:
        ts=time.perf_counter();fixed=voxel_coverage_order(A,a.size,a.angles,len(TILTS),maxbudget,seed,a.candidate_pool)
        fixed_time=time.perf_counter()-ts
        baseline=policies(a.size,a.angles,len(TILTS),seed)
        for objtype in a.object_types:
            for name in a.phantoms:
                truth,fine_truth=objects[name][objtype]
                matched=A@truth
                for offset,M in operators.items():
                    clean=np.asarray(M@fine_truth).ravel()
                    mismatch=float(np.linalg.norm(clean-matched)/max(np.linalg.norm(matched),1.e-12))
                    diagnostics.append(dict(object_type=objtype,offset=offset,phantom=name,seed=seed,
                        relative_projection_mismatch=mismatch,projection_rmse=float(np.sqrt(np.mean((clean-matched)**2)))))
                    for noise in sorted(set(a.noise_fractions)):
                        obs=noisy_full_projection(clean,noise,noise_seed_for(seed,name,noise))
                        for budget in sorted(set(a.budgets)):
                            chosen,trace,adaptive_s=adaptive_order(A,obs,a.size,a.angles,fixed,budget,seed,
                                a.warm_rays,a.batch,a.provisional_iterations,a.candidate_pool,1.)
                            off,_,off_s=adaptive_order(A,obs,a.size,a.angles,fixed,budget,seed,
                                a.warm_rays,a.batch,a.provisional_iterations,a.candidate_pool,0.)
                            meta=dict(object_type=objtype,offset=offset,phantom=name,seed=seed,budget=budget,noise_fraction=noise)
                            diver=divergence(chosen,off,a.warm_rays)
                            divergences.append(dict(**meta,**diver))
                            for info in selection_feature_diagnostics(A,obs,truth,a.size,chosen,a.warm_rays,a.batch,a.provisional_iterations):
                                features.append(dict(**meta,policy='adaptive_feedback',**info))
                            selections=dict(adaptive_feedback=chosen,feedback_off_control=off,
                                voxel_coverage_greedy=fixed[:budget],random=baseline['random'][:budget],
                                geometry_balanced=baseline['geometry_balanced'][:budget])
                            for policy,ids in selections.items():
                                assert len(ids)==budget and len(np.unique(ids))==budget
                                ts=time.perf_counter();sub=A[ids];estimate=sirt_silent(sub,obs[ids],a.sirt_iterations)
                                solve_s=time.perf_counter()-ts
                                error=float(np.sqrt(np.mean((estimate-truth)**2)))
                                cov=coverage(A,ids,a.size,a.angles,len(TILTS),budget)
                                metrics.append(dict(**meta,policy=policy,rmse=error,relative_projection_mismatch=mismatch,
                                    covered_voxels=cov['covered_voxels'],voxel_pathlength_cv=cov['voxel_pathlength_cv'],
                                    view_count_cv=cov['view_count_cv'],solver_s=solve_s))
                                times.append(dict(**meta,policy=policy,
                                    selection_s=adaptive_s if policy=='adaptive_feedback' else off_s if policy=='feedback_off_control' else fixed_time if policy=='voxel_coverage_greedy' else 0.,
                                    selection_scope='online_per_case' if policy in ('adaptive_feedback','feedback_off_control') else 'precomputed_max_budget' if policy=='voxel_coverage_greedy' else 'baseline_not_timed'))
                                print(f'{objtype:10} offset={offset:.3g} {name:7} seed={seed} rays={budget:4} noise={noise:.3g} {policy:22} rmse={error:.6f}',flush=True)
    pairs,summary=paired_summary(metrics)
    for filename,rows in [('metrics.csv',metrics),('paired_cases.csv',pairs),('paired_summary.csv',summary),
             ('mismatch_diagnostics.csv',diagnostics),('divergence.csv',divergences),
             ('provisional_features.csv',features),('selection_timing.csv',times)]:
        write_csv(a.output_dir/filename,rows)
    (a.output_dir/'protocol.json').write_text(json.dumps(dict(experiment='04N',
        parameters={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},
        controls=['replicated: same coarse piecewise-constant object in both grids',
                  'subvoxel: fine analytic object, evaluate vs its block average',
                  'offset sweep: perturb fine detector ray origins only'],
        frozen_selector='04J adaptive_order imported unchanged',
        cautions=['03D/04K phantom families have been used in development; mechanistic analysis not new holdout',
                  'Fine and coarse operators share ray traversal physics, so not a truly independent physical simulator',
                  'Noise and seeds are correlated repeated conditions, not independent populations',
                  'Ground truth feature maps only used in post-hoc audit, never selector',
                  'Feature correlation does not prove causality',
                  'Time for precomputed frozen greedy differs in scope from online selection',
                  'No clinical dose or hardware claim']),indent=2),encoding='utf-8')
    print(f'04N completed {len(metrics)} reconstructions and {len(pairs)//4} paired cases; results: {a.output_dir}',flush=True)
if __name__=='__main__':main()
