"""08AJ-AB: genuine shadow numerical backend for a disabled 480-job specification.

The only executable namespace is ENGINEERING_SHADOW with the hardcoded noncohort
seed 970099. No production-object ID, arbitrary seed, unlock, or source-freeze
command exists. Real MART runs and immutable artifacts are generated per job.
"""
from __future__ import annotations
import argparse, hashlib, json, os, time
from pathlib import Path
import numpy as np
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_08aj_e import full_resolution_pair, model_measurements, checked_mart
from experiment_08aj_g import fair_orders
import experiment_08aj_aa as aa
import experiment_08aj_q as q

SCHEMA='RBYRCT-08AJ-AB-engineering-shadow-backend-v1'
SOURCE_NAMES=('experiment_08aj_ab.py','experiment_08aj_ab_audit.py', 'experiment_08aj_aa.py',
 'experiment_08aj_m.py','experiment_08aj_q.py','experiment_08aj_g.py','experiment_08aj_e.py',
 'experiment_04b.py','experiment_04g.py','experiment_04qa.py','experiment_05b_mart.py')
FILES=('order.npy','measurements.npy','clean_catalogue.npy','noisy_catalogue.npy',
       'csr_data.npy','csr_indices.npy','csr_indptr.npy','reconstruction.npy')
POLICIES=aa.POLICIES
MODELS=aa.MODELS
ENGINEERING_SEED=970099
ENGINEERING_FAMILY='smooth_heterogeneity'
ENGINEERING_ACQ=940411
ENGINEERING_NOISE=970119

