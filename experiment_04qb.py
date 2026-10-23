"""04Q-B: frozen-policy cross-projector 3D synthetic tomography benchmark.

Measurements: independently implemented 04Q-A trilinear ray marching.
Reconstruction + selectors: exactly the coarse Siddon and frozen 04P methods.
This is numerical-model cross-validation, not physical CT/dose validation.
"""
from __future__ import annotations
import argparse,csv,json,hashlib,time
from pathlib import Path
from collections import defaultdict
import numpy as np
from experiment_04b import system_matrix
from experiment_04g import TILTS,policies
from experiment_04h import voxel_coverage_order
from experiment_04i import noisy_full_projection
from experiment_04j import adaptive_order,sirt_silent
from experiment_04m import high_resolution_matrix,downsample_average
from experiment_04n import replicate_coarse
from experiment_04oc import online_order
from experiment_04qa import project, discrepancy

FAMILIES=('branches','layers','pores','defects')
POLICIES=('adaptive_feedback','feedback_off_control','geometry_balanced','voxel_coverage_greedy','reliability_gate')

def phantoms(n):
    """Deterministic analytic families not present in 04K--04O."""
    q=(np.arange(n,dtype=float)+.5-n/2)/(n/2)
    z,y,x=np.meshgrid(q,q,q,indexing='ij')
    # Union of tapered oblique tubes, with junction near the origin.
    d1=(y-.18*z)**2+(x+.22*z)**2
    d2=(x-.40*y-.12)**2+(z+.32*y)**2
    d3=(y+.30*x+.18)**2+(z-.45*x+.12)**2
    branches=.025+.58*(d1<(.11+.08*(z+1)/2)**2)+.34*(d2<.115**2)+.23*(d3<.085**2)
    # Disjoint curved concentric shells with angular modulation.
    r=np.sqrt(x*x+y*y+z*z)
    wav=.035*np.sin(5*np.arctan2(y,x)+2.3*z)
    layers=.025+.55*(np.abs(r-(.63+wav))<.085)+.24*(np.abs(r-(.35-.04*z))<.065)
    # Non-periodic spherical pores punched from a large host solid.
    solid=(x*x/.76**2+y*y/.65**2+z*z/.71**2)<1
    holes=np.zeros_like(x,dtype=bool)
    for px,py,pz,rad in [(-.38,-.10,.02,.13),(.22,.32,-.14,.09),(.29,-.22,.31,.11),(-.10,.15,.39,.07),(-.31,.30,-.30,.09),(.05,-.33,-.25,.08)]:
        holes|=((x-px)**2+(y-py)**2+(z-pz)**2<rad*rad)
    pores=.025+.57*(solid & ~holes)
    # Large host with a narrow internal oblique crack plus localized void.
    host=(x*x/.79**2+y*y/.72**2+z*z/.67**2)<1
    crack=(np.abs(x+.42*y-.31*z-.08)<.042)&(y>-.52)&(y<.55)&(z>-.54)&(z<.55)
    pit=(x-.26)**2+(y+.18)**2+(z-.16)**2<.105**2
    defects=.025+.53*(host & ~crack & ~pit)
    return {k:np.asarray(v,dtype=np.float64) for k,v in locals().copy().items() if k in FAMILIES}

def object_pair(name,n,factor):
    if name not in FAMILIES or factor<2:raise ValueError('invalid family/factor')
    coarse=phantoms(n)[name]
    fine=phantoms(n*factor)[name]
    return {'replicated':(coarse.ravel(),replicate_coarse(coarse,factor).ravel()),
            'subvoxel':(downsample_average(fine,factor).ravel(),fine.ravel())}

