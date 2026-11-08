"""07D: Read-only, independent 07C2 saved-output audit and guard-scale diagnostic.

No experimental acquisition/reconstruction is rerun. Geometric sensitivity is
post-hoc and does not claim to replay the original candidate pools.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math, struct, sys
from collections import defaultdict, Counter
from pathlib import Path
from statistics import mean

POLICIES=('coverage','gradient','guarded_05')
BUDGETS=(1024,2048,4096)
FILES=('acquisition_orders.csv','environment.txt','guard_batch_audit.csv',
       'matched_cases.csv','matrix_profile.json','object_level_summary.csv',
       'object_manifest.csv','prefix_reconstructions.csv','protocol.json',
       'run_status.json','study_status.json','threshold_crossings.csv','timing.csv')

class Checks:
    def __init__(self):self.n=0;self.errors=[];self.warnings=[]
    def ok(self, condition, msg):
        self.n+=1
        if not condition:self.errors.append(msg)
    def warn(self,msg):self.warnings.append(msg)

def loadcsv(root,name):
    with (root/name).open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))

def number(v):
    x=float(v)
    if not math.isfinite(x):raise ValueError('nonfinite number')
    return x

def close(a,b):return math.isclose(number(a),number(b),rel_tol=1e-9,abs_tol=1e-11)

def fingerprint(ids):
    h=hashlib.sha256()
    for x in ids:h.update(struct.pack('<q',int(x)))
    return h.hexdigest()

def key(r):return(r['object_id'],r['model'],str(r['acquisition_seed']),r['policy'])

def verify_manifest(root,c):
    lines=(root/'run_manifest.sha256').read_text(encoding='utf-8').splitlines()
    found=set()
    for line in lines:
        split=line.split('  ',1)
        if len(split)!=2:
            c.ok(False,'malformed manifest entry');continue
        digest,name=split
        c.ok(name not in found,'duplicate manifest name '+name)
        found.add(name)
        c.ok(name in FILES,'unexpected or unsafe manifest filename '+name)
        if name not in FILES:continue
        data=(root/name).read_bytes()
        c.ok(hashlib.sha256(data).hexdigest()==digest,'manifest checksum mismatch '+name)
    c.ok(found==set(FILES),'manifest file set differs from frozen outputs')

def gain_from_rmse(baseline,adaptive):
    baseline=number(baseline);adaptive=number(adaptive)
    if baseline<=0 or adaptive<0:raise ValueError('invalid nonnegative RMSE')
    return (baseline-adaptive)/baseline

def weighted_rmse_identity(global_rmse,defect_rmse,nondefect_rmse,n_defect,n_voxels):
    return (n_defect*number(defect_rmse)**2+(n_voxels-n_defect)*number(nondefect_rmse)**2)/n_voxels

def audit(root,check_masks=False,geometry=False):
    root=Path(root);c=Checks();stats={}
    for f in (*FILES,'run_manifest.sha256'):
        if not (root/f).is_file():raise FileNotFoundError(f'Missing frozen output: {root/f}')
    verify_manifest(root,c)
    p=json.loads((root/'protocol.json').read_text(encoding='utf-8'))
    old=p.get('protocol_sha256')
    expected=hashlib.sha256(json.dumps({k:v for k,v in p.items() if k!='protocol_sha256'},sort_keys=True).encode()).hexdigest()
    c.ok(old==expected,'protocol checksum mismatch')
    c.ok(not p.get('allow_test_scale',False),'not frozen production protocol')
    for field,expected in [('size',32),('budget',4096),('checkpoints',[1024,2048,4096]),
                           ('primary_checkpoint',2048),('warm',64),('batch',32),('pool',16),
                           ('final_epochs',16),('provisional_epochs',2),('eta',0.05),
                           ('policies',list(POLICIES)),('models',['same','independent']),
                           ('acquisition_seeds',[104729,130363])]:
        c.ok(p.get(field)==expected,'frozen protocol mismatch: '+field)
    seeds=[2077001+7919*i for i in range(8)]
    c.ok(p.get('object_seeds')==seeds,'frozen object seeds mismatch')
    completion=json.loads((root/'run_status.json').read_text())
    c.ok(completion.get('complete') is True,'study run was incomplete')
    status=json.loads((root/'study_status.json').read_text())
    c.ok(status.get('pass_engineering_checks') is True,'generator engineering flag false')
    orders=loadcsv(root,'acquisition_orders.csv')
    rows=loadcsv(root,'prefix_reconstructions.csv')
    object_summary=loadcsv(root,'object_level_summary.csv')
    manifest=loadcsv(root,'object_manifest.csv')
    auditrows=loadcsv(root,'guard_batch_audit.csv')
    matched=loadcsv(root,'matched_cases.csv')
    thresholds=loadcsv(root,'threshold_crossings.csv')
    timings=loadcsv(root,'timing.csv')
    expected_count={'orders':393216,'rows':288,'objects':24,'manifests':8,'matched':96,'thresholds':96,'timings':288,'guards':4032}
    for name,data in [('orders',orders),('rows',rows),('objects',object_summary),('manifests',manifest),('matched',matched),('thresholds',thresholds),('timings',timings),('guards',auditrows)]:
        c.ok(len(data)==expected_count[name],f'wrong row count in {name}: {len(data)}')
    c.ok(status.get('acquisition_histories')==96 and status.get('reconstructions')==288 and status.get('ray_order_rows')==393216,'status counts incorrect')
    c.ok(completion.get('completed_histories')==96 and completion.get('completed_reconstructions')==288,'run completion counts wrong')
    objects={x['object_id']:x for x in manifest}
    c.ok(len(objects)==8 and set(objects)=={f'localized_defect_{s}' for s in seeds},'object manifest IDs wrong')
    for oid,x in objects.items():
        c.ok(int(x['mask_voxels'])>0 and int(x['mask_voxels'])<32768, 'invalid mask size '+oid)
        c.ok(close(x['mask_fraction'],int(x['mask_voxels'])/32768),'wrong mask fraction '+oid)
        c.ok(len(x['mask_sha256'])==64 and len(x['coarse_sha256'])==64 and len(x['fine_sha256'])==64,'object SHA-256 missing '+oid)
    if check_masks:
        try:
            from experiment_07c_preflight import defect_support
            from experiment_06b import defect_phantom
            import numpy as np
            for oid,x in objects.items():
                seed=int(x['object_seed'])
                mask, info=defect_support(32,2,seed,relative_threshold=.08,absolute_threshold=.01)
                truth,fine,desc=defect_phantom(32,2,seed)
                c.ok(info['mask_sha256']==x['mask_sha256'] and info['mask_voxels']==int(x['mask_voxels']),'regenerated defect mask mismatch '+oid)
                c.ok(hashlib.sha256(np.asarray(truth,dtype='<f8').tobytes()).hexdigest()==x['coarse_sha256'],'regenerated coarse phantom mismatch '+oid)
                c.ok(hashlib.sha256(np.asarray(fine,dtype='<f8').tobytes()).hexdigest()==x['fine_sha256'],'regenerated fine phantom mismatch '+oid)
                c.ok(desc['n_defects']==int(x['n_defects']),'regenerated defect count mismatch '+oid)
            stats['mask_regeneration']='PASS'
        except Exception as e:c.ok(False,'mask regeneration unavailable/failed: '+repr(e))
    grouped=defaultdict(list)
    for r in orders:
        try:grouped[key(r)].append((int(r['acquired_index']),int(r['ray_id'])))
        except Exception as e:c.ok(False,'bad acquisition CSV row: '+repr(e))
    expected_keys={(oid,m,str(s),policy) for oid in objects for m in ('same','independent') for s in (104729,130363) for policy in POLICIES}
    c.ok(set(grouped)==expected_keys,'acquisition Cartesian keys incomplete')
    raylists={}
    for k,g in grouped.items():
        ids=[j for _,j in g]
        c.ok(len(g)==4096 and [i for i,_ in g]==list(range(1,4097)),'acquisition index/order wrong '+str(k))
        c.ok(len(set(ids))==4096 and all(0<=v<12288 for v in ids),'invalid or repeated ray '+str(k))
        raylists[k]=ids
    for oid in objects:
        for model in ('same','independent'):
            for seed in ('104729','130363'):
                refs=[raylists.get((oid,model,seed,pol),[]) for pol in POLICIES]
                c.ok(all(len(r)>=64 for r in refs) and refs[0][:64]==refs[1][:64]==refs[2][:64], 'warm prefix differs '+oid+model+seed)
    rowmap={}
    for r in rows:
        try:
            k=(*key(r),int(r['acquired']))
            c.ok(k not in rowmap,'duplicate reconstruction '+str(k))
            rowmap[k]=r
            c.ok(k[-1] in BUDGETS,'unexpected budget '+str(k))
            for name in ('global_rmse','defect_region_rmse','nondefect_rmse'):
                c.ok(number(r[name])>0,'nonpositive RMSE '+str(k)+name)
            nmask=int(objects[r['object_id']]['mask_voxels'])
            mse=weighted_rmse_identity(r['global_rmse'],r['defect_region_rmse'],r['nondefect_rmse'],nmask,32768)
            c.ok(close(number(r['global_rmse'])**2,mse),'global/defect/nondefect RMSE inconsistent '+str(k))
            sequence=raylists.get(key(r),[])
            c.ok(fingerprint(sequence[:k[-1]])==r['ray_order_sha256'],'ray prefix hash mismatch '+str(k))
        except Exception as e:c.ok(False,'bad reconstruction row: '+repr(e))
    expected_rows={(*k,b) for k in expected_keys for b in BUDGETS}
    c.ok(set(rowmap)==expected_rows,'reconstruction records do not cover full protocol')
    gain_rows=defaultdict(list); summary={}
    for k,r in rowmap.items():
        oid,model,seed,policy,budget=k
        ref=rowmap.get((oid,model,seed,'coverage',budget))
        if ref is None:continue
        for metric,gfield in [('global_rmse','gain_vs_coverage'),('defect_region_rmse','defect_gain_vs_coverage'),('nondefect_rmse','nondefect_gain_vs_coverage')]:
            val=gain_from_rmse(ref[metric],r[metric])
            c.ok(close(val,r[gfield]),'paired RMSE gain incorrect '+str(k)+' '+gfield)
            gain_rows[(oid,policy,budget,model,gfield)].append(val)
        common=len(set(raylists[key(r)][:budget]) & set(raylists[(oid,model,seed,'coverage')][:budget]))
        c.ok(int(r['shared_with_coverage'])==common,'shared ray count incorrect '+str(k))
        c.ok(close(r['relative_forward_mismatch'],ref['relative_forward_mismatch']),'within-case forward mismatch disagreement '+str(k))
    summary_map={(r['object_id'],r['policy']):r for r in object_summary}
    c.ok(len(summary_map)==24,'duplicate object-level summary row')
    for oid in sorted(objects):
        for policy in POLICIES:
            s=summary_map.get((oid,policy))
            c.ok(s is not None,'missing object summary '+oid+policy)
            if s is None:continue
            for field,gfield in [('mean_relative_gain','gain_vs_coverage'),('mean_defect_gain','defect_gain_vs_coverage'),('mean_nondefect_gain','nondefect_gain_vs_coverage')]:
                vals=[g for model in ('same','independent') for g in gain_rows[(oid,policy,2048,model,gfield)]]
                c.ok(len(vals)==4 and close(mean(vals),s[field]),'object-level mean wrong '+oid+policy+field)
            c.ok(int(s['n_conditions'])==4,'wrong object condition count '+oid+policy)
    primary=[mean([v for model in ('same','independent') for v in gain_rows[(oid,'guarded_05',2048,model,'gain_vs_coverage')]]) for oid in sorted(objects)]
    pstatus=status['primary_result']
    c.ok(close(mean(primary),pstatus['primary_mean_object_balanced_gain']),'primary status mean differs')
    c.ok(sum(v>0 for v in primary)==pstatus['primary_object_wins'],'primary object win count differs')
    c.ok(all(close(a,b) for a,b in zip(primary,pstatus['primary_object_gains'])) and len(pstatus['primary_object_gains'])==8,'primary object gain vector wrong')
    c.ok((mean(primary)>0 and all(v>0 for v in primary)) is pstatus['favorable_primary'],'favorable flag inconsistent')
    for budget in BUDGETS:
        for policy in ('gradient','guarded_05'):
            for gfield in ('gain_vs_coverage','defect_gain_vs_coverage','nondefect_gain_vs_coverage'):
                vals=[mean([v for model in ('same','independent') for v in gain_rows[(oid,policy,budget,model,gfield)]]) for oid in sorted(objects)]
                summary[f'{budget}_{policy}_{gfield}']=dict(mean=mean(vals),object_wins=sum(v>0 for v in vals))
    stats['primary_result']=dict(mean_gain=mean(primary),object_wins=sum(v>0 for v in primary),object_gains=dict(zip(sorted(objects),primary)))
    stats['budget_metrics']=summary
    identical={}
    for budget in BUDGETS:
        identical[str(budget)]=sum(raylists[(oid,model,str(seed),'gradient')][:budget]==raylists[(oid,model,str(seed),'guarded_05')][:budget] for oid in objects for model in ('same','independent') for seed in (104729,130363))
    stats['identical_gradient_guarded_histories']=identical
    tracegroups=defaultdict(list)
    for r in auditrows:
        try:
            k=key(r);t=json.loads(r['trace_json']);tracegroups[k].append(t)
            c.ok(r['policy']=='guarded_05','non-guarded trace row')
            c.ok(0<=number(t['fraction_guard_binding'])<=1 and 0<=number(t['fraction_coverage_reference'])<=1,'trace fraction invalid '+str(k))
            c.ok(1<=number(t['mean_eligible'])<=16,'eligible count invalid '+str(k))
            c.ok(1<=int(t['choices'])<=32 and int(t['acquired_after'])-int(t['acquired_before'])==int(t['choices']),'invalid batch trace '+str(k))
        except Exception as e:c.ok(False,'bad guard trace row: '+repr(e))
    c.ok(set(tracegroups)=={k for k in expected_keys if k[-1]=='guarded_05'},'guard trace conditions incomplete')
    choices=0;binding=0.
    for k,trace in tracegroups.items():
        c.ok(len(trace)==126,'guard trace count mismatch '+str(k))
        c.ok([int(t['acquired_after']) for t in trace]==list(range(96,4097,32)),'batch sequence mismatch '+str(k))
        for t in trace:
            choices+=int(t['choices']);binding+=number(t['fraction_guard_binding'])*int(t['choices'])
    stats['guard_diagnostics']=dict(batch_rows=len(auditrows),choices=choices,guard_binding_choices=round(binding),binding_fraction=binding/choices if choices else None,
                                    min_mean_eligible=min(number(t['mean_eligible']) for v in tracegroups.values() for t in v))
    c.ok(choices==129024,'wrong count of evaluated guard choices')
    for r in matched:
        k=(*key(r),int(r['acquired']))
        src=rowmap.get(k)
        c.ok(src is not None and k[-1]==2048,'matched case not a primary reconstruction '+str(k))
        if src:
            for name in ('global_rmse','defect_region_rmse','nondefect_rmse','gain_vs_coverage','defect_gain_vs_coverage','nondefect_gain_vs_coverage','ray_order_sha256'):
                c.ok(str(r[name])==str(src[name]),'matched case differs '+str(k)+name)
    crossing={}
    for r in thresholds:
        k=key(r)
        c.ok(k not in crossing,'duplicate threshold '+str(k));crossing[k]=r
        expected=next((b for b in BUDGETS if number(rowmap[(*k,b)]['global_rmse'])<=number(r['rmse_threshold'])),None)
        c.ok(str(r['first_observed_checkpoint'])==('' if expected is None else str(expected)),'checkpoint threshold crossing wrong '+str(k))
        c.ok(int(r['crossed_by_budget'])==int(expected is not None),'crossing flag wrong '+str(k))
    c.ok(set(crossing)==expected_keys,'threshold cases missing')
    stats['threshold_counts']={p:dict(Counter(r['first_observed_checkpoint'] or 'not_reached' for r in thresholds if r['policy']==p)) for p in POLICIES}
    tkeys=set()
    for r in timings:
        k=(*key(r),int(r['acquired']))
        c.ok(k not in tkeys,'duplicate timing '+str(k));tkeys.add(k)
        c.ok(number(r['selection_s'])>=0 and number(r['reconstruction_s'])>=0,'negative timing '+str(k))
    c.ok(tkeys==set(rowmap),'timing/reconstruction key mismatch')
    if geometry:
        try:stats['geometry_sensitivity']=geometry_sensitivity(root,p)
        except Exception as e:c.ok(False,'geometry diagnostic failed: '+repr(e))
    stats['manifest_sha256_valid']=not any('manifest' in e for e in c.errors)
    return c,stats

def geometry_sensitivity(root,protocol):
    import numpy as np
    from experiment_04b import system_matrix
    from experiment_04g import TILTS
    A=system_matrix(32,4,TILTS).tocsr()
    # Post-hoc sample: coverage prefix, not exact historical guarded candidate pools.
    from experiment_04h import voxel_coverage_order
    warm=voxel_coverage_order(A,32,4,len(TILTS),4096,104729,16)
    sq=np.asarray(A.multiply(A).sum(axis=1)).ravel()
    row_sum=np.asarray(A.sum(axis=1)).ravel()
    out=[]
    for budget in (64,1024,2048,4096):
        acquired=np.asarray(warm[:budget],dtype=int)
        counts=np.asarray(A[acquired].sum(axis=0)).ravel()
        mu=counts.mean();v=counts.var(); centered=counts-mu
        cross=np.asarray(A@centered).ravel()
        delta=(2*cross+sq)/A.shape[1] - (row_sum/A.shape[1])**2
        variance=v+delta
        remaining=np.ones(A.shape[0],dtype=bool);remaining[acquired]=False
        candidate=variance[remaining]
        low=float(candidate.min());high=float(candidate.max())
        out.append(dict(coverage_prefix=budget,coverage_variance=float(v),min_candidate_variance=low,
           max_candidate_variance=high,range_relative_to_min=(high-low)/max(low,1e-12),
           tolerance=.05,all_candidates_within_5pct_of_min=(high<=low+.05*max(low,1e-12)+1e-14)))
    return dict(scope='Post-hoc geometry-only global range on coverage order for one seed; not a replay of actual candidate pools',samples=out)

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results-dir',type=Path,required=True)
    ap.add_argument('--report',type=Path,required=True)
    ap.add_argument('--check-masks',action='store_true',help='Regenerate original objects/masks and validate their stored hashes; does not rerun acquisition')
    ap.add_argument('--geometry',action='store_true',help='Compute post-hoc imbalance sensitivity on frozen 32^3 geometry; not an exact candidate replay')
    a=ap.parse_args(argv)
    if a.results_dir.resolve()==a.report.resolve() or a.results_dir.resolve() in a.report.resolve().parents:
        ap.error('report must be outside original frozen results directory')
    try:
        c,stats=audit(a.results_dir,check_masks=a.check_masks,geometry=a.geometry)
        report=dict(audit='RBYRCT-07D frozen 07C2 numerical and guard-scale audit',verdict='PASS' if not c.errors else 'FAIL',checks_performed=c.n,
                    errors=c.errors,warnings=c.warnings,results=stats,
                    limitations=['Does not rerun MART or physical forward projections','Cannot recompute voxel errors without archived reconstructed volumes',
                      'Exact original 16 candidate IDs and imbalance scores were not saved in guard trace',
                      'Geometry sensitivity is a post-hoc diagnostic, not proof of guard failure mechanism'])
        a.report.parent.mkdir(parents=True,exist_ok=True)
        a.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(dict(verdict=report['verdict'],checks_performed=c.n,errors=c.errors[:12],error_count=len(c.errors),
                              primary=stats.get('primary_result'),guard=stats.get('guard_diagnostics'),
                              geometry=stats.get('geometry_sensitivity')),indent=2))
        return 0 if not c.errors else 1
    except Exception as e:
        print('AUDIT ERROR:',repr(e),file=sys.stderr)
        return 2

if __name__=='__main__':sys.exit(main())
