"""RBYRCT-07C2: FROZEN prospective 32^3 synthetic defect validation.

This code must be run once, without outcome-driven overrides. The full study is
NOT executed by its tests. Uses acquisition-only ray values; defect mask is
provided to the post-reconstruction evaluator only.
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
from experiment_05b_11_stage2 import _env_data, _sha256, order_sha256
from experiment_06a import acquire_guarded
from experiment_06b import defect_phantom
from experiment_07c_preflight import defect_support, error_metrics
from experiment_07b import current_rss_bytes, peak_rss_bytes, csr_bytes

SIZE=32
ANGLES=4
FACTOR=2
BUDGET=4096
CHECKPOINTS=(1024,2048,4096)
PRIMARY=2048
WARM=64
BATCH=32
POOL=16
PROVISIONAL_EPOCHS=2
FINAL_EPOCHS=16
RELAXATION=.25
ETA=.05
POLICIES=('coverage','gradient','guarded_05')
MODELS=('same','independent')
ACQUISITION_SEEDS=(104729,130363)
OBJECT_SEEDS=tuple(2077001 + 7919*i for i in range(8))
NOISE_FRACTION=.005
OFFSET=.15
STEP=.25
DEFECT_REL_THRESHOLD=.08
DEFECT_ABS_THRESHOLD=.01
THRESHOLD=.10

COLUMNS={
 'object_manifest.csv':('object_id','object_seed','n_defects','mask_voxels','mask_fraction','mask_sha256','coarse_sha256','fine_sha256','parameters_json'),
 'acquisition_orders.csv':('object_id','model','acquisition_seed','policy','acquired_index','ray_id'),
 'prefix_reconstructions.csv':('object_id','object_seed','model','acquisition_seed','policy','acquired','global_rmse','defect_region_rmse','nondefect_rmse','gain_vs_coverage','defect_gain_vs_coverage','nondefect_gain_vs_coverage','shared_with_coverage','relative_forward_mismatch','ray_order_sha256'),
 'timing.csv':('object_id','model','acquisition_seed','policy','acquired','selection_s','reconstruction_s','matrix_build_s'),
 'guard_batch_audit.csv':('object_id','model','acquisition_seed','policy','trace_json'),
}


def validate(*,size,angles,factor,budget,checkpoints,warm,batch,pool,provisional_epochs,
             final_epochs,relaxation,eta,object_seeds,acquisition_seeds,models,
             noise_fraction,offset,step,allow_test_scale=False):
    actual=(size,angles,factor,budget,tuple(checkpoints),warm,batch,pool,provisional_epochs,
            final_epochs,relaxation,eta,tuple(object_seeds),tuple(acquisition_seeds),
            tuple(models),noise_fraction,offset,step)
    frozen=(SIZE,ANGLES,FACTOR,BUDGET,CHECKPOINTS,WARM,BATCH,POOL,PROVISIONAL_EPOCHS,
            FINAL_EPOCHS,RELAXATION,ETA,OBJECT_SEEDS,ACQUISITION_SEEDS,MODELS,
            NOISE_FRACTION,OFFSET,STEP)
    if not allow_test_scale and actual!=frozen:
        raise ValueError('07C2 production protocol frozen; parameter overrides forbidden')
    if (size<4 or angles<2 or factor!=2 or budget>size*size*angles*len(TILTS)
        or not 0<warm<budget or not checkpoints or tuple(checkpoints)!=tuple(sorted(set(checkpoints)))
        or checkpoints[-1]!=budget or any(k<=warm or (k-warm)%batch for k in checkpoints)
        or (budget-warm)%batch or min(batch,pool,provisional_epochs,final_epochs)<1
        or not 0<relaxation<=1 or not np.isfinite(relaxation) or eta!=ETA
        or not object_seeds or len(set(object_seeds))!=len(object_seeds)
        or not acquisition_seeds or len(set(acquisition_seeds))!=len(acquisition_seeds)
        or not models or not set(models)<=set(MODELS)
        or not np.isfinite(noise_fraction) or noise_fraction<0 or offset<0 or step<=0):
        raise ValueError('invalid 07C2 configuration')
    earlier={950101,950202,707001} | {900001+1009*i+j for i in range(4) for j in range(2)} | {960001+1009*i+j for i in range(4) for j in range(2)} | {1066001+7919*i for i in range(8)}
    if set(object_seeds)&earlier:
        raise ValueError('reused development or validation object seed')


def append_rows(path, rows):
    rows=list(rows)
    if not rows:return
    with path.open('a',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=COLUMNS[path.name],extrasaction='raise')
        w.writerows(rows)
        f.flush()


def make_table(path, rows):
    rows=list(rows)
    if rows:
        names=list(rows[0])
    else:
        raise ValueError('empty table')
    with path.open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=names);w.writeheader();w.writerows(rows)


def summarize(rows, primary_checkpoint):
    focus=[r for r in rows if int(r['acquired'])==primary_checkpoint]
    if not focus:raise ValueError('no primary checkpoint records')
    objects=[]
    for oid in sorted({r['object_id'] for r in focus}):
        for policy in POLICIES:
            group=[r for r in focus if r['object_id']==oid and r['policy']==policy]
            if not group:raise ValueError('missing object/policy primary case')
            objects.append(dict(object_id=oid,policy=policy,n_conditions=len(group),
                mean_relative_gain=float(np.mean([r['gain_vs_coverage'] for r in group])),
                mean_defect_gain=float(np.mean([r['defect_gain_vs_coverage'] for r in group])),
                mean_nondefect_gain=float(np.mean([r['nondefect_gain_vs_coverage'] for r in group]))))
    vals=[r['mean_relative_gain'] for r in objects if r['policy']=='guarded_05']
    return objects,dict(primary_mean_object_balanced_gain=float(np.mean(vals)),
         primary_object_wins=sum(v>0 for v in vals), n_objects=len(vals),
         primary_object_gains=vals,
         favorable_primary=bool(len(vals)==8 and np.mean(vals)>0 and all(v>0 for v in vals)),
         note='prespecified descriptive rule; not a statistical significance test')


def run_validation(output_dir, *,size=SIZE,angles=ANGLES,factor=FACTOR,budget=BUDGET,
        checkpoints=CHECKPOINTS,warm=WARM,batch=BATCH,pool=POOL,
        provisional_epochs=PROVISIONAL_EPOCHS,final_epochs=FINAL_EPOCHS,
        relaxation=RELAXATION,eta=ETA,object_seeds=OBJECT_SEEDS,
        acquisition_seeds=ACQUISITION_SEEDS,models=MODELS,
        noise_fraction=NOISE_FRACTION,offset=OFFSET,step=STEP,allow_test_scale=False):
    validate(size=size,angles=angles,factor=factor,budget=budget,checkpoints=checkpoints,
        warm=warm,batch=batch,pool=pool,provisional_epochs=provisional_epochs,
        final_epochs=final_epochs,relaxation=relaxation,eta=eta,
        object_seeds=object_seeds,acquisition_seeds=acquisition_seeds,models=models,
        noise_fraction=noise_fraction,offset=offset,step=step,allow_test_scale=allow_test_scale)
    output=Path(output_dir)
    if output.exists() and any(output.iterdir()):raise ValueError('refusing overwrite of nonempty output directory')
    output.mkdir(parents=True,exist_ok=True)
    primary=PRIMARY if PRIMARY in checkpoints else (checkpoints[-1] if allow_test_scale else PRIMARY)
    protocol=dict(stage='RBYRCT-07C2 prospective frozen 32^3 synthetic localized defect validation',
        size=size,angles=angles,tilts=list(map(float,TILTS)),factor=factor,
        budget=budget,checkpoints=list(checkpoints),primary_checkpoint=primary,
        warm=warm,batch=batch,pool=pool,provisional_epochs=provisional_epochs,
        final_epochs=final_epochs,relaxation=relaxation,eta=eta,
        policies=list(POLICIES),object_seeds=list(object_seeds),
        acquisition_seeds=list(acquisition_seeds),models=list(models),noise_fraction=noise_fraction,
        offset=offset,step=step,mask_relative_threshold=DEFECT_REL_THRESHOLD,
        mask_absolute_threshold=DEFECT_ABS_THRESHOLD,
        primary_estimand='object-balanced mean paired relative whole-volume RMSE gain: guarded_05 vs coverage at 2048 rays',
        primary_success_rule='positive overall mean and positive mean for every one of eight distinct objects',
        secondary='defect and nondefect RMSE gains; gradient baseline; 1024/4096 checkpoints; forward-model mismatch; checkpoint-censored RMSE threshold',
        design_note='2048 is 1/6 of 12288 candidate rays; engineering preflight used final 4 MART epochs, scientific validation freezes 16 as in 06B',
        acquired_only=True,mask_evaluation_only=True,unit_of_replication='object',
        stop_rule='one run only; no post-hoc selector tuning or changing primary checkpoint',
        caveat='synthetic parallel-ray CT; no physical measurement dose or defect detection validity',
        allow_test_scale=allow_test_scale)
    protocol['protocol_sha256']=hashlib.sha256(json.dumps(protocol,sort_keys=True).encode()).hexdigest()
    (output/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n',encoding='utf8')
    (output/'environment.txt').write_text(_env_data(Path(__file__)),encoding='utf8')
    for filename,fields in COLUMNS.items():
        with (output/filename).open('w',newline='',encoding='utf8') as f:csv.writer(f).writerow(fields)
    before,_=current_rss_bytes()
    t0=time.perf_counter(); A=system_matrix(size,angles,TILTS).tocsr();matrix_s=time.perf_counter()-t0
    if A.shape!=(size*size*angles*len(TILTS),size**3) or A.nnz<1:raise RuntimeError('unexpected projection matrix')
    after,_=current_rss_bytes();peak,_=peak_rss_bytes()
    matrix_profile=dict(matrix_build_s=matrix_s,nnz=int(A.nnz),csr_storage_bytes=csr_bytes(A),
        rss_before_bytes=before,rss_after_bytes=after,process_peak_bytes=peak)
    (output/'matrix_profile.json').write_text(json.dumps(matrix_profile,indent=2)+'\n',encoding='utf8')
    coverage_orders={}
    coverage_order_timing={}
    for seed in acquisition_seeds:
        begin=time.perf_counter()
        coverage_orders[int(seed)]=np.asarray(voxel_coverage_order(
            A,size,angles,len(TILTS),budget,int(seed),pool),dtype=np.int64)
        coverage_order_timing[str(seed)]=time.perf_counter()-begin
        if len(np.unique(coverage_orders[int(seed)]))!=budget:
            raise RuntimeError('duplicate rays in common coverage order')
    matrix_profile['common_coverage_order_s_by_seed']=coverage_order_timing
    (output/'matrix_profile.json').write_text(json.dumps(matrix_profile,indent=2)+'\n',encoding='utf8')
    rows=[];histories=0;last_obj=None
    try:
        for obj_seed in object_seeds:
            oid=f'localized_defect_{obj_seed}'
            truth,fine,desc=defect_phantom(size,factor,obj_seed)
            mask,mask_info=defect_support(size,factor,obj_seed,
                relative_threshold=DEFECT_REL_THRESHOLD,absolute_threshold=DEFECT_ABS_THRESHOLD)
            if not (0<np.count_nonzero(mask)<len(mask)) or not np.isfinite(truth).all() or np.min(truth)<=0:
                raise RuntimeError('invalid synthetic object or evaluation mask')
            append_rows(output/'object_manifest.csv',[dict(object_id=oid,object_seed=obj_seed,
                n_defects=desc['n_defects'],mask_voxels=mask_info['mask_voxels'],
                mask_fraction=mask_info['fraction'],mask_sha256=mask_info['mask_sha256'],
                coarse_sha256=hashlib.sha256(np.asarray(truth,dtype='<f8').tobytes()).hexdigest(),
                fine_sha256=hashlib.sha256(np.asarray(fine,dtype='<f8').tobytes()).hexdigest(),
                parameters_json=json.dumps(desc,sort_keys=True))])
            for model_index,model in enumerate(models):
                clean=np.asarray(A@truth).ravel() if model=='same' else np.asarray(project(
                    fine,size,angles,TILTS,factor=factor,offset=offset,step=step,mode='linear')).ravel()
                if clean.shape!=(A.shape[0],) or not np.isfinite(clean).all() or (clean<0).any():
                    raise RuntimeError('invalid forward projections')
                base_signal=np.asarray(A@truth).ravel()
                mismatch=float(np.linalg.norm(clean-base_signal)/max(np.linalg.norm(base_signal),1e-12))
                noise_seed=(int(obj_seed)*37+model_index*100003+17011)%(2**32)
                measured=nonnegative_noisy_measurements(clean,noise_fraction,noise_seed)
                for seed in acquisition_seeds:
                    warm_order=coverage_orders[int(seed)]
                    condition=[];policy_orders={}
                    for policy in POLICIES:
                        oracle=AcquiredOnly(measured);oracle.commit(warm_order[:warm])
                        if policy=='coverage':
                            t=time.perf_counter();order=warm_order.copy();oracle.commit(order[warm:]);trace=[]
                            selection_s=time.perf_counter()-t
                        elif policy=='gradient':
                            order,trace,selection_s=select_order(A,oracle,size,angles,warm_order,budget,int(seed),
                                policy='gradient',warm_rays=warm,batch=batch,candidate_pool=pool,
                                provisional_epochs=provisional_epochs,relaxation=relaxation)
                        else:
                            order,trace,selection_s=acquire_guarded(A,oracle,size,angles,warm_order,budget,int(seed),
                                eta=eta,warm_rays=warm,batch=batch,candidate_pool=pool,
                                provisional_epochs=provisional_epochs,relaxation=relaxation)
                        order=np.asarray(order,dtype=np.int64)
                        if (len(order)!=budget or len(np.unique(order))!=budget or
                            not np.array_equal(order[:warm],warm_order[:warm]) or
                            oracle.allowed!=set(map(int,order))):
                            raise RuntimeError('acquisition order violates acquired-only or uniqueness')
                        policy_orders[policy]=order
                        append_rows(output/'acquisition_orders.csv',(
                            dict(object_id=oid,model=model,acquisition_seed=seed,policy=policy,
                                acquired_index=i+1,ray_id=int(ray)) for i,ray in enumerate(order)))
                        if policy=='guarded_05':
                            append_rows(output/'guard_batch_audit.csv',(
                                dict(object_id=oid,model=model,acquisition_seed=seed,policy=policy,
                                     trace_json=json.dumps(batchtrace,sort_keys=True,default=float)) for batchtrace in trace))
                        for checkpoint in checkpoints:
                            prefix=order[:checkpoint]
                            start=time.perf_counter()
                            reconstructed=mart_reconstruct(A[prefix],oracle[prefix],final_epochs,relaxation=relaxation)
                            reconstruct_s=time.perf_counter()-start
                            if not np.isfinite(reconstructed).all() or (np.asarray(reconstructed)<=0).any():
                                raise RuntimeError('invalid positive finite reconstruction')
                            metrics=error_metrics(reconstructed,truth,mask)
                            condition.append(dict(object_id=oid,object_seed=obj_seed,model=model,
                                acquisition_seed=seed,policy=policy,acquired=checkpoint,**metrics,
                                gain_vs_coverage=0.,defect_gain_vs_coverage=0.,nondefect_gain_vs_coverage=0.,
                                shared_with_coverage=0,relative_forward_mismatch=mismatch,
                                ray_order_sha256=order_sha256(prefix)))
                            append_rows(output/'timing.csv',[dict(object_id=oid,model=model,
                                acquisition_seed=seed,policy=policy,acquired=checkpoint,
                                selection_s=selection_s,reconstruction_s=reconstruct_s,matrix_build_s=matrix_s)])
                        histories+=1
                        print(f'{oid} {model:11s} seed={seed} {policy:11s} {budget} rays; '
                              f'select={selection_s:.2f}s',flush=True)
                    for r in condition:
                        baseline=next(v for v in condition if v['policy']=='coverage' and v['acquired']==r['acquired'])
                        for name,gain_name in (('global_rmse','gain_vs_coverage'),('defect_region_rmse','defect_gain_vs_coverage'),('nondefect_rmse','nondefect_gain_vs_coverage')):
                            r[gain_name]=(baseline[name]-r[name])/max(baseline[name],1e-12)
                        k=r['acquired']
                        r['shared_with_coverage']=len(set(policy_orders[r['policy']][:k]) & set(policy_orders['coverage'][:k]))
                    rows.extend(condition)
                    append_rows(output/'prefix_reconstructions.csv',condition)
            last_obj=oid
            (output/'run_status.json').write_text(json.dumps(dict(complete=False,
                last_finished_object=last_obj,completed_histories=histories,
                completed_reconstructions=len(rows),message='partial output: not a completed study'),indent=2)+'\n')
    except BaseException:
        (output/'run_status.json').write_text(json.dumps(dict(complete=False,
             last_finished_object=last_obj,completed_histories=histories,
             completed_reconstructions=len(rows),message='interrupted; preserve folder; do not overwrite'),indent=2)+'\n')
        raise
    object_rows,primary_result=summarize(rows,primary)
    make_table(output/'object_level_summary.csv',object_rows)
    make_table(output/'matched_cases.csv',[r for r in rows if r['acquired']==primary])
    threshold=[]
    for obj_seed in object_seeds:
      for model in models:
       for seed in acquisition_seeds:
        for policy in POLICIES:
         samples=sorted((r for r in rows if (r['object_seed'],r['model'],r['acquisition_seed'],r['policy'])==
                         (obj_seed,model,seed,policy)),key=lambda r:r['acquired'])
         first=next((r['acquired'] for r in samples if r['global_rmse']<=THRESHOLD),None)
         threshold.append(dict(object_id=f'localized_defect_{obj_seed}',model=model,
               acquisition_seed=seed,policy=policy,rmse_threshold=THRESHOLD,
               first_observed_checkpoint=first if first is not None else '',
               crossed_by_budget=int(first is not None),
               note='checkpoint-censored; no interpolated ray savings'))
    make_table(output/'threshold_crossings.csv',threshold)
    status=dict(pass_engineering_checks=True,distinct_objects=len(object_seeds),
        acquisition_histories=histories,reconstructions=len(rows),ray_order_rows=histories*budget,
        primary_checkpoint=primary,primary_result=primary_result,
        stop_rule='one frozen run; no retuning',caveat='synthetic only; object is replication unit')
    (output/'study_status.json').write_text(json.dumps(status,indent=2)+'\n',encoding='utf8')
    (output/'run_status.json').write_text(json.dumps(dict(complete=True,
        completed_histories=histories,completed_reconstructions=len(rows)),indent=2)+'\n')
    manifest=sorted(p for p in output.iterdir() if p.is_file() and p.name!='run_manifest.sha256')
    (output/'run_manifest.sha256').write_text(''.join(f'{_sha256(p)}  {p.name}\n' for p in manifest),encoding='utf8')
    print(f'07C2 complete: {len(object_seeds)} objects, {histories} histories, '
          f'{len(rows)} reconstructions; output={output}',flush=True)
    return status


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    try:run_validation(args.output_dir)
    except (ValueError,RuntimeError,OSError) as exc:parser.error(str(exc))

if __name__=='__main__':main()
