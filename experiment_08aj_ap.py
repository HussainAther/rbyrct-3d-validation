"""08AJ-AP: READ-ONLY production-qualification evidence assessment.

No prospective execution, no scientific approvals, no source freeze.
Input audit outputs are *reported* independent audits, not replayed by AP.
"""
from __future__ import annotations
import argparse, hashlib, json, math, os
from pathlib import Path

SCHEMA='RBYRCT-08AJ-AP-read-only-qualification-v1'
POLICIES=('information_diag','uniform_multiscale','coverage','stratified_random_04h','complete_view')
MODELS=('same','independent')
OBJECTS=('engineering_alpha','engineering_beta')
SEEDS=('seed_a','seed_b')
GATES={
 'G1_phantom_population':'PENDING_NAMED_SCIENTIFIC_APPROVAL',
 'G2_estimand_inference':'PENDING_NAMED_SCIENTIFIC_APPROVAL',
 'G3_resource_failure_policy':'PENDING_REVIEW_AND_APPROVAL',
 'G4_480_job_executor_auditor':'NOT_CERTIFIED',
 'G5_signoff_source_freeze':'NOT_AUTHORIZED',
}

def canonical(x):
    return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False,ensure_ascii=True)+'\n').encode('ascii')

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load(path):
    path=Path(path)
    if not path.is_file() or path.is_symlink():raise ValueError('missing/unsafe evidence file: '+str(path))
    return json.loads(path.read_text(encoding='utf-8-sig'))

def require(condition,message):
    if not condition:raise ValueError(message)

def valid_numerical_difference(value, tolerance):
    return (
        type(value) in (int, float)
        and math.isfinite(value)
        and 0.0 <= value <= tolerance
    )

