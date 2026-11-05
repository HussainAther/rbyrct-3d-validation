"""08AD: independent 192-volume 08AC synthetic voxel-MART replay.

Reuses frozen source-defined phantom/geometry/independent forward projector and
archived acquisition orders. Reimplements noise, MART, voxel metrics, aggregation.
No imported production MART/selector/metrics. Read-only archived sources.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import sparse

OBJECTS = tuple(range(920201, 920207))
SEEDS = (920411, 920829)
MODELS = ('same', 'independent')
POLICIES = ('coverage', 'information_diag', 'information_full', 'full_spatial_balanced')
CHECKPOINTS = (512, 1024)
N, FACTOR, ANGLES = 32, 2, 4
BUDGET, EPOCHS, RELAXATION = 1024, 16, .25
NOISE, OFFSET, STEP = .005, .15, .25
ARCHIVED_FILES = ('run_status.json','protocol.json','environment.json',
                  'acquisition_orders.csv','prefix_reconstructions.csv','object_level_summary.csv',
                  'aggregate_summary.csv','primary_object_comparison.csv','object_manifest.csv')
METRICS = (('global_rmse','gain_vs_coverage'),('defect_region_rmse','defect_gain_vs_coverage'),
           ('nondefect_rmse','nondefect_gain_vs_coverage'))


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()


def order_digest(order):
    return hashlib.sha256(np.asarray(order,dtype='<i8').tobytes()).hexdigest()


def rows(path):
    with Path(path).open('r',newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))


def save_rows(path,data):
    if not data:raise ValueError('empty CSV')
    with Path(path).open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)


def independently_noisy(clean, seed, fraction=NOISE):
    v=np.asarray(clean,dtype=np.float64).ravel()
    if not len(v) or not np.isfinite(v).all() or np.any(v<0) or fraction<0:
        raise ValueError('invalid clean projections')
    sigma=fraction*float(np.sqrt(np.mean(v*v)))
    return np.maximum(v+np.random.default_rng(seed).normal(0.,sigma,v.shape),0.)


def independent_mart(matrix, measured, epochs=EPOCHS, relaxation=RELAXATION, initial=.3):
    """CSR row-ordered MART, independent of experiment_05b_mart."""
    a=sparse.csr_matrix(matrix,dtype=np.float64)
    b=np.asarray(measured,dtype=np.float64).ravel()
    if a.shape[0]!=b.size or epochs<1 or not 0<relaxation<=1 or initial<=0:
        raise ValueError('invalid dimensions or MART parameters')
    if (np.any(a.data<0) or not np.isfinite(a.data).all() or np.any(b<0)
            or not np.isfinite(b).all()):raise ValueError('MART requires finite nonnegative inputs')
    x=np.full(a.shape[1],float(initial),dtype=np.float64)
    floor=1e-10
    for _ in range(epochs):
        for row in range(a.shape[0]):
            start,end=int(a.indptr[row]),int(a.indptr[row+1])
            if start==end:continue
            ids=a.indices[start:end]
            weights=a.data[start:end]
            largest=float(np.max(weights))
            if largest<=0:continue
            estimate=float(np.dot(weights,x[ids]))
            ratio=max(float(b[row]),floor)/max(estimate,floor)
            change=np.clip((relaxation/largest)*weights*math.log(max(ratio,floor)),-12.,12.)
            x[ids]=np.maximum(x[ids]*np.exp(change),floor)
    if not np.isfinite(x).all():raise FloatingPointError('nonfinite reconstructed volume')
    return x


def independent_errors(x,truth,mask):
    x=np.asarray(x,dtype=np.float64).ravel()
    truth=np.asarray(truth,dtype=np.float64).ravel()
    mask=np.asarray(mask,dtype=bool).ravel()
    if x.shape!=truth.shape or truth.shape!=mask.shape or not 0<mask.sum()<len(mask):
        raise ValueError('truth/replay/mask dimensions mismatch')
    e=(x-truth)**2
    return dict(global_rmse=float(np.sqrt(np.mean(e))),
                defect_region_rmse=float(np.sqrt(np.mean(e[mask]))),
                nondefect_rmse=float(np.sqrt(np.mean(e[~mask]))))


def near(a,b,tol):
    return math.isclose(float(a),float(b),rel_tol=tol,abs_tol=tol)


def verify_original(archive, preflight, source_dir):
    archive,preflight,source_dir=map(Path,(archive,preflight,source_dir))
    if not archive.is_dir() or not preflight.is_dir() or not source_dir.is_dir():
        raise FileNotFoundError('expected existing original, preflight, source directories')
    for file in ARCHIVED_FILES:
        if not (archive/file).is_file():raise FileNotFoundError(archive/file)
    saved_hashes=json.loads((archive/'sha256.json').read_text(encoding='utf-8'))
    if set(saved_hashes)!=(set(ARCHIVED_FILES)):
        raise RuntimeError(f'08AC SHA manifest keys mismatch: missing {set(ARCHIVED_FILES)-set(saved_hashes)}, unexpected {set(saved_hashes)-set(ARCHIVED_FILES)}')
    for name in ARCHIVED_FILES:
        if digest(archive/name)!=saved_hashes[name]:
            raise RuntimeError('archived 08AC SHA mismatch: '+name)
    status=json.loads((archive/'run_status.json').read_text(encoding='utf-8'))
    if not(status.get('complete') is True and status.get('completed_reconstructions')==192
           and status.get('expected_reconstructions')==192):raise RuntimeError('08AC archived status not complete 192/192')
    protocol=json.loads((archive/'protocol.json').read_text(encoding='utf-8'))
    expected={'schema':'RBYRCT-08AC-PROTOCOL-v1','size':N,'angles':ANGLES,'factor':FACTOR,
              'object_seeds':list(OBJECTS),'acquisition_seeds':list(SEEDS),
              'models':list(MODELS),'policies':list(POLICIES),'checkpoints':list(CHECKPOINTS),
              'budget':BUDGET,'primary_checkpoint':1024,'primary_policy':'full_spatial_balanced',
              'primary_reference':'information_full','epochs':EPOCHS,'relaxation':RELAXATION,
              'noise_fraction':NOISE,'offset':OFFSET,'step':STEP,'spatial_alpha':.25,
              'warm':64,'batch':32,'pool':16}
    for key,value in expected.items():
        if protocol.get(key)!=value:raise RuntimeError('08AC protocol mismatch: '+key)
    frozen=source_dir/'protocol_08ac_frozen.json'
    if not frozen.is_file() or json.loads(frozen.read_text(encoding='utf-8'))!=protocol:
        raise RuntimeError('frozen protocol lock does not match archived 08AC protocol')
    # Validate the subset of source modules that the replay deliberately reuses.
    for module in ('experiment_04b','experiment_04g','experiment_04qa','experiment_06b','experiment_07c_preflight'):
        code=source_dir/(module+'.py')
        if not code.is_file() or digest(code)!=protocol.get('source_sha256',{}).get(module):
            raise RuntimeError('frozen source file mismatch: '+str(code))
    pf=json.loads((preflight/'preflight.json').read_text(encoding='utf-8'))
    if not (pf.get('complete') is True and pf.get('geometry_only') is True and
            pf.get('size')==N and pf.get('budget')==BUDGET and pf.get('alpha')==.25):
        raise RuntimeError('08AC preflight protocol mismatch')
    if digest(preflight/'acquisition_orders.csv')!=pf.get('acquisition_orders_file_sha256'):
        raise RuntimeError('preflight acquisition file SHA mismatch')
    if (preflight/'acquisition_orders.csv').read_bytes()!=(archive/'acquisition_orders.csv').read_bytes():
        raise RuntimeError('archive and preflight acquisition orders differ')
    return protocol,pf


def archived_orders(archive,pf,num_candidate_rays):
    grouped=defaultdict(list)
    for r in rows(Path(archive)/'acquisition_orders.csv'):
        key=(int(r['acquisition_seed']),r['policy'])
        if key[0] not in SEEDS or key[1] not in POLICIES:raise RuntimeError('unexpected order row')
        grouped[key].append(r)
    if set(grouped)!={(s,p) for s in SEEDS for p in POLICIES}:
        raise RuntimeError('missing/extra acquisition order groups')
    result={}
    for (s,p),group in grouped.items():
        if len(group)!=BUDGET:raise RuntimeError('order count mismatch')
        group=sorted(group,key=lambda z:int(z['acquired_index']))
        if [int(z['acquired_index']) for z in group]!=list(range(1,BUDGET+1)):
            raise RuntimeError('noncontiguous order indices')
        ids=np.array([int(z['ray_id']) for z in group],dtype=np.int64)
        if np.any(ids<0) or np.any(ids>=num_candidate_rays) or len(np.unique(ids))!=BUDGET:
            raise RuntimeError('invalid ray order')
        fingerprint=order_digest(ids)
        if fingerprint!=pf.get('order_sha256',{}).get(str(s),{}).get(p) or any(z['order_sha256']!=fingerprint for z in group):
            raise RuntimeError('saved full ray order fingerprint mismatch')
        result[s,p]=ids
    for s in SEEDS:
        warm=result[s,'coverage'][:64]
        if any(not np.array_equal(result[s,p][:64],warm) for p in POLICIES):
            raise RuntimeError('unequal warm start')
    return result


def stored_records(archive, orders):
    raw=rows(Path(archive)/'prefix_reconstructions.csv')
    stored={}
    for r in raw:
        key=(r['object_id'],int(r['acquisition_seed']),r['model'],r['policy'],int(r['acquired']))
        if key in stored:raise RuntimeError('duplicate archived reconstruction key')
        if r['order_sha256']!=order_digest(orders[key[1],key[3]][:key[4]]):
            raise RuntimeError('stored prefix order hash mismatch: '+str(key))
        stored[key]=r
    expected={(f'defect_validation_08ac_{o}',s,m,p,b) for o in OBJECTS for s in SEEDS for m in MODELS for p in POLICIES for b in CHECKPOINTS}
    if set(stored)!=expected:raise RuntimeError('missing/extra original reconstruction rows')
    return stored


def replay(archive,preflight,source_dir,output_dir,tolerance=2e-8,save_volumes=True):
    archive,preflight,source_dir,out=map(Path,(archive,preflight,source_dir,output_dir))
    if not (np.isfinite(tolerance) and 0<tolerance<=1e-4):raise ValueError('tolerance outside safe range')
    if out.exists():raise FileExistsError('refusing to overwrite any existing 08AD result')
    protocol,pf=verify_original(archive,preflight,source_dir)
    sys.path.insert(0,str(source_dir.resolve()))
    # Original source is reused only for the synthetic simulation model, not for MART,
    # noise, voxel metrics, selection, or summary arithmetic.
    from experiment_04b import system_matrix
    from experiment_04g import TILTS
    from experiment_04qa import project
    from experiment_06b import defect_phantom
    from experiment_07c_preflight import defect_support
    A=system_matrix(N,ANGLES,TILTS).tocsr()
    if A.shape!=(len(TILTS)*ANGLES*N*N,N**3):raise RuntimeError('geometry shape mismatch')
    orders=archived_orders(archive,pf,A.shape[0])
    stored=stored_records(archive,orders)
    manifest_rows=rows(archive/'object_manifest.csv')
    manifest={r['object_id']:r for r in manifest_rows}
    if len(manifest_rows)!=len(OBJECTS) or set(manifest)!={f'defect_validation_08ac_{o}' for o in OBJECTS}:
        raise RuntimeError('object manifest incomplete')
    original_object={(r['object_id'],int(r['acquired']),r['policy']):r for r in rows(archive/'object_level_summary.csv')}
    original_agg={(int(r['acquired']),r['policy']):r for r in rows(archive/'aggregate_summary.csv')}
    original_primary={r['object_id']:r for r in rows(archive/'primary_object_comparison.csv')}
    if len(original_object)!=48 or len(original_agg)!=8 or len(original_primary)!=6:
        raise RuntimeError('archive summary row counts mismatch')
    out.mkdir(parents=True)
    (out/'run_status.json').write_text(json.dumps({'complete':False,'volumes_replayed':0},indent=2)+'\n')
    checked=[]; gains=[]; volumes=[]; object_summaries=[]; aggregate=[]; primary=[]; problems=[]
    replayed_gains={}
    replayed_rmse={}
    n_done=0; t0=time.perf_counter()
    try:
        for obj_seed in OBJECTS:
            object_id=f'defect_validation_08ac_{obj_seed}'
            truth,fine,desc=defect_phantom(N,FACTOR,obj_seed)
            mask,info=defect_support(N,FACTOR,obj_seed)
            truth=np.asarray(truth,dtype=np.float64).ravel();mask=np.asarray(mask,dtype=bool).ravel()
            truth_hash=hashlib.sha256(np.asarray(truth,dtype='<f8').tobytes()).hexdigest()
            ref=manifest[object_id]
            if (truth_hash!=ref['truth_sha256'] or info['mask_sha256']!=ref['mask_sha256']
                 or int(info['mask_voxels'])!=int(ref['mask_voxels']) or int(desc['n_defects'])!=int(ref['n_defects'])):
                raise RuntimeError('truth/mask locked fingerprint mismatch: '+object_id)
            for acq_index,s in enumerate(SEEDS):
                for model_index,model in enumerate(MODELS):
                    if model=='same': clean=np.asarray(A@truth,dtype=np.float64).ravel()
                    else: clean=np.asarray(project(fine,N,ANGLES,TILTS,factor=FACTOR,offset=OFFSET,step=STEP,mode='linear'),dtype=np.float64).ravel()
                    noise_seed=(obj_seed*37+model_index*100003+17011+acq_index*133337)%(2**32)
                    measurement=independently_noisy(clean,noise_seed)
                    this={}
                    for p in POLICIES:
                        order=orders[s,p]
                        for b in CHECKPOINTS:
                            x=independent_mart(A[order[:b]],measurement[order[:b]])
                            metrics=independent_errors(x,truth,mask)
                            this[p,b]=metrics
                            replayed_rmse[object_id,s,model,p,b]=metrics
                            archived=stored[object_id,s,model,p,b]
                            for metric,_ in METRICS:
                                v=metrics[metric];stored_v=float(archived[metric]);delta=abs(v-stored_v)
                                passed=near(v,stored_v,tolerance)
                                checked.append(dict(object_id=object_id,acquisition_seed=s,model=model,policy=p,acquired=b,metric=metric,
                                                    replayed=v,archived=stored_v,abs_difference=delta,pass_check=passed))
                                if not passed:problems.append(f'RMSE {object_id}/{s}/{model}/{p}/{b}/{metric}: {delta:.9g}')
                            if save_volumes:
                                name=f'{object_id}_seed{s}_{model}_{p}_{b}.npy'
                                np.save(out/name,x,allow_pickle=False)
                                volumes.append(dict(filename=name,sha256=digest(out/name),object_id=object_id,acquisition_seed=s,
                                                    model=model,policy=p,acquired=b,voxels=x.size))
                            n_done+=1
                    for p in POLICIES:
                        for b in CHECKPOINTS:
                            for metric,gain_field in METRICS:
                                policy_value=this[p,b][metric]
                                coverage=this['coverage',b][metric]
                                value=(coverage-policy_value)/max(coverage,1e-12)
                                reference=float(stored[object_id,s,model,p,b][gain_field])
                                passed=near(value,reference,tolerance)
                                gains.append(dict(object_id=object_id,acquisition_seed=s,model=model,policy=p,acquired=b,
                                                  gain_type=gain_field,replayed=value,archived=reference,abs_difference=abs(value-reference),pass_check=passed))
                                replayed_gains[object_id,s,model,p,b,gain_field]=value
                                if not passed:problems.append(f'gain {object_id}/{s}/{model}/{p}/{b}/{gain_field}')
                    print(f'08AD object {obj_seed}, acquisition {s}, model {model}: {len(POLICIES)*len(CHECKPOINTS)} volumes; total {n_done}/192',flush=True)
                    (out/'run_status.json').write_text(json.dumps({'complete':False,'volumes_replayed':n_done},indent=2)+'\n')
        for obj_seed in OBJECTS:
            obj_id=f'defect_validation_08ac_{obj_seed}'
            for b in CHECKPOINTS:
                for p in POLICIES:
                    sub={field:float(np.mean([replayed_gains[obj_id,s,m,p,b,field] for s in SEEDS for m in MODELS]))
                         for _,field in METRICS}
                    old=original_object[obj_id,b,p]
                    mean_rmse=float(np.mean([replayed_rmse[obj_id,s,m,p,b]['global_rmse'] for s in SEEDS for m in MODELS]))
                    good=(all(near(sub[field],old[archived_field],tolerance) for field,archived_field in (
                        ('gain_vs_coverage','mean_global_gain'),('defect_gain_vs_coverage','mean_defect_gain'),
                        ('nondefect_gain_vs_coverage','mean_nondefect_gain')))
                        and near(mean_rmse,old['mean_global_rmse'],tolerance))
                    object_summaries.append(dict(object_id=obj_id,acquired=b,policy=p,n_conditions=4,
                                                 mean_global_gain=sub['gain_vs_coverage'],mean_defect_gain=sub['defect_gain_vs_coverage'],
                                                 mean_nondefect_gain=sub['nondefect_gain_vs_coverage'],mean_global_rmse=mean_rmse,archived_match=good))
                    if not good:problems.append(f'object summary {obj_id}/{b}/{p}')
        for b in CHECKPOINTS:
            for p in POLICIES:
                group=[z for z in object_summaries if z['acquired']==b and z['policy']==p]
                g=float(np.mean([z['mean_global_gain'] for z in group]))
                d=float(np.mean([z['mean_defect_gain'] for z in group]))
                gw=sum(z['mean_global_gain']>0 for z in group)
                dw=sum(z['mean_defect_gain']>0 for z in group)
                orig=original_agg[b,p]
                good=near(g,orig['mean_global_gain'],tolerance) and near(d,orig['mean_defect_gain'],tolerance) and gw==int(orig['object_global_wins']) and dw==int(orig['object_defect_wins'])
                aggregate.append(dict(acquired=b,policy=p,n_objects=6,mean_global_gain=g,mean_defect_gain=d,
                                      object_global_wins=gw,object_defect_wins=dw,archived_match=good))
                if not good:problems.append(f'aggregate {b}/{p}')
        for obj_seed in OBJECTS:
            obj_id=f'defect_validation_08ac_{obj_seed}'
            f=next(z for z in object_summaries if z['object_id']==obj_id and z['acquired']==1024 and z['policy']=='information_full')
            s=next(z for z in object_summaries if z['object_id']==obj_id and z['acquired']==1024 and z['policy']=='full_spatial_balanced')
            diff=s['mean_global_gain']-f['mean_global_gain']
            old=original_primary[obj_id]
            rmse_diff=s['mean_global_rmse']-f['mean_global_rmse']
            wins=int(s['mean_global_rmse']<f['mean_global_rmse'])
            good=(near(diff,old['spatial_minus_full_global_gain'],tolerance)
                  and near(rmse_diff,old['spatial_minus_full_global_rmse'],tolerance)
                  and wins==int(old['spatial_better_global'])
                  and near(s['mean_global_gain'],old['spatial_global_gain_vs_coverage'],tolerance)
                  and near(f['mean_global_gain'],old['full_global_gain_vs_coverage'],tolerance))
            primary.append(dict(object_id=obj_id,spatial_minus_full_gain=diff,spatial_minus_full_rmse=rmse_diff,
                                spatial_better_global=wins,archived_match=good))
            if not good:problems.append(f'primary difference {obj_id}')
        primary_diff=float(np.mean([r['spatial_minus_full_gain'] for r in primary]))
        if not near(100*primary_diff,9.657769736799208,tolerance):
            problems.append('primary predeclared numerical expectation differs')
        save_rows(out/'voxel_rmse_comparison.csv',checked)
        save_rows(out/'replayed_gain_comparison.csv',gains)
        save_rows(out/'object_replayed.csv',object_summaries)
        save_rows(out/'aggregate_replayed.csv',aggregate)
        save_rows(out/'primary_replayed.csv',primary)
        if save_volumes:save_rows(out/'volume_manifest.csv',volumes)
        complete=(n_done==192 and len(checked)==576 and len(gains)==576 and len(object_summaries)==48
                  and len(aggregate)==8 and len(primary)==6 and not problems)
        report=dict(verdict='PASS' if complete else 'FAIL',complete=complete,
                    scope='08AC all 192 frozen synthetic voxel reconstructions',independent_objects=6,
                    acquisition_seeds=list(SEEDS),models=list(MODELS),policies=list(POLICIES),checkpoints=list(CHECKPOINTS),
                    volumes_replayed=n_done,rmse_comparisons=len(checked),gain_comparisons=len(gains),
                    object_comparisons=len(object_summaries),aggregate_comparisons=len(aggregate),
                    primary_comparisons=len(primary),saved_volumes=len(volumes),
                    max_abs_rmse_difference=max((x['abs_difference'] for x in checked),default=None),
                    max_abs_gain_difference=max((x['abs_difference'] for x in gains),default=None),
                    primary_spatial_minus_full_gain_pp=100*primary_diff,
                    primary_spatial_vs_full_object_wins=sum(z['spatial_better_global'] for z in primary),
                    tolerance=tolerance,source_archived_files_verified=len(ARCHIVED_FILES),
                    acquisition_orders_verified=len(SEEDS)*len(POLICIES),
                    original_sources_unchanged=True,elapsed_seconds=time.perf_counter()-t0,
                    errors=problems, limitations=[
                      'Independent MART arithmetic, noise and voxel errors but shared original phantom, geometry and independent forward-projector implementations.',
                      'Archived acquisition orders are replayed; acquisition selection is not independently regenerated.',
                      'Original 08AC archive has no voxel arrays; RMSE agreements do not establish exact voxel-by-voxel equality to unsaved originals.',
                      'Six synthetic objects, with seeds and forward models as paired conditions, not independent biological replicates.',
                      'Not a clinical/physical tomography validation or radiation-dose demonstration.'])
        (out/'replay_report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        (out/'run_status.json').write_text(json.dumps({'complete':complete,'verdict':report['verdict'],'volumes_replayed':n_done},indent=2)+'\n')
        (out/'sha256.json').write_text(json.dumps({p.name:digest(p) for p in sorted(out.iterdir()) if p.is_file()},indent=2)+'\n')
        print(json.dumps(report,indent=2),flush=True)
        if not complete:raise RuntimeError('08AD replay mismatch: preserve failed output')
        return report
    except BaseException as exc:
        (out/'run_status.json').write_text(json.dumps({'complete':False,'volumes_replayed':n_done,'failure':str(exc)},indent=2)+'\n')
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results-dir',required=True,type=Path)
    p.add_argument('--preflight-dir',required=True,type=Path)
    p.add_argument('--source-dir',default='.',type=Path)
    p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--tolerance',type=float,default=2e-8)
    p.add_argument('--no-volumes',action='store_true')
    args=p.parse_args()
    replay(args.results_dir,args.preflight_dir,args.source_dir,args.output_dir,args.tolerance,not args.no_volumes)


if __name__=='__main__':main()
