"""RBYRCT-08M: prospectively frozen independent 32-cubed synthetic validation.

Existing baselines use unchanged selectors; the new information policy uses
only known ray geometry and acquired ray IDs. All use identical MART reconstruction. Object truth and defect masks are generated outside acquisition,
and accessed only by evaluation. No automatic lambda tuning or success gate.
"""
from __future__ import annotations
import argparse
import importlib.util
import csv
import hashlib
import json
import platform
import sys
import os
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
from experiment_06b import defect_phantom
from experiment_07c_preflight import defect_support, error_metrics
from experiment_08b import select_incremental
from experiment_08a import NEW_LAMBDA
from experiment_08j import PRIOR_VARIANCE, OBSERVATION_VARIANCE
from experiment_08k import select_information

POLICIES=('coverage','gradient','incremental_25','information_diag')
MODELS=('same','independent')
ANGLES=4
FACTOR=2
RELAXATION=.25
NOISE_FRACTION=.005
OFFSET=.15
STEP=.25
ACQUISITION_SEEDS=(820411, 820829)
OBJECT_SEEDS={32: tuple(820101+7919*i for i in range(8))}
CONFIGS={32:dict(budget=4096,checkpoints=(1024,2048,4096),warm=64,batch=32,pool=16,epochs=2,final_epochs=16)}
PRIMARY_BUDGET=2048
PRIMARY_POLICY='information_diag'
REFERENCE_POLICY='coverage'
LOCK_SCHEMA='RBYRCT-08M-LOCK-v1'
# The lock contains SHA-256 of these exact imported source modules, not only the driver.
SOURCE_MODULES=('experiment_08m','experiment_08k','experiment_08j','experiment_08b',
  'experiment_08a','experiment_04b','experiment_04g','experiment_04h',
  'experiment_04qa','experiment_05b_04','experiment_05b_08b',
  'experiment_05b_gate','experiment_05b_mart','experiment_06b',
  'experiment_07c_preflight')

RESERVED={810411,811011,810201,810202,810301,810302,820411,820829} | {104729,130363,707001,808201,808202,950101,950202,808401,808402,808403,808404,808501,808502,808503,808504,809701,809702,809801,809802} | {2077001+7919*i for i in range(8)} | {1066001+7919*i for i in range(8)}
FIELDS=('size','object_id','object_seed','model','acquisition_seed','policy','acquired',
        'global_rmse','defect_region_rmse','nondefect_rmse','gain_vs_coverage',
        'defect_gain_vs_coverage','nondefect_gain_vs_coverage','shared_with_coverage',
        'order_sha256','selection_seconds','reconstruction_seconds','guard_binding_choices',
        'guard_intervention_choices')



def validate(sizes,object_seeds,configs,models,acquisition_seeds):
    if not sizes or len(set(sizes))!=len(sizes) or not models or not set(models)<=set(MODELS):
        raise ValueError('invalid sizes/models')
    seen=set()
    for n in sizes:
        if n not in configs or n not in object_seeds or n<4:
            raise ValueError('unsupported size')
        cfg=configs[n]
        if not all(k in cfg for k in ('budget','checkpoints','warm','batch','pool','epochs','final_epochs')):
            raise ValueError('incomplete config')
        b,w,check=cfg['budget'],cfg['warm'],tuple(cfg['checkpoints'])
        if not(0<w<b<=n*n*ANGLES*len(TILTS) and check and check==tuple(sorted(set(check)))
               and check[-1]==b and all(w<k<=b for k in check)
               and min(cfg['batch'],cfg['pool'],cfg['epochs'],cfg['final_epochs'])>=1):
            raise ValueError('bad budgets/checkpoints')
        seeds=tuple(object_seeds[n]);
        if not seeds or len(set(seeds))!=len(seeds) or set(seeds)&(RESERVED|seen):
            raise ValueError('reused or reserved seeds')
        seen.update(seeds)
    seeds=tuple(acquisition_seeds)
    if not seeds or len(seeds)!=len(set(seeds)) or set(seeds)&seen:
        raise ValueError('invalid acquisition seeds')


def append(path,fields,rows):
    with path.open('a',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='raise');w.writerows(rows)


def write(path,rows):
    if not rows:raise ValueError('empty rows')
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),extrasaction='raise');w.writeheader();w.writerows(rows)


def sha(order):
    return hashlib.sha256(np.asarray(order,dtype='<i8').tobytes()).hexdigest()


