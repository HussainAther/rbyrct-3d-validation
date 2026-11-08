"""08AJ-AF: fresh NONCOHORT engineering object, shared catalogue, audited MART jobs.

No prospective-object selection, arbitrary seeds, production-run, or unlock. The
480-job AA roster is read only to enforce disjointness and retain its lock.
"""
from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path
import numpy as np
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_08aj_e import full_resolution_pair,model_measurements,checked_mart
from experiment_08aj_g import fair_orders
import experiment_08aj_aa as aa

SCHEMA='RBYRCT-08AJ-AF-fresh-engineering-v1'
SEED=971337
FAMILY='irregular_inclusions'
ACQ=971349
NOISE={'same':971361,'independent':971363}
SOURCE_FILES=('experiment_08aj_af.py','experiment_08aj_af_audit.py')
ARRAY_FILES=('order.npy','measurements.npy','csr_data.npy','csr_indices.npy','csr_indptr.npy','reconstruction.npy')


def canonical(obj):return (json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('ascii')
def sha_file(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def load_json(p):
    b=Path(p).read_bytes();v=json.loads(b)
    if b!=canonical(v):raise ValueError('noncanonical JSON evidence '+str(p))
    return v

def create(p,b):
    with Path(p).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def save(p,x):
    with Path(p).open('xb') as f:np.save(f,np.asarray(x),allow_pickle=False);f.flush();os.fsync(f.fileno())
def cfg(n):
    if n not in (8,32):raise ValueError('only n=8 or n=32 engineering geometry permitted')
    return {'n':n,'budget':128 if n==8 else 2048,'warm':8 if n==8 else 64,'epochs':2 if n==8 else 16,'relaxation':.25}
def source_hashes():
    d=Path(__file__).resolve().parent
    return {name:sha_file(d/name) for name in SOURCE_FILES}
def validate_contract(aa_dir,m_dir):
    manifest,h,groups=aa.check(aa_dir,m_dir)
    roster=load_json(Path(aa_dir)/'job_specifications.json')
    if len(roster)!=480 or len(groups)!=96 or manifest['confirmatory_execution_allowed'] is not False:
        raise ValueError('AA production execution gate invalid')
    if any(r.get('execution_allowed') is not False or r.get('execution_status')!='BLOCKED_NOT_EXECUTED' for r in roster):
        raise ValueError('AA production roster has unauthorized jobs')
    # Refuse a hardcoded engineering object or acquisition seed if it ever enters the cohort.
    if SEED in {int(r['object_seed']) for r in roster} or ACQ in {int(r['acquisition_seed']) for r in roster}:
        raise ValueError('engineering seed overlaps 24-object prospective design')
    return h,sha_file(Path(aa_dir)/'job_specifications.json')
def plan_for(n,aa_h,spec_h):
    return {'schema':SCHEMA,'namespace':'FRESH_ENGINEERING_ONLY','family':FAMILY,
       'engineering_seed':SEED,'acquisition_seed':ACQ,'noise_seed_by_model':NOISE,
       **cfg(n),'aa_manifest_sha256':aa_h,'aa_spec_sha256':spec_h,
       'source_sha256':source_hashes(),'allowed_policies':list(aa.POLICIES),
       'allowed_models':list(aa.MODELS),'production_roster_jobs':480,
       'production_jobs_executed':0,'production_execution_allowed':False,
       'resource_policy_approved':False,'scientific_signoff':False,'frozen':False,
       'no_confirmatory_outcomes':True}
def initialize(root,aa_dir,m_dir,n=8):
    root=Path(root)
    if root.exists():raise FileExistsError('AF evidence already exists; do not overwrite')
    ah,sh=validate_contract(aa_dir,m_dir)
    plan=plan_for(n,ah,sh)
    root.mkdir(parents=True)
    create(root/'plan.json',canonical(plan))
    (root/'groups').mkdir();(root/'jobs').mkdir()
    return {'verdict':'AF_FRESH_ENGINEERING_PREPARED','n':n,
       'engineering_policy_model_jobs':10,'production_jobs_executed':0,
       'production_execution_allowed':False,'no_confirmatory_outcomes':True}
def check(root,aa_dir,m_dir):
    root=Path(root)
    ah,sh=validate_contract(aa_dir,m_dir)
    p=load_json(root/'plan.json')
    if p!=plan_for(p['n'],ah,sh):raise ValueError('AF plan or source drift')
    for sub,allowed in [('groups',aa.MODELS),('jobs',{f'{a}__{b}' for a in aa.POLICIES for b in aa.MODELS})]:
        d=root/sub
        if not d.is_dir() or d.is_symlink():raise ValueError('missing/unsafe '+sub)
        if any(x.is_symlink() or x.name not in allowed for x in d.iterdir()):raise ValueError('unexpected '+sub+' evidence')
    return p

def build_group(root,aa_dir,m_dir,model):
    p=check(root,aa_dir,m_dir)
    if model not in aa.MODELS:raise ValueError('unknown model')
    dst=Path(root)/'groups'/model
    if dst.exists():
        validate_group(root,aa_dir,m_dir,model)
        return {'verdict':'AF_SHARED_CATALOGUE_REUSED','model':model,'production_execution_allowed':False}
    stage=Path(root)/'groups'/('.staging_'+model)
    if stage.exists():raise RuntimeError('incomplete catalogue staging; manual audit required')
    stage.mkdir()
    n=p['n'];A=system_matrix(n,4,TILTS).tocsr()
    truth,fine=full_resolution_pair(FAMILY,SEED,n)
    clean,noisy=model_measurements(A,truth,fine,n=n,angles=4,model=model,noise_seed=NOISE[model],noise_fraction=.005)
    if clean.shape!=(12*n*n,) or noisy.shape!=(12*n*n,) or not np.isfinite(noisy).all():raise ValueError('invalid fresh catalogue')
    save(stage/'clean.npy',clean);save(stage/'noisy.npy',noisy)
    r={'schema':SCHEMA,'model':model,'plan_sha256':sha_file(Path(root)/'plan.json'),
       'namespace':'FRESH_ENGINEERING_ONLY','truth_sha256':sha_bytes(np.asarray(truth,dtype='<f8').tobytes()),
       'clean_sha256':sha_file(stage/'clean.npy'),'noisy_sha256':sha_file(stage/'noisy.npy'),
       'production_execution_allowed':False,'no_confirmatory_outcomes':True}
    create(stage/'receipt.json',canonical(r));stage.rename(dst)
    return {'verdict':'AF_SHARED_CATALOGUE_PREPARED','model':model,'candidate_rays':12*n*n,'production_execution_allowed':False,'no_confirmatory_outcomes':True}
def validate_group(root,aa_dir,m_dir,model):
    p=check(root,aa_dir,m_dir)
    d=Path(root)/'groups'/model
    if not d.is_dir() or d.is_symlink() or {x.name for x in d.iterdir()}!={'clean.npy','noisy.npy','receipt.json'}:raise ValueError('invalid group files')
    r=load_json(d/'receipt.json')
    if r!={'schema':SCHEMA,'model':model,'plan_sha256':sha_file(Path(root)/'plan.json'),
       'namespace':'FRESH_ENGINEERING_ONLY','truth_sha256':r.get('truth_sha256'),
       'clean_sha256':sha_file(d/'clean.npy'),'noisy_sha256':sha_file(d/'noisy.npy'),
       'production_execution_allowed':False,'no_confirmatory_outcomes':True}:raise ValueError('catalogue receipt mismatch')
    A=system_matrix(p['n'],4,TILTS).tocsr();truth,fine=full_resolution_pair(FAMILY,SEED,p['n'])
    cc,nn=model_measurements(A,truth,fine,n=p['n'],angles=4,model=model,noise_seed=NOISE[model],noise_fraction=.005)
    stored_cc=np.load(d/'clean.npy',allow_pickle=False);stored_nn=np.load(d/'noisy.npy',allow_pickle=False)
    if r['truth_sha256']!=sha_bytes(np.asarray(truth,dtype='<f8').tobytes()) or not np.array_equal(cc,stored_cc) or not np.array_equal(nn,stored_nn):raise ValueError('fresh catalogue does not regenerate')
    return p,A,truth,stored_nn

def execute(root,aa_dir,m_dir,policy,model):
    if policy not in aa.POLICIES or model not in aa.MODELS:raise ValueError('not an engineering template')
    p,A,truth,noisy=validate_group(root,aa_dir,m_dir,model)
    jid=policy+'__'+model;dst=Path(root)/'jobs'/jid
    if dst.exists():
        from experiment_08aj_af_audit import audit_one
        a=audit_one(root,aa_dir,m_dir,policy,model)
        if not a['pass']:raise ValueError('existing AF job failed independent audit')
        return {'verdict':'AF_ENGINEERING_JOB_REUSED','job_id':jid,'production_execution_allowed':False}
    stage=Path(root)/'jobs'/('.staging_'+jid)
    if stage.exists():raise RuntimeError('incomplete job staging preserved')
    stage.mkdir()
    orders,_=fair_orders(A,n=p['n'],angles=4,seed=ACQ,budget=p['budget'],warm=p['warm'],pool=16,batch=8 if p['n']==8 else 32)
    order=np.asarray(orders[policy],dtype=np.int64)
    if order.shape!=(p['budget'],) or len(set(order.tolist()))!=p['budget']:raise ValueError('invalid acquisition order')
    recon=np.asarray(checked_mart(A,noisy,order,epochs=p['epochs'],relaxation=p['relaxation']),dtype=np.float64)
    sub=A[order].tocsr();rmse=float(np.sqrt(np.mean((recon-truth)**2)))
    vals={'order.npy':order,'measurements.npy':noisy[order],
          'csr_data.npy':sub.data,'csr_indices.npy':sub.indices,
          'csr_indptr.npy':sub.indptr,'reconstruction.npy':recon}
    for name,arr in vals.items():
        if not np.isfinite(arr).all():raise ValueError('nonfinite numerical output')
        save(stage/name,arr)
    r={'schema':SCHEMA,'namespace':'FRESH_ENGINEERING_ONLY','job_id':jid,
       'plan_sha256':sha_file(Path(root)/'plan.json'),
       'group_receipt_sha256':sha_file(Path(root)/'groups'/model/'receipt.json'),
       'artifact_sha256':{k:sha_file(stage/k) for k in ARRAY_FILES},
       'truth_sha256':sha_bytes(np.asarray(truth,dtype='<f8').tobytes()),
       'rmse':rmse,'production_execution_allowed':False,'no_confirmatory_outcomes':True}
    create(stage/'receipt.json',canonical(r));stage.rename(dst)
    return {'verdict':'AF_FRESH_ENGINEERING_JOB_PASS','job_id':jid,'n':p['n'],'epochs':p['epochs'],
      'production_jobs_executed':0,'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',required=True,choices=('init','catalogue','run','check','production-run','unlock','freeze'))
    for x in ('output-dir','aa-dir','m-dir'):ap.add_argument('--'+x,type=Path,required=True)
    ap.add_argument('--n',type=int,choices=(8,32),default=8)
    ap.add_argument('--model',choices=aa.MODELS);ap.add_argument('--policy',choices=aa.POLICIES)
    a=ap.parse_args()
    if a.mode in ('production-run','unlock','freeze'):ap.error('PROSPECTIVE_EXECUTION_DISABLED')
    if a.mode=='init':res=initialize(a.output_dir,a.aa_dir,a.m_dir,a.n)
    elif a.mode=='check':
        p=check(a.output_dir,a.aa_dir,a.m_dir)
        res={'verdict':'AF_SOURCE_AND_PRODUCTION_LOCK_PASS','n':p['n'],'production_execution_allowed':False}
    elif a.mode=='catalogue':
        if not a.model:ap.error('--model required')
        res=build_group(a.output_dir,a.aa_dir,a.m_dir,a.model)
    else:
        if not a.model or not a.policy:ap.error('--policy and --model required')
        res=execute(a.output_dir,a.aa_dir,a.m_dir,a.policy,a.model)
    print(json.dumps(res,indent=2))
if __name__=='__main__':main()