def inspect(aa_dir, an8_dir, ao_dir, an8_audit, ao_audit, y_dir=None):
    aa_dir=Path(aa_dir); an8_dir=Path(an8_dir); ao_dir=Path(ao_dir)
    specs=load(aa_dir/'job_specifications.json')
    manifest=load(aa_dir/'aa_manifest.json')
    require(isinstance(specs,list) and len(specs)==480,'AA expected exactly 480 specifications')
    require(manifest.get('job_count')==480 and manifest.get('shared_catalogues')==96,'AA manifest dimensions mismatch')
    require(manifest.get('spec_sha256')==digest(aa_dir/'job_specifications.json'),'AA manifest/spec hash mismatch')
    for flag in ('scientific_signoff','resource_policy_approved','frozen','confirmatory_execution_allowed','production_numerical_certified'):
        require(manifest.get(flag) is False,'AA lock changed: '+flag)
    require(manifest.get('no_confirmatory_outcomes') is True,'AA confirmatory lock missing')
    groups={}; jobids=set(); objects=set(); acquisitions=set()
    for job in specs:
        require(isinstance(job,dict),'invalid AA job')
        jid=job.get('job_id');require(isinstance(jid,str) and jid not in jobids,'AA duplicate or invalid job id')
        jobids.add(jid)
        key=job.get('shared_catalogue_key');require(isinstance(key,str),'missing AA group key')
        groups.setdefault(key,[]).append(job)
        require(job.get('execution_allowed') is False and job.get('execution_status')=='BLOCKED_NOT_EXECUTED','AA job unexpectedly enabled')
        require(job.get('no_confirmatory_outcomes') is True,'AA outcome lock missing')
        require(job.get('n')==32 and job.get('ray_budget')==2048 and job.get('mart_epochs')==16 and job.get('relaxation')==0.25,'AA numerical contract mismatch')
        require(job.get('model') in MODELS and job.get('policy') in POLICIES,'AA model/policy mismatch')
        require(job.get('acquisition_unit')==('full_view' if job['policy']=='complete_view' else 'individual_ray'),'AA acquisition unit mismatch')
        require(job.get('warm_prefix')==(None if job['policy']=='complete_view' else 64),'AA warm prefix mismatch')
        objects.add((job.get('family'),job.get('object_seed')));acquisitions.add(job.get('acquisition_seed'))
    require(len(groups)==96 and len(objects)==24 and len(acquisitions)==2,'AA group/object/seed dimensionality mismatch')
    for key,items in groups.items():
        require(len(items)==5 and {j['policy'] for j in items}==set(POLICIES),'AA five-policy group mismatch: '+key)
        require(len({(j['object_seed'],j['acquisition_seed'],j['model']) for j in items})==1,'AA group mixing: '+key)
    audits=[]
    for name,root,apath,n,expected_jobs in (
        ('AN_8',an8_dir,an8_audit,8,40),('AO_32',ao_dir,ao_audit,32,20)):
        plan=load(root/'plan.json'); audit=load(apath)
        require(plan.get('namespace')=='MULTI_SEED_FIVE_POLICY_ENGINEERING_ONLY','wrong AN namespace: '+name)
        require(plan.get('config',{}).get('n')==n,'wrong engineering resolution: '+name)
        require(plan.get('engineering_jobs')==40 and plan.get('engineering_groups')==8,'wrong AN matrix: '+name)
        require(set(plan.get('policies',[]))==set(POLICIES) and set(plan.get('models',[]))==set(MODELS),'AN policies/models mismatch: '+name)
        require(set(plan.get('objects',{}))==set(OBJECTS) and set(plan.get('acquisition_seeds',{}))==set(SEEDS),'AN objects/seeds mismatch: '+name)
        for flag in ('production_execution_allowed','production_480_job_certified','scientific_signoff','resource_policy_approved','frozen'):
            require(plan.get(flag) is False,'AN plan permission changed: '+name+'/'+flag)
        require(plan.get('no_confirmatory_outcomes') is True,'AN outcome guard missing')
        require(plan.get('aa_manifest_sha256')==digest(aa_dir/'aa_manifest.json'),'AN AA source linkage mismatch: '+name)
        require(plan.get('aa_spec_sha256')==digest(aa_dir/'job_specifications.json'),'AN AA spec linkage mismatch: '+name)
        require(audit.get('pass') is True and audit.get('verdict')=='AN_INDEPENDENT_MULTI_SEED_AUDIT_PASS' and audit.get('errors')==[],'reported audit does not pass: '+name)
        require(audit.get('engineering_jobs_audited')==expected_jobs and audit.get('shared_groups_audited')==8,'reported audit coverage mismatch: '+name)
        require(audit.get('engineering_objects')==2 and audit.get('acquisition_seeds')==2,'reported audit factors mismatch: '+name)
        require(audit.get('production_jobs_executed')==0 and audit.get('production_execution_allowed') is False and audit.get('production_480_job_certified') is False and audit.get('no_confirmatory_outcomes') is True,'reported audit lock mismatch: '+name)
        details=audit.get('details',[])
        require(len(details)==expected_jobs and len({d.get('job_id') for d in details})==expected_jobs,'reported audit job uniqueness mismatch: '+name)
        for d in details:
            require(d.get('pass') is True and d.get('errors')==[] and valid_numerical_difference(d.get('max_abs_replay_error'),1e-11) and valid_numerical_difference(d.get('abs_rmse_difference'),1e-12),'reported numerical discrepancy: '+name)
            require((root/'jobs'/d['job_id']/'final'/'receipt.json').is_file(),'missing final engineering receipt: '+name+'/'+d['job_id'])
            receipt=load(root/'jobs'/d['job_id']/'final'/'receipt.json')
            require(receipt.get('job_id')==d['job_id'] and receipt.get('production_execution_allowed') is False and receipt.get('no_confirmatory_outcomes') is True,'final receipt/lock mismatch: '+name+'/'+d['job_id'])
            require(receipt.get('rows_done')==(256 if n==8 else 32768),'wrong completed row count: '+name+'/'+d['job_id'])
        expected_names={f'{o}__{a}__{m}__{p}' for o in OBJECTS for a in SEEDS for m in MODELS for p in POLICIES}
        require({d['job_id'] for d in details}.issubset(expected_names),'non-engineering job in reported audit')
        if n==8:require({d['job_id'] for d in details}==expected_names,'AN 8 engineering factorial incomplete')
        if n==32:
            combos={(o,a,m) for o in OBJECTS for a in SEEDS for m in MODELS}
            present={tuple(d['job_id'].split('__')[:3]) for d in details}
            require(len(present)==4 and present.issubset(combos),'AO expected exactly four distinct groups')
            require(all(sum(d['job_id'].startswith('__'.join(k)+'__') for d in details)==5 for k in present),'AO incomplete policy group')
        audits.append({'stage':name,'resolution_n':n,'reported_jobs_audited':expected_jobs,'reported_groups_audited':8,
                       'plan_sha256':digest(root/'plan.json'),'audit_file_sha256':digest(apath),
                       'report_origin':'independent_auditor_stdout_captured_separately',
                       'numerical_replay_performed_by_AP':False})
    y_evidence=None
    if y_dir is not None:
        y_dir=Path(y_dir)
        status=load(y_dir/'run_status.json');decisions=load(y_dir/'scientific_decision_register.json')
        y_evidence={'run_status_sha256':digest(y_dir/'run_status.json'),'decision_register_sha256':digest(y_dir/'scientific_decision_register.json'),
                    'status':status,'decision_register':decisions}
        # Y is a review artifact, not a scientific authorization.
    evidence={'aa_manifest_sha256':digest(aa_dir/'aa_manifest.json'),'aa_spec_sha256':digest(aa_dir/'job_specifications.json'),
              'aa_count':len(specs),'aa_groups':len(groups),'aa_objects':len(objects),'aa_acquisition_seeds':len(acquisitions),
              'engineering_audits':audits,'y_review':y_evidence}
    report={'schema':SCHEMA,'verdict':'AP_READ_ONLY_EVIDENCE_RECONCILED_NOT_APPROVED',
            'evidence':evidence,'gates':GATES,'gates_blocked':5,'production_jobs_executed':0,
            'production_480_job_certified':False,'resource_policy_approved':False,'scientific_signoff':False,
            'frozen':False,'production_execution_allowed':False,'no_confirmatory_outcomes':True,
            'limitations':['AP does not run or independently repeat the numerical audits.','Audit JSON inputs are reported evidence; AP checks report fields and final receipt linkage, not numerical truth.','Source/environment freeze and named scientific approvals require separate review.','Engineering performance is not prospective evidence.']}
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=['prepare','check'],required=True)
    for name in ('output-dir','aa-dir','an8-dir','ao-dir','an8-audit','ao-audit'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--y-dir',type=Path)
    a=p.parse_args()
    report=inspect(a.aa_dir,a.an8_dir,a.ao_dir,a.an8_audit,a.ao_audit,a.y_dir)
    out=a.output_dir/'qualification_report.json'
    if a.mode=='prepare':
        if a.output_dir.exists():raise FileExistsError('AP output directory exists; refusing overwrite')
        a.output_dir.mkdir(parents=True)
        with out.open('xb') as f:f.write(canonical(report));f.flush();os.fsync(f.fileno())
    else:
        if out.read_bytes()!=canonical(report):raise ValueError('AP report changed or upstream evidence drifted')
    print(json.dumps({'verdict':report['verdict'],'pass':True,'aa_jobs':480,'aa_groups':96,'engineering_jobs_reported':60,
                      'gates_blocked':5,'production_execution_allowed':False,'report_sha256':digest(out)},indent=2))
if __name__=='__main__':main()
