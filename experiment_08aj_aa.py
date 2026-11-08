"""08AJ-AA: 480-job production execution SPECIFICATION with a fail-closed gate.

Production numerical execution is intentionally absent. Provides immutable per-job
specifications, 96 shared-measurement dependency groups, recoverable engineering
orchestration receipts, and optional independently audited Z evidence attachment.
No prospective phantom is generated or reconstructed.
"""
from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path
import experiment_08aj_m as m

SCHEMA='RBYRCT-08AJ-AA-disabled-numerical-pathway-v1'
SOURCES=('experiment_08aj_aa.py','experiment_08aj_aa_audit.py')
POLICIES=('information_diag','uniform_multiscale','coverage','stratified_random_04h','complete_view')
MODELS=('same','independent')
REHEARSAL_IDS=('contract_check','shared_dependency_check','engineering_link_check')

def canonical(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('ascii')
def sha(data):return hashlib.sha256(data).hexdigest()
def source_hashes():
    base=Path(__file__).resolve().parent
    return {name:sha((base/name).read_bytes()) for name in SOURCES}
def exclusive(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
def share_key(job):return f"{job['family']}__{job['object_seed']}__{job['acquisition_seed']}__{job['model']}"
def specs(roster):
    if len(roster)!=480:raise ValueError('expected exactly 480 jobs')
    results=[];seen=set()
    for job in roster:
        if job.get('status')!='DISABLED' or job.get('execution_allowed') is not False or job.get('n')!=32 or job.get('ray_budget')!=2048 or job.get('mart_epochs')!=16:
            raise ValueError('unapproved job parameters')
        identity=job['job_id'];key=share_key(job)
        if identity in seen:raise ValueError('duplicate job')
        seen.add(identity)
        results.append({'schema':'RBYRCT-08AJ-AA-job-spec-v1','job_id':identity,
          'family':job['family'],'object_seed':job['object_seed'],
          'acquisition_seed':job['acquisition_seed'],'model':job['model'],
          'policy':job['policy'],'shared_catalogue_key':key,
          'n':32,'ray_budget':2048,'mart_epochs':16,'relaxation':0.25,
          'warm_prefix':None if job['policy']=='complete_view' else 64,
          'acquisition_unit':'full_view' if job['policy']=='complete_view' else 'individual_ray',
          'required_artifacts':list(m.REQUIRED_JOB_ARRAYS)+['receipt.json','truth_sha256','rmse'],
          'execution_allowed':False,'execution_status':'BLOCKED_NOT_EXECUTED',
          'no_confirmatory_outcomes':True})
    if len(results)!=480:return ValueError('wrong roster size')
    return results

def validate_groups(rows):
    groups={}
    for row in rows:groups.setdefault(row['shared_catalogue_key'],[]).append(row)
    if len(groups)!=96:raise ValueError('96 shared catalogues required')
    for key,items in groups.items():
        if len(items)!=5 or {x['policy'] for x in items}!=set(POLICIES) or len({x['model'] for x in items})!=1:
            raise ValueError('invalid group membership '+key)
        if len({(x['object_seed'],x['acquisition_seed'],x['family']) for x in items})!=1:raise ValueError('inconsistent object group')
        if len({x['warm_prefix'] for x in items if x['policy']!='complete_view'})!=1:raise ValueError('inconsistent warm prefix')
        cv=next(x for x in items if x['policy']=='complete_view')
        if cv['acquisition_unit']!='full_view' or cv['warm_prefix'] is not None:raise ValueError('broken whole view')
    return groups

def prepare(root,m_dir):
    root=Path(root);m_dir=Path(m_dir)
    if root.exists():raise FileExistsError('refusing to overwrite AA evidence')
    contract,contract_sha=m.check(m_dir)
    if contract['execution_gate']['enabled'] is not False:raise ValueError('M contract unexpectedly enabled')
    r=json.loads((m_dir/'jobs.json').read_bytes());rows=specs(r);groups=validate_groups(rows)
    manifest={'schema':SCHEMA,'contract_sha256':contract_sha,
       'roster_sha256':sha((m_dir/'jobs.json').read_bytes()),
       'spec_sha256':sha(canonical(rows)),'job_count':480,'shared_catalogues':96,
       'source_sha256':source_hashes(),
       'scientific_signoff':False,'resource_policy_approved':False,
       'frozen':False,'confirmatory_execution_allowed':False,'no_confirmatory_outcomes':True,
       'production_numerical_certified':False,
       'resume_rule':'committed engineering receipts must verify byte-for-byte; no overwrite',
       'failure_rule':'preserve prior evidence; no automatic retry or outcome-based stopping',
       'engineering_only_attachment':True}
    root.mkdir(parents=True)
    exclusive(root/'job_specifications.json',canonical(rows))
    exclusive(root/'aa_manifest.json',canonical(manifest))
    (root/'rehearsal_receipts').mkdir();(root/'engineering_link').mkdir()
    return {'verdict':'AA_DISABLED_PRODUCTION_PATH_PREPARED','production_jobs':480,
            'shared_measurement_groups':len(groups),'confirmatory_execution_allowed':False,
            'production_numerical_certified':False,'no_confirmatory_outcomes':True}

def check(root,m_dir):
    root=Path(root);m_dir=Path(m_dir);contract,contract_sha=m.check(m_dir)
    spec_blob=(root/'job_specifications.json').read_bytes();rows=json.loads(spec_blob)
    expected=specs(json.loads((m_dir/'jobs.json').read_bytes()))
    if spec_blob!=canonical(rows) or rows!=expected:raise ValueError('AA job spec / source roster mismatch')
    groups=validate_groups(rows)
    manifest_blob=(root/'aa_manifest.json').read_bytes();manifest=json.loads(manifest_blob)
    wanted={'schema':SCHEMA,'contract_sha256':contract_sha,
       'roster_sha256':sha((m_dir/'jobs.json').read_bytes()),
       'spec_sha256':sha(spec_blob),'job_count':480,'shared_catalogues':96,
       'source_sha256':source_hashes(),
       'scientific_signoff':False,'resource_policy_approved':False,
       'frozen':False,'confirmatory_execution_allowed':False,'no_confirmatory_outcomes':True,
       'production_numerical_certified':False,
       'resume_rule':'committed engineering receipts must verify byte-for-byte; no overwrite',
       'failure_rule':'preserve prior evidence; no automatic retry or outcome-based stopping',
       'engineering_only_attachment':True}
    if manifest_blob!=canonical(manifest) or manifest!=wanted:raise ValueError('AA source / authorization gate mismatch')
    for name in ('rehearsal_receipts','engineering_link'):
        folder=root/name
        if not folder.is_dir() or folder.is_symlink():raise ValueError('missing or unsafe evidence directory')
    return manifest,sha(manifest_blob),groups

def receipt_payload(job,manifest_sha):
    if job not in REHEARSAL_IDS:raise ValueError('unauthorized rehearsal')
    return {'schema':'RBYRCT-08AJ-AA-engineering-rehearsal-v1','rehearsal_id':job,
            'manifest_sha256':manifest_sha,'engineered_receipt_only':True,
            'no_numerical_reconstruction':True,'no_confirmatory_outcomes':True}

def rehearse(root,m_dir,ids=None):
    root=Path(root);_,h,_=check(root,m_dir)
    ids=REHEARSAL_IDS if ids is None else tuple(ids)
    if any(i not in REHEARSAL_IDS for i in ids):raise ValueError('rehearsal ID not allowed')
    new=[];reused=[]
    for i in ids:
        p=root/'rehearsal_receipts'/(i+'.json');blob=canonical(receipt_payload(i,h))
        if p.exists():
            if p.is_symlink() or p.read_bytes()!=blob:raise ValueError('committed engineering receipt corrupt '+i)
            reused.append(i)
        else:exclusive(p,blob);new.append(i)
    return {'verdict':'AA_ENGINEERING_RECOVERY_PASS','new':new,'reused':reused,
            'production_jobs_executed':0,'confirmatory_execution_allowed':False,'no_confirmatory_outcomes':True}

def attach_z(root,m_dir,z_dir):
    from experiment_08aj_z_audit import audit
    root=Path(root);z_dir=Path(z_dir);_,h,_=check(root,m_dir)
    result=audit(z_dir,m_dir,require_complete=True)
    if not result['pass'] or result['audited_engineering_jobs']!=10:raise ValueError('Z engineering evidence not independently verified')
    zplan=(z_dir/'z_plan.json').read_bytes()
    receipt={'schema':'RBYRCT-08AJ-AA-Z-link-v1','manifest_sha256':h,
             'z_plan_sha256':sha(zplan),'z_independently_audited_jobs':10,
             'z_engineering_only':True,'no_production_execution':True,
             'no_confirmatory_outcomes':True}
    p=root/'engineering_link'/'z_receipt.json';blob=canonical(receipt)
    if p.exists():
        if p.is_symlink() or p.read_bytes()!=blob:raise ValueError('Z link corrupted')
        verdict='AA_Z_ENGINEERING_LINK_REUSED'
    else:exclusive(p,blob);verdict='AA_Z_ENGINEERING_LINK_PASS'
    return {'verdict':verdict,'audited_engineering_jobs':10,'production_jobs_executed':0,
            'confirmatory_execution_allowed':False,'no_confirmatory_outcomes':True}

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--output-dir',required=True,type=Path);a.add_argument('--m-dir',required=True,type=Path)
    a.add_argument('--z-dir',type=Path)
    a.add_argument('--mode',required=True,choices=('prepare','check','rehearse','attach-z','execute','production-run','unlock','freeze'))
    x=a.parse_args()
    if x.mode in ('execute','production-run','unlock','freeze'):
        a.error('PRODUCTION_EXECUTION_DISABLED; NO SCIENTIFIC SIGNOFF OR IMMUTABLE SOURCE FREEZE')
    if x.mode=='prepare':res=prepare(x.output_dir,x.m_dir)
    elif x.mode=='check':
        _,h,groups=check(x.output_dir,x.m_dir)
        res={'verdict':'AA_SOURCE_AND_480_JOB_MAPPING_PASS','manifest_sha256':h,'shared_groups':len(groups),'confirmatory_execution_allowed':False}
    elif x.mode=='rehearse':res=rehearse(x.output_dir,x.m_dir)
    else:
        if x.z_dir is None:a.error('--z-dir required for attach-z')
        res=attach_z(x.output_dir,x.m_dir,x.z_dir)
    print(json.dumps(res,indent=2))
if __name__=='__main__':main()
