"""08AJ-AE: locked engineering dispatcher for AA policy/model templates and AD checkpointed MART.

Never executes an AA production job. Its only jobs are the 10 policy/model
engineering templates, using previously audited AB noncohort numerical inputs.
"""
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path
import experiment_08aj_aa as aa
import experiment_08aj_ab as ab
import experiment_08aj_ad as ad

SCHEMA='RBYRCT-08AJ-AE-locked-engineering-dispatch-v1'
SRC=('experiment_08aj_ae.py','experiment_08aj_ae_audit.py','experiment_08aj_ad.py','experiment_08aj_ad_audit.py')

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('ascii')
def receipt(p):
    b=Path(p).read_bytes();x=json.loads(b)
    if b!=canonical(x):raise ValueError('noncanonical receipt '+str(p))
    return x

def store(p,record):
    with Path(p).open('xb') as f:
        f.write(canonical(record));f.flush();os.fsync(f.fileno())

def template_counts(aa_dir):
    r=receipt(Path(aa_dir)/'job_specifications.json')
    if len(r)!=480:raise ValueError('wrong AA roster size')
    counts={(p,m):0 for p in aa.POLICIES for m in aa.MODELS}
    for job in r:
        if job.get('execution_allowed') is not False or job.get('execution_status')!='BLOCKED_NOT_EXECUTED':raise ValueError('AA job unlocked')
        key=(job['policy'],job['model'])
        if key not in counts:raise ValueError('unknown AA template')
        counts[key]+=1
    if any(n!=48 for n in counts.values()):raise ValueError('AA template counts !=48')
    return counts

def context(aa_dir,m_dir,ab_dir):
    manifest,h,groups=aa.check(aa_dir,m_dir)
    plan,ph=ab.check(ab_dir,aa_dir,m_dir)
    if len(groups)!=96 or manifest.get('confirmatory_execution_allowed') is not False:raise ValueError('AA gate invalid')
    if plan['engineering_seed']!=ad.SEED or plan['namespace']!='ENGINEERING_SHADOW_ONLY' or plan['n'] not in (8,32):raise ValueError('non-engineering AB inputs')
    counts=template_counts(aa_dir)
    root=Path(__file__).resolve().parent
    return {'schema':SCHEMA,'aa_manifest_sha256':h,
        'aa_job_specifications_sha256':digest(Path(aa_dir)/'job_specifications.json'),
        'ab_plan_sha256':ph,'engineering_seed':ad.SEED,'n':plan['n'],
        'policy_model_templates':{p+'__'+m:counts[(p,m)] for p in aa.POLICIES for m in aa.MODELS},
        'sources_sha256':{name:digest(root/name) for name in SRC},
        'jobs_allowed':10,'production_roster_jobs':480,'production_jobs_executed':0,
        'production_execution_allowed':False,'production_480_job_certified':False,
        'resource_policy_approved':False,'scientific_signoff':False,
        'frozen':False,'no_confirmatory_outcomes':True}