def object_summary(rows, policies=POLICIES):
    """Average model x acquisition-seed conditions inside each object first."""
    result=[]
    for n in sorted({r['size'] for r in rows}):
        for obj in sorted({r['object_id'] for r in rows if r['size']==n}):
            for k in sorted({r['acquired'] for r in rows if r['size']==n}):
                reference={(r['model'],r['acquisition_seed']) for r in rows
                           if (r['size'],r['object_id'],r['acquired'],r['policy'])==(n,obj,k,'coverage')}
                for policy in policies:
                    z=[r for r in rows if (r['size'],r['object_id'],r['acquired'],r['policy'])==(n,obj,k,policy)]
                    if not z or len(z)!=len(reference) or {(r['model'],r['acquisition_seed']) for r in z}!=reference:
                        raise ValueError('incomplete or duplicated paired object conditions')
                    result.append(dict(size=n,object_id=obj,acquired=k,policy=policy,n_conditions=len(z),
                        mean_global_gain=float(np.mean([r['gain_vs_coverage'] for r in z])),
                        mean_defect_gain=float(np.mean([r['defect_gain_vs_coverage'] for r in z])),
                        mean_nondefect_gain=float(np.mean([r['nondefect_gain_vs_coverage'] for r in z]))))
    return result


def source_hashes():
    hashes={}
    for module in SOURCE_MODULES:
        spec=importlib.util.find_spec(module)
        if spec is None or spec.origin is None or not Path(spec.origin).is_file():
            raise FileNotFoundError(f'missing source module: {module}')
        hashes[module]=hashlib.sha256(Path(spec.origin).read_bytes()).hexdigest()
    return hashes


def protocol():
    return dict(schema=LOCK_SCHEMA,stage='08M independent confirmatory synthetic validation',
       size=32,objects=list(OBJECT_SEEDS[32]),acquisition_seeds=list(ACQUISITION_SEEDS),
       configs={'32':dict(CONFIGS[32],checkpoints=list(CONFIGS[32]['checkpoints']))},models=list(MODELS),policies=list(POLICIES),
       angles=ANGLES,tilts=list(map(float,TILTS)),factor=FACTOR,
       lambda_incremental=float(NEW_LAMBDA),prior_variance=float(PRIOR_VARIANCE),
       observation_variance=float(OBSERVATION_VARIANCE),
       relaxation=RELAXATION,noise_fraction=NOISE_FRACTION,offset=OFFSET,step=STEP,
       primary=dict(policy=PRIMARY_POLICY,reference=REFERENCE_POLICY,budget=PRIMARY_BUDGET,
           endpoint='object-balanced mean paired fractional whole-volume RMSE gain',
           unit='independent phantom; first average two models x two acquisition seeds',
           descriptive_wins='number of objects with positive model/seed-averaged gain',
           inference='report descriptive object mean, individual gains, optional bootstrap CI; no post-hoc threshold'),
       secondary=['defect-region RMSE gain at 2048 rays',
           'whole-volume and defect gains at 1024 and 4096 rays',
           'results stratified by model and acquisition seed',
           'ray-order distinctness and seed dependence'],
       source_hashes=source_hashes(),
       interpretation='Geometry-only information policy, NOT measurement-adaptive; no clinical or dose claims',
       run_rule='single complete execution after protocol lock committed; no outcome-driven retuning')


def freeze(lock_path):
    path=Path(lock_path)
    if path.exists():
        raise FileExistsError(f'protocol lock exists, refusing overwrite: {path}')
    frozen=protocol()
    path.write_text(json.dumps(frozen,indent=2,sort_keys=True,allow_nan=False)+'\n',encoding='utf-8')
    return frozen


def verify_lock(lock_path):
    path=Path(lock_path)
    if not path.is_file():
        raise FileNotFoundError('missing frozen protocol; run --freeze-protocol, review and COMMIT before execution')
    locked=json.loads(path.read_text(encoding='utf-8'))
    current=protocol()
    if locked!=current:
        diff=[x for x in sorted(set(current)|set(locked)) if current.get(x)!=locked.get(x)]
        raise RuntimeError(f'08M frozen protocol/source mismatch in {diff}; do not auto-rewrite lock')
    return locked


def aggregate_summary(object_rows):
    aggregate=[]
    for k in CONFIGS[32]['checkpoints']:
        for policy in POLICIES:
            group=[x for x in object_rows if (x['size'],x['acquired'],x['policy'])==(32,k,policy)]
            if len(group)!=len(OBJECT_SEEDS[32]):
                raise ValueError('missing independent objects in aggregate')
            aggregate.append(dict(size=32,acquired=k,policy=policy,n_objects=len(group),
                mean_global_gain=float(np.mean([x['mean_global_gain'] for x in group])),
                mean_defect_gain=float(np.mean([x['mean_defect_gain'] for x in group])),
                object_global_wins=sum(x['mean_global_gain']>0 for x in group),
                object_defect_wins=sum(x['mean_defect_gain']>0 for x in group)))
    return aggregate


