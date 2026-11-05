"""08AA: independent, read-only saved-output and provenance audit of RBYRCT-08Z.

No import from experiment_08z. This audits saved CSV arithmetic and acquisition
fingerprints; it cannot independently reconstruct unsaved MART volumes.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import numpy as np

POLICIES = ('coverage','information_diag','information_full','full_spatial_balanced')
CHECKPOINTS = (144,288)
SEEDS = (910201,910202,910203,910204)
MODELS = ('same','independent')
SIZE=12
BUDGET=288
RAYS=SIZE*SIZE*4*3


def read_csv(path):
    with Path(path).open('r',encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def emit_csv(path,rows):
    if not rows: raise ValueError('no output rows')
    with Path(path).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)


def sha_order(seq):
    return hashlib.sha256(np.asarray(seq,dtype='<i8').tobytes()).hexdigest()


def close(a,b,atol=1e-10,rtol=1e-9):
    return math.isclose(float(a),float(b),rel_tol=rtol,abs_tol=atol)


def sha_manifest(root,errors,tag):
    p=root/'sha256.json'
    if not p.is_file():
        errors.append(f'{tag}: missing SHA-256 manifest');return 0
    try: obj=json.loads(p.read_text(encoding='utf-8'))
    except Exception as exc:
        errors.append(f'{tag}: invalid manifest: {exc}');return 0
    if not isinstance(obj,dict) or not obj:
        errors.append(f'{tag}: empty manifest');return 0
    count=0
    for name,digest in obj.items():
        if Path(name).name!=name or not isinstance(digest,str) or len(digest)!=64:
            errors.append(f'{tag}: invalid manifest entry {name!r}');continue
        q=root/name
        if not q.is_file() or hashlib.sha256(q.read_bytes()).hexdigest()!=digest:
            errors.append(f'{tag}: changed/missing archive file: {name}')
        else:count+=1
    return count


def orders_from_csv(root,errors):
    rows=read_csv(root/'acquisition_orders.csv')
    expected=len(POLICIES)*BUDGET
    if len(rows)!=expected:errors.append(f'order rows: {len(rows)} expected {expected}')
    groups={p:[] for p in POLICIES}
    for r in rows:
        if r['policy'] not in groups:errors.append('unknown order policy');continue
        groups[r['policy']].append(r)
    result={}
    for p,group in groups.items():
        try:
            vals=sorted((int(r['acquired_index']),int(r['ray_id']),r['order_sha256']) for r in group)
            idx=[v[0] for v in vals];rays=[v[1] for v in vals]
            if idx!=list(range(1,BUDGET+1)) or len(set(rays))!=BUDGET or any(v<0 or v>=RAYS for v in rays):
                errors.append(f'{p}: invalid order indices/IDs')
            digest=sha_order(rays)
            if any(v[2]!=digest for v in vals):errors.append(f'{p}: SHA-256 mismatch')
            result[p]=rays
        except (ValueError,KeyError) as exc:errors.append(f'{p}: invalid order content {exc}')
    return result


def check_rows(rows,orders,errors):
    expected={(f'defect_dev_{seed}',m,p,k) for seed in SEEDS for m in MODELS for p in POLICIES for k in CHECKPOINTS}
    actual={}
    for r in rows:
        try:key=(r['object_id'],r['model'],r['policy'],int(r['acquired']))
        except (ValueError,KeyError) as exc:errors.append(f'invalid reconstruction identity {exc}');continue
        if key in actual:errors.append(f'duplicate reconstruction row {key}')
        actual[key]=r
    for key in sorted(expected-set(actual)):errors.append(f'missing reconstruction row {key}')
    for key in sorted(set(actual)-expected):errors.append(f'unexpected reconstruction row {key}')
    checks=0
    for key in expected & set(actual):
        r=actual[key];oid,model,p,k=key
        for field in ('global_rmse','defect_region_rmse','nondefect_rmse'):
            try:
                x=float(r[field]);checks+=1
                if not math.isfinite(x) or x<0:errors.append(f'{key}: invalid {field}')
            except (ValueError,KeyError):errors.append(f'{key}: missing {field}')
        if p in orders:
            checks+=1
            if r.get('order_sha256')!=sha_order(orders[p][:k]):errors.append(f'{key}: prefix fingerprint mismatch')
        ref=actual.get((oid,model,'coverage',k))
        if ref:
            for field,gain in (('global_rmse','gain_vs_coverage'),('defect_region_rmse','defect_gain_vs_coverage'),('nondefect_rmse','nondefect_gain_vs_coverage')):
                try:
                    expected_gain=(float(ref[field])-float(r[field]))/max(float(ref[field]),1e-12)
                    checks+=1
                    if not close(r[gain],expected_gain):errors.append(f'{key}: wrong {gain}')
                except (ValueError,KeyError) as exc:errors.append(f'{key}: invalid gain {exc}')
    return actual,checks


def objects_from_records(records):
    out={}
    for seed in SEEDS:
        oid=f'defect_dev_{seed}'
        for k in CHECKPOINTS:
            for p in POLICIES:
                subset=[records[(oid,m,p,k)] for m in MODELS]
                out[(oid,k,p)]={
                    'object_id':oid,'acquired':k,'policy':p,'n_models':len(MODELS),
                    'mean_global_gain':float(np.mean([float(r['gain_vs_coverage']) for r in subset])),
                    'mean_defect_gain':float(np.mean([float(r['defect_gain_vs_coverage']) for r in subset])),
                    'mean_global_rmse':float(np.mean([float(r['global_rmse']) for r in subset])),
                    'mean_defect_rmse':float(np.mean([float(r['defect_region_rmse']) for r in subset]))}
    return out


def check_object_tables(root,objs,errors):
    checks=0
    table=read_csv(root/'object_level_summary.csv')
    if len(table)!=len(objs):errors.append('object summary row count mismatch')
    seen=set()
    for row in table:
        try:key=(row['object_id'],int(row['acquired']),row['policy'])
        except (ValueError,KeyError):errors.append('bad object summary identity');continue
        if key in seen:errors.append(f'duplicate object summary {key}')
        seen.add(key)
        if key not in objs:errors.append(f'extraneous object summary {key}');continue
        for field in ('n_models','mean_global_gain','mean_defect_gain','mean_global_rmse','mean_defect_rmse'):
            checks+=1
            if not close(row[field],objs[key][field]):errors.append(f'{key}: object summary {field}')
    if seen!=set(objs):errors.append('missing object summary entries')
    aggregates={}
    for k in CHECKPOINTS:
        for p in POLICIES:
            z=[objs[(f'defect_dev_{seed}',k,p)] for seed in SEEDS]
            aggregates[(k,p)]={
                'n_objects':len(z),'mean_global_gain':float(np.mean([v['mean_global_gain'] for v in z])),
                'mean_defect_gain':float(np.mean([v['mean_defect_gain'] for v in z])),
                'object_global_wins':sum(v['mean_global_gain']>0 for v in z),
                'object_defect_wins':sum(v['mean_defect_gain']>0 for v in z)}
    seen=set();table=read_csv(root/'aggregate_summary.csv')
    if len(table)!=len(aggregates):errors.append('aggregate row count mismatch')
    for row in table:
        try:key=(int(row['acquired']),row['policy'])
        except (KeyError,ValueError):errors.append('bad aggregate identity');continue
        if key in seen:errors.append(f'duplicate aggregate {key}')
        seen.add(key)
        if key not in aggregates:errors.append(f'extra aggregate {key}');continue
        checks+=1
        if int(row['size'])!=SIZE:errors.append(f'{key}: size mismatch')
        for field,value in aggregates[key].items():
            checks+=1
            if not close(row[field],value):errors.append(f'{key}: aggregate {field}')
    if seen!=set(aggregates):errors.append('missing aggregate entries')
    expected_pairs={(f'defect_dev_{seed}',k) for seed in SEEDS for k in CHECKPOINTS}
    seen=set();table=read_csv(root/'spatial_vs_full_object.csv')
    if len(table)!=len(expected_pairs):errors.append('spatial-vs-full row count mismatch')
    for row in table:
        try:key=(row['object_id'],int(row['acquired']))
        except (KeyError,ValueError):errors.append('bad comparison identity');continue
        if key in seen:errors.append(f'duplicate comparison {key}')
        seen.add(key)
        if key not in expected_pairs:errors.append(f'extra comparison {key}');continue
        oid,k=key;s=objs[(oid,k,'full_spatial_balanced')];f=objs[(oid,k,'information_full')]
        expectations={
            'spatial_minus_full_global_rmse':s['mean_global_rmse']-f['mean_global_rmse'],
            'spatial_minus_full_defect_rmse':s['mean_defect_rmse']-f['mean_defect_rmse'],
            'spatial_better_global':int(s['mean_global_rmse']<f['mean_global_rmse']),
            'spatial_better_defect':int(s['mean_defect_rmse']<f['mean_defect_rmse'])}
        for field,value in expectations.items():
            checks+=1
            if not close(row[field],value):errors.append(f'{key}: comparison {field}')
    if seen!=expected_pairs:errors.append('missing comparison entries')
    return checks,aggregates


def gini(A,seq):
    rows=A[np.asarray(seq,dtype=int)].tocsr().copy();rows.data=np.abs(rows.data)
    w=np.asarray(rows.sum(axis=0)).ravel();w=np.sort(w)
    n=len(w)
    return float(2*np.dot(np.arange(1,n+1),w)/(n*w.sum())-(n+1)/n)


def entropy(indices,bins):
    vals=np.bincount(np.asarray(indices,dtype=int),minlength=bins).astype(float)
    vals=vals[vals>0];prob=vals/vals.sum()
    return float(-np.sum(prob*np.log(prob))/np.log(bins))


def check_geometry(root,orders,errors,geometry=True):
    rows=read_csv(root/'geometry_summary.csv')
    expected={(p,k) for p in POLICIES for k in CHECKPOINTS}
    seen=set();checks=0
    if len(rows)!=len(expected):errors.append('geometry row count mismatch')
    A=None
    if geometry:
        from experiment_04b import system_matrix
        from experiment_04g import TILTS
        A=system_matrix(SIZE,4,TILTS).tocsr()
        if A.shape!=(RAYS,SIZE**3):errors.append('unexpected source geometry shape')
    for r in rows:
        try:key=(r['policy'],int(r['acquired']))
        except (KeyError,ValueError):errors.append('invalid geometry row');continue
        if key in seen:errors.append(f'duplicate geometry row {key}')
        seen.add(key)
        if key not in expected:errors.append(f'extra geometry row {key}');continue
        p,k=key
        if p not in orders:continue
        seq=orders[p][:k]
        expected_entropy=entropy(np.asarray(seq)%(SIZE*SIZE),SIZE*SIZE)
        expected_bins=len(set(int(ray)%(SIZE*SIZE) for ray in seq))
        expected_overlap=len(set(seq)&set(orders['information_full'][:k]))/k
        vals={'detector_entropy':expected_entropy,'detector_bins_visited':expected_bins,'overlap_with_full':expected_overlap}
        if A is not None:
            vals['weighted_sensitivity_gini']=gini(A,seq)
            vals['visited_voxel_fraction']=float(np.mean(np.asarray((A[seq].copy().sign()!=0).sum(axis=0)).ravel()>0))
        for field,value in vals.items():
            checks+=1
            if not close(r[field],value):errors.append(f'{key}: geometry {field}')
    if seen!=expected:errors.append('missing geometry entries')
    return checks


def inspect_manifest(root,errors):
    rows=read_csv(root/'object_manifest.csv')
    if len(rows)!=len(SEEDS):errors.append('object manifest length mismatch')
    seen=set();checks=0
    for r in rows:
        try:seed=int(r['seed']);oid=r['object_id']
        except (KeyError,ValueError):errors.append('invalid object manifest row');continue
        if seed in seen:errors.append('duplicate object manifest seed')
        seen.add(seed)
        checks+=1
        if oid!=f'defect_dev_{seed}' or seed not in SEEDS:errors.append(f'wrong object manifest seed {seed}')
        for h in ('truth_sha256','mask_sha256'):
            checks+=1
            if len(r.get(h,''))!=64:errors.append(f'object {seed}: invalid {h}')
    if seen!=set(SEEDS):errors.append('missing object manifest seeds')
    return checks


def audit(complete_dir,failed_dir,output_dir,geometry=True,preflight_dir=None):
    root=Path(complete_dir);earlier=Path(failed_dir) if failed_dir else None;out=Path(output_dir)
    if out.exists():raise FileExistsError('refusing to overwrite prior audit')
    errors=[];checks=0
    if not root.is_dir():raise FileNotFoundError(root)
    if earlier and not earlier.is_dir():raise FileNotFoundError(earlier)
    status=json.loads((root/'run_status.json').read_text(encoding='utf8'))
    checks+=3
    if status.get('complete') is not True or status.get('completed_reconstructions')!=64 or status.get('expected_reconstructions')!=64:
        errors.append('completed archive run status invalid')
    protocol=json.loads((root/'protocol.json').read_text(encoding='utf8'))
    checks+=1
    if protocol.get('spatial_novelty_weight')!=0.25:errors.append('spatial alpha protocol mismatch')
    verified=sha_manifest(root,errors,'completed');checks+=verified
    orders=orders_from_csv(root,errors)
    preflight_verified=False
    if preflight_dir is not None:
        pf=json.loads((Path(preflight_dir)/'preflight.json').read_text(encoding='utf8'))
        checks+=5
        if (pf.get('complete') is not True or pf.get('alpha')!=0.25
            or pf.get('size')!=SIZE or pf.get('budget')!=BUDGET
            or pf.get('alpha_zero_equals_full') is not True
            or pf.get('intervention_deterministic') is not True):
            errors.append('invalid archived 08Z engineering preflight')
        if any(pf.get('order_sha256',{}).get(p)!=sha_order(order) for p,order in orders.items()):
            errors.append('preflight acquisition order does not match saved reconstruction histories')
        if not all(pf.get('spatial_gini_reduced_at_checkpoints',{}).get(str(k)) is True for k in CHECKPOINTS):
            errors.append('preflight did not pass spatial Gini direction gates')
        preflight_verified=True
    if len(orders)==len(POLICIES):
        records=read_csv(root/'prefix_reconstructions.csv')
        keyed,n=check_rows(records,orders,errors);checks+=n
        if len(keyed)==64:
            objects=objects_from_records(keyed)
            n,aggregates=check_object_tables(root,objects,errors);checks+=n
        else:aggregates={}
        checks+=check_geometry(root,orders,errors,geometry=geometry)
    else:aggregates={}
    checks+=inspect_manifest(root,errors)
    comparisons=[];first_sha_count=0
    if earlier:
        before=json.loads((earlier/'run_status.json').read_text(encoding='utf8'))
        checks+=2
        if before.get('complete') is not False or before.get('completed_reconstructions')!=64:
            errors.append('first-run status inconsistent with recorded reporting failure')
        # First run crashed before geometry/report finalization; it need not have a sha256.json.
        for name in ('protocol.json','acquisition_orders.csv','prefix_reconstructions.csv',
                     'object_manifest.csv','object_level_summary.csv','aggregate_summary.csv','spatial_vs_full_object.csv'):
            left=earlier/name;right=root/name
            checks+=1
            if not left.is_file() or not right.is_file():
                errors.append(f'first-versus-second file missing: {name}')
            elif name in ('prefix_reconstructions.csv',):
                a=read_csv(left);b=read_csv(right)
                ignore={'reconstruction_seconds','selection_seconds'}
                same=len(a)==len(b) and all({k:v for k,v in x.items() if k not in ignore}==
                    {k:v for k,v in y.items() if k not in ignore} for x,y in zip(a,b))
                comparisons.append({'file':name,'agreement':'PASS' if same else 'FAIL','mode':'CSV ignoring timing fields'})
                if not same:errors.append('first/second reconstruction CSV mismatch excluding timings')
            else:
                same=left.read_bytes()==right.read_bytes()
                comparisons.append({'file':name,'agreement':'PASS' if same else 'FAIL','mode':'byte-identical'})
                if not same:errors.append(f'first/second changed file: {name}')
    out.mkdir(parents=True)
    summary=[]
    for (k,p),z in sorted(aggregates.items()):
        summary.append(dict(acquired=k,policy=p,mean_global_gain=z['mean_global_gain'],
            mean_defect_gain=z['mean_defect_gain'],object_global_wins=z['object_global_wins'],
            object_defect_wins=z['object_defect_wins']))
    if summary:emit_csv(out/'independently_recomputed_summary.csv',summary)
    if comparisons:emit_csv(out/'first_vs_second.csv',comparisons)
    report={'audit':'08AA independent 08Z saved-output audit','complete':not errors,
        'checks_performed':checks,'verified_sha256_files':verified,
        'reconstruction_rows_audited':64,'failed_attempt_compared':bool(earlier),
        'geometry_recomputed':geometry,'preflight_verified':preflight_verified,'errors':errors,
        'limitations':['Saved CSVs do not contain reconstructed voxel arrays: this is NOT an independent MART replay.',
            'Saved data arithmetic can be independently checked, but voxel-wise RMSE and masks cannot be confirmed from CSV alone.',
            'Using the repository system_matrix for geometry is not an independent forward-projector implementation.',
            'Four synthetic objects are exploratory; same and independent models are paired conditions, not eight independent phantoms.',
            'No new acquisitions or reconstruction runs; original archives are read-only.']}
    (out/'audit_report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    if errors:raise RuntimeError(f'08AA saved-output audit FAILED: {len(errors)} mismatches; see {out}')
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--complete-dir',required=True)
    ap.add_argument('--failed-dir',required=True)
    ap.add_argument('--output-dir',required=True)
    ap.add_argument('--preflight-dir',required=True,help='original 08Z engineering preflight directory')
    ap.add_argument('--skip-geometry',action='store_true',help='for isolated CI with no repository projector; not for final audit')
    args=ap.parse_args()
    audit(args.complete_dir,args.failed_dir,args.output_dir,geometry=not args.skip_geometry,preflight_dir=args.preflight_dir)

if __name__=='__main__': main()