def init(out,aa_dir,m_dir,ab_dir):
    out=Path(out)
    if out.exists():raise FileExistsError('AE evidence already exists; no overwrite')
    p=context(aa_dir,m_dir,ab_dir)
    out.mkdir(parents=True);store(out/'dispatch_plan.json',p);(out/'jobs').mkdir()
    return {'verdict':'AE_ENGINEERING_DISPATCH_PREPARED','engineering_templates':10,'aa_production_specs':480,
      'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def check(out,aa_dir,m_dir,ab_dir):
    out=Path(out)
    p=receipt(out/'dispatch_plan.json')
    if p!=context(aa_dir,m_dir,ab_dir):raise ValueError('AE source or contract drift')
    jobs=out/'jobs'
    if not jobs.is_dir() or jobs.is_symlink():raise ValueError('unsafe AE jobs directory')
    allowed=set(p['policy_model_templates'])
    for path in jobs.iterdir():
        if path.is_symlink() or not path.is_dir() or path.name not in allowed:raise ValueError('unexpected AE job directory')
        if not (path/'dispatch.json').is_file() or (path/'dispatch.json').is_symlink():raise ValueError('missing AE dispatch receipt')
        r=receipt(path/'dispatch.json')
        if r!=dispatch_record(p,path.name,digest(path/'numerical'/'plan.json')):raise ValueError('AE dispatch receipt mismatch')
        numerical=path/'numerical'
        if not numerical.is_dir() or numerical.is_symlink():raise ValueError('unsafe AD numerical dir')
        if r['ad_plan_sha256']!=digest(numerical/'plan.json'):raise ValueError('AD plan fingerprint changed')
    return p

def dispatch_record(p,jid,ad_sha=None):
    return {'schema':SCHEMA,'job_id':jid,'namespace':'ENGINEERING_SHADOW_ONLY',
        'aa_template_count':p['policy_model_templates'][jid],
        'ae_plan_sha256':hashlib.sha256(canonical(p)).hexdigest(),
        'ad_plan_sha256':ad_sha,
        'production_job_id':None,'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def dispatch(out,aa_dir,m_dir,ab_dir,policy,model):
    p=check(out,aa_dir,m_dir,ab_dir)
    jid=ab.job_id(policy,model)
    if jid not in p['policy_model_templates']:raise ValueError('not authorized template')
    # Independently inspect source job before creating any AE evidence.
    ad.validate_ab(ab_dir,aa_dir,m_dir,policy,model)
    root=Path(out)/'jobs'/jid
    if root.exists():
        from experiment_08aj_ad_audit import audit as ad_audit
        ad.check_inputs(root/'numerical',ab_dir,aa_dir,m_dir)
        ad.verify_chain(root/'numerical',receipt(root/'numerical'/'plan.json'))
        if (root/'numerical'/'final.json').exists():
            audited=ad_audit(root/'numerical',ab_dir,aa_dir,m_dir)
            if not audited['pass']:raise ValueError('completed engineering job failed audit')
        return {'verdict':'AE_ENGINEERING_DISPATCH_REUSED','job_id':jid,'production_execution_allowed':False}
    root.mkdir();numerical=root/'numerical'
    ad.initialize(numerical,ab_dir,aa_dir,m_dir,policy,model)
    store(root/'dispatch.json',dispatch_record(p,jid,digest(numerical/'plan.json')))
    return {'verdict':'AE_ENGINEERING_TEMPLATE_DISPATCHED','job_id':jid,'n':p['n'],
      'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def execute(out,aa_dir,m_dir,ab_dir,policy,model,stop_after_rows=None,wall_seconds=600):
    p=check(out,aa_dir,m_dir,ab_dir)
    jid=ab.job_id(policy,model)
    folder=Path(out)/'jobs'/jid
    if not folder.is_dir():raise ValueError('dispatch template before executing')
    result=ad.run(folder/'numerical',ab_dir,aa_dir,m_dir,stop_after_rows,wall_seconds)
    return {'verdict':'AE_ENGINEERING_EXECUTION_'+('PAUSED' if 'INTERRUPTED' in result['verdict'] else 'PASS'),
      'ad_verdict':result['verdict'],'job_id':jid,'rows_done':result['rows_done'],
      'production_jobs_executed':0,'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',choices=('init','check','dispatch','run','audit','production-run','unlock','freeze'),required=True)
    for name in ('output-dir','aa-dir','m-dir','ab-dir'):ap.add_argument('--'+name,required=True,type=Path)
    ap.add_argument('--policy',choices=aa.POLICIES);ap.add_argument('--model',choices=aa.MODELS)
    ap.add_argument('--stop-after-rows',type=int);ap.add_argument('--wall-seconds',type=float,default=600)
    x=ap.parse_args()
    if x.mode in ('production-run','unlock','freeze'):ap.error('PROSPECTIVE_EXECUTION_DISABLED: scientific signoff and source freeze absent')
    if x.mode=='init':res=init(x.output_dir,x.aa_dir,x.m_dir,x.ab_dir)
    elif x.mode=='check':
        p=check(x.output_dir,x.aa_dir,x.m_dir,x.ab_dir)
        res={'verdict':'AE_SOURCE_AND_ENGINEERING_GATE_MATCH','dispatched_jobs':len(list((x.output_dir/'jobs').iterdir())),
             'aa_production_specs':480,'production_execution_allowed':False}
    elif x.mode=='audit':
        from experiment_08aj_ae_audit import audit
        res=audit(x.output_dir,x.aa_dir,x.m_dir,x.ab_dir)
        print(json.dumps(res,indent=2))
        if not res['pass']:raise SystemExit(2)
        return
    else:
        if x.policy is None or x.model is None:ap.error('dispatch/run require --policy and --model')
        if x.mode=='dispatch':res=dispatch(x.output_dir,x.aa_dir,x.m_dir,x.ab_dir,x.policy,x.model)
        else:res=execute(x.output_dir,x.aa_dir,x.m_dir,x.ab_dir,x.policy,x.model,x.stop_after_rows,x.wall_seconds)
    print(json.dumps(res,indent=2))
if __name__=='__main__':main()
