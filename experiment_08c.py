"""RBYRCT-08C: exploratory MART reconstruction comparison; NOT held-out validation.

All policies use the unchanged acquired-only 08B selector and an identical MART
reconstructor. Object truth and defect masks are generated outside acquisition,
and accessed only by evaluation. No automatic lambda tuning or success gate.
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
from experiment_04qa import project
from experiment_05b_04 import select_order
from experiment_05b_08b import nonnegative_noisy_measurements
from experiment_05b_gate import AcquiredOnly
from experiment_05b_mart import mart_reconstruct
from experiment_06b import defect_phantom
from experiment_07c_preflight import defect_support, error_metrics
from experiment_08b import select_incremental
from experiment_08a import NEW_LAMBDA

POLICIES=('coverage','gradient','incremental_25')
MODELS=('same','independent')
ANGLES=4
FACTOR=2
RELAXATION=.25
NOISE_FRACTION=.005
OFFSET=.15
STEP=.25
ACQUISITION_SEED=808611
OBJECT_SEEDS={12:(808401,808402,808403,808404),32:(808501,808502,808503,808504)}
CONFIGS={12:dict(budget=288,checkpoints=(144,288),warm=24,batch=16,pool=16,epochs=2,final_epochs=16),
         32:dict(budget=1024,checkpoints=(512,1024),warm=64,batch=32,pool=16,epochs=2,final_epochs=16)}
FROZEN_OBJECTS=set(OBJECT_SEEDS[12]+OBJECT_SEEDS[32])
RESERVED={104729,130363,707001,808201,808202,950101,950202} | {2077001+7919*i for i in range(8)} | {1066001+7919*i for i in range(8)}
FIELDS=('size','object_id','object_seed','model','acquisition_seed','policy','acquired',
        'global_rmse','defect_region_rmse','nondefect_rmse','gain_vs_coverage',
        'defect_gain_vs_coverage','nondefect_gain_vs_coverage','shared_with_coverage',
        'order_sha256','selection_seconds','reconstruction_seconds','guard_binding_choices',
        'guard_intervention_choices')


def validate(sizes,object_seeds,configs,models,acquisition_seed):
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
    if acquisition_seed in seen or acquisition_seed in RESERVED:
        raise ValueError('reserved acquisition seed')


def append(path,fields,rows):
    with path.open('a',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='raise');w.writerows(rows)


def write(path,rows):
    if not rows:raise ValueError('empty rows')
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),extrasaction='raise');w.writeheader();w.writerows(rows)


def sha(order):
    return hashlib.sha256(np.asarray(order,dtype='<i8').tobytes()).hexdigest()


def object_summary(rows):
    result=[]
    for n in sorted({r['size'] for r in rows}):
        for obj in sorted({r['object_id'] for r in rows if r['size']==n}):
            for k in sorted({r['acquired'] for r in rows if r['size']==n}):
                for policy in POLICIES:
                    z=[r for r in rows if (r['size'],r['object_id'],r['acquired'],r['policy'])==(n,obj,k,policy)]
                    if not z:raise ValueError('incomplete object summary')
                    result.append(dict(size=n,object_id=obj,acquired=k,policy=policy,n_conditions=len(z),
                        mean_global_gain=float(np.mean([r['gain_vs_coverage'] for r in z])),
                        mean_defect_gain=float(np.mean([r['defect_gain_vs_coverage'] for r in z])),
                        mean_nondefect_gain=float(np.mean([r['nondefect_gain_vs_coverage'] for r in z]))))
    return result


def run(output_dir, *,sizes=(12,32),object_seeds=None,configs=None,models=MODELS,
        acquisition_seed=ACQUISITION_SEED,allow_test_scale=False):
    if object_seeds is None:object_seeds=OBJECT_SEEDS
    if configs is None:configs=CONFIGS
    sizes=tuple(sizes);models=tuple(models)
    if not allow_test_scale and (sizes!=(12,32) or object_seeds!=OBJECT_SEEDS or configs!=CONFIGS or models!=MODELS or acquisition_seed!=ACQUISITION_SEED):
        raise ValueError('default 08C exploratory protocol locked; test overrides require allow_test_scale')
    validate(sizes,object_seeds,configs,models,acquisition_seed)
    out=Path(output_dir)
    if out.exists() and any(out.iterdir()):raise FileExistsError('refusing to overwrite previous run')
    out.mkdir(parents=True,exist_ok=True)
    protocol=dict(stage='08C exploratory development, NOT prospective validation',sizes=list(sizes),
      object_seeds={str(n):list(object_seeds[n]) for n in sizes},configs={str(n):configs[n] for n in sizes},
      angles=ANGLES,tilts=list(map(float,TILTS)),factor=FACTOR,models=list(models),
      acquisition_seed=acquisition_seed,policies=list(POLICIES),lambda_incremental=NEW_LAMBDA,
      relaxation=RELAXATION,noise_fraction=NOISE_FRACTION,offset=OFFSET,step=STEP,
      primary_claim='none; every checkpoint, size, and model reported descriptively',
      selection='AcquiredOnly oracle; truth/mask never passed to selectors',
      warning='development results must not be used as independent confirmatory evidence; no tuning on 06B/07C2 objects')
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n',encoding='utf-8')
    (out/'environment.json').write_text(json.dumps(dict(python=sys.version,platform=platform.platform(),numpy=np.__version__),indent=2)+'\n')
    with (out/'prefix_reconstructions.csv').open('w',encoding='utf8',newline='') as f:csv.writer(f).writerow(FIELDS)
    for filename,fields in [('acquisition_orders.csv',('size','object_id','model','policy','acquired_index','ray_id')),
        ('guard_batch_audit.csv',('size','object_id','model','trace_json'))]:
        with (out/filename).open('w',encoding='utf8',newline='') as f:csv.writer(f).writerow(fields)
    rows=[];finished=0;manifest=[]
    try:
        for n in sizes:
            cfg=configs[n];A=system_matrix(n,ANGLES,TILTS).tocsr()
            budget=cfg['budget'];warm=cfg['warm']
            seed=acquisition_seed+n
            coverage_order=np.asarray(voxel_coverage_order(A,n,ANGLES,len(TILTS),budget,seed,cfg['pool']),dtype=np.int64)
            for obj_seed in object_seeds[n]:
                oid=f'defect_dev_{obj_seed}'
                truth,fine,desc=defect_phantom(n,FACTOR,obj_seed)
                mask,info=defect_support(n,FACTOR,obj_seed)
                manifest.append(dict(size=n,object_id=oid,object_seed=obj_seed,mask_voxels=info['mask_voxels'],
                  mask_sha256=info['mask_sha256'],truth_sha256=hashlib.sha256(np.asarray(truth,dtype='<f8').tobytes()).hexdigest(),
                  n_defects=desc['n_defects']))
                for mi,model in enumerate(models):
                    clean=np.asarray(A@truth).ravel() if model=='same' else np.asarray(project(fine,n,ANGLES,TILTS,factor=FACTOR,offset=OFFSET,step=STEP,mode='linear')).ravel()
                    noise_seed=(obj_seed*37+mi*100003+17011)%(2**32)
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
                        else:
                            order,trace,seconds=select_incremental(A,oracle,n,ANGLES,coverage_order,budget,seed,
                                warm_rays=warm,batch=cfg['batch'],candidate_pool=cfg['pool'],
                                provisional_epochs=cfg['epochs'])
                        order=np.asarray(order,dtype=np.int64)
                        if len(order)!=budget or len(set(order.tolist()))!=budget or oracle.allowed!=set(map(int,order)) or not np.array_equal(order[:warm],coverage_order[:warm]):
                            raise RuntimeError('acquisition gate/order violation')
                        orders[policy]=order
                        append(out/'acquisition_orders.csv',('size','object_id','model','policy','acquired_index','ray_id'),
                            (dict(size=n,object_id=oid,model=model,policy=policy,acquired_index=i+1,ray_id=int(ray)) for i,ray in enumerate(order)))
                        if policy=='incremental_25':
                            append(out/'guard_batch_audit.csv',('size','object_id','model','trace_json'),
                                (dict(size=n,object_id=oid,model=model,trace_json=json.dumps(x,sort_keys=True)) for x in trace))
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
                        print(f'08C {n}^3 object={obj_seed} model={model:11s} {policy:15s} rays={budget} select={seconds:.2f}s',flush=True)
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
    aggregate=[]
    for n in sizes:
        for k in configs[n]['checkpoints']:
            for policy in POLICIES:
                group=[x for x in summaries if (x['size'],x['acquired'],x['policy'])==(n,k,policy)]
                aggregate.append(dict(size=n,acquired=k,policy=policy,n_objects=len(group),
                    mean_global_gain=float(np.mean([x['mean_global_gain'] for x in group])),
                    mean_defect_gain=float(np.mean([x['mean_defect_gain'] for x in group])),
                    object_global_wins=sum(x['mean_global_gain']>0 for x in group),
                    object_defect_wins=sum(x['mean_defect_gain']>0 for x in group)))
    write(out/'aggregate_summary.csv',aggregate)
    (out/'run_status.json').write_text(json.dumps(dict(complete=True,completed_histories=finished,completed_reconstructions=len(rows)),indent=2)+'\n')
    digest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()}
    (out/'sha256.json').write_text(json.dumps(digest,indent=2)+'\n')
    print(f'08C complete: {finished} histories, {len(rows)} reconstructions; output={out}',flush=True)
    return aggregate


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,default=Path('results/experiment08c/exploratory_first'))
    args=p.parse_args()
    run(args.output_dir)

if __name__=='__main__':main()