def canonical(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('ascii')
def digest(data):return hashlib.sha256(data).hexdigest()
def file_sha(p):return digest(Path(p).read_bytes())
def source_sha():
    base=Path(__file__).resolve().parent
    return {name:file_sha(base/name) for name in SOURCE_NAMES}
def write_new(p,data):
    p=Path(p)
    with p.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
def save_new(p,arr):
    with Path(p).open('xb') as f:np.save(f,arr,allow_pickle=False);f.flush();os.fsync(f.fileno())
def job_id(policy,model):
    if policy not in POLICIES or model not in MODELS:raise ValueError('unauthorized engineering shadow job')
    return policy+'__'+model

def make_plan(n,aa_manifest_sha,aa_spec_sha):
    if n not in (8,32):raise ValueError('engineering resolution must be 8 or 32')
    return {'schema':SCHEMA,'namespace':'ENGINEERING_SHADOW_ONLY','engineering_seed':ENGINEERING_SEED,
       'family':ENGINEERING_FAMILY,'acquisition_seed':ENGINEERING_ACQ,'noise_seed':ENGINEERING_NOISE,
       'n':n,'budget':128 if n==8 else 2048,'warm':8 if n==8 else 64,
       'epochs':2 if n==8 else 16,'relaxation':.25,'noise_fraction':.005,
       'policies':list(POLICIES),'models':list(MODELS),
       'aa_manifest_sha256':aa_manifest_sha,'aa_spec_sha256':aa_spec_sha,
       'source_sha256':source_sha(),
       'production_roster_size':480,'production_jobs_executed':0,
       'production_execution_allowed':False,'scientific_signoff':False,'resource_policy_approved':False,
       'frozen':False,'no_confirmatory_outcomes':True}

def init(root,aa_dir,m_dir,n=8):
    root=Path(root)
    if root.exists():raise FileExistsError('will not overwrite existing AB evidence')
    _,amh,_=aa.check(aa_dir,m_dir)
    aspec=file_sha(Path(aa_dir)/'job_specifications.json')
    plan=make_plan(n,amh,aspec)
    root.mkdir(parents=True)
    write_new(root/'ab_plan.json',canonical(plan))
    (root/'jobs').mkdir()
    return {'verdict':'AB_ENGINEERING_BACKEND_PREPARED','engineering_jobs':10,'n':n,
            'production_jobs':480,'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def check(root,aa_dir,m_dir):
    root=Path(root)
    _,amh,_=aa.check(aa_dir,m_dir)
    blob=(root/'ab_plan.json').read_bytes()
    plan=json.loads(blob)
    expected=make_plan(plan['n'],amh,file_sha(Path(aa_dir)/'job_specifications.json'))
    if blob!=canonical(plan) or plan!=expected:raise ValueError('AB_SOURCE_OR_EXECUTION_GATE_MISMATCH')
    jobs=root/'jobs'
    if not jobs.is_dir() or jobs.is_symlink():raise ValueError('missing/unsafe jobs directory')
    allowed={job_id(p,m) for p in POLICIES for m in MODELS}
    for child in jobs.iterdir():
        if child.is_symlink() or (child.name not in allowed and not child.name.startswith('.staging__')):
            raise ValueError('unexpected job path '+child.name)
    return plan,digest(blob)

def perform(root,aa_dir,m_dir,policy,model,*,interrupt_after_commit=False):
    from experiment_08aj_ab_audit import audit_one
    jid=job_id(policy,model)
    root=Path(root);plan,ph=check(root,aa_dir,m_dir)
    dst=root/'jobs'/jid
    if dst.exists():
        result=audit_one(root,aa_dir,m_dir,policy,model)
        if not result['pass']:raise ValueError('existing job failed independent audit: '+str(result['errors']))
        return {'verdict':'AB_ENGINEERING_JOB_REUSED','job_id':jid,'replay_error':result['max_abs_replay_error'],
                'production_execution_allowed':False,'no_confirmatory_outcomes':True}
    stage=root/'jobs'/('.staging__'+jid)
    if stage.exists():raise RuntimeError('incomplete staging preserved; investigate before controlled retry: '+str(stage))
    stage.mkdir()
    started=time.perf_counter()
    try:
        n=plan['n'];budget=plan['budget']
        A=system_matrix(n,4,TILTS).tocsr()
        orders,_=fair_orders(A,n=n,angles=4,seed=ENGINEERING_ACQ,budget=budget,
                             warm=plan['warm'],pool=16,batch=8 if n==8 else 32)
        order=np.asarray(orders[policy],dtype=np.int64)
        truth,fine=full_resolution_pair(ENGINEERING_FAMILY,ENGINEERING_SEED,n)
        clean,noisy=model_measurements(A,truth,fine,n=n,angles=4,model=model,
                  noise_seed=ENGINEERING_NOISE,noise_fraction=.005)
        rec=np.asarray(checked_mart(A,noisy,order,epochs=plan['epochs'],relaxation=.25))
        sub=A[order].tocsr()
        arrays={'order.npy':order,'measurements.npy':noisy[order],
                'clean_catalogue.npy':clean,'noisy_catalogue.npy':noisy,
                'csr_data.npy':sub.data,'csr_indices.npy':sub.indices,
                'csr_indptr.npy':sub.indptr,'reconstruction.npy':rec}
        if set(arrays)!=set(FILES) or any(not np.isfinite(v).all() for v in arrays.values()) or np.any(rec<=0):
            raise ValueError('invalid engineering numerical arrays')
        for name in FILES:save_new(stage/name,arrays[name])
        rmse=float(np.sqrt(np.mean((rec-truth)**2)))
        receipt={'schema':SCHEMA,'job_id':jid,'policy':policy,'model':model,'plan_sha256':ph,
                 'n':n,'budget':budget,'epochs':plan['epochs'],
                 'truth_sha256':digest(np.asarray(truth,dtype='<f8').tobytes()),
                 'rmse':rmse,'elapsed_seconds':time.perf_counter()-started,
                 'artifact_sha256':{name:file_sha(stage/name) for name in FILES},
                 'engineering_only':True,'production_execution_allowed':False,'no_confirmatory_outcomes':True}
        write_new(stage/'receipt.json',canonical(receipt))
        stage.rename(dst)
    except Exception:
        # Preserve staged files on any error. Re-execution cannot hide a failed attempt.
        raise
    if interrupt_after_commit:raise RuntimeError('SIMULATED_INTERRUPTION_AFTER_COMMIT')
    return {'verdict':'AB_NUMERICAL_ENGINEERING_JOB_PASS','job_id':jid,'n':plan['n'],
            'epochs':plan['epochs'],'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir',required=True,type=Path)
    ap.add_argument('--aa-dir',required=True,type=Path)
    ap.add_argument('--m-dir',required=True,type=Path)
    ap.add_argument('--mode',required=True,choices=('init','check','run'))
    ap.add_argument('--n',type=int,choices=(8,32),default=8)
    ap.add_argument('--policy',choices=POLICIES);ap.add_argument('--model',choices=MODELS)
    opt=ap.parse_args()
    if opt.mode=='init':out=init(opt.output_dir,opt.aa_dir,opt.m_dir,opt.n)
    elif opt.mode=='check':
        _,h=check(opt.output_dir,opt.aa_dir,opt.m_dir)
        out={'verdict':'AB_SOURCE_AND_LOCK_PASS','plan_sha256':h,'production_execution_allowed':False}
    else:
        if opt.policy is None or opt.model is None:ap.error('run requires policy and model')
        out=perform(opt.output_dir,opt.aa_dir,opt.m_dir,opt.policy,opt.model)
    print(json.dumps(out,indent=2))
if __name__=='__main__':main()
