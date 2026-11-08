"""08AJ-AK: immutable four-job engineering-shadow roster, guarded MART, recovery.

No prospective object seeds are accepted. Only pre-existing AF noncohort jobs
may supply numerics. AA is checked only as an execution-disabled template.
"""
from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path
import experiment_08aj_aa as aa
import experiment_08aj_af as af
import experiment_08aj_ah as ah

SCHEMA='RBYRCT-08AJ-AK-engineering-shadow-roster-v1'
POLICIES=('information_diag','uniform_multiscale')
MODELS=('same','independent')
IDS=tuple(f'{p}__{m}' for m in MODELS for p in POLICIES)

def canonical(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('ascii')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save_once(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as f:f.write(canonical(x));f.flush();os.fsync(f.fileno())
def load(p):
    p=Path(p);b=p.read_bytes();r=json.loads(b)
    if b!=canonical(r):raise ValueError('noncanonical AK receipt: '+str(p))
    return r

def expected(af_dir,aa_dir,m_dir):
    manifest,h,groups=aa.check(aa_dir,m_dir)
    if len(groups)!=96 or manifest['job_count']!=480 or manifest['confirmatory_execution_allowed'] is not False:
        raise ValueError('AA disabled roster invalid')
    p=af.check(af_dir,aa_dir,m_dir)
    if p['namespace']!='FRESH_ENGINEERING_ONLY' or p['production_execution_allowed'] is not False:
        raise ValueError('AF source not explicitly engineering-only')
    from experiment_08aj_af_audit import audit_one
    entries=[]
    for model in MODELS:
        af.validate_group(af_dir,aa_dir,m_dir,model)
        group_sha=sha(Path(af_dir)/'groups'/model/'receipt.json')
        for policy in POLICIES:
            r=audit_one(af_dir,aa_dir,m_dir,policy,model)
            if r['pass'] is not True:raise ValueError('AF numerical input not independently audited: '+policy+' '+model)
            jid=policy+'__'+model
            source=ah.plan_for(af_dir,aa_dir,m_dir,policy,model)
            if source['namespace']!='FRESH_ENGINEERING_RESOURCE_GUARD_ONLY' or source['production_execution_allowed'] is not False:
                raise ValueError('AH disabled numerical plan invalid')
            entries.append({'job_id':jid,'policy':policy,'model':model,
                'engineering_namespace':'FRESH_ENGINEERING_ONLY',
                'af_receipt_sha256':sha(Path(af_dir)/'jobs'/jid/'receipt.json'),
                'shared_group_receipt_sha256':group_sha,
                'ah_source_sha256':hashlib.sha256(canonical(source)).hexdigest(),
                'aa_template_only':True,'execution_allowed':False})
    return {'schema':SCHEMA,'namespace':'LOCKED_ENGINEERING_SHADOW_ONLY',
        'aa_manifest_sha256':h,'aa_spec_sha256':sha(Path(aa_dir)/'job_specifications.json'),
        'af_plan_sha256':sha(Path(af_dir)/'plan.json'),
        'entries':entries,'shadow_jobs':4,'shared_engineering_groups':2,
        'prospective_roster_specs':480,'prospective_groups':96,
        'scientific_signoff':False,'frozen':False,'resource_policy_approved':False,
        'production_480_job_certified':False,'production_execution_allowed':False,
        'no_confirmatory_outcomes':True}

def prepare(root,af_dir,aa_dir,m_dir):
    root=Path(root)
    if root.exists():raise FileExistsError('AK evidence exists; no overwrite')
    e=expected(af_dir,aa_dir,m_dir)
    root.mkdir(parents=True);save_once(root/'plan.json',e);(root/'jobs').mkdir()
    return {'verdict':'AK_LOCKED_SHADOW_ROSTER_PREPARED','engineering_jobs':4,
            'shared_engineering_groups':2,'production_jobs_executed':0,
            'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def check(root,af_dir,aa_dir,m_dir):
    root=Path(root)
    r=load(root/'plan.json')
    if r!=expected(af_dir,aa_dir,m_dir):raise ValueError('AK input or roster drift')
    jobs=root/'jobs'
    if not jobs.is_dir() or jobs.is_symlink():raise ValueError('missing/unsafe AK jobs folder')
    if {x.name for x in jobs.iterdir()}-set(IDS):raise ValueError('unexpected AK jobs')
    for p in jobs.iterdir():
        if not p.is_dir() or p.is_symlink():raise ValueError('unsafe AK job')
        j=load(p/'dispatch.json')
        match=next(x for x in r['entries'] if x['job_id']==p.name)
        if j!={'schema':SCHEMA,'entry':match,'plan_sha256':sha(root/'plan.json'),
              'production_execution_allowed':False,'no_confirmatory_outcomes':True}:
            raise ValueError('AK dispatch receipt changed')
        if (p/'worker').exists():
            source,folder,n,x,last=ah.verify(p/'worker',af_dir,aa_dir,m_dir)
            if source['source']['policy']!=match['policy'] or source['source']['model']!=match['model']:
                raise ValueError('AH job identity mismatch')
    return r

def dispatch(root,af_dir,aa_dir,m_dir,policy,model):
    if policy not in POLICIES or model not in MODELS:raise ValueError('engineering shadow selection restricted')
    r=check(root,af_dir,aa_dir,m_dir);jid=policy+'__'+model;d=Path(root)/'jobs'/jid
    if d.exists():return {'verdict':'AK_ENGINEERING_DISPATCH_REUSED','job_id':jid,'production_execution_allowed':False}
    entry=next(x for x in r['entries'] if x['job_id']==jid)
    d.mkdir();save_once(d/'dispatch.json',{'schema':SCHEMA,'entry':entry,
         'plan_sha256':sha(Path(root)/'plan.json'),
         'production_execution_allowed':False,'no_confirmatory_outcomes':True})
    ah.init(d/'worker',af_dir,aa_dir,m_dir,policy,model)
    check(root,af_dir,aa_dir,m_dir)
    return {'verdict':'AK_ENGINEERING_JOB_DISPATCHED','job_id':jid,'production_execution_allowed':False}

def run(root,af_dir,aa_dir,m_dir,policy,model,wall_seconds=600,max_mib=8192,stop_after_rows=None):
    if policy not in POLICIES or model not in MODELS:raise ValueError('engineering shadow selection restricted')
    check(root,af_dir,aa_dir,m_dir);jid=policy+'__'+model
    d=Path(root)/'jobs'/jid
    if not d.is_dir():raise ValueError('dispatch first')
    out=ah.supervise(d/'worker',af_dir,aa_dir,m_dir,wall_seconds,max_mib,stop_after_rows)
    return {'verdict':'AK_ENGINEERING_JOB_'+('PASS' if out['verdict'] in ('AH_ENGINEERING_RECOVERY_PASS','AH_ENGINEERING_RESULT_REUSED') else 'PAUSED' if out['verdict']=='AH_ENGINEERING_PAUSED' else 'STOPPED'),
        'job_id':jid,'worker':out,'production_jobs_executed':0,
        'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',required=True,choices=('prepare','check','dispatch','run','production-run','unlock','freeze'))
    for n in ('output-dir','af-dir','aa-dir','m-dir'):ap.add_argument('--'+n,type=Path,required=True)
    ap.add_argument('--policy');ap.add_argument('--model')
    ap.add_argument('--stop-after-rows',type=int);ap.add_argument('--wall-seconds',type=float,default=600)
    ap.add_argument('--max-mib',type=int,default=8192)
    a=ap.parse_args()
    if a.mode in ('production-run','unlock','freeze'):ap.error('PRODUCTION_EXECUTION_DISABLED')
    args=(a.output_dir,a.af_dir,a.aa_dir,a.m_dir)
    if a.mode=='prepare':result=prepare(*args)
    elif a.mode=='check':
        p=check(*args);result={'verdict':'AK_LOCKED_SHADOW_SOURCES_MATCH','engineering_jobs':len(p['entries']),
                                 'dispatched_jobs':len(list((a.output_dir/'jobs').iterdir())),
                                 'production_execution_allowed':False}
    elif a.mode=='dispatch':result=dispatch(*args,a.policy,a.model)
    else:result=run(*args,a.policy,a.model,a.wall_seconds,a.max_mib,a.stop_after_rows)
    print(json.dumps(result,indent=2))
    if result['verdict']=='AK_ENGINEERING_JOB_STOPPED':raise SystemExit(2)
if __name__=='__main__':main()
