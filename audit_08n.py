"""08N read-only independent saved-output audit of frozen 08M.

Recompute paired metrics, object-balanced endpoints and ray-order invariants
from archived CSVs. Does NOT replay reconstruction physics or independently
calculate RMSE from voxel volumes (not preserved in 08M archive).
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
import numpy as np

POLICIES = ('coverage', 'gradient', 'incremental_25', 'information_diag')
MODELS = ('same', 'independent')
FILES = ('protocol.json','environment.json','acquisition_orders.csv',
         'prefix_reconstructions.csv','object_manifest.csv','object_level_summary.csv',
         'aggregate_summary.csv','guard_batch_audit.csv','primary_endpoint.json','run_status.json')
METRICS = (('global_rmse','gain_vs_coverage','mean_global_gain'),
           ('defect_region_rmse','defect_gain_vs_coverage','mean_defect_gain'),
           ('nondefect_rmse','nondefect_gain_vs_coverage','mean_nondefect_gain'))

def read_csv(p):
    with p.open('r',encoding='utf-8-sig',newline='') as stream:
        return list(csv.DictReader(stream))

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def order_hash(ids):
    return hashlib.sha256(np.asarray(ids,dtype='<i8').tobytes()).hexdigest()

def number(row,key):
    value=float(row[key]);
    if not math.isfinite(value): raise ValueError(f'nonfinite {key}')
    return value

def integer(row,key):
    value=int(row[key]);
    if str(value)!=str(row[key]).strip(): raise ValueError(f'bad integer {key}')
    return value

def equal(a,b):
    return math.isclose(a,b,rel_tol=2e-10,abs_tol=2e-11)

def audit(root, *, protocol_lock, source_dir, check_masks=False):
    root=Path(root); lock_path=Path(protocol_lock); source_dir=Path(source_dir)
    errors=[]; checks=0
    def check(ok, label):
        nonlocal checks
        checks+=1
        if not ok:errors.append(label)
    for name in FILES+('sha256.json',):
        if not (root/name).is_file():raise FileNotFoundError(root/name)
    if not lock_path.is_file():raise FileNotFoundError(lock_path)
    status=json.loads((root/'run_status.json').read_text(encoding='utf8'))
    protocol=json.loads((root/'protocol.json').read_text(encoding='utf8'))
    locked=json.loads(lock_path.read_text(encoding='utf8'))
    digests=json.loads((root/'sha256.json').read_text(encoding='utf8'))
    check(status.get('complete') is True,'study not complete')
    check(integer(status,'completed_histories')==128,'history completion count')
    check(integer(status,'completed_reconstructions')==384,'reconstruction completion count')
    check(set(digests)==set(FILES),'SHA256 manifest file list mismatch')
    for name in FILES:
        check(digests.get(name)==sha(root/name),'SHA256 mismatch: '+name)
    check(protocol==locked,'archived protocol differs from committed lock')
    check(protocol.get('schema')=='RBYRCT-08M-LOCK-v1','lock schema')
    check(protocol.get('size')==32,'resolution')
    check(tuple(protocol.get('policies',()))==POLICIES,'policy lock')
    check(tuple(protocol.get('models',()))==MODELS,'model lock')
    check(tuple(protocol.get('acquisition_seeds',()))==(820411,820829),'acquisition seed lock')
    seeds=tuple(int(x) for x in protocol['objects'])
    check(len(seeds)==8 and len(set(seeds))==8,'eight unique objects')
    cfg=protocol['configs']['32'];budget=int(cfg['budget']);warm=int(cfg['warm']);cp=tuple(cfg['checkpoints'])
    check(budget==4096 and cp==(1024,2048,4096) and warm==64,'frozen checkpoint/budget settings')
    check(protocol['primary']['policy']=='information_diag' and protocol['primary']['reference']=='coverage' and protocol['primary']['budget']==2048,'primary endpoint lock')
    source_hashes=protocol.get('source_hashes',{})
    check(len(source_hashes)==15,'source lock count')
    for name,expected in source_hashes.items():
        path=source_dir/(name+'.py')
        check(path.is_file() and sha(path)==expected,'frozen source mismatch: '+name)
    dataset=read_csv(root/'prefix_reconstructions.csv')
    orders=read_csv(root/'acquisition_orders.csv')
    objects=read_csv(root/'object_level_summary.csv')
    aggregate=read_csv(root/'aggregate_summary.csv')
    manifest=read_csv(root/'object_manifest.csv')
    guard=read_csv(root/'guard_batch_audit.csv')
    primary=json.loads((root/'primary_endpoint.json').read_text(encoding='utf8'))
    check(len(dataset)==384,'reconstruction CSV row count')
    check(len(manifest)==8,'object manifest row count')
    # Histories are keyed on all condition dimensions, including acquisition seed.
    histories=defaultdict(list)
    for r in orders:
        key=(integer(r,'size'),r['object_id'],r['model'],integer(r,'acquisition_seed'),r['policy'])
        histories[key].append((integer(r,'acquired_index'),integer(r,'ray_id')))
        check(key[0]==32 and key[2] in MODELS and key[4] in POLICIES,'invalid acquisition key')
    expected_hist={(32,f'defect_validation_{obj}',model,s+32,policy)
                   for obj in seeds for model in MODELS for s in protocol['acquisition_seeds'] for policy in POLICIES}
    check(set(histories)==expected_hist,'missing or duplicated acquisition histories')
    check(len(histories)==128,'expected 128 histories')
    rays={};same_order=defaultdict(set); coverage_order=defaultdict(set)
    n_candidates=32**2*int(protocol['angles'])*len(protocol['tilts'])
    for key, pairs in histories.items():
        idx=[x[0] for x in pairs];ids=[x[1] for x in pairs]
        check(len(ids)==budget,'history length '+str(key))
        check(idx==list(range(1,budget+1)),'history indices '+str(key))
        check(len(set(ids))==budget,'duplicate rays '+str(key))
        check(all(0<=ray<n_candidates for ray in ids),'out-of-range rays '+str(key))
        rays[key]=ids
        if key[-1]=='information_diag':same_order[key[3]].add(order_hash(ids))
        if key[-1]=='coverage':coverage_order[key[3]].add(order_hash(ids))
    # Different acquisition seeds may produce different geometric orders.
    order_by_seed={str(seed):dict(information_identical_across_objects_models=(len(same_order[seed])==1),
                                   coverage_identical_across_objects_models=(len(coverage_order[seed])==1))
                   for seed in sorted(set(k[3] for k in histories))}
    for seed,result in order_by_seed.items():
        check(result['information_identical_across_objects_models'],'information ordering depends on phantom/model seed='+seed)
        check(result['coverage_identical_across_objects_models'],'coverage ordering depends on phantom/model seed='+seed)
    for key,ids in rays.items():
        if key[-1]=='information_diag':
            base=rays.get(key[:-1]+('coverage',))
            if base is not None:check(ids[:warm]==base[:warm],'warm coverage prefix differs '+str(key))
    # Saved RMSE arithmetic and overlap, independently recomputed.
    rec={}
    for r in dataset:
        key=(integer(r,'size'),r['object_id'],r['model'],integer(r,'acquisition_seed'),r['policy'],integer(r,'acquired'))
        check(key not in rec,'duplicate reconstruction '+str(key))
        rec[key]=r
        check(key[0]==32 and key[5] in cp,'bad reconstruction size/checkpoint')
        hist=rays.get(key[:5]);cov=rays.get(key[:4]+('coverage',))
        check(hist is not None,'history absent '+str(key))
        if hist is not None:
            check(r['order_sha256']==order_hash(hist[:key[5]]),'ray prefix fingerprint '+str(key))
            if cov is not None:
                check(integer(r,'shared_with_coverage')==len(set(hist[:key[5]])&set(cov[:key[5]])),'coverage overlap '+str(key))
        check(integer(r,'object_seed') in seeds,'unregistered object seed '+str(key))
        check(key[1]==f'defect_validation_{integer(r,"object_seed")}', 'object/seed mismatch '+str(key))
        check(number(r,'selection_seconds')>=0 and number(r,'reconstruction_seconds')>=0,'negative runtime '+str(key))
        for metric,_,_ in METRICS:check(number(r,metric)>=0,'negative RMSE '+str(key))
    expected_rec={history+(k,) for history in expected_hist for k in cp}
    check(set(rec)==expected_rec,'reconstruction Cartesian product incomplete')
    for key,r in rec.items():
        cov=rec.get(key[:4]+('coverage',key[5]))
        if cov is None:continue
        for metric,gain,_ in METRICS:
            baseline=number(cov,metric)
            predicted=(baseline-number(r,metric))/max(baseline,1e-12)
            check(equal(number(r,gain),predicted),'paired '+gain+' mismatch '+str(key))
            if key[4]=='coverage':check(equal(number(r,gain),0),'nonzero reference gain '+str(key))
    by_object=defaultdict(list)
    for key,r in rec.items(): by_object[(key[0],key[1],key[5],key[4])].append(r)
    object_map={}
    for r in objects:
        key=(integer(r,'size'),r['object_id'],integer(r,'acquired'),r['policy'])
        check(key not in object_map,'duplicate object summary '+str(key))
        object_map[key]=r
    check(set(object_map)==set(by_object),'object summary set mismatch')
    for key,group in by_object.items():
        item=object_map.get(key)
        if item is None:continue
        check(len(group)==4 and integer(item,'n_conditions')==4,'wrong model/seed condition count '+str(key))
        check({(r['model'],integer(r,'acquisition_seed')) for r in group}=={(m,s+32) for m in MODELS for s in protocol['acquisition_seeds']},'duplicated/missing paired conditions '+str(key))
        for _,gain,col in METRICS:
            check(equal(number(item,col),sum(number(r,gain) for r in group)/4),'object mean '+col+' '+str(key))
    by_aggregate=defaultdict(list)
    for key,r in object_map.items():by_aggregate[(key[0],key[2],key[3])].append(r)
    aggregate_map={}
    for r in aggregate:
        key=(integer(r,'size'),integer(r,'acquired'),r['policy'])
        check(key not in aggregate_map,'duplicate aggregate '+str(key))
        aggregate_map[key]=r
    check(set(aggregate_map)==set(by_aggregate),'aggregate row coverage')
    for key,group in by_aggregate.items():
        item=aggregate_map.get(key)
        if item is None:continue
        check(len(group)==8 and integer(item,'n_objects')==8,'aggregate phantom count '+str(key))
        for gain,wins in [('mean_global_gain','object_global_wins'),('mean_defect_gain','object_defect_wins')]:
            check(equal(number(item,gain),sum(number(o,gain) for o in group)/8),'aggregate gain '+gain+' '+str(key))
            check(integer(item,wins)==sum(number(o,gain)>0 for o in group),'aggregate wins '+wins+' '+str(key))
    primary_group=by_aggregate.get((32,2048,'information_diag'),[])
    primary_calculated=dict(mean_global_gain=sum(number(r,'mean_global_gain') for r in primary_group)/len(primary_group) if primary_group else None,
                            mean_defect_gain=sum(number(r,'mean_defect_gain') for r in primary_group)/len(primary_group) if primary_group else None,
                            object_global_wins=sum(number(r,'mean_global_gain')>0 for r in primary_group),
                            object_defect_wins=sum(number(r,'mean_defect_gain')>0 for r in primary_group))
    p=primary['primary']
    check(p['size']==32 and p['acquired']==2048 and p['policy']=='information_diag' and p['n_objects']==8,'primary identifier')
    for metric,value in primary_calculated.items():
        if value is not None:check(equal(float(p[metric]),value),'primary endpoint '+metric)
    primary_object_map={r['object_id']:r for r in primary.get('object_gains',[])}
    check(len(primary_object_map)==8 and set(primary_object_map)=={x['object_id'] for x in primary_group},'primary per-object IDs')
    for r in primary_group:
        stored=primary_object_map.get(r['object_id'])
        if stored:
            for metric in ('mean_global_gain','mean_defect_gain'):
                check(equal(float(stored[metric]),number(r,metric)),'primary per-object '+metric+' '+r['object_id'])
    manifest_map={r['object_id']:r for r in manifest}
    check(len(manifest_map)==8 and set(manifest_map)=={f'defect_validation_{s}' for s in seeds},'object manifest IDs')
    regenerated=0
    if check_masks:
        from experiment_06b import defect_phantom
        from experiment_07c_preflight import defect_support
        for oid,r in manifest_map.items():
            seed=integer(r,'object_seed');n=integer(r,'size')
            truth,_,desc=defect_phantom(n,int(protocol['factor']),seed)
            mask,info=defect_support(n,int(protocol['factor']),seed)
            check(sha_array(truth)==r['truth_sha256'],'truth hash '+oid)
            check(info['mask_sha256']==r['mask_sha256'],'mask hash '+oid)
            check(int(info['mask_voxels'])==integer(r,'mask_voxels'),'mask size '+oid)
            check(int(desc['n_defects'])==integer(r,'n_defects'),'defect count '+oid)
            regenerated+=1
    check(bool(guard),'guard traces missing')
    for r in guard:
        try: check(isinstance(json.loads(r['trace_json']),dict),'malformed guard trace')
        except (TypeError, ValueError):check(False,'invalid guard JSON')
    model_report=[]
    for k in cp:
        for model in MODELS:
            for policy in POLICIES:
                # Each of eight objects has two acquisition seeds; average within object.
                per_object=[]
                for obj in seeds:
                    cells=[rec.get((32,f'defect_validation_{obj}',model,s+32,policy,k)) for s in protocol['acquisition_seeds']]
                    if any(c is None for c in cells):continue
                    per_object.append((sum(number(c,'gain_vs_coverage') for c in cells)/2,
                                       sum(number(c,'defect_gain_vs_coverage') for c in cells)/2))
                if per_object:
                    model_report.append(dict(acquired=k,model=model,policy=policy,n_objects=len(per_object),
                        mean_global_gain=sum(x[0] for x in per_object)/len(per_object),
                        mean_defect_gain=sum(x[1] for x in per_object)/len(per_object),
                        object_global_wins=sum(x[0]>0 for x in per_object),
                        object_defect_wins=sum(x[1]>0 for x in per_object)))
    return dict(verdict='PASS' if not errors else 'FAIL',checks_performed=checks,error_count=len(errors),errors=errors[:100],
       read_only=True,original_files_modified=False,sha256_files_verified=len(FILES),
       source_modules_checked=len(source_hashes),histories_verified=len(histories),
       checkpoint_rows_verified=len(rec),regenerated_masks=regenerated,
       geometry_order_consistency_by_seed=order_by_seed,
       independently_recalculated_primary=primary_calculated,model_stratified_results=model_report,
       limitations=['Saved-output consistency audit; no independent replay of MART or measurement generation.',
                    'RMSE was recomputed from stored RMSE columns, NOT raw reconstruction arrays (not saved).',
                    'Eight independent synthetic phantoms; forward models and acquisition seeds are repeated conditions, not independent objects.',
                    'The information selector is geometry-based, not measurement-responsive.',
                    'Source hash matching proves available source files agree with the lock, not that every on-disk byte stayed fixed during execution.'])

def sha_array(arr):
    return hashlib.sha256(np.asarray(arr,dtype='<f8').tobytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results-dir',type=Path,required=True)
    ap.add_argument('--protocol-lock',type=Path,default=Path('protocol_08m_frozen.json'))
    ap.add_argument('--source-dir',type=Path,default=Path('.'))
    ap.add_argument('--report',type=Path,required=True)
    ap.add_argument('--check-masks',action='store_true')
    args=ap.parse_args()
    if args.report.resolve().is_relative_to(args.results_dir.resolve()):ap.error('report must be outside original dataset')
    if args.report.exists():ap.error('report exists: refusing overwrite')
    result=audit(args.results_dir,protocol_lock=args.protocol_lock,source_dir=args.source_dir,check_masks=args.check_masks)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('model_stratified_results','errors')},indent=2))
    if result['errors']:
        print('--- errors ---');print('\n'.join(result['errors'][:30]))
    print('--- information policy by forward model (object balanced) ---')
    for row in result['model_stratified_results']:
        if row['policy']=='information_diag':
            print(f"{row['acquired']:4d} {row['model']:11s} global={100*row['mean_global_gain']:+.3f}% defect={100*row['mean_defect_gain']:+.3f}% wins(global/defect)={row['object_global_wins']}/{row['object_defect_wins']} of {row['n_objects']}")
    if result['verdict']!='PASS':raise SystemExit(1)

if __name__=='__main__':main()
