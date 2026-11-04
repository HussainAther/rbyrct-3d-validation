"""RBYRCT-08L: read-only saved-output audit of the 08K exploratory study.

Recalculates reported quantities from serialized data; does not rerun MART.
With --check-masks, independently regenerates synthetic truth/mask from seeds.
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

POLICIES = ('coverage','gradient','incremental_25','information_diag')
MODELS = ('same','independent')
REQUIRED = ('protocol.json','environment.json','acquisition_orders.csv',
            'prefix_reconstructions.csv','object_manifest.csv',
            'object_level_summary.csv','aggregate_summary.csv',
            'guard_batch_audit.csv','run_status.json')
METRICS = [('global_rmse','gain_vs_coverage','mean_global_gain'),
           ('defect_region_rmse','defect_gain_vs_coverage','mean_defect_gain'),
           ('nondefect_rmse','nondefect_gain_vs_coverage','mean_nondefect_gain')]

def rows(path):
    with path.open('r',encoding='utf-8-sig',newline='') as fh:
        return list(csv.DictReader(fh))

def digest_order(ids):
    return hashlib.sha256(np.asarray(ids,dtype='<i8').tobytes()).hexdigest()

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def f(row,name):
    out=float(row[name]);
    if not math.isfinite(out):raise ValueError(f'nonfinite {name}')
    return out

def i(row,name):
    result=int(row[name])
    if str(result)!=str(row[name]).strip():raise ValueError(f'invalid integer {name}')
    return result

def near(actual,expected,atol=2e-11,rtol=2e-10):
    return math.isclose(actual,expected,abs_tol=atol,rel_tol=rtol)

def audit(root, *, check_masks=False, expected_full=True):
    root=Path(root); errors=[]; count=0
    def check(condition,description):
        nonlocal count
        count+=1
        if not condition:errors.append(description)
    for name in REQUIRED+('sha256.json',):
        if not (root/name).is_file():raise FileNotFoundError(root/name)
    status=json.loads((root/'run_status.json').read_text(encoding='utf8'))
    protocol=json.loads((root/'protocol.json').read_text(encoding='utf8'))
    manifests=json.loads((root/'sha256.json').read_text(encoding='utf8'))
    check(status.get('complete') is True,'study not complete')
    check(set(manifests)==set(REQUIRED),'SHA256 manifest file set mismatch')
    for name,hexdigest in manifests.items():
        check(name in REQUIRED and (root/name).is_file() and sha256(root/name)==hexdigest,
              'SHA256 mismatch: '+name)
    check(tuple(protocol['policies'])==POLICIES,'policy protocol mismatch')
    check(set(protocol['models'])==set(MODELS),'forward-model protocol mismatch')
    check(protocol['information_score'].lower().find('geometry-only')>=0,'information score disclosure missing')
    check(tuple(int(x) for x in protocol['sizes'])==(12,32) if expected_full else True,'resolution protocol mismatch')
    csv_orders=rows(root/'acquisition_orders.csv')
    csv_prefix=rows(root/'prefix_reconstructions.csv')
    csv_manifest=rows(root/'object_manifest.csv')
    csv_object=rows(root/'object_level_summary.csv')
    csv_aggregate=rows(root/'aggregate_summary.csv')
    csv_guard=rows(root/'guard_batch_audit.csv')
    order_map=defaultdict(list)
    for r in csv_orders:
        key=(i(r,'size'),r['object_id'],r['model'],r['policy'])
        check(r['policy'] in POLICIES and r['model'] in MODELS,'unexpected order policy or model')
        order_map[key].append((i(r,'acquired_index'),i(r,'ray_id')))
    check(len(order_map)==i(status,'completed_histories'),'acquisition history count mismatch')
    check(len(csv_prefix)==i(status,'completed_reconstructions'),'reconstruction row count mismatch')
    if expected_full:
        check(len(order_map)==32 and len(csv_prefix)==64,'unexpected full-study counts')
    cfg={int(k):v for k,v in protocol['configs'].items()}
    objseeds={int(k):tuple(map(int,v)) for k,v in protocol['object_seeds'].items()}
    organized={}
    for key,pairs in order_map.items():
        n,oid,model,policy=key
        budget=int(cfg[n]['budget'])
        ids=[ray for index,ray in pairs]
        check(len(ids)==budget,'incorrect ray-order length '+str(key))
        check([index for index,ray in pairs]==list(range(1,budget+1)), 'noncontiguous acquisition index '+str(key))
        check(len(set(ids))==len(ids),'duplicate acquired ray '+str(key))
        # Number of candidate rays follows the documented 08K acquisition model.
        check(all(0<=ray<n*n*int(protocol['angles'])*len(protocol['tilts']) for ray in ids),
              'ray out of range '+str(key))
        organized[key]=ids
    # Geometry-only design cannot respond to object, model, or detector values.
    info_groups=defaultdict(list); coverage_groups=defaultdict(list)
    for (n,oid,model,policy),ids in organized.items():
        if policy=='information_diag':info_groups[n].append((oid,model,ids))
        if policy=='coverage':coverage_groups[n].append((oid,model,ids))
    info_identical={};coverage_identical={}
    for n in sorted(cfg):
        info=info_groups[n];coverage=coverage_groups[n]
        check(bool(info),'information acquisitions missing at '+str(n))
        check(bool(coverage),'coverage acquisitions missing at '+str(n))
        info_identical[n]=len({digest_order(x[2]) for x in info})==1
        coverage_identical[n]=len({digest_order(x[2]) for x in coverage})==1
        check(info_identical[n],f'geometry-only information orders differ across object/models at {n}^3')
        check(coverage_identical[n],f'coverage orders differ across object/models at {n}^3')
        if info and coverage:
            warm=int(cfg[n]['warm'])
            check(info[0][2][:warm]==coverage[0][2][:warm],f'information warm prefix mismatch at {n}^3')
    prefmap={}
    for r in csv_prefix:
        key=(i(r,'size'),r['object_id'],r['model'],r['policy'],i(r,'acquired'))
        check(key not in prefmap,'duplicate reconstruction record '+str(key))
        prefmap[key]=r
        history=organized.get(key[:4])
        if history is None:
            check(False,'reconstruction has no ray order '+str(key));continue
        n,oid,model,policy,k=key
        check(k in cfg[n]['checkpoints'],'unexpected checkpoint '+str(key))
        check(digest_order(history[:k])==r['order_sha256'],'ray fingerprint mismatch '+str(key))
        cov=organized.get((n,oid,model,'coverage'))
        if cov is not None:
            check(len(set(history[:k])&set(cov[:k]))==i(r,'shared_with_coverage'),
                  'coverage-overlap mismatch '+str(key))
        check(i(r,'object_seed') in objseeds[n],'reconstruction object seed not registered '+str(key))
        check(i(r,'acquisition_seed')==i(protocol,'acquisition_seed')+n,'acquisition seed mismatch '+str(key))
        for m,_,_ in METRICS:
            check(f(r,m)>=0,'negative RMSE '+str(key))
        check(f(r,'selection_seconds')>=0 and f(r,'reconstruction_seconds')>=0,'negative timing '+str(key))
    # Full expected Cartesian coverage.
    expected_keys={(n,f'defect_dev_{seed}',model,policy,int(k))
                   for n in cfg for seed in objseeds[n] for model in protocol['models']
                   for policy in POLICIES for k in cfg[n]['checkpoints']}
    check(set(prefmap)==expected_keys,'missing/unexpected reconstruction rows')
    for key,r in prefmap.items():
        base=prefmap.get(key[:3]+('coverage',key[4]))
        if base is None:continue
        for metric,gain,_ in METRICS:
            predicted=(f(base,metric)-f(r,metric))/max(f(base,metric),1e-12)
            check(near(f(r,gain),predicted),'incorrect paired gain '+gain+' '+str(key))
            if key[3]=='coverage':check(near(f(r,gain),0),'nonzero coverage gain '+str(key))
    # Object-level means calculated independently from raw paired records.
    by_obj=defaultdict(list)
    for key,r in prefmap.items():by_obj[(key[0],key[1],key[4],key[3])].append(r)
    objmap={}
    for r in csv_object:
        key=(i(r,'size'),r['object_id'],i(r,'acquired'),r['policy'])
        check(key not in objmap,'duplicate object summary '+str(key))
        objmap[key]=r
    check(set(objmap)==set(by_obj),'object summary coverage mismatch')
    for key,group in by_obj.items():
        if key not in objmap:continue
        item=objmap[key]
        check(i(item,'n_conditions')==len(group),'object summary condition count '+str(key))
        for metric,gain,col in METRICS:
            predicted=sum(f(r,gain) for r in group)/len(group)
            check(near(f(item,col),predicted),'object summary mismatch '+col+' '+str(key))
    # Per-checkpoint aggregate is an equally-weighted mean over objects.
    by_agg=defaultdict(list)
    for key,r in objmap.items():by_agg[(key[0],key[2],key[3])].append(r)
    aggmap={}
    for r in csv_aggregate:
        key=(i(r,'size'),i(r,'acquired'),r['policy'])
        check(key not in aggmap,'duplicate aggregate '+str(key));aggmap[key]=r
    check(set(by_agg)==set(aggmap),'aggregate summary coverage mismatch')
    for key,group in by_agg.items():
        if key not in aggmap:continue
        item=aggmap[key]
        check(i(item,'n_objects')==len(group),'object replication count '+str(key))
        for gain,col in (('mean_global_gain','object_global_wins'),('mean_defect_gain','object_defect_wins')):
            actual=sum(f(r,gain) for r in group)/len(group)
            check(near(f(item,gain),actual),'aggregated mean mismatch '+gain+' '+str(key))
            check(i(item,col)==sum(f(r,gain)>0 for r in group),'object wins mismatch '+str(key))
    manifest_map={(i(r,'size'),r['object_id']):r for r in csv_manifest}
    check(len(manifest_map)==sum(len(v) for v in objseeds.values()),'object manifest size mismatch')
    for (n,oid),r in manifest_map.items():
        seed=i(r,'object_seed')
        check(seed in objseeds[n] and oid==f'defect_dev_{seed}','object manifest ID/seed mismatch')
        check(i(r,'mask_voxels')>0,'empty defect mask')
        check(len(r['mask_sha256'])==64 and len(r['truth_sha256'])==64,'malformed truth/mask hash')
    check(len(csv_guard)>0,'guard audit empty')
    for r in csv_guard:
        try:
            t=json.loads(r['trace_json'])
            check(isinstance(t,dict),'bad guard trace')
        except (TypeError,ValueError):check(False,'invalid guard trace JSON')
    mask_checks=0
    if check_masks:
        # Independent regeneration of truth/mask; never used by the selector.
        try:
            from experiment_06b import defect_phantom
            from experiment_07c_preflight import defect_support
        except ImportError as exc:
            raise RuntimeError('mask regeneration requires the existing 06B and 07C preflight modules') from exc
        for (n,oid),r in manifest_map.items():
            seed=i(r,'object_seed')
            truth,_,desc=defect_phantom(n,int(protocol['factor']),seed)
            mask,info=defect_support(n,int(protocol['factor']),seed)
            actual_truth=hashlib.sha256(np.asarray(truth,dtype='<f8').tobytes()).hexdigest()
            check(actual_truth==r['truth_sha256'],'truth regeneration hash mismatch '+oid)
            check(info['mask_sha256']==r['mask_sha256'],'mask regeneration hash mismatch '+oid)
            check(int(info['mask_voxels'])==i(r,'mask_voxels'),'mask voxel count mismatch '+oid)
            check(int(desc['n_defects'])==i(r,'n_defects'),'defect count mismatch '+oid)
            mask_checks+=1
    # Model-specific descriptive results, reconstructed from individual object means.
    condition_report=[]
    for n in sorted(cfg):
        for k in cfg[n]['checkpoints']:
            for model in protocol['models']:
                for policy in POLICIES:
                    objs=[]
                    for seed in objseeds[n]:
                        key=(n,f'defect_dev_{seed}',model,policy,k)
                        if key in prefmap:objs.append(prefmap[key])
                    if not objs:continue
                    condition_report.append(dict(size=n,acquired=k,model=model,policy=policy,n_objects=len(objs),
                        mean_global_gain=sum(f(r,'gain_vs_coverage') for r in objs)/len(objs),
                        mean_defect_gain=sum(f(r,'defect_gain_vs_coverage') for r in objs)/len(objs),
                        global_wins=sum(f(r,'gain_vs_coverage')>0 for r in objs),
                        defect_wins=sum(f(r,'defect_gain_vs_coverage')>0 for r in objs)))
    return dict(verdict='PASS' if not errors else 'FAIL',checks_performed=count,error_count=len(errors),errors=errors,
                read_only=True,original_files_modified=False,
                sha256_files_verified=len(manifests),histories_verified=len(order_map),checkpoint_rows_verified=len(prefmap),
                regenerated_masks=mask_checks,information_orders_identical_by_size={str(k):v for k,v in info_identical.items()},
                coverage_orders_identical_by_size={str(k):v for k,v in coverage_identical.items()},
                model_stratified_results=condition_report,
                limitations=['Saved-output verification, not independent replay of MART physics or measurement generation.',
                   'Information selection reads geometric ray IDs and projection geometry, not detector intensities; this is geometry-based design, not measurement-adaptive feedback.',
                   'Only two independent objects per resolution; matched and independent models share each object.',
                   '08K is exploratory and was observed before any future prospective validation.',
                   'Mask regeneration is post-hoc evaluation and does not enter acquisition.'])

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results-dir',type=Path,required=True)
    ap.add_argument('--report',type=Path,required=True)
    ap.add_argument('--check-masks',action='store_true')
    args=ap.parse_args()
    if args.report.resolve().is_relative_to(args.results_dir.resolve()):
        ap.error('report must be outside the original 08K directory')
    if args.report.exists():ap.error('refusing to overwrite previous report')
    result=audit(args.results_dir,check_masks=args.check_masks)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    compact={k:v for k,v in result.items() if k!='model_stratified_results'}
    print(json.dumps(compact,indent=2))
    print('--- model-stratified information policy ---')
    for r in result['model_stratified_results']:
        if r['policy']=='information_diag':
            print(f"{r['size']}^3 {r['acquired']:4d} {r['model']:11s} global={100*r['mean_global_gain']:+.3f}% defect={100*r['mean_defect_gain']:+.3f}% wins={r['defect_wins']}/{r['n_objects']}")
    if result['verdict']!='PASS':raise SystemExit(1)

if __name__=='__main__':main()
