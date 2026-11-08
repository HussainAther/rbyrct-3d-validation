"""08Q independent voxel-level MART replay of archived frozen 08M ray schedules.

No acquisition selection is performed. Data generation uses the frozen projectors
and phantom specification, while sequential MART and RMSE are reimplemented here.
This is a source-locked computational replay, not an independent physical simulator.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import sparse

ARCHIVE_FILES = ('protocol.json','environment.json','acquisition_orders.csv',
                 'prefix_reconstructions.csv','object_manifest.csv','object_level_summary.csv',
                 'aggregate_summary.csv','guard_batch_audit.csv','primary_endpoint.json','run_status.json')
POLICIES = ('coverage','gradient','incremental_25','information_diag')
CHECKPOINTS = (1024,2048,4096)


def digest_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path):
    with Path(path).open(newline='',encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    if not rows: raise ValueError('cannot write empty records')
    with Path(path).open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def order_digest(indices):
    return hashlib.sha256(np.asarray(indices,dtype='<i8').tobytes()).hexdigest()


def replay_mart(matrix, measured, *, epochs=16, relaxation=.25, initial=.3):
    """Independent sequential row update; never imports experiment_05b_mart.

    Produces a new voxel vector via explicit CSR traversal with preserved row order.
    Guard against invalid inputs and perform the frozen multiplicative log update.
    """
    a=sparse.csr_matrix(matrix,dtype=np.float64)
    b=np.asarray(measured,dtype=np.float64).reshape(-1)
    if a.shape[0]!=len(b) or epochs<1 or not (0<relaxation<=1) or initial<=0:
        raise ValueError('invalid replay dimensions/parameters')
    if not np.isfinite(a.data).all() or np.any(a.data<0) or not np.isfinite(b).all() or np.any(b<0):
        raise ValueError('nonnegative finite projection data required')
    estimate=np.full(a.shape[1],initial,dtype=np.float64)
    floor=1.e-10
    for _ in range(epochs):
        for row in range(a.shape[0]):
            left,right=int(a.indptr[row]),int(a.indptr[row+1])
            if left==right: continue
            locations=a.indices[left:right]
            weights=a.data[left:right]
            largest=float(np.max(weights))
            if largest<=0.: continue
            predicted=float(weights @ estimate[locations])
            log_ratio=math.log(max(float(b[row]),floor)/max(predicted,floor))
            correction=np.clip((relaxation/largest)*weights*log_ratio,-12.,12.)
            estimate[locations]=np.maximum(estimate[locations]*np.exp(correction),floor)
    if not np.isfinite(estimate).all():raise FloatingPointError('nonfinite replay image')
    return estimate


def voxel_rmse(reconstruction, truth, defect_mask):
    """Freshly compute three RMSEs from voxels, independent of archived RMSE."""
    x=np.asarray(reconstruction,dtype=np.float64).reshape(-1)
    y=np.asarray(truth,dtype=np.float64).reshape(-1)
    mask=np.asarray(defect_mask,dtype=bool).reshape(-1)
    if x.shape!=y.shape or x.shape!=mask.shape or not 0<mask.sum()<mask.size:
        raise ValueError('incompatible image and defect mask')
    sq=np.square(x-y)
    return dict(global_rmse=float(np.sqrt(sq.mean())),
                defect_region_rmse=float(np.sqrt(sq[mask].mean())),
                nondefect_rmse=float(np.sqrt(sq[~mask].mean())))


def verify_inputs(archive,lock,source):
    archive=Path(archive);lock=Path(lock);source=Path(source)
    if not lock.is_file():raise FileNotFoundError(lock)
    frozen=json.loads(lock.read_text(encoding='utf8'))
    if frozen.get('schema')!='RBYRCT-08M-LOCK-v1':raise ValueError('unexpected lock schema')
    if frozen['size']!=32 or len(frozen['objects'])!=8 or tuple(frozen['models'])!=('same','independent'):
        raise ValueError('08M protocol mismatch')
    if tuple(frozen['policies'])!=POLICIES or tuple(frozen['configs']['32']['checkpoints'])!=CHECKPOINTS:
        raise ValueError('unexpected policies/checkpoints')
    if frozen['primary']['budget']!=2048 or frozen['primary']['policy']!='information_diag':
        raise ValueError('primary endpoint has changed')
    if len(frozen['source_hashes'])!=15:raise ValueError('incomplete frozen source list')
    for name,expected in frozen['source_hashes'].items():
        file=source/(name+'.py')
        if not file.is_file() or digest_file(file)!=expected:
            raise RuntimeError('source lock mismatch: '+name)
    saved=json.loads((archive/'protocol.json').read_text(encoding='utf8'))
    if saved!=frozen:raise RuntimeError('archived protocol differs from source lock')
    manifest=json.loads((archive/'sha256.json').read_text(encoding='utf8'))
    if set(manifest)!=set(ARCHIVE_FILES):raise RuntimeError('archive SHA file list mismatch')
    for name in ARCHIVE_FILES:
        if digest_file(archive/name)!=manifest[name]:raise RuntimeError('archive SHA mismatch: '+name)
    status=json.loads((archive/'run_status.json').read_text(encoding='utf8'))
    if not status.get('complete') or status.get('completed_histories')!=128 or status.get('completed_reconstructions')!=384:
        raise RuntimeError('incomplete archived validation')
    return frozen


def load_orders(archive,lock):
    groups=defaultdict(list)
    for r in read_csv(Path(archive)/'acquisition_orders.csv'):
        key=(r['object_id'],r['model'],int(r['acquisition_seed']),r['policy'])
        groups[key].append((int(r['acquired_index']),int(r['ray_id'])))
    expected={(f'defect_validation_{s}',m,base+32,p)
              for s in lock['objects'] for m in lock['models']
              for base in lock['acquisition_seeds'] for p in POLICIES}
    if set(groups)!=expected:raise ValueError('missing or extra acquisition histories')
    out={}
    max_ray=32*32*int(lock['angles'])*len(lock['tilts'])
    for key,pairs in groups.items():
        if len(pairs)!=4096 or [i for i,_ in pairs]!=list(range(1,4097)):
            raise ValueError('invalid ray indices: '+str(key))
        ids=np.array([j for _,j in pairs],dtype=np.int64)
        if ids.min()<0 or ids.max()>=max_ray or len(np.unique(ids))!=4096:
            raise ValueError('out-of-bounds or repeated ray: '+str(key))
        out[key]=ids
    return out


def stored_rows(archive):
    result={}
    for r in read_csv(Path(archive)/'prefix_reconstructions.csv'):
        key=(r['object_id'],r['model'],int(r['acquisition_seed']),r['policy'],int(r['acquired']))
        if key in result: raise ValueError('duplicate stored metric')
        result[key]=r
    if len(result)!=384:raise ValueError('incomplete metric rows')
    return result


def summarize(rows):
    """Object-first paired fractional reduction, not condition-level pseudoreplication."""
    grouped=defaultdict(list)
    for r in rows:
        grouped[(r['object_id'],r['acquired'])].append(r)
    per_object=[]
    for (obj,k),entries in sorted(grouped.items()):
        if len(entries)!=4 or len({(x['model'],x['acquisition_seed']) for x in entries})!=4:
            raise ValueError('missing paired conditions for '+obj)
        per_object.append(dict(object_id=obj,acquired=k,n_conditions=4,
            mean_global_gain=float(np.mean([x['global_gain'] for x in entries])),
            mean_defect_gain=float(np.mean([x['defect_gain'] for x in entries]))))
    by_checkpoint=defaultdict(list)
    for x in per_object:by_checkpoint[x['acquired']].append(x)
    aggregates=[]
    for k,items in sorted(by_checkpoint.items()):
        if len(items)!=8:raise ValueError('not eight independent objects')
        aggregates.append(dict(acquired=k,n_objects=8,
            mean_global_gain=float(np.mean([x['mean_global_gain'] for x in items])),
            mean_defect_gain=float(np.mean([x['mean_defect_gain'] for x in items])),
            object_global_wins=sum(x['mean_global_gain']>0 for x in items),
            object_defect_wins=sum(x['mean_defect_gain']>0 for x in items)))
    return per_object,aggregates


def run(archive,lock_path,source_dir,output_dir,*,scope='primary', tolerance=2e-8,save_volumes=True):
    """Replay cached 08M acquisition orders and independently calculate voxel errors.

    scope=primary: 64 volumes (two policies at 2048, 8 objects x 4 conditions).
    scope=all: all 384 volumes, compare all checkpoints and all four policies.
    """
    archive,source_dir,out=Path(archive),Path(source_dir),Path(output_dir)
    frozen=verify_inputs(archive,lock_path,source_dir)
    orders=load_orders(archive,frozen)
    saved=stored_rows(archive)
    if out.exists() and any(out.iterdir()):raise FileExistsError('refusing overwrite of existing replay')
    out.mkdir(parents=True,exist_ok=True)
    # Imports occur AFTER source-hash verification and solely to reproduce the frozen
    # phantom, forward model and geometry. MART and RMSE are new implementations.
    sys.path.insert(0,str(source_dir.resolve()))
    from experiment_04b import system_matrix
    from experiment_04qa import project
    from experiment_06b import defect_phantom
    from experiment_07c_preflight import defect_support
    A=system_matrix(32,int(frozen['angles']),frozen['tilts']).tocsr()
    if A.shape!=(32*32*int(frozen['angles'])*len(frozen['tilts']),32**3):
        raise RuntimeError('geometry shape mismatch')
    checkpoints=(2048,) if scope=='primary' else CHECKPOINTS
    policies=('coverage','information_diag') if scope=='primary' else POLICIES
    expected=8*2*2*len(policies)*len(checkpoints)
    # Exposing measured values only here, after acquisition orders are fixed.
    comparisons=[];paired=[];volumes=[];start=time.perf_counter()
    cfg=frozen['configs']['32']
    try:
        for object_seed in frozen['objects']:
            oid=f'defect_validation_{object_seed}'
            truth,fine,_=defect_phantom(32,int(frozen['factor']),object_seed)
            mask,mask_info=defect_support(32,int(frozen['factor']),object_seed)
            manifest={r['object_id']:r for r in read_csv(archive/'object_manifest.csv')}
            if hashlib.sha256(np.asarray(truth,dtype='<f8').tobytes()).hexdigest()!=manifest[oid]['truth_sha256']:
                raise RuntimeError('phantom SHA mismatch '+oid)
            if mask_info['mask_sha256']!=manifest[oid]['mask_sha256']:
                raise RuntimeError('defect mask SHA mismatch '+oid)
            for mi,model in enumerate(frozen['models']):
                if model=='same':clean=np.asarray(A@truth,dtype=float).ravel()
                else:clean=np.asarray(project(fine,32,int(frozen['angles']),frozen['tilts'],
                    factor=int(frozen['factor']),offset=float(frozen['offset']),
                    step=float(frozen['step']),mode='linear'),dtype=float).ravel()
                for ai,base in enumerate(frozen['acquisition_seeds']):
                    acq_seed=int(base)+32
                    noise_seed=(object_seed*37+mi*100003+17011+ai*133337)%(2**32)
                    # Independent implementation of frozen Gaussian + zero clip rule.
                    sigma=float(frozen['noise_fraction'])*float(np.sqrt(np.mean(clean**2)))
                    noise=np.random.default_rng(noise_seed).normal(0.,sigma,clean.shape)
                    measured=np.maximum(clean+noise,0.)
                    temporary={}
                    for policy in policies:
                        order=orders[(oid,model,acq_seed,policy)]
                        for k in checkpoints:
                            key=(oid,model,acq_seed,policy,k)
                            expected_row=saved.get(key)
                            if expected_row is None:raise ValueError('missing archived metric '+str(key))
                            if expected_row['order_sha256']!=order_digest(order[:k]):
                                raise RuntimeError('archived reconstruction order fingerprint mismatch')
                            selected=A[order[:k],:]
                            reconstructed=replay_mart(selected,measured[order[:k]],epochs=int(cfg['final_epochs']),
                                relaxation=float(frozen['relaxation']))
                            actual=voxel_rmse(reconstructed,truth,mask)
                            temporary[(policy,k)]=actual
                            for name in actual:
                                previous=float(expected_row[name]); observed=actual[name]
                                ok=math.isclose(previous,observed,rel_tol=tolerance,abs_tol=tolerance)
                                comparisons.append(dict(object_id=oid,model=model,acquisition_seed=acq_seed,
                                    policy=policy,acquired=k,metric=name,replayed_rmse=observed,
                                    archived_rmse=previous,absolute_difference=abs(observed-previous),pass_check=ok))
                            if save_volumes:
                                # Save uncompressed .npy to preserve exact 64-bit voxels and simple reuse.
                                file=f'{oid}_{model}_{acq_seed}_{policy}_{k}.npy'
                                np.save(out/file,reconstructed,allow_pickle=False)
                                volumes.append(dict(filename=file,sha256=digest_file(out/file),
                                    object_id=oid,model=model,acquisition_seed=acq_seed,
                                    policy=policy,acquired=k,voxels=len(reconstructed)))
                    for k in checkpoints:
                        coverage=temporary[('coverage',k)]
                        for policy in policies:
                            actual=temporary[(policy,k)]
                            paired.append(dict(object_id=oid,model=model,acquisition_seed=acq_seed,
                                policy=policy,acquired=k,
                                global_gain=(coverage['global_rmse']-actual['global_rmse'])/max(coverage['global_rmse'],1e-12),
                                defect_gain=(coverage['defect_region_rmse']-actual['defect_region_rmse'])/max(coverage['defect_region_rmse'],1e-12)))
                    print(f'08Q replay {oid} model={model} seed={acq_seed}: {len(policies)*len(checkpoints)} volumes',flush=True)
        write_csv(out/'voxel_rmse_comparison.csv',comparisons)
        write_csv(out/'paired_gains.csv',paired)
        if volumes:write_csv(out/'volume_manifest.csv',volumes)
        info_rows=[x for x in paired if x['policy']=='information_diag']
        objects,aggregate=summarize(info_rows)
        write_csv(out/'object_level_replayed.csv',objects)
        write_csv(out/'aggregate_replayed.csv',aggregate)
        primary=next(x for x in aggregate if x['acquired']==2048)
        original=json.loads((archive/'primary_endpoint.json').read_text(encoding='utf8'))['primary']
        maxdiff=max(x['absolute_difference'] for x in comparisons)
        endpoint_match=all(math.isclose(primary[k],float(original[k]),rel_tol=tolerance,abs_tol=tolerance)
                           for k in ('mean_global_gain','mean_defect_gain'))
        count_match=all(primary[k]==int(original[k]) for k in ('object_global_wins','object_defect_wins'))
        passed=(len(comparisons)==expected*3 and all(x['pass_check'] for x in comparisons)
                and endpoint_match and count_match)
        report=dict(verdict='PASS' if passed else 'FAIL',scope=scope,
            check_type='Independent MART update and voxel-level RMSE on archived acquisition orders',
            independent_objects=8,volumes_reconstructed=expected,
            voxel_rmse_comparisons=len(comparisons),max_absolute_rmse_difference=maxdiff,
            primary_replayed=primary,primary_archived=original,
            primary_matches=endpoint_match and count_match,
            elapsed_seconds=time.perf_counter()-start,
            frozen_protocol_sha256=digest_file(lock_path),
            archive_manifest_sha256=digest_file(archive/'sha256.json'),
            source_hashes_checked=len(frozen['source_hashes']),
            limitations=['Phantom generator, sparse geometry and independent forward-projector remain those of frozen source; not independent physical-model replication.',
              'MART kernel and error metrics independently implemented, but numerical agreement does not rule out shared modeling assumptions.',
              'Archived ray orders are replayed as fixed; no acquisition policy reselection.',
              'Only eight independent synthetic objects; repeated model and seed conditions are paired, not independent samples.'])
        (out/'replay_report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf8')
        (out/'run_status.json').write_text(json.dumps(dict(complete=True,verdict=report['verdict'],
           volumes_reconstructed=expected),indent=2)+'\n',encoding='utf8')
        (out/'sha256.json').write_text(json.dumps({p.name:digest_file(p) for p in sorted(out.iterdir()) if p.is_file()},indent=2)+'\n',encoding='utf8')
        print(json.dumps(report,indent=2),flush=True)
        if not passed:raise RuntimeError('08Q replay mismatch; preserve outputs and investigate without changing 08M')
        return report
    except BaseException:
        if not (out/'run_status.json').exists():
            (out/'run_status.json').write_text(json.dumps(dict(complete=False,scope=scope,
               compared_metrics=len(comparisons),message='interrupted or failed; preserve directory unchanged'),indent=2)+'\n')
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results-dir',type=Path,required=True)
    p.add_argument('--protocol-lock',type=Path,default=Path('protocol_08m_frozen.json'))
    p.add_argument('--source-dir',type=Path,default=Path('.'))
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--scope',choices=('primary','all'),default='primary')
    p.add_argument('--no-volumes',action='store_true',help='disable voxel array persistence; not recommended')
    args=p.parse_args()
    run(args.results_dir,args.protocol_lock,args.source_dir,args.output_dir,scope=args.scope,
        save_volumes=not args.no_volumes)

if __name__=='__main__':main()
