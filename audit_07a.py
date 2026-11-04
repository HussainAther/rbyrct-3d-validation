"""Read-only independent structural and numerical audit of RBYRCT-06B outputs.

Standard library only; does not import the experiment or run simulations.
Exit code 0 means all checks passed, 1 means failed checks, 2 means missing inputs.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import statistics
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

EXPECTED = ('protocol.json', 'environment.txt', 'object_manifest.csv',
 'acquisition_orders.csv', 'prefix_reconstructions.csv', 'matched_cases.csv',
 'object_level_summary.csv', 'threshold_crossings.csv', 'timing.csv',
 'guard_batch_audit.csv', 'study_status.json', 'run_manifest.sha256')
POLICIES = ('coverage','gradient','guarded_05')

class Audit:
 def __init__(self): self.checks=0; self.errors=[]; self.warnings=[]; self.stats={}
 def check(self, condition, message):
  self.checks+=1
  if not condition: self.errors.append(message)
 def warn(self, message): self.warnings.append(message)

def readcsv(root,name):
 with (root/name).open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))

def fnum(v):
 result=float(v)
 if not math.isfinite(result): raise ValueError(f'nonfinite value {v}')
 return result

def valid_rmse_gain(rmse, gain):
 # Negative gains are valid: adaptive RMSE can exceed coverage RMSE.
 # A strictly positive baseline RMSE implies finite gain <= 1.
 return fnum(rmse)>0 and fnum(gain)<=1+1e-8

def sha_prefix(values):
 return hashlib.sha256(b''.join(struct.pack('<q', int(k)) for k in values)).hexdigest()

def key(r):return (r['object_id'],r['model'],str(r['acquisition_seed']),r['policy'])
def rkey(r):return (*key(r),int(r['acquired']))

def near(a,b,atol=1e-11,rtol=1e-9):return math.isclose(float(a),float(b),abs_tol=atol,rel_tol=rtol)

def safe_mean(vals):
 vals=list(vals)
 return statistics.mean(vals) if vals else float('nan')

def verify_manifest(root,a):
 lines=(root/'run_manifest.sha256').read_text(encoding='utf-8').splitlines()
 names=[]
 for line in lines:
  bits=line.split('  ',1)
  if len(bits)!=2:
   a.check(False,f'malformed manifest line: {line[:90]}');continue
  h,name=bits;names.append(name)
  if '/' in name or '\\' in name or name in ('.','..'):
   a.check(False,f'unsafe manifest filename {name}');continue
  p=root/name
  a.check(p.is_file(),f'manifest refers to missing file {name}')
  if p.is_file():a.check(hashlib.sha256(p.read_bytes()).hexdigest()==h,f'manifest checksum mismatch: {name}')
 a.check(len(names)==len(set(names)),'duplicate manifest entries')
 expected=set(EXPECTED)-{'run_manifest.sha256'}
 a.check(set(names)==expected,f'manifest filename set mismatch: missing={sorted(expected-set(names))}, extra={sorted(set(names)-expected)}')

def audit(root):
 root=Path(root);a=Audit()
 missing=[x for x in EXPECTED if not (root/x).is_file()]
 if missing:raise FileNotFoundError(f'Incomplete 06B output folder: {missing}')
 verify_manifest(root,a)
 cfg=json.loads((root/'protocol.json').read_text(encoding='utf-8'))
 stored=cfg.get('protocol_sha256'); base={k:v for k,v in cfg.items() if k!='protocol_sha256'}
 a.check(hashlib.sha256(json.dumps(base,sort_keys=True).encode()).hexdigest()==stored,'protocol hash mismatch')
 a.check(not cfg.get('allow_test_scale',False),'protocol is marked TEST SCALE, not frozen production')
 a.check(cfg.get('size')==12 and cfg.get('budget')==576,'unexpected 06B spatial size or budget')
 a.check(cfg.get('checkpoints')==[144,288,576] and cfg.get('primary_checkpoint')==288,'unexpected checkpoints')
 a.check(near(cfg.get('guard_eta',-1),.05),'guard eta not frozen 0.05')
 a.check(cfg.get('policies')==list(POLICIES),'policy list mismatch')
 a.check(cfg.get('models')==['same','independent'],'forward model list mismatch')
 a.check(len(cfg.get('object_seeds',[]))==8 and len(set(cfg['object_seeds']))==8,'unexpected object seeds')
 a.check(cfg.get('acquisition_seeds')==[104729,130363],'unexpected acquisition seeds')
 a.check(cfg.get('warm_rays')==36 and cfg.get('batch')==12 and cfg.get('pool')==24,'unexpected sampling settings')
 a.check(cfg.get('final_epochs')==16 and near(cfg.get('relaxation',-1),.25),'unexpected MART final settings')
 status=json.loads((root/'study_status.json').read_text(encoding='utf-8'))
 orders=readcsv(root,'acquisition_orders.csv');rows=readcsv(root,'prefix_reconstructions.csv')
 matched=readcsv(root,'matched_cases.csv');objects=readcsv(root,'object_level_summary.csv')
 thresholds=readcsv(root,'threshold_crossings.csv');timings=readcsv(root,'timing.csv')
 guards=readcsv(root,'guard_batch_audit.csv');manif=readcsv(root,'object_manifest.csv')
 a.check(len(manif)==8,'object manifest must have 8 rows')
 a.check(len(orders)==55296,'acquisition orders must contain 55,296 rows')
 a.check(len(rows)==288,'checkpoint reconstructions must contain 288 rows')
 a.check(len(matched)==96,'matched primary cases must contain 96 rows')
 a.check(len(objects)==24,'object summaries must contain 24 rows')
 a.check(len(thresholds)==96,'threshold crossings must contain 96 rows')
 a.check(len(timings)==288,'timing rows must contain 288 rows')
 a.check(len(guards)>0,'no guarded acquisition batch audit rows')
 a.check(status.get('pass_engineering_checks') is True,'generator reported failed engineering checks')
 a.check(status.get('distinct_objects')==len(manif),'status object count mismatch')
 a.check(status.get('acquisition_histories')==96 and status.get('reconstructions')==len(rows) and status.get('ray_order_rows')==len(orders),'status count mismatch')
 manifest_ids={x['object_id'] for x in manif}
 a.check(manifest_ids=={f'localized_defect_{s}' for s in cfg['object_seeds']},'manifest object ID mismatch')
 for x in manif:
  try:
   pars=json.loads(x['parameters_json'])
   a.check(int(x['n_defects'])==pars['n_defects'] and 2<=pars['n_defects']<=4,f'invalid defect descriptor {x["object_id"]}')
   a.check(len(x['coarse_sha256'])==64 and len(x['fine_sha256'])==64,'bad object hash shape')
  except Exception as e:a.check(False,f'cannot parse object descriptor: {e}')

 grouping=defaultdict(list)
 for o in orders:
  try:grouping[key(o)].append((int(o['acquired_index']),int(o['ray_id'])))
  except Exception as e:a.check(False,f'bad acquisition row: {e}')
 expected_keys={(oid,model,str(seed),policy) for oid in manifest_ids for model in cfg['models'] for seed in cfg['acquisition_seeds'] for policy in POLICIES}
 a.check(set(grouping)==expected_keys,'acquisition group keys do not match frozen Cartesian design')
 orderlists={}
 ray_max=int(cfg['size'])**2*int(cfg['angles'])*len(cfg['tilts'])
 for k,g in grouping.items():
  indexes=[i for i,_ in g]; rays=[r for _,r in g]
  a.check(len(g)==576 and indexes==list(range(1,577)),f'acquisition length/order/index mismatch {k}')
  a.check(len(set(rays))==len(rays) and all(0<=r<ray_max for r in rays),f'nonunique or out of range ray {k}')
  orderlists[k]=rays
 for oid in manifest_ids:
  for model in cfg['models']:
   for seed in cfg['acquisition_seeds']:
    ids=[orderlists.get((oid,model,str(seed),p),[]) for p in POLICIES]
    if all(len(x)>=36 for x in ids):a.check(ids[0][:36]==ids[1][:36]==ids[2][:36],f'warm prefix mismatch {oid}, {model}, {seed}')

 rowmap={}; shape_error=0
 for r in rows:
  try:
   k=rkey(r)
   if k in rowmap:shape_error+=1
   rowmap[k]=r
   a.check(int(r['acquired']) in cfg['checkpoints'],f'wrong checkpoint {k}')
   a.check(valid_rmse_gain(r['rmse'],r['gain_vs_coverage']),f'invalid RMSE or gain {k}')
   seq=orderlists.get(key(r))
   if seq:
    n=int(r['acquired'])
    a.check(sha_prefix(seq[:n])==r['ray_order_sha256'],f'prefix fingerprint mismatch {k}')
  except Exception as e:a.check(False,f'invalid prefix reconstruction row: {e}')
 a.check(shape_error==0,'duplicate checkpoint reconstruction keys')
 expected_rows={(oid,model,str(seed),p,b) for oid in manifest_ids for model in cfg['models'] for seed in cfg['acquisition_seeds'] for p in POLICIES for b in cfg['checkpoints']}
 a.check(set(rowmap)==expected_rows,'reconstruction row keys mismatch full frozen design')
 gain_by_obj=defaultdict(lambda:defaultdict(list)); budget_summary={}; model_summary={}
 for k,r in rowmap.items():
  oid,model,seed,p,n=k
  base=rowmap.get((oid,model,seed,'coverage',n))
  if base:
   gain=(fnum(base['rmse'])-fnum(r['rmse']))/max(fnum(base['rmse']),1e-12)
   a.check(near(gain,r['gain_vs_coverage']),f'GAIN DOES NOT MATCH RAW RMSE {k}')
   refs=orderlists.get((oid,model,seed,'coverage'),[])
   own=orderlists.get((oid,model,seed,p),[])
   if len(own)>=n and len(refs)>=n:
    shared=len(set(own[:n]) & set(refs[:n]))
    a.check(int(r['shared_with_coverage'])==shared,f'shared ray count mismatch {k}')
   gain_by_obj[(oid,p,n)][model].append(gain)
  a.check(near(r['relative_forward_mismatch'],rowmap[(oid,model,seed,'coverage',n)]['relative_forward_mismatch']) if (oid,model,seed,'coverage',n) in rowmap else False,f'forward mismatch differs within pairing {k}')

 summary_map={(o['object_id'],o['policy']):o for o in objects}
 a.check(len(summary_map)==len(objects),'duplicate object summary keys')
 for oid in manifest_ids:
  for p in POLICIES:
   source=[x for vals in gain_by_obj[(oid,p,288)].values() for x in vals]
   s=summary_map.get((oid,p))
   a.check(s is not None,f'missing object summary: {oid} {p}')
   if s and source:
    a.check(int(s['n_conditions'])==4 and len(source)==4,f'wrong object replication count {oid} {p}')
    a.check(near(statistics.mean(source),s['mean_relative_gain']),f'OBJECT MEAN WRONG {oid} {p}')
    a.check(near(min(source),s['worst_relative_gain']),f'OBJECT MIN WRONG {oid} {p}')

 primary=[]
 for oid in sorted(manifest_ids):
  vals=[v for m in gain_by_obj[(oid,'guarded_05',288)].values() for v in m]
  if len(vals)==4:primary.append(statistics.mean(vals))
 a.check(len(primary)==8,'primary result missing objects')
 if primary:
  res=status.get('primary_result',{})
  a.check(near(statistics.mean(primary),res.get('primary_mean_object_balanced_gain',-999)),'STATUS PRIMARY MEAN DOES NOT MATCH RMSE')
  a.check(sum(x>0 for x in primary)==res.get('primary_object_wins'),'status primary object wins wrong')
  a.check(res.get('n_objects')==8,'status n_objects wrong')
  a.check(all(near(x,y) for x,y in zip(primary,res.get('primary_object_gains',[]))) and len(res.get('primary_object_gains',[]))==8,'status primary per-object values wrong')
  rule=(statistics.mean(primary)>0 and all(x>0 for x in primary))
  a.check(rule==res.get('favorable_primary'),'status favorable_primary wrong')
  a.stats['primary_mean_object_balanced_gain']=statistics.mean(primary)
  a.stats['primary_object_wins']=sum(x>0 for x in primary)
  a.stats['primary_object_gains']=dict(zip(sorted(manifest_ids),primary))

 for n in cfg['checkpoints']:
  for p in ('gradient','guarded_05'):
   per=[safe_mean(v for model in gain_by_obj[(oid,p,n)].values() for v in model) for oid in sorted(manifest_ids)]
   a.check(all(math.isfinite(x) for x in per),f'missing observations for budget summary {n}, {p}')
   budget_summary[f'{n}_{p}']={'mean_gain':safe_mean(per),'object_wins':sum(x>0 for x in per)}
 for model in cfg['models']:
  for p in ('gradient','guarded_05'):
   vals=[safe_mean(gain_by_obj[(oid,p,288)][model]) for oid in sorted(manifest_ids)]
   a.check(all(math.isfinite(x) for x in vals),f'missing observations for model summary {model}, {p}')
   model_summary[f'{model}_{p}']={'mean_gain':safe_mean(vals),'object_wins':sum(x>0 for x in vals)}
 a.stats['budget_summary']=budget_summary;a.stats['forward_model_summary']=model_summary

 identical={}
 for n in cfg['checkpoints']:
  cnt=sum(sha_prefix(orderlists.get((oid,model,str(seed),'gradient'),[])[:n])==sha_prefix(orderlists.get((oid,model,str(seed),'guarded_05'),[])[:n]) for oid in manifest_ids for model in cfg['models'] for seed in cfg['acquisition_seeds'])
  identical[str(n)]=cnt
 a.stats['identical_gradient_guarded_ordered_histories']=identical

 expected_primary={(oid,model,str(seed),p,288) for oid in manifest_ids for model in cfg['models'] for seed in cfg['acquisition_seeds'] for p in POLICIES}
 observed_primary=set()
 for r in matched:
  try:
   k=rkey(r);observed_primary.add(k)
   src=rowmap.get(k)
   a.check(src is not None,f'matched row lacks source {k}')
   if src:
    for field in ('rmse','gain_vs_coverage','shared_with_coverage','ray_order_sha256'):
     a.check(str(r[field])==str(src[field]),f'matched_cases differs from raw row {k}, {field}')
  except Exception as e:a.check(False,f'malformed matched case: {e}')
 a.check(observed_primary==expected_primary,'matched cases key set mismatch')

 thresholdmap={}
 for r in thresholds:
  k=key(r); a.check(k not in thresholdmap,f'duplicate threshold record {k}');thresholdmap[k]=r
  grp=[rowmap.get((*k,n)) for n in cfg['checkpoints']]
  if not all(grp):a.check(False,f'missing reconstruction for threshold {k}');continue
  first=next((n for n,x in zip(cfg['checkpoints'],grp) if fnum(x['rmse'])<=fnum(r['rmse_threshold'])),None)
  actual=str(r['first_observed_checkpoint']).strip()
  a.check(actual==('' if first is None else str(first)),f'wrong threshold crossing {k}')
  a.check(int(r['crossed_by_budget'])==int(first is not None),f'wrong threshold reached flag {k}')
  a.check(near(r['rmse_threshold'],.1),f'unexpected threshold {k}')
 a.check(set(thresholdmap)==set(grouping),'threshold key set differs from histories')
 thr_counts={}
 for p in POLICIES:
  counts=Counter(x['first_observed_checkpoint'] or 'not_reached' for x in thresholds if x['policy']==p)
  thr_counts[p]=dict(counts)
 a.stats['threshold_counts']=thr_counts

 tmap={}
 for r in timings:
  k=rkey(r);a.check(k not in tmap,f'duplicate timing record {k}');tmap[k]=r
  a.check(fnum(r['selection_s'])>=0 and fnum(r['reconstruction_s'])>=0,f'negative timing {k}')
 a.check(set(tmap)==set(rowmap),'timing key set differs from reconstructions')
 duration={}
 for p in POLICIES:
  times=[]
  for oid in manifest_ids:
   for model in cfg['models']:
    for seed in cfg['acquisition_seeds']:
     k=(oid,model,str(seed),p,288)
     if k in tmap:
      d=fnum(tmap[k]['selection_s']);times.append(d)
      for n in cfg['checkpoints']:
       other=tmap.get((oid,model,str(seed),p,n))
       if other:a.check(near(other['selection_s'],d),f'selection time repeated inconsistently {k}')
  duration[p]={'mean_selection_s_per_history':statistics.mean(times) if times else None,'n_histories':len(times)}
 a.stats['selection_timing']=duration
 expected_guard_keys={(oid,model,str(seed),'guarded_05') for oid in manifest_ids for model in cfg['models'] for seed in cfg['acquisition_seeds']}
 guard_groups=defaultdict(list)
 for r in guards:
  k=key(r);guard_groups[k].append(r)
  a.check(r['policy']=='guarded_05',f'guard audit includes non-guarded policy {k}')
  a.check(0<=fnum(r['fraction_guard_binding'])<=1 and 0<=fnum(r['fraction_coverage_reference'])<=1,f'guard fraction outside [0,1] {k}')
  a.check(fnum(r['mean_eligible'])>=1,'no eligible ray in guard audit')
 a.check(set(guard_groups)==expected_guard_keys,'guard audit key set mismatch')
 expected_batches=(cfg['budget']-cfg['warm_rays'])//cfg['batch']
 for k,group in guard_groups.items():
  a.check(len(group)==expected_batches,f'guard audit batch count differs: {k}')
  b=sorted(group,key=lambda r:int(r['acquired_after']))
  a.check([int(r['acquired_after']) for r in b]==list(range(cfg['warm_rays']+cfg['batch'],cfg['budget']+1,cfg['batch'])),f'guard batch end indices mismatch {k}')
 a.stats['guard_audit_rows']=len(guards)
 a.stats['files_sha256_valid']=not any('checksum mismatch' in m for m in a.errors)
 return a

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--results-dir',type=Path,required=True)
 p.add_argument('--report',type=Path,help='write JSON report to a SEPARATE path (never overwrite experiment data)')
 args=p.parse_args(argv)
 try:a=audit(args.results_dir)
 except (FileNotFoundError,ValueError,KeyError,TypeError,ZeroDivisionError) as e:
  print('AUDIT BLOCKED:',e,file=sys.stderr);return 2
 output={'audit_name':'RBYRCT-07A independent read-only 06B audit','source_dir':str(args.results_dir),
  'verdict':'PASS' if not a.errors else 'FAIL','checks_performed':a.checks,'errors':a.errors,'warnings':a.warnings,'derived_statistics':a.stats,
  'scope_note':'Validates persisted CSV/JSON provenance, numerical aggregation and acquisition invariants; does not independently re-simulate forward projections, validate physical CT, or infer causal effect of guarding.'}
 print(json.dumps(output,indent=2))
 if args.report:
  if args.report.resolve().is_relative_to(args.results_dir.resolve()):
   print('Refusing to write report into immutable experiment directory',file=sys.stderr);return 2
  args.report.parent.mkdir(parents=True,exist_ok=True)
  args.report.write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
 return 0 if not a.errors else 1

if __name__=='__main__':sys.exit(main())