def run(output_dir, *, lock_path='protocol_08m_frozen.json'):
    frozen=verify_lock(lock_path)
    sizes=(32,);object_seeds=OBJECT_SEEDS;configs=CONFIGS;models=MODELS
    acquisition_seeds=ACQUISITION_SEEDS
    validate(sizes,object_seeds,configs,models,acquisition_seeds)
    out=Path(output_dir)
    if out.exists() and any(out.iterdir()):raise FileExistsError('refusing to overwrite previous run')
    out.mkdir(parents=True,exist_ok=True)
    (out/'protocol.json').write_text(json.dumps(frozen,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    (out/'environment.json').write_text(json.dumps(dict(python=sys.version,platform=platform.platform(),numpy=np.__version__),indent=2)+'\n')
    with (out/'prefix_reconstructions.csv').open('w',encoding='utf8',newline='') as f:csv.writer(f).writerow(FIELDS)
    for filename,fields in [('acquisition_orders.csv',('size','object_id','model','acquisition_seed','policy','acquired_index','ray_id')),
        ('guard_batch_audit.csv',('size','object_id','model','acquisition_seed','trace_json'))]:
        with (out/filename).open('w',encoding='utf8',newline='') as f:csv.writer(f).writerow(fields)
    rows=[];finished=0;manifest=[]
    try:
        for n in sizes:
            cfg=configs[n];A=system_matrix(n,ANGLES,TILTS).tocsr()
            budget=cfg['budget'];warm=cfg['warm']
            for obj_seed in object_seeds[n]:
                oid=f'defect_validation_{obj_seed}'
                truth,fine,desc=defect_phantom(n,FACTOR,obj_seed)
                mask,info=defect_support(n,FACTOR,obj_seed)
                manifest.append(dict(size=n,object_id=oid,object_seed=obj_seed,mask_voxels=info['mask_voxels'],
                  mask_sha256=info['mask_sha256'],truth_sha256=hashlib.sha256(np.asarray(truth,dtype='<f8').tobytes()).hexdigest(),
                  n_defects=desc['n_defects']))
                for acq_index,seed_base in enumerate(acquisition_seeds):
                    seed=seed_base+n
                    coverage_order=np.asarray(voxel_coverage_order(A,n,ANGLES,len(TILTS),budget,seed,cfg['pool']),dtype=np.int64)
                    for mi,model in enumerate(models):
                        clean=np.asarray(A@truth).ravel() if model=='same' else np.asarray(project(fine,n,ANGLES,TILTS,factor=FACTOR,offset=OFFSET,step=STEP,mode='linear')).ravel()
                        noise_seed=(obj_seed*37+mi*100003+17011+acq_index*133337)%(2**32)
                        measured=nonnegative_noisy_measurements(clean,NOISE_FRACTION,noise_seed)
                        orders={};condition=[]
                        for policy in POLICIES:
                            oracle=AcquiredOnly(measured);oracle.commit(coverage_order[:warm])
                            if policy=='coverage':
                                t=time.perf_counter();order=coverage_order.copy();oracle.commit(order[warm:]);trace=[];seconds=time.perf_counter()-t
                            elif policy=='gradient':
                                order,trace,seconds=select_order(A,oracle,n,ANGLES,coverage_order,budget,seed,
                                    policy='gradient',warm_rays=warm,batch=cfg['batch'],candidate_pool=cfg['pool'],
                                    provisional_epochs=cfg['epochs'],relaxation=RELAXATION)
                            elif policy=='incremental_25':
                                order,trace,seconds=select_incremental(A,oracle,n,ANGLES,coverage_order,budget,seed,
                                    warm_rays=warm,batch=cfg['batch'],candidate_pool=cfg['pool'],
                                    provisional_epochs=cfg['epochs'])
                            else:
                                order,trace,seconds=select_information(A,oracle,n,ANGLES,coverage_order,budget,seed,
                                    warm_rays=warm,batch=cfg['batch'],candidate_pool=cfg['pool'])
                            order=np.asarray(order,dtype=np.int64)
                            if len(order)!=budget or len(set(order.tolist()))!=budget or oracle.allowed!=set(map(int,order)) or not np.array_equal(order[:warm],coverage_order[:warm]):
                                raise RuntimeError('acquisition gate/order violation')
                            orders[policy]=order
                            append(out/'acquisition_orders.csv',('size','object_id','model','acquisition_seed','policy','acquired_index','ray_id'),
                                (dict(size=n,object_id=oid,model=model,acquisition_seed=seed,policy=policy,acquired_index=i+1,ray_id=int(ray)) for i,ray in enumerate(order)))
                            if policy=='incremental_25':
                                append(out/'guard_batch_audit.csv',('size','object_id','model','acquisition_seed','trace_json'),
                                    (dict(size=n,object_id=oid,model=model,acquisition_seed=seed,trace_json=json.dumps(x,sort_keys=True)) for x in trace))
                            for k in cfg['checkpoints']:
                                t=time.perf_counter();recon=mart_reconstruct(A[order[:k]],oracle[order[:k]],cfg['final_epochs'],relaxation=RELAXATION)
                                reconstruct_seconds=time.perf_counter()-t
                                metrics=error_metrics(recon,truth,mask)
                                condition.append(dict(size=n,object_id=oid,object_seed=obj_seed,model=model,
                                    acquisition_seed=seed,policy=policy,acquired=k,**metrics,
                                    gain_vs_coverage=0.,defect_gain_vs_coverage=0.,nondefect_gain_vs_coverage=0.,
                                    shared_with_coverage=0,order_sha256=sha(order[:k]),selection_seconds=seconds,
                                    reconstruction_seconds=reconstruct_seconds,
                                    guard_binding_choices=sum(x.get('binding_choices',0) for x in trace),
                                    guard_intervention_choices=sum(x.get('intervention_choices',0) for x in trace)))
                            finished+=1
                            print(f'08M {n}^3 object={obj_seed} seed={seed} model={model:11s} {policy:15s} rays={budget} select={seconds:.2f}s',flush=True)
                        for r in condition:
                            base=next(z for z in condition if z['policy']=='coverage' and z['acquired']==r['acquired'])
                            for metric,gain in [('global_rmse','gain_vs_coverage'),('defect_region_rmse','defect_gain_vs_coverage'),('nondefect_rmse','nondefect_gain_vs_coverage')]:
                                r[gain]=(base[metric]-r[metric])/max(base[metric],1e-12)
                            r['shared_with_coverage']=len(set(orders[r['policy']][:r['acquired']])&set(orders['coverage'][:r['acquired']]))
                        rows.extend(condition)
                        append(out/'prefix_reconstructions.csv',FIELDS,condition)
                        (out/'run_status.json').write_text(json.dumps(dict(complete=False,completed_histories=finished,completed_reconstructions=len(rows)),indent=2)+'\n')
    except BaseException:
        (out/'run_status.json').write_text(json.dumps(dict(complete=False,completed_histories=finished,completed_reconstructions=len(rows),message='interrupted; retain folder unchanged'),indent=2)+'\n')
        raise
    write(out/'object_manifest.csv',manifest)
    summaries=object_summary(rows);write(out/'object_level_summary.csv',summaries)
    aggregate=aggregate_summary(summaries)
    write(out/'aggregate_summary.csv',aggregate)
    primary=next(x for x in aggregate if x['policy']==PRIMARY_POLICY and x['acquired']==PRIMARY_BUDGET)
    primary_objects=[x for x in summaries if x['policy']==PRIMARY_POLICY and x['acquired']==PRIMARY_BUDGET]
    (out/'primary_endpoint.json').write_text(json.dumps(dict(
        status='descriptive; independent source audit/replay still required',
        primary=primary,object_gains=[dict(object_id=x['object_id'],mean_global_gain=x['mean_global_gain'],
          mean_defect_gain=x['mean_defect_gain']) for x in primary_objects]),indent=2)+'\n')
    (out/'run_status.json').write_text(json.dumps(dict(complete=True,completed_histories=finished,completed_reconstructions=len(rows)),indent=2)+'\n')
    digest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()}
    (out/'sha256.json').write_text(json.dumps(digest,indent=2)+'\n')
    print(f'08M complete: {finished} histories, {len(rows)} reconstructions; output={out}',flush=True)
    return aggregate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--freeze-protocol',action='store_true',help='write lock once; commit before run')
    action.add_argument('--run',action='store_true',help='require matching source-verified lock and run once')
    parser.add_argument('--protocol-lock',type=Path,default=Path('protocol_08m_frozen.json'))
    parser.add_argument('--output-dir',type=Path,default=Path('results/experiment08m/frozen_first'))
    args=parser.parse_args()
    if args.freeze_protocol:
        frozen=freeze(args.protocol_lock)
        print(f'08M frozen protocol written: {args.protocol_lock}; source hashes={len(frozen["source_hashes"])}; REVIEW AND COMMIT BEFORE RUN')
    else:
        run(args.output_dir,lock_path=args.protocol_lock)

if __name__=='__main__':main()
