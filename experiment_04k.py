"""04K: frozen 04J measurement-feedback acquisition on NEW analytical 3D phantoms.

Imports 04J's adaptive_order / sirt_silent unchanged. This is a synthetic
out-of-family validation, not external or clinical validation. No selection
hyperparameters are tuned to the new phantoms.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, time
from collections import defaultdict
from pathlib import Path
import numpy as np
from experiment_04b import system_matrix
from experiment_04g import TILTS, policies
from experiment_04h import voxel_coverage_order
from experiment_04i import noisy_full_projection, paired_summary
from experiment_04j import adaptive_order, divergence, sirt_silent

POLICY_NAMES=('adaptive_feedback','feedback_off_control','voxel_coverage_greedy','random','geometry_balanced')

def new_phantoms(n):
    q=(np.arange(n)+.5-n/2)/(n/2)
    z,y,x=np.meshgrid(q,q,q,indexing='ij')
    rho=np.sqrt(x*x+y*y)
    # Torus: fundamentally different from 04I's spherical shell.
    torus=.025+.63*((rho-.49)**2+(z-.10)**2 < .17**2)
    torus+=.19*((x+.20)**2+(y-.34)**2+(z+.25)**2<.13**2)
    # Oblique slats: sparse, oriented planar objects.
    slats=.025+.51*((np.abs(x+.64*y-.23*z)<.105)&(np.abs(z)<.68)&(np.abs(y)<.7))
    slats+=.26*((np.abs(x-.35*y+.56*z-.22)<.07)&(np.abs(x)<.70)&(np.abs(y)<.7))
    # Separated unequal beads, no ellipsoids.
    beads=np.full_like(x,.025)
    for px,py,pz,r,v in [(-.48,-.36,-.37,.20,.69),(.41,-.39,.28,.16,.50),(.15,.42,-.19,.24,.42),(-.34,.35,.42,.12,.72)]:
        beads+=v*((x-px)**2+(y-py)**2+(z-pz)**2<r*r)
    # Nonparallel wedge and taper.
    wedges=.025+.55*((z>-.50)&(z<.60)&(y>-.42)&(y<.48)&(x>-.45)&(x<.40+.35*z))
    wedges+=.18*((x+.30*y>.02)&(x+.30*y<.13)&(z>-.6)&(z<.53)&(y<.35))
    return {name:np.asarray(obj,dtype=np.float64) for name,obj in locals().copy().items() if name in ('torus','slats','beads','wedges')}

def save_csv(path,rows):
    if not rows:return
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def noise_seed_for(seed,phantom,noise):
    return (seed+int(hashlib.sha256(f'{phantom}:{noise:.12g}'.encode()).hexdigest()[:8],16))%(2**32)

def paired_per_case(rows,base):
    records=defaultdict(dict)
    for row in rows: records[(row['phantom'],row['seed'],row['budget'],row['noise_fraction'])][row['policy']]=row['rmse']
    out=[]
    for (phantom,seed,budget,noise),policies_ in sorted(records.items()):
        if base not in policies_ or 'adaptive_feedback' not in policies_:continue
        ref,got=policies_[base],policies_['adaptive_feedback']
        out.append(dict(phantom=phantom,seed=seed,budget=budget,noise_fraction=noise,comparator=base,
                        adaptive_rmse=got,comparator_rmse=ref,relative_gain=(ref-got)/max(ref,1e-12),win=int(got<ref)))
    return out

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--size',type=int,default=16);p.add_argument('--angles',type=int,default=12)
    p.add_argument('--budgets',type=int,nargs='+',default=[512,1024,2048])
    p.add_argument('--seeds',type=int,nargs='+',default=[104729,130363,155921])
    p.add_argument('--phantoms',nargs='+',default=['torus','slats','beads','wedges'])
    p.add_argument('--noise-fractions',type=float,nargs='+',default=[0.,.002,.01])
    p.add_argument('--warm-rays',type=int,default=128);p.add_argument('--batch',type=int,default=64)
    p.add_argument('--provisional-iterations',type=int,default=60)
    p.add_argument('--sirt-iterations',type=int,default=400)
    p.add_argument('--candidate-pool',type=int,default=64)
    p.add_argument('--feedback-strength',type=float,default=1.)
    p.add_argument('--output-dir',type=Path,default=Path('results/experiment04k'))
    args=p.parse_args(argv)
    bounds=len(TILTS)*args.angles*args.size**2
    if (args.size<4 or args.angles<2 or not args.budgets or not args.seeds or not args.noise_fractions
        or min(args.budgets)<=args.warm_rays or max(args.budgets)>bounds or args.warm_rays<1
        or min(args.noise_fractions)<0 or args.batch<1 or args.provisional_iterations<1 or
        args.sirt_iterations<1 or args.candidate_pool<1 or args.feedback_strength<0):p.error('invalid 04K configuration')
    phantoms=new_phantoms(args.size)
    if not args.phantoms or any(name not in phantoms for name in args.phantoms):p.error('unknown 04K phantom')
    budgets=sorted(set(args.budgets));noises=sorted(set(args.noise_fractions))
    args.output_dir.mkdir(parents=True,exist_ok=True)
    start=time.perf_counter();A=system_matrix(args.size,args.angles,TILTS).tocsr()
    print(f'04K - frozen 04J feedback validation on new synthetic families\nvolume={args.size}^3 rays={A.shape[0]} nnz={A.nnz} build_s={time.perf_counter()-start:.2f}',flush=True)
    metrics=[]; orders=[]; trace_rows=[]; diverge_rows=[]; swap_rows=[]
    for seed in args.seeds:
        t=time.perf_counter()
        fixed=voxel_coverage_order(A,args.size,args.angles,len(TILTS),max(budgets),seed,args.candidate_pool)
        fixed_s=time.perf_counter()-t
        baselines=policies(args.size,args.angles,len(TILTS),seed)
        for noise in noises:
            for budget in budgets:
                swaps={}
                for name in args.phantoms:
                    truth=phantoms[name].ravel(); clean=np.asarray(A@truth)
                    observed=noisy_full_projection(clean,noise,noise_seed_for(seed,name,noise))
                    adaptive,tr,adaptive_s=adaptive_order(A,observed,args.size,args.angles,fixed,budget,seed,
                        args.warm_rays,args.batch,args.provisional_iterations,args.candidate_pool,args.feedback_strength)
                    off,_,off_s=adaptive_order(A,observed,args.size,args.angles,fixed,budget,seed,
                        args.warm_rays,args.batch,args.provisional_iterations,args.candidate_pool,0.)
                    swaps[name]=adaptive
                    selections=dict(adaptive_feedback=adaptive,feedback_off_control=off,
                                    voxel_coverage_greedy=fixed[:budget],random=baselines['random'][:budget],
                                    geometry_balanced=baselines['geometry_balanced'][:budget])
                    for state in tr:trace_rows.append(dict(phantom=name,seed=seed,budget=budget,noise_fraction=noise,**state))
                    for comparator,cmpids in [('feedback_off',off),('frozen_greedy',fixed[:budget])]:
                        diverge_rows.append(dict(phantom=name,seed=seed,budget=budget,noise_fraction=noise,
                                                 comparator=comparator,**divergence(adaptive,cmpids,args.warm_rays)))
                    for policy,ids in selections.items():
                        if len(ids)!=budget or len(np.unique(ids))!=budget:raise AssertionError('invalid selection')
                        t=time.perf_counter();sub=A[ids];x=sirt_silent(sub,observed[ids],args.sirt_iterations)
                        solver_s=time.perf_counter()-t
                        err=float(np.sqrt(np.mean((x-truth)**2)))
                        residual=float(np.linalg.norm(sub@x-observed[ids])/max(np.linalg.norm(observed[ids]),1e-12))
                        metrics.append(dict(phantom=name,seed=seed,budget=budget,noise_fraction=noise,policy=policy,
                                            rmse=err,acquired_residual=residual,solver_s=solver_s))
                        orders.append(dict(phantom=name,seed=seed,budget=budget,noise_fraction=noise,policy=policy,
                                           order_hash=hashlib.sha256(ids.astype('<i8').tobytes()).hexdigest(),
                                           selection_s=adaptive_s if policy=='adaptive_feedback' else off_s if policy=='feedback_off_control' else fixed_s if policy=='voxel_coverage_greedy' else 0.,
                                           timing_scope='per_online_run' if policy in ('adaptive_feedback','feedback_off_control') else 'full_max_budget_greedy' if policy=='voxel_coverage_greedy' else 'baseline_not_timed'))
                        print(f'{name:7} seed={seed} budget={budget:4} noise={noise:.3g} {policy:22} rmse={err:.6f}',flush=True)
                for i,name in enumerate(args.phantoms):
                    for other in args.phantoms[i+1:]:
                        swap_rows.append(dict(seed=seed,budget=budget,noise_fraction=noise,phantom_a=name,phantom_b=other,
                                              **divergence(swaps[name],swaps[other],args.warm_rays)))
    for base in ('feedback_off_control','voxel_coverage_greedy','random','geometry_balanced'):
        save_csv(args.output_dir/f'per_case_vs_{base}.csv',paired_per_case(metrics,base))
    for name,rows in [('metrics.csv',metrics),('orders.csv',orders),('adaptive_trace.csv',trace_rows),
                      ('divergence.csv',diverge_rows),('object_swap.csv',swap_rows)]:save_csv(args.output_dir/name,rows)
    groups=defaultdict(list)
    for r in metrics:groups[(r['budget'],r['noise_fraction'],r['policy'])].append(r['rmse'])
    save_csv(args.output_dir/'summary.csv',[dict(budget=b,noise_fraction=n,policy=policy,n=len(v),mean_rmse=float(np.mean(v)),median_rmse=float(np.median(v))) for (b,n,policy),v in sorted(groups.items())])
    for base in ('feedback_off_control','voxel_coverage_greedy','random','geometry_balanced'):
        save_csv(args.output_dir/f'paired_vs_{base}.csv',paired_summary(metrics,base))
    (args.output_dir/'protocol.json').write_text(json.dumps(dict(experiment='04K',
      design='prospective-style additional analytical phantom family validation, not external validation',
      frozen_source='experiment_04j.adaptive_order and experiment_04j.sirt_silent imported without edits',
      parameters={k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()},
      note='04I shell/cross/bands/ribbon were already used for 04J development and are NOT 04K validation objects.',
      limitations=['Four new but handcrafted synthetic phantom families; not patient or measured CT data',
       'Reuse of 04J scoring rule and hyperparameters, but not a preregistered external study',
       'Three seeds/noise levels on four families are correlated repeated measures',
       'Gaussian projection noise rather than Poisson photon counting or realistic system artifacts',
       'Same CPU sparse forward model for both simulation and reconstruction; inverse crime',
       'Selection time includes online provisional reconstructions; baseline ordering times not comparable',
       'No physical dose, clinical efficacy, or hardware feasibility claims']),indent=2),encoding='utf-8')
    print(f'Completed {len(metrics)} reconstructions; results: {args.output_dir}',flush=True)

if __name__=='__main__':main()
