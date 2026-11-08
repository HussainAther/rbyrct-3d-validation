"""RBYRCT-06B: frozen prospective synthetic localized-defect 12^3 study.

Development-selected policy: 06A 5% guard, compared against coverage and
unconstrained gradient. The design must remain frozen after examining results.
No physical CT / dose / clinical generalization claims.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_04qa import project
from experiment_05b_04 import select_order
from experiment_05b_08b import nonnegative_noisy_measurements
from experiment_05b_gate import AcquiredOnly
from experiment_05b_mart import mart_reconstruct
from experiment_06a import acquire_guarded
from experiment_05b_11_stage2 import _env_data, _sha256, _write_csv, order_sha256

SIZE = 12
ANGLES = 4
FACTOR = 2
BUDGET = 576
CHECKPOINTS = (144, 288, 576)
PRIMARY = 288
WARM = 36
BATCH = 12
POOL = 24
PROVISIONAL_EPOCHS = 4
FINAL_EPOCHS = 16
RELAXATION = .25
ETA = .05
POLICIES = ('coverage', 'gradient', 'guarded_05')
MODELS = ('same', 'independent')
ACQUISITION_SEEDS = (104729, 130363)
OBJECT_SEEDS = tuple(1066001 + 7919*i for i in range(8))
NOISE_FRACTION = .005
OFFSET = .15
STEP = .25
THRESHOLD = .10


def defect_phantom(n: int, factor: int, seed: int):
    """Parameterized, unseen-by-development 3D localized-defect generator.

    Positive ellipsoidal host with mild 3D texture and 2-4 local attenuative
    Gaussian defects (ellipsoidal, heterogeneous). Not a clinical CT phantom.
    Different seeds alter host position/radii, texture, defect count/shape,
    location, severity and orientation. All parameters determined by seed.
    """
    if n < 4 or factor < 2 or seed < 0:
        raise ValueError('invalid defect generator inputs')
    rng = np.random.default_rng(seed)
    m = n*factor
    q = (np.arange(m, dtype=float) + .5 - m/2)/(m/2)
    z, y, x = np.meshgrid(q, q, q, indexing='ij')
    center = rng.uniform(-.08, .08, 3)
    radii = rng.uniform(.69, .86, 3)
    radial = ((x-center[0])/radii[0])**2 + ((y-center[1])/radii[1])**2 + ((z-center[2])/radii[2])**2
    host = np.clip((1.13-radial)/.22, 0., 1.)
    texture = 1. + .05*np.sin(rng.uniform(2.,5.)*x + rng.uniform(1.,4.)*y) * np.cos(rng.uniform(2.,5.)*z)
    image = .04 + .64*host*texture
    n_defects = int(rng.integers(2, 5))
    descriptors = []
    for k in range(n_defects):
        pos = rng.uniform(-.38,.38,3)
        widths = rng.uniform(.075,.19,3)
        amplitude = float(rng.uniform(.28,.52))
        # Randomly rotate anisotropic defect axes; avoids axis-aligned-only structures.
        Q, _ = np.linalg.qr(rng.normal(size=(3,3)))
        disp = np.stack([x-pos[0],y-pos[1],z-pos[2]],axis=-1)
        rotated = disp @ Q
        d2 = np.sum((rotated/widths)**2,axis=-1)
        image -= amplitude*np.exp(-1.4*d2)*host
        descriptors.append(dict(center=[float(v) for v in pos],
                                widths=[float(v) for v in widths],
                                amplitude=amplitude))
    image = np.maximum(image,.005)
    coarse = image.reshape(n,factor,n,factor,n,factor).mean(axis=(1,3,5))
    return coarse.ravel(), image, dict(n_defects=n_defects, defects=descriptors,
        host_center=[float(v) for v in center], host_radii=[float(v) for v in radii])


def validate(*, size, angles, factor, budget, checkpoints, warm_rays, batch,
             pool, provisional_epochs, final_epochs, relaxation, eta,
             object_seeds, acquisition_seeds, models, noise_fraction, offset, step,
             allow_test_scale=False):
    if not allow_test_scale and (size!=SIZE or angles!=ANGLES or factor!=FACTOR or
        budget!=BUDGET or tuple(checkpoints)!=CHECKPOINTS or warm_rays!=WARM or
        batch!=BATCH or pool!=POOL or provisional_epochs!=PROVISIONAL_EPOCHS or
        final_epochs!=FINAL_EPOCHS or relaxation!=RELAXATION or eta!=ETA or
        tuple(object_seeds)!=OBJECT_SEEDS or tuple(acquisition_seeds)!=ACQUISITION_SEEDS or
        tuple(models)!=MODELS or noise_fraction!=NOISE_FRACTION or offset!=OFFSET or step!=STEP):
        raise ValueError('06B protocol is frozen: no production parameter overrides')
    if (size<4 or angles<2 or factor!=2 or budget>size*size*angles*len(TILTS) or
        not 1<warm_rays<budget or not checkpoints or checkpoints[-1]!=budget or
        tuple(checkpoints)!=tuple(sorted(set(checkpoints))) or
        any(k<=warm_rays or k>budget or (k-warm_rays)%batch for k in checkpoints) or
        (budget-warm_rays)%batch or min(batch,pool,provisional_epochs,final_epochs)<1 or
        not 0<relaxation<=1 or not np.isfinite(relaxation) or not np.isfinite(eta) or eta!=ETA or
        not object_seeds or len(set(object_seeds))!=len(object_seeds) or
        not acquisition_seeds or len(set(acquisition_seeds))!=len(acquisition_seeds) or
        not models or not set(models)<=set(MODELS) or
        not np.isfinite(noise_fraction) or noise_fraction<0 or offset<0 or step<=0):
        raise ValueError('invalid 06B configuration')
    prior = set([950101,950202]) | {900001+1009*i+j for i in range(4) for j in range(2)} | {960001+1009*i+j for i in range(4) for j in range(2)}
    if set(object_seeds)&prior:raise ValueError('object seeds reused from prior studies')


def analyze(rows, checkpoint):
    chosen = [r for r in rows if r['acquired']==checkpoint]
    objects=[]
    for oid in sorted({r['object_id'] for r in chosen}):
        for policy in POLICIES:
            group=[r for r in chosen if r['object_id']==oid and r['policy']==policy]
            objects.append(dict(object_id=oid, policy=policy, n_conditions=len(group),
                mean_relative_gain=float(np.mean([r['gain_vs_coverage'] for r in group])),
                worst_relative_gain=float(min(r['gain_vs_coverage'] for r in group))))
    primary=[r['mean_relative_gain'] for r in objects if r['policy']=='guarded_05']
    return objects, dict(primary_mean_object_balanced_gain=float(np.mean(primary)),
        primary_object_wins=int(sum(x>0 for x in primary)), n_objects=len(primary),
        primary_object_gains=primary,
        favorable_primary=bool(np.mean(primary)>0 and all(x>0 for x in primary)))


def run_validation(output_dir, *, size=SIZE, angles=ANGLES, factor=FACTOR,
        budget=BUDGET, checkpoints=CHECKPOINTS, warm_rays=WARM, batch=BATCH,
        pool=POOL, provisional_epochs=PROVISIONAL_EPOCHS,
        final_epochs=FINAL_EPOCHS, relaxation=RELAXATION, eta=ETA,
        object_seeds=OBJECT_SEEDS, acquisition_seeds=ACQUISITION_SEEDS,
        models=MODELS, noise_fraction=NOISE_FRACTION, offset=OFFSET, step=STEP,
        allow_test_scale=False):
    validate(size=size, angles=angles, factor=factor, budget=budget,
        checkpoints=checkpoints, warm_rays=warm_rays, batch=batch, pool=pool,
        provisional_epochs=provisional_epochs, final_epochs=final_epochs,
        relaxation=relaxation, eta=eta, object_seeds=object_seeds,
        acquisition_seeds=acquisition_seeds, models=models,
        noise_fraction=noise_fraction, offset=offset, step=step,
        allow_test_scale=allow_test_scale)
    out=Path(output_dir)
    if out.exists() and any(out.iterdir()):raise ValueError('refusing to overwrite nonempty output directory')
    out.mkdir(parents=True,exist_ok=True)
    primary_checkpoint = PRIMARY if PRIMARY in checkpoints else (checkpoints[-1] if allow_test_scale else PRIMARY)
    cfg=dict(experiment='RBYRCT-06B prospective frozen synthetic defects validation',
        stage='confirmatory relative to 06A2 development; synthetic only', size=size,
        angles=angles, tilts=list(map(float,TILTS)),factor=factor, budget=budget,
        checkpoints=list(checkpoints), primary_checkpoint=primary_checkpoint,
        warm_rays=warm_rays,batch=batch,pool=pool,
        provisional_epochs=provisional_epochs,final_epochs=final_epochs,
        relaxation=relaxation, guard_eta=eta,policies=list(POLICIES),
        object_seeds=list(object_seeds),acquisition_seeds=list(acquisition_seeds),
        models=list(models), noise_fraction=noise_fraction,offset=offset,step=step,
        object_generator='independent seeded ellipsoid host with rotated localized Gaussian defects',
        model_same='A @ coarse block-mean truth',
        model_independent='trilinear fine-volume midpoint ray marching with detector offset',
        primary_estimand='mean over distinct objects of per-object mean paired relative RMSE gain, guarded_05 vs coverage, at 288 rays',
        primary_success_rule='overall mean > 0 and positive per-object mean for all 8 objects',
        secondary='gradient baseline, ray checkpoints 144 and 576, 0.10 RMSE checkpoint-censored threshold, selection time, mismatch',
        unit_of_replication='independent object; models/seeds repeated conditions',
        interpretation='success rule is stringent descriptive criterion, not a statistical significance test',
        stop_rule='one frozen run irrespective of outcome; no retuning based on 06B outputs',
        no_physical_ct_or_dose=True, allow_test_scale=bool(allow_test_scale))
    cfg['protocol_sha256']=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()
    (out/'protocol.json').write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf8')
    (out/'environment.txt').write_text(_env_data(Path(__file__)),encoding='utf8')
    t0=time.perf_counter()
    A=system_matrix(size,angles,TILTS).tocsr()
    matrix_s=time.perf_counter()-t0
    if A.shape!=(size*size*angles*len(TILTS),size**3):raise RuntimeError('matrix shape mismatch')
    warm_orders={seed:voxel_coverage_order(A,size,angles,len(TILTS),budget,seed,pool) for seed in acquisition_seeds}
    manifest=[];orders=[];rows=[];timings=[];audit_rows=[]
    for oid_index,obj_seed in enumerate(object_seeds):
        oid=f'localized_defect_{obj_seed}'
        truth,fine,description=defect_phantom(size,factor,obj_seed)
        if not np.isfinite(truth).all() or np.min(truth)<=0:raise RuntimeError('invalid phantom truth')
        manifest.append(dict(object_id=oid,object_seed=obj_seed,n_defects=description['n_defects'],
            coarse_sha256=hashlib.sha256(np.asarray(truth,dtype='<f8').tobytes()).hexdigest(),
            fine_sha256=hashlib.sha256(np.asarray(fine,dtype='<f8').tobytes()).hexdigest(),
            parameters_json=json.dumps(description,sort_keys=True)))
        for model_index,model in enumerate(models):
            clean=np.asarray(A@truth).ravel() if model=='same' else project(
                fine,size,angles,TILTS,factor=factor,offset=offset,step=step,mode='linear')
            if clean.shape!=(A.shape[0],) or not np.isfinite(clean).all() or (clean<0).any():
                raise RuntimeError('invalid forward projections')
            mismatch=float(np.linalg.norm(clean-A@truth)/max(np.linalg.norm(A@truth),1.e-12))
            noise_seed=(obj_seed*37+model_index*100003+17011)%(2**32)
            measured=nonnegative_noisy_measurements(clean,noise_fraction,noise_seed)
            for seed in acquisition_seeds:
                this=[]; acquired_orders={}
                warm=warm_orders[seed]
                for policy in POLICIES:
                    oracle=AcquiredOnly(measured)
                    oracle.commit(warm[:warm_rays])
                    if policy=='guarded_05':
                        order,trace,selection_s=acquire_guarded(A,oracle,size,angles,warm,budget,seed,
                            eta=eta,warm_rays=warm_rays,batch=batch,candidate_pool=pool,
                            provisional_epochs=provisional_epochs,relaxation=relaxation)
                        for a in trace:
                            audit_rows.append(dict(object_id=oid,model=model,acquisition_seed=seed,
                                policy=policy,**a))
                    else:
                        order,trace,selection_s=select_order(A,oracle,size,angles,warm,budget,seed,
                            policy=policy,warm_rays=warm_rays,batch=batch,candidate_pool=pool,
                            provisional_epochs=provisional_epochs,relaxation=relaxation)
                    order=np.asarray(order,dtype=np.int64)
                    if (len(order)!=budget or len(np.unique(order))!=budget or
                        not np.array_equal(order[:warm_rays],warm[:warm_rays]) or
                        oracle.allowed!=set(map(int,order))):
                        raise RuntimeError('acquired-only or uniqueness verification failed')
                    acquired_orders[policy]=order
                    orders.extend(dict(object_id=oid,model=model,acquisition_seed=seed,
                        policy=policy, acquired_index=i+1,ray_id=int(ray)) for i,ray in enumerate(order))
                    for checkpoint in checkpoints:
                        prefix=order[:checkpoint]
                        t=time.perf_counter()
                        x=mart_reconstruct(A[prefix],measured[prefix],final_epochs,relaxation=relaxation)
                        recon_s=time.perf_counter()-t
                        if not np.isfinite(x).all() or np.any(x<=0):raise RuntimeError('invalid MART reconstruction')
                        rmse=float(np.sqrt(np.mean((x-truth)**2)))
                        this.append(dict(object_id=oid,object_seed=obj_seed,model=model,
                            acquisition_seed=seed,policy=policy,acquired=checkpoint,
                            rmse=rmse,gain_vs_coverage=0.,shared_with_coverage=0,
                            relative_forward_mismatch=mismatch,
                            ray_order_sha256=order_sha256(prefix)))
                        timings.append(dict(object_id=oid,model=model,acquisition_seed=seed,
                            policy=policy,acquired=checkpoint,selection_s=selection_s,
                            reconstruction_s=recon_s,matrix_build_s=matrix_s))
                    print(f'{oid} {model:11s} seed={seed} {policy:11s} {budget} rays; selection={selection_s:.2f}s',flush=True)
                for r in this:
                    base=next(v['rmse'] for v in this if v['policy']=='coverage' and v['acquired']==r['acquired'])
                    r['gain_vs_coverage']=(base-r['rmse'])/max(base,1.e-12)
                    k=r['acquired']
                    r['shared_with_coverage']=len(set(acquired_orders[r['policy']][:k]) & set(acquired_orders['coverage'][:k]))
                rows.extend(this)
    object_rows,primary_result=analyze(rows,primary_checkpoint)
    threshold_rows=[]
    for obj_seed in object_seeds:
        oid=f'localized_defect_{obj_seed}'
        for model in models:
            for seed in acquisition_seeds:
                for policy in POLICIES:
                    group=sorted((r for r in rows if (r['object_id'],r['model'],r['acquisition_seed'],r['policy'])==(oid,model,seed,policy)),key=lambda r:r['acquired'])
                    first=next((r['acquired'] for r in group if r['rmse']<=THRESHOLD),None)
                    threshold_rows.append(dict(object_id=oid,model=model,acquisition_seed=seed,
                        policy=policy,rmse_threshold=THRESHOLD,
                        first_observed_checkpoint=first if first is not None else '',
                        crossed_by_budget=int(first is not None),
                        note='checkpoint-censored: no interpolated ray savings'))
    for name,data in [('object_manifest.csv',manifest),('acquisition_orders.csv',orders),
                      ('prefix_reconstructions.csv',rows),('matched_cases.csv',[r for r in rows if r['acquired']==primary_checkpoint]),
                      ('object_level_summary.csv',object_rows),('threshold_crossings.csv',threshold_rows),
                      ('timing.csv',timings),('guard_batch_audit.csv',audit_rows)]:
        _write_csv(out/name,data)
    status=dict(pass_engineering_checks=True,distinct_objects=len(manifest),
        acquisition_histories=len(orders)//budget,reconstructions=len(rows),
        ray_order_rows=len(orders),primary_checkpoint=primary_checkpoint,
        primary_result=primary_result,
        stop_rule='One frozen 06B run; do not retune or rerun based on performance.',
        caveat='Synthetic only, no physical CT/dose benefit; object is replication unit')
    (out/'study_status.json').write_text(json.dumps(status,indent=2)+'\n',encoding='utf8')
    files=sorted(p for p in out.iterdir() if p.is_file() and p.name!='run_manifest.sha256')
    (out/'run_manifest.sha256').write_text(''.join(f'{_sha256(p)}  {p.name}\n' for p in files),encoding='utf8')
    print(f'06B complete: {len(manifest)} objects, {len(orders)//budget} histories, '
          f'{len(rows)} reconstructions; output={out}',flush=True)
    return status


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,
        default=Path('results/experiment06b/frozen_first'))
    args=parser.parse_args(argv)
    try:run_validation(args.output_dir)
    except (ValueError,RuntimeError,OSError) as e:parser.error(str(e))

if __name__=='__main__':main()
