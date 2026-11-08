"""08AJ-AR engineering-only manifest-to-worker dispatch, bound to AA and AN.

Only an internal, hardcoded noncohort fixture roster can execute. It deliberately
has no prospective loader, arbitrary object parameters, unlock, or production mode.
Actual numerical work is delegated to AN's guarded MART worker and checkpointing.
"""
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path
import experiment_08aj_an as an
import experiment_08aj_aa as aa

SCHEMA='RBYRCT-08AJ-AR-manifest-driven-noncohort-numerical-adapter-v1'
POLICIES=('information_diag','uniform_multiscale','coverage','stratified_random_04h','complete_view')
MODELS=('same','independent')
SOURCE_FILES=('experiment_08aj_ar.py','experiment_08aj_ar_audit.py')

def digest(data):return hashlib.sha256(data).hexdigest()
def canonical(obj):return (json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('ascii')
def source_hashes():
    folder=Path(__file__).resolve().parent
    return {name:digest((folder/name).read_bytes()) for name in SOURCE_FILES}
def plain(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file():raise ValueError('missing or symlinked evidence file: '+str(path))
    b=path.read_bytes();data=json.loads(b)
    if b!=canonical(data):raise ValueError('noncanonical or modified evidence file: '+str(path))
    return data
def write_new(path,obj):
    path=Path(path)
    with path.open('xb') as f:
        f.write(canonical(obj));f.flush();os.fsync(f.fileno())
def identifier(obj,seed,model,policy):return f'{obj}__{seed}__{model}__{policy}'
def fixed_roster():
    if tuple(an.POLICIES)!=POLICIES or tuple(an.MODELS)!=MODELS:raise ValueError('AN policy/model contract changed')
    items=[]
    for obj in an.OBJECTS:
        for acq in an.ACQUISITIONS:
            for model in MODELS:
                for policy in POLICIES:
                    items.append({'schema':'RBYRCT-08AJ-AR-engineering-job-v1',
                        'job_id':identifier(obj,acq,model,policy),
                        'group_id':an.group_name(obj,acq,model),'object_id':obj,
                        'family':an.OBJECTS[obj]['family'],
                        'object_seed':an.OBJECTS[obj]['seed'],
                        'acquisition_id':acq,'acquisition_seed':an.ACQUISITIONS[acq],
                        'noise_seed':an.noise_seed(obj,acq,model),'model':model,'policy':policy,
                        'execution_scope':'ENGINEERING_ONLY','execution_allowed':True,
                        'production_execution_allowed':False})
    return items

def expected(aa_dir,m_dir,n):
    if n not in (8,32):raise ValueError('engineering n only')
    # Validate the actual 480-row AA contract rather than just its existence.
    manifest,aa_hash,groups=aa.check(aa_dir,m_dir)
    if len(groups)!=96 or manifest['confirmatory_execution_allowed'] is not False:raise ValueError('AA production gate drift')
    an.protected(aa_dir,m_dir) # explicitly prohibit seed overlap with prospective cohort
    rows=fixed_roster()
    prospective={int(x['object_seed']) for x in plain(Path(aa_dir)/'job_specifications.json')}
    if any(x['object_seed'] in prospective for x in rows):raise ValueError('prospective seed overlap')
    return {'schema':SCHEMA,'namespace':'NONCOHORT_ENGINEERING_ONLY',
        'n':n,'ray_budget':128 if n==8 else 2048,'mart_epochs':2 if n==8 else 16,
        'relaxation':.25,'warm_prefix':8 if n==8 else 64,
        'aa_manifest_sha256':aa_hash,'aa_contract_jobs':480,'aa_shared_groups':96,
        'source_sha256':source_hashes(),
        'an_source_sha256':an.src_sha(),
        'jobs':rows,'job_count':len(rows),'group_count':8,
        'production_execution_allowed':False,'production_480_job_certified':False,
        'resource_policy_approved':False,'scientific_signoff':False,'frozen':False,
        'no_confirmatory_outcomes':True}

def prepare(root,aa_dir,m_dir,n):
    root=Path(root)
    if root.exists():raise FileExistsError('AR evidence root exists; no overwrite')
    p=expected(aa_dir,m_dir,n)
    root.mkdir(parents=True)
    try:
        write_new(root/'ar_manifest.json',p)
        an.init(root/'engine',aa_dir,m_dir,n)
    except Exception:
        # Keep partially committed evidence for forensic inspection, no implicit cleanup.
        raise
    return {'verdict':'AR_ENGINEERING_MANIFEST_PREPARED','jobs':40,'groups':8,'n':n,
            'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def check(root,aa_dir,m_dir):
    root=Path(root)
    p=plain(root/'ar_manifest.json')
    if p!=expected(aa_dir,m_dir,p['n']):raise ValueError('AR manifest or source drift')
    engine=root/'engine'
    if engine.is_symlink() or not engine.is_dir():raise ValueError('unsafe engine root')
    q=an.check(engine,aa_dir,m_dir)
    if q['config']['n']!=p['n']:raise ValueError('AN resolution drift')
    return p

def lookup(root,aa_dir,m_dir,job_id):
    p=check(root,aa_dir,m_dir)
    rows=[x for x in p['jobs'] if x['job_id']==job_id]
    if len(rows)!=1 or job_id not in {x['job_id'] for x in fixed_roster()}:raise ValueError('AR job not allowlisted')
    return p,rows[0]

def dispatch(root,aa_dir,m_dir,job_id,mode,wall_seconds=600,max_mib=8192,stop_after_rows=None):
    _,j=lookup(root,aa_dir,m_dir,job_id)
    args=(Path(root)/'engine',aa_dir,m_dir,j['object_id'],j['acquisition_id'],j['model'])
    if mode=='catalogue':
        r=an.catalogue(*args)
    elif mode=='dispatch':
        r=an.prepare_job(*args,j['policy'])
    elif mode=='run':
        # Run is invoked only after job/inputs/AN immutable source validation.
        r=an.run(*args,j['policy'],wall_seconds,max_mib,stop_after_rows)
    else:raise ValueError('unsupported operation')
    return {'verdict':'AR_'+r['verdict'],'manifest_job_id':job_id,
            'engine_result':r,'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',required=True,choices=('prepare','check','catalogue','dispatch','run','production-run','unlock','freeze'))
    for x in ('output-dir','aa-dir','m-dir'):ap.add_argument('--'+x,required=True,type=Path)
    ap.add_argument('--n',type=int,choices=(8,32),default=8)
    ap.add_argument('--job-id')
    ap.add_argument('--stop-after-rows',type=int)
    ap.add_argument('--wall-seconds',type=float,default=600)
    ap.add_argument('--max-mib',type=int,default=8192)
    a=ap.parse_args()
    if a.mode in ('production-run','unlock','freeze'):ap.error('PROSPECTIVE_EXECUTION_DISABLED')
    args=(a.output_dir,a.aa_dir,a.m_dir)
    if a.mode=='prepare':r=prepare(*args,a.n)
    elif a.mode=='check':
        p=check(*args);r={'verdict':'AR_LOCKED_ENGINEERING_MANIFEST_MATCH','jobs':p['job_count'],
            'groups':p['group_count'],'production_execution_allowed':False}
    else:
        if not a.job_id:ap.error('--job-id required')
        r=dispatch(*args,a.job_id,a.mode,a.wall_seconds,a.max_mib,a.stop_after_rows)
    print(json.dumps(r,indent=2))
    if r.get('engine_result',{}).get('verdict') in ('AN_GUARD_STOP','AN_WORKER_FAILED'):raise SystemExit(2)
if __name__=='__main__':main()
