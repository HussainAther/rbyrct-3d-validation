"""07C-P: bounded engineering preflight for prospective 32^3 validation.

NOT an accuracy study. Uses a manufactured positive signal for profiling; never
uses defect truth or defect masks in acquisition. Profiles 1024 rays for all
three selectors and 4096 rays for coverage only. No parameter optimization.
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

from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_05b_04 import select_order
from experiment_05b_gate import AcquiredOnly
from experiment_05b_mart import mart_reconstruct
from experiment_06a import acquire_guarded
from experiment_06b import defect_phantom
from experiment_07b import deterministic_signal, current_rss_bytes, peak_rss_bytes, csr_bytes

SIZE=32
ANGLES=4
SMALL_BUDGET=1024
LARGE_BUDGET=4096
WARM=64
BATCH=32
POOL=16
PROVISIONAL_EPOCHS=2
FINAL_EPOCHS=4
RELAXATION=.25
GUARD_ETA=.05
SEED=707031
POLICIES=('coverage','gradient','guarded_05')


def defect_support(n:int, factor:int, seed:int, *, relative_threshold=.08, absolute_threshold=.01):
    """Evaluation-only mask from the injected defect contrast, not a selector input.

    Reproduce 06B's seeded host + texture draws independently, then compare
    the host-only image against defect_phantom's coarse defective image.
    Rotated Gaussian defects are thus included exactly (up to float rounding).
    A voxel is in the evaluation mask if the positive coarse contrast exceeds
    max(8% of peak contrast, 0.01 intensity units). Constants fixed a priori.
    """
    if n<4 or factor<2 or seed<0:raise ValueError('bad generator arguments')
    rng=np.random.default_rng(seed)
    m=n*factor
    q=(np.arange(m,dtype=float)+.5-m/2)/(m/2)
    z,y,x=np.meshgrid(q,q,q,indexing='ij')
    center=rng.uniform(-.08,.08,3)
    radii=rng.uniform(.69,.86,3)
    radial=((x-center[0])/radii[0])**2+((y-center[1])/radii[1])**2+((z-center[2])/radii[2])**2
    host=np.clip((1.13-radial)/.22,0.,1.)
    texture=1.+.05*np.sin(rng.uniform(2.,5.)*x+rng.uniform(1.,4.)*y)*np.cos(rng.uniform(2.,5.)*z)
    base=np.maximum(.04+.64*host*texture,.005)
    base_coarse=base.reshape(n,factor,n,factor,n,factor).mean(axis=(1,3,5)).ravel()
    defective,_,desc=defect_phantom(n,factor,seed)
    delta=np.maximum(base_coarse-defective,0.)
    cutoff=max(absolute_threshold,relative_threshold*float(delta.max()))
    mask=delta>=cutoff
    if not 0<mask.sum()<mask.size:raise RuntimeError('evaluation mask empty or entire grid')
    return mask, dict(seed=seed,n=n,factor=factor,n_defects=desc['n_defects'],
       mask_voxels=int(mask.sum()),fraction=float(mask.mean()),
       peak_defect_contrast=float(delta.max()),contrast_cutoff=float(cutoff),
       mask_sha256=hashlib.sha256(mask.astype(np.uint8).tobytes()).hexdigest(),
       definition='positive coarse counterfactual host minus defective truth >= max(0.01, 0.08 * maximum defect contrast)',
       evaluation_only=True)


def error_metrics(estimate,truth,mask):
    """Pure evaluation helper, never used for acquisition selection."""
    estimate=np.asarray(estimate,dtype=float).reshape(-1)
    truth=np.asarray(truth,dtype=float).reshape(-1)
    mask=np.asarray(mask,dtype=bool).reshape(-1)
    if estimate.shape!=truth.shape or mask.shape!=truth.shape or not (0<mask.sum()<mask.size):
        raise ValueError('bad truth/estimate/mask dimensions')
    if not np.isfinite(estimate).all() or not np.isfinite(truth).all():raise ValueError('nonfinite estimate or truth')
    sq=(estimate-truth)**2
    return dict(global_rmse=float(np.sqrt(sq.mean())),
                defect_region_rmse=float(np.sqrt(sq[mask].mean())),
                nondefect_rmse=float(np.sqrt(sq[~mask].mean())))


def verify_config(n, angles, small_budget, large_budget, warm, batch, pool, provisional_epochs,
                  final_epochs,relaxation,eta,seed,allow_test_scale):
    prod=(n,angles,small_budget,large_budget,warm,batch,pool,provisional_epochs,
          final_epochs,relaxation,eta,seed)
    ref=(SIZE,ANGLES,SMALL_BUDGET,LARGE_BUDGET,WARM,BATCH,POOL,PROVISIONAL_EPOCHS,
         FINAL_EPOCHS,RELAXATION,GUARD_ETA,SEED)
    if not allow_test_scale and prod!=ref:raise ValueError('production 07C preflight configuration fixed')
    if not (4<=n<=SIZE and angles>=2 and 0<warm<small_budget<=large_budget<=n*n*angles*len(TILTS)
            and (small_budget-warm)%batch==0 and (large_budget-warm)%batch==0
            and min(batch,pool,provisional_epochs,final_epochs)>=1 and 0<relaxation<=1
            and eta==GUARD_ETA and seed>=0):raise ValueError('invalid preflight configuration')


def _write_csv(path,rows):
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def run(output_dir, *, n=SIZE,angles=ANGLES,small_budget=SMALL_BUDGET,
        large_budget=LARGE_BUDGET,warm=WARM,batch=BATCH,pool=POOL,
        provisional_epochs=PROVISIONAL_EPOCHS,final_epochs=FINAL_EPOCHS,
        relaxation=RELAXATION,eta=GUARD_ETA,seed=SEED,allow_test_scale=False):
    verify_config(n,angles,small_budget,large_budget,warm,batch,pool,provisional_epochs,
                  final_epochs,relaxation,eta,seed,allow_test_scale)
    out=Path(output_dir)
    if out.exists() and any(out.iterdir()):raise ValueError('refusing overwrite of nonempty directory')
    out.mkdir(parents=True,exist_ok=True)
    protocol=dict(stage='07C engineering preflight ONLY',size=n,angles=angles,
         small_budget=small_budget,large_budget=large_budget,warm=warm,batch=batch,pool=pool,
         provisional_epochs=provisional_epochs,final_epochs=final_epochs,
         relaxation=relaxation,guard_eta=eta,seed=seed,tilts=list(map(float,TILTS)),
         small_budget_policies=list(POLICIES),large_budget_policies=['coverage'],
         no_accuracy_comparison=True,mask_evaluation_only=True,
         caveat='Timing/memory for engineering feasibility only; not held-out 32^3 result',
         test_scale=allow_test_scale)
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n',encoding='utf-8')
    before,src=current_rss_bytes();peakbefore,peaks=peak_rss_bytes()
    t=time.perf_counter();A=system_matrix(n,angles,TILTS).tocsr();build_s=time.perf_counter()-t
    if A.shape!=(n*n*angles*len(TILTS),n**3) or A.nnz<1 or (A.data<0).any():
        raise RuntimeError('invalid sparse geometry')
    after,_=current_rss_bytes();peakafter,_=peak_rss_bytes()
    truth=deterministic_signal(n)
    measured=np.asarray(A@truth).ravel()
    t=time.perf_counter()
    coverage_order=np.asarray(voxel_coverage_order(A,n,angles,len(TILTS),large_budget,seed,pool),dtype=np.int64)
    coverage_order_time=time.perf_counter()-t
    if len(np.unique(coverage_order))!=large_budget:raise RuntimeError('coverage duplicate rays')
    runs=[]
    for policy in POLICIES:
        oracle=AcquiredOnly(measured);oracle.commit(coverage_order[:warm])
        if policy=='coverage':
            t=time.perf_counter();order=coverage_order[:small_budget].copy();select_time=time.perf_counter()-t
            oracle.commit(order[warm:])
            trace=[]
        elif policy=='gradient':
            order,trace,select_time=select_order(A,oracle,n,angles,coverage_order,small_budget,seed,
                policy='gradient',warm_rays=warm,batch=batch,candidate_pool=pool,
                provisional_epochs=provisional_epochs,relaxation=relaxation)
        else:
            order,trace,select_time=acquire_guarded(A,oracle,n,angles,coverage_order,small_budget,seed,
                eta=eta,warm_rays=warm,batch=batch,candidate_pool=pool,
                provisional_epochs=provisional_epochs,relaxation=relaxation)
        order=np.asarray(order,dtype=np.int64)
        if len(order)!=small_budget or len(set(map(int,order)))!=small_budget or oracle.allowed!=set(map(int,order)):
            raise RuntimeError('acquired-only check failed')
        t=time.perf_counter();x=mart_reconstruct(A[order],measured[order],final_epochs,relaxation=relaxation)
        reconstruct_time=time.perf_counter()-t
        if not np.isfinite(x).all() or (x<=0).any():raise RuntimeError('invalid MART output')
        peak,_=peak_rss_bytes();rss,_=current_rss_bytes()
        runs.append(dict(budget=small_budget,policy=policy,coverage_order_time_s=coverage_order_time,
            adaptive_selection_s=select_time,total_selection_s=coverage_order_time+select_time,
            final_mart_s=reconstruct_time,unique_rays=len(order),audit_batches=len(trace),
            ray_sha256=hashlib.sha256(order.astype('<i8').tobytes()).hexdigest(),
            rss_after_bytes=rss,peak_so_far_bytes=peak,acquired_only_pass=True))
        print(f'{policy:12s} rays={small_budget} select={coverage_order_time+select_time:.2f}s MART={reconstruct_time:.2f}s',flush=True)
    # Stress the large ray budget under coverage selection only; this is NOT an
    # adaptive extrapolation nor a claim that full adaptive 4096-ray run is feasible.
    long_order=coverage_order[:large_budget]
    oracle=AcquiredOnly(measured);oracle.commit(long_order)
    t=time.perf_counter();x=mart_reconstruct(A[long_order],oracle[long_order],final_epochs,relaxation=relaxation)
    long_mart_s=time.perf_counter()-t
    if not np.isfinite(x).all() or (x<=0).any():raise RuntimeError('invalid long-budget MART')
    rss,_=current_rss_bytes();peak,_=peak_rss_bytes()
    runs.append(dict(budget=large_budget,policy='coverage',coverage_order_time_s=coverage_order_time,
        adaptive_selection_s=0.,total_selection_s=coverage_order_time,final_mart_s=long_mart_s,
        unique_rays=large_budget,audit_batches=0,
        ray_sha256=hashlib.sha256(long_order.astype('<i8').tobytes()).hexdigest(),
        rss_after_bytes=rss,peak_so_far_bytes=peak,acquired_only_pass=True))
    # Independently define mask for FUTURE evaluation. Do not compute any
    # competing-policy errors on defect phantoms in this preflight.
    _,mask_info=defect_support(n,2,707001)
    memory=dict(rss_before_matrix_bytes=before,rss_after_matrix_bytes=after,
          process_peak_before_matrix_bytes=peakbefore,process_peak_after_matrix_bytes=peakafter,
          process_peak_final_bytes=peak_rss_bytes()[0],rss_source=src,peak_source=peaks)
    profile=dict(size=n,voxels=n**3,candidate_rays=A.shape[0],nnz=int(A.nnz),
          csr_storage_bytes=csr_bytes(A),matrix_build_s=build_s,
          coverage_order_time_s=coverage_order_time,
          max_profiled_adaptive_budget=small_budget,max_profiled_coverage_budget=large_budget,
          adaptive_4096_budget_measured=False,**memory)
    (out/'profile.json').write_text(json.dumps(profile,indent=2)+'\n',encoding='utf-8')
    (out/'defect_metric_definition.json').write_text(json.dumps(mask_info,indent=2)+'\n',encoding='utf-8')
    _write_csv(out/'policy_timing.csv',runs)
    (out/'environment.json').write_text(json.dumps(dict(python=sys.version,platform=platform.platform(),
         numpy=np.__version__),indent=2)+'\n',encoding='utf-8')
    return profile,runs,mask_info


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args()
    profile,runs,mask=run(args.output_dir)
    print(json.dumps(dict(profile=profile,mask=mask,policy_runs=len(runs)),indent=2))

if __name__=='__main__':main()
