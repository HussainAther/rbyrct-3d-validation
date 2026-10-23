"""04M: frozen 04J adaptive selection under high-resolution forward-model mismatch.

The coarse 04B CSR operator handles reconstruction/selection. Measurements
come from a separate fine-grid Siddon integration, optionally with deterministic
ray origins shifted in detector coordinates. This remains synthetic modeling.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, time
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy import sparse
from experiment_04b import system_matrix, trace_ray
from experiment_04g import TILTS, policies
from experiment_04h import voxel_coverage_order, coverage
from experiment_04i import noisy_full_projection
from experiment_04j import adaptive_order, sirt_silent, divergence
from experiment_04k import new_phantoms, noise_seed_for

POLICY_NAMES=('adaptive_feedback','feedback_off_control','voxel_coverage_greedy','random','geometry_balanced')


def high_resolution_matrix(n, angles, tilts, factor=2, offset=0.0):
    """Same physical ray labels as 04B, but integrate through fine voxels.

    offset is detector-plane displacement in COARSE voxel units, with fixed
    signed variations by view/detector index. Nonzero offsets simulate a
    systematic unmodeled geometric calibration perturbation, not randomness.
    Fine path lengths are converted back to coarse voxel physical units.
    """
    if factor < 2 or n < 4 or angles < 2 or offset < 0:
        raise ValueError('invalid independent simulator configuration')
    fine=n*factor
    rows=[];cols=[];vals=[];ray=0
    dc=np.arange(n,dtype=float)+0.5-n/2
    for t,tilt in enumerate(tilts):
        elev=np.deg2rad(tilt)
        for a,theta in enumerate(np.linspace(0,np.pi,angles,endpoint=False)):
            u=np.array([np.cos(theta),np.sin(theta),0.])
            direction=np.array([-np.sin(theta)*np.cos(elev),np.cos(theta)*np.cos(elev),np.sin(elev)])
            v=np.cross(u,direction)
            for j,dv in enumerate(dc):
                for i,du in enumerate(dc):
                    # Fixed geometry distortion: 0 at offset=0; never shared
                    # with the coarse reconstruction or selector model.
                    shift_u=offset*np.sin(0.83*a+0.47*t+0.19*i+0.31*j)
                    shift_v=offset*np.cos(0.61*a-0.29*t+0.37*i-0.23*j)
                    origin=(du+shift_u)*u+(dv+shift_v)*v
                    ids,lengths=trace_ray(origin*factor,direction,fine)
                    rows.extend([ray]*len(ids));cols.extend(ids)
                    vals.extend(np.asarray(lengths)/factor)
                    ray+=1
    return sparse.coo_matrix((vals,(rows,cols)),shape=(ray,fine**3),dtype=np.float64).tocsr()


def downsample_average(vol,factor):
    n=vol.shape[0]//factor
    if vol.shape != (n*factor,)*3:raise ValueError('fine volume incompatible with factor')
    return vol.reshape(n,factor,n,factor,n,factor).mean(axis=(1,3,5))


def write_csv(path, rows):
    if not rows:return
    with Path(path).open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def paired_cases(rows, comparator):
    cases=defaultdict(dict)
    for r in rows:
        key=(r['stage'],r['phantom'],r['seed'],r['budget'],r['noise_fraction'])
        if r['policy'] in cases[key]:raise ValueError('duplicate case')
        cases[key][r['policy']]=r['rmse']
    out=[]
    for key,d in sorted(cases.items()):
        if 'adaptive_feedback' not in d or comparator not in d:continue
        a=float(d['adaptive_feedback']); b=float(d[comparator])
        out.append(dict(stage=key[0],phantom=key[1],seed=key[2],budget=key[3],noise_fraction=key[4],
                        comparator=comparator,adaptive_rmse=a,comparator_rmse=b,
                        relative_gain=(b-a)/max(b,1e-12),win=int(a<b)))
    return out


def summarize_pairs(rows):
    groups=defaultdict(list)
    for r in rows:groups[(r['stage'],r['budget'],r['comparator'])].append(r['relative_gain'])
    return [dict(stage=s,budget=b,comparator=c,n=len(v),wins=sum(x>0 for x in v),
                 mean_relative_gain=float(np.mean(v)),median_relative_gain=float(np.median(v)))
            for (s,b,c),v in sorted(groups.items())]


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--size',type=int,default=16);p.add_argument('--angles',type=int,default=12)
    p.add_argument('--factor',type=int,default=2)
    p.add_argument('--stages',nargs='+',choices=['matched','fine','fine_offset'],default=['matched','fine','fine_offset'])
    p.add_argument('--geometry-offset',type=float,default=0.15)
    p.add_argument('--budgets',nargs='+',type=int,default=[512,1024,2048])
    p.add_argument('--seeds',nargs='+',type=int,default=[104729,130363,155921])
    p.add_argument('--phantoms',nargs='+',default=['torus','slats','beads','wedges'])
    p.add_argument('--noise-fractions',nargs='+',type=float,default=[0.,0.01])
    p.add_argument('--warm-rays',type=int,default=128);p.add_argument('--batch',type=int,default=64)
    p.add_argument('--provisional-iterations',type=int,default=60)
    p.add_argument('--sirt-iterations',type=int,default=400)
    p.add_argument('--candidate-pool',type=int,default=64)
    p.add_argument('--output-dir',type=Path,default=Path('results/experiment04m'))
    a=p.parse_args(argv)
    available=len(TILTS)*a.angles*a.size*a.size
    if (a.size<4 or a.angles<2 or a.factor<2 or a.geometry_offset<0 or not a.budgets or not a.seeds or not a.phantoms
        or not a.noise_fractions or min(a.noise_fractions)<0 or min(a.budgets)<=a.warm_rays
        or max(a.budgets)>available or a.warm_rays<1 or a.batch<1 or a.provisional_iterations<1
        or a.sirt_iterations<1 or a.candidate_pool<1):p.error('invalid 04M configuration')
    if any(q not in new_phantoms(a.size) for q in a.phantoms):p.error('unknown phantom')
    a.output_dir.mkdir(parents=True,exist_ok=True)
    t=time.perf_counter();coarse=system_matrix(a.size,a.angles,TILTS).tocsr()
    fine_matrices={}
    for stage in a.stages:
        if stage!='matched':
            ts=time.perf_counter()
            fine_matrices[stage]=high_resolution_matrix(a.size,a.angles,TILTS,a.factor,a.geometry_offset if stage=='fine_offset' else 0.)
            print(f'{stage} fine operator nnz={fine_matrices[stage].nnz} built_s={time.perf_counter()-ts:.2f}',flush=True)
    print(f'04M inverse-crime mismatch experiment: coarse={coarse.shape} build_s={time.perf_counter()-t:.2f}',flush=True)
    phantoms_fine=new_phantoms(a.size*a.factor)
    truth={name:downsample_average(phantoms_fine[name],a.factor).ravel() for name in a.phantoms}
    # Stage A uses *same* resolution truth projected with matched model; stage B/C
    # project fine truth and evaluate against its coarse block-average.
    metrics=[];pairs=[];diagnostics=[];divergences=[];timing=[]
    max_budget=max(a.budgets)
    for seed in a.seeds:
        ts=time.perf_counter()
        fixed=voxel_coverage_order(coarse,a.size,a.angles,len(TILTS),max_budget,seed,a.candidate_pool)
        fixed_s=time.perf_counter()-ts
        baseline=policies(a.size,a.angles,len(TILTS),seed)
        for stage in a.stages:
            for name in a.phantoms:
                ref=truth[name]
                if stage=='matched':clean=np.asarray(coarse@ref).ravel()
                else:clean=np.asarray(fine_matrices[stage]@phantoms_fine[name].ravel()).ravel()
                predicted=np.asarray(coarse@ref).ravel()
                relative_mismatch=float(np.linalg.norm(clean-predicted)/max(np.linalg.norm(predicted),1e-12))
                diagnostics.append(dict(stage=stage,phantom=name,seed=seed,relative_projection_mismatch=relative_mismatch,
                                        projection_rmse=float(np.sqrt(np.mean((clean-predicted)**2)))))
                for noise in sorted(set(a.noise_fractions)):
                    observed=noisy_full_projection(clean,noise,noise_seed_for(seed,name,noise))
                    for budget in sorted(set(a.budgets)):
                        ids,trace,sel_s=adaptive_order(coarse,observed,a.size,a.angles,fixed,budget,seed,
                            a.warm_rays,a.batch,a.provisional_iterations,a.candidate_pool,1.0)
                        off,_,off_s=adaptive_order(coarse,observed,a.size,a.angles,fixed,budget,seed,
                            a.warm_rays,a.batch,a.provisional_iterations,a.candidate_pool,0.0)
                        div=divergence(ids,off,a.warm_rays)
                        divergences.append(dict(stage=stage,phantom=name,seed=seed,budget=budget,noise_fraction=noise,**div))
                        selections={'adaptive_feedback':ids,'feedback_off_control':off,
                            'voxel_coverage_greedy':fixed[:budget],
                            'random':baseline['random'][:budget],
                            'geometry_balanced':baseline['geometry_balanced'][:budget]}
                        for policy,chosen in selections.items():
                            if len(np.unique(chosen))!=budget:raise AssertionError('duplicate ray IDs')
                            ts=time.perf_counter();sub=coarse[chosen]
                            x=sirt_silent(sub,observed[chosen],a.sirt_iterations)
                            recon_s=time.perf_counter()-ts
                            rmse=float(np.sqrt(np.mean((x-ref)**2)))
                            metrics.append(dict(stage=stage,phantom=name,seed=seed,budget=budget,noise_fraction=noise,
                                policy=policy,rmse=rmse,relative_projection_mismatch=relative_mismatch,solver_s=recon_s))
                            timing.append(dict(stage=stage,phantom=name,seed=seed,budget=budget,noise_fraction=noise,
                                policy=policy,selection_s=sel_s if policy=='adaptive_feedback' else off_s if policy=='feedback_off_control' else fixed_s if policy=='voxel_coverage_greedy' else 0.,
                                solver_s=recon_s,scope='online per case' if policy in ('adaptive_feedback','feedback_off_control') else 'full max-budget geometry order' if policy=='voxel_coverage_greedy' else 'baseline ordering not timed'))
                            print(f'{stage:11} {name:7} seed={seed} b={budget:4} noise={noise:.3g} {policy:22} rmse={rmse:.6f}',flush=True)
    for cmp in ('feedback_off_control','voxel_coverage_greedy','random','geometry_balanced'):
        pairs+=paired_cases(metrics,cmp)
    write_csv(a.output_dir/'metrics.csv',metrics)
    write_csv(a.output_dir/'paired_cases.csv',pairs)
    write_csv(a.output_dir/'paired_summary.csv',summarize_pairs(pairs))
    write_csv(a.output_dir/'mismatch_diagnostics.csv',diagnostics)
    write_csv(a.output_dir/'divergence.csv',divergences)
    write_csv(a.output_dir/'selection_timing.csv',timing)
    (a.output_dir/'protocol.json').write_text(json.dumps(dict(experiment='04M',parameters={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},
        frozen_selector='experiment_04j.adaptive_order imported without edits',
        matched_stage='Both projection and reconstruction use the coarse 04B matrix; same block-averaged fine reference',
        fine_stage='High-resolution analytic phantom sampled on fine grid and projected using fine ray traversal, coarse-grid reconstruction',
        fine_offset_stage='Fine projector plus fixed detector-plane ray-origin perturbations hidden from reconstruction model',
        limitations=['Synthetic fine-grid Siddon physics still shares underlying parallel-ray assumptions with coarse model',
        'Not a physically independent simulator or actual CT measurement','Matched stage truth is coarse block-averaged fine phantom and differs from original 04K coarse-defined truth',
        'No hardware feasibility or dose claim','Fixed Gaussian noise defined using full fine sinogram RMS','Repeated seed and noise combinations are correlated']),indent=2),encoding='utf-8')
    print(f'Completed {len(metrics)} reconstructions; results: {a.output_dir}',flush=True)

if __name__=='__main__':main()