def rows_csv(path,records):
    if not records:return
    with open(path,'w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)

def paired_results(metrics):
    groups=defaultdict(dict)
    keys=('object_type','offset','phantom','seed','budget','noise_fraction')
    for r in metrics:
        k=tuple(r[x] for x in keys)
        if r['policy'] in groups[k]:raise ValueError('duplicate policy result')
        groups[k][r['policy']]=float(r['rmse'])
    pairs=[]
    for k,v in sorted(groups.items()):
        if set(v)!=set(POLICIES):raise ValueError(f'missing policies: {k}')
        for p in POLICIES:
            if p=='feedback_off_control':continue
            base=v['feedback_off_control'];val=v[p]
            pairs.append(dict(zip(keys,k),policy=p,rmse=val,feedback_off_rmse=base,
                relative_gain=(base-val)/max(base,1e-12),win=int(val<base)))
    summary=[]
    grouped=defaultdict(list)
    for r in pairs:grouped[(r['object_type'],r['offset'],r['budget'],r['noise_fraction'],r['policy'])].append(r['relative_gain'])
    for k,vals in sorted(grouped.items()):
        summary.append(dict(zip(('object_type','offset','budget','noise_fraction','policy'),k),n=len(vals),wins=sum(v>0 for v in vals),mean_gain=float(np.mean(vals)),median_gain=float(np.median(vals))))
    return pairs,summary

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--size',type=int,default=16);p.add_argument('--angles',type=int,default=12);p.add_argument('--factor',type=int,default=2)
    p.add_argument('--phantoms',nargs='+',choices=FAMILIES,default=list(FAMILIES))
    p.add_argument('--object-types',nargs='+',choices=['replicated','subvoxel'],default=['replicated','subvoxel'])
    p.add_argument('--offsets',nargs='+',type=float,default=[0.,.15])
    p.add_argument('--budgets',nargs='+',type=int,default=[1024,2048])
    p.add_argument('--seeds',nargs='+',type=int,default=[271828,314159,577215])
    p.add_argument('--noise-fractions',nargs='+',type=float,default=[0.])
    p.add_argument('--warm-rays',type=int,default=128);p.add_argument('--batch',type=int,default=64)
    p.add_argument('--provisional-iterations',type=int,default=60);p.add_argument('--diagnostic-iterations',type=int,default=60)
    p.add_argument('--sirt-iterations',type=int,default=400);p.add_argument('--candidate-pool',type=int,default=64)
    p.add_argument('--threshold',type=float,default=2.0);p.add_argument('--gate-strength',type=float,default=0.)
    p.add_argument('--diagnostic-every',type=int,default=256);p.add_argument('--holdout-fraction',type=float,default=.2)
    p.add_argument('--step',type=float,default=0.25,help='ray marching integration step in coarse voxel units')
    p.add_argument('--output-dir',type=Path,default=Path('results/experiment04qb'))
    a=p.parse_args(argv)
    n_rays=a.size*a.size*a.angles*len(TILTS)
    if (not np.isfinite(a.step) or a.step<=0 or a.step>1 or a.size<4 or a.angles<2 or a.factor<2 or a.warm_rays<12 or a.batch<1 or a.candidate_pool<1
        or a.provisional_iterations<1 or a.diagnostic_iterations<1 or a.sirt_iterations<1 or a.diagnostic_every<1
        or a.threshold<=0 or not 0<a.holdout_fraction<.5 or not 0<=a.gate_strength<=1
        or not a.budgets or min(a.budgets)<=a.warm_rays or max(a.budgets)>n_rays or not a.seeds
        or not a.phantoms or not a.object_types or not a.offsets or min(a.offsets)<0
        or not a.noise_fractions or min(a.noise_fractions)<0):p.error('invalid 04P configuration')
    a.output_dir.mkdir(parents=True,exist_ok=True)
    A=system_matrix(a.size,a.angles,TILTS).tocsr()
    fine_ops={offset:high_resolution_matrix(a.size,a.angles,TILTS,a.factor,offset) for offset in sorted(set(a.offsets))}
    objects={name:object_pair(name,a.size,a.factor) for name in a.phantoms}
    baseline={seed:policies(a.size,a.angles,len(TILTS),seed) for seed in a.seeds}
    warm={seed:voxel_coverage_order(A,a.size,a.angles,len(TILTS),max(a.budgets),seed,a.candidate_pool) for seed in a.seeds}
    metrics=[];gates=[];timings=[];mismatches=[]
    for name in a.phantoms:
      for typ in a.object_types:
       truth,fine=objects[name][typ]
       for offset,M in fine_ops.items():
        # The new projector generates EVERY measurement. 04M Siddon fine projector
        # is computed only for offline diagnostic comparison, never fed to selectors.
        clean=project(fine.reshape((a.size*a.factor,)*3),a.size,a.angles,TILTS,
                      factor=a.factor,offset=offset,step=a.step,mode='linear')
        ideal=np.asarray(A@truth).ravel()
        fine_siddon=np.asarray(M@fine).ravel()
        mismatch=discrepancy(clean,ideal)['relative_l2']
        siddon_mismatch=discrepancy(clean,fine_siddon)['relative_l2']
        if len(clean)!=A.shape[0] or not np.isfinite(clean).all():raise AssertionError('invalid independent projections')
        mismatches.append(dict(phantom=name,object_type=typ,offset=offset,
            relative_projection_mismatch=mismatch,relative_projector_disagreement=siddon_mismatch,
            step_coarse=a.step))
        for seed in a.seeds:
         for noise in a.noise_fractions:
          noise_seed=(seed+int(hashlib.sha256(f'{name}:{noise:.12g}'.encode()).hexdigest()[:8],16))%(2**32)
          obs=noisy_full_projection(clean,noise,noise_seed)
          for budget in sorted(set(a.budgets)):
           # Frozen 04J, frozen geometric baselines, frozen 04O-C gate.
           t=time.perf_counter()
           adap,_,_=adaptive_order(A,obs,a.size,a.angles,warm[seed],budget,seed,a.warm_rays,a.batch,a.provisional_iterations,a.candidate_pool,1.)
           ada_s=time.perf_counter()-t
           t=time.perf_counter()
           off,_,_=adaptive_order(A,obs,a.size,a.angles,warm[seed],budget,seed,a.warm_rays,a.batch,a.provisional_iterations,a.candidate_pool,0.)
           off_s=time.perf_counter()-t
           gate,trace,gate_s=online_order(A,obs,a.size,a.angles,warm[seed],budget,seed,
              warm_rays=a.warm_rays,batch=a.batch,provisional_iterations=a.provisional_iterations,
              diagnostic_iterations=a.diagnostic_iterations,candidate_pool=a.candidate_pool,
              holdout_fraction=a.holdout_fraction,threshold=a.threshold,gate_strength=a.gate_strength,
              diagnostic_every=a.diagnostic_every)
           selections={'adaptive_feedback':adap,'feedback_off_control':off,
              'geometry_balanced':baseline[seed]['geometry_balanced'][:budget],
              'voxel_coverage_greedy':warm[seed][:budget],'reliability_gate':gate}
           base_meta=dict(phantom=name,object_type=typ,offset=offset,seed=seed,budget=budget,noise_fraction=noise)
           for decision in trace:gates.append(dict(**base_meta,**decision))
           for policy,ids in selections.items():
            if len(ids)!=budget or len(set(map(int,ids)))!=budget:raise AssertionError('invalid ray order')
            start=time.perf_counter();x=sirt_silent(A[ids],obs[ids],a.sirt_iterations);rec_s=time.perf_counter()-start
            rmse=float(np.sqrt(np.mean((x-truth)**2)))
            metrics.append(dict(**base_meta,policy=policy,rmse=rmse,relative_projection_mismatch=mismatch))
            sel_s={'adaptive_feedback':ada_s,'feedback_off_control':off_s,'reliability_gate':gate_s}.get(policy,float('nan'))
            timings.append(dict(**base_meta,policy=policy,selection_s=sel_s,reconstruction_s=rec_s))
            print(f'04Q-B {name:8s} {typ:10s} offset={offset:g} seed={seed} b={budget} {policy:22s} RMSE={rmse:.6f}',flush=True)
    paired,summary=paired_results(metrics)
    for name,records in [('metrics.csv',metrics),('paired_cases.csv',paired),('paired_summary.csv',summary),
                         ('gate_trace.csv',gates),('timing.csv',timings),('mismatch_diagnostics.csv',mismatches)]:
        rows_csv(a.output_dir/name,records)
    protocol={'experiment':'04Q-B','design':'cross-projector frozen-policy confirmation',
      'parameters':{k:(str(v) if isinstance(v,Path) else v) for k,v in vars(a).items()},
      'measurement_generator':'04Q-A independent trilinear ray marching, midpoint integration',
      'reconstructor':'04B coarse Siddon-like operator with 04J frozen SIRT',
      'selectors':['04J full and feedback-off frozen','04G geometry baseline frozen','04H coverage baseline frozen','04O-C gate threshold=2 frozen'],
      'limitations':['Different numerical integration and interpolation, but not independent physical CT',
       'Fine Siddon projector used for offline diagnostics only','Seeds and offsets repeated within phantom family are not independent phantoms',
       'No physical detector/dose/clinical claims','No threshold optimization on these results',
       'Noise fraction is an existing synthetic perturbation model']}
    (a.output_dir/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf8')
    ncase=len(metrics)//len(POLICIES)
    print(f'04Q-B complete: {ncase} matched cases; {len(metrics)} reconstructions; output={a.output_dir}',flush=True)

if __name__=='__main__':main()
