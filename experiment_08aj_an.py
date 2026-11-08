"""08AJ-AN: two noncohort objects, two acquisition seeds, all five policies,
atomic row-level MART checkpoints and supervised engineering-only execution.

This is NOT a prospective 24-object runner; all arbitrary objects, seeds,
production unlocks, and external inputs are rejected. Existing AF/AH evidence
is not modified.
"""
from __future__ import annotations
import argparse, hashlib, io, json, os, subprocess, sys, time
from pathlib import Path
import numpy as np
import experiment_08aj_aa as aa
import experiment_08aj_af as af
import experiment_08aj_ah as ah
import experiment_08aj_ad as ad
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_08aj_e import full_resolution_pair, model_measurements
from experiment_08aj_g import fair_orders

SCHEMA='RBYRCT-08AJ-AN-multi-seed-five-policy-engineering-v1'
OBJECTS={'engineering_alpha':{'seed':972101,'family':'localized_defects'},
         'engineering_beta':{'seed':972103,'family':'smooth_heterogeneity'}}
POLICIES=tuple(aa.POLICIES)
MODELS=('same','independent')
ACQUISITIONS={'seed_a':972119,'seed_b':972121}
def noise_seed(obj,acq,model):
    """Independent deterministic noise per object/acquisition/model; shared by policies."""
    key=f'RBYRCT-AN|{obj}|{acq}|{model}'.encode('ascii')
    return 1+int.from_bytes(hashlib.sha256(key).digest()[:8],'big')%2147483646

CHECKPOINT_INTERVAL=256
SOURCE_FILES=('experiment_08aj_an.py','experiment_08aj_an_audit.py')

def canonical(x):return af.canonical(x)
def sha(path):return af.sha_file(path)
def read(path):return af.load_json(path)
def write(path,value):af.create(path,canonical(value))
def array_bytes(x):
    b=io.BytesIO();np.save(b,np.asarray(x),allow_pickle=False);return b.getvalue()
def array(path,x):af.save(path,x)
def src_sha():
    folder=Path(__file__).resolve().parent
    return {name:sha(folder/name) for name in SOURCE_FILES}
def protected(aa_dir,m_dir):
    aa_hash,spec_hash=af.validate_contract(aa_dir,m_dir)
    roster=read(Path(aa_dir)/'job_specifications.json')
    used_objects={int(row['object_seed']) for row in roster}
    used_acquisition={int(row['acquisition_seed']) for row in roster}
    if len(set(x['seed'] for x in OBJECTS.values()))!=2 or any(x['seed'] in used_objects for x in OBJECTS.values()):
        raise ValueError('engineering object overlaps prospective roster')
    if (len(set(ACQUISITIONS.values()))!=2 or
        any(v in used_acquisition or v in used_objects for v in ACQUISITIONS.values())):
        raise ValueError('engineering acquisition overlaps prospective roster')
    noises={noise_seed(o,a,m) for o in OBJECTS for a in ACQUISITIONS for m in MODELS}
    if len(noises)!=8 or noises & (used_acquisition|used_objects|set(ACQUISITIONS.values())|{x['seed'] for x in OBJECTS.values()}):
        raise ValueError('engineering noise seed overlap')
    if any(x['seed']==af.SEED for x in OBJECTS.values()):raise ValueError('AF object reuse prohibited')
    return aa_hash,spec_hash

def expected(n,aa_dir,m_dir):
    h,s=protected(aa_dir,m_dir)
    return {'schema':SCHEMA,'namespace':'MULTI_SEED_FIVE_POLICY_ENGINEERING_ONLY',
       'config':af.cfg(n),'objects':OBJECTS,'acquisition_seeds':ACQUISITIONS,'noise_seed_by_group':{group_name(o,a,m):noise_seed(o,a,m) for o in OBJECTS for a in ACQUISITIONS for m in MODELS},
       'policies':list(POLICIES),'models':list(MODELS),
       'source_sha256':src_sha(),'aa_manifest_sha256':h,'aa_spec_sha256':s,
       'engineering_groups':8,'engineering_jobs':40,'production_specifications':480,
       'production_execution_allowed':False,'production_480_job_certified':False,
       'scientific_signoff':False,'resource_policy_approved':False,'frozen':False,
       'no_confirmatory_outcomes':True}

def init(root,aa_dir,m_dir,n):
    root=Path(root)
    if root.exists():raise FileExistsError('AN root already exists; refusing overwrite')
    p=expected(n,aa_dir,m_dir)
    root.mkdir(parents=True);write(root/'plan.json',p)
    (root/'groups').mkdir();(root/'jobs').mkdir()
    return {'verdict':'AN_ENGINEERING_OBJECTS_PREPARED','objects':2,'acquisition_seeds':2,'shared_groups':8,
            'jobs':40,'n':n,'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def check(root,aa_dir,m_dir):
    root=Path(root);p=read(root/'plan.json')
    if p!=expected(p['config']['n'],aa_dir,m_dir):raise ValueError('AN source or immutable plan drift')
    groups=root/'groups';jobs=root/'jobs'
    if not groups.is_dir() or not jobs.is_dir() or groups.is_symlink() or jobs.is_symlink():raise ValueError('missing/unsafe AN evidence folders')
    possible_groups={group_name(o,a,m) for o in OBJECTS for a in ACQUISITIONS for m in MODELS}
    possible_jobs={job_name(o,a,m,policy) for o in OBJECTS for a in ACQUISITIONS for m in MODELS for policy in POLICIES}
    if any(x.is_symlink() or x.name not in possible_groups for x in groups.iterdir()):raise ValueError('unexpected AN group')
    if any(x.is_symlink() or x.name not in possible_jobs for x in jobs.iterdir()):raise ValueError('unexpected AN job')
    return p

def group_name(obj,acq,model):
    if obj not in OBJECTS or acq not in ACQUISITIONS or model not in MODELS:
        raise ValueError('only fixed engineering objects/acquisition seeds/models')
    return obj+'__'+acq+'__'+model

def catalogue(root,aa_dir,m_dir,obj,acq,model):
    p=check(root,aa_dir,m_dir);name=group_name(obj,acq,model)
    dst=Path(root)/'groups'/name
    if dst.exists():
        group_inputs(root,aa_dir,m_dir,obj,acq,model)
        return {'verdict':'AN_SHARED_GROUP_REUSED','group':name,'production_execution_allowed':False}
    stage=Path(root)/'groups'/('.stage-'+name)
    if stage.exists():raise ValueError('uncommitted group staging exists')
    stage.mkdir()
    n=p['config']['n'];A=system_matrix(n,4,TILTS).tocsr()
    truth,fine=full_resolution_pair(OBJECTS[obj]['family'],OBJECTS[obj]['seed'],n)
    clean,noisy=model_measurements(A,truth,fine,n=n,angles=4,model=model,
                 noise_seed=noise_seed(obj,acq,model),noise_fraction=.005)
    if np.shape(noisy)!=(12*n*n,) or not np.isfinite(noisy).all():raise ValueError('invalid measurement catalogue')
    array(stage/'clean.npy',clean);array(stage/'noisy.npy',noisy)
    receipt={'schema':SCHEMA,'namespace':'MULTI_SEED_FIVE_POLICY_ENGINEERING_ONLY','object':obj,'acquisition':acq,'acquisition_seed':ACQUISITIONS[acq], 'noise_seed':noise_seed(obj,acq,model),'model':model,
             'object_seed':OBJECTS[obj]['seed'],'plan_sha256':sha(Path(root)/'plan.json'),
             'truth_sha256':hashlib.sha256(np.asarray(truth,dtype='<f8').tobytes()).hexdigest(),
             'clean_sha256':sha(stage/'clean.npy'),'noisy_sha256':sha(stage/'noisy.npy'),
             'production_execution_allowed':False,'no_confirmatory_outcomes':True}
    write(stage/'receipt.json',receipt);os.replace(stage,dst)
    return {'verdict':'AN_SHARED_GROUP_PREPARED','group':name,'truth_sha256':receipt['truth_sha256'],
            'candidate_rays':12*n*n,'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def group_inputs(root,aa_dir,m_dir,obj,acq,model):
    p=check(root,aa_dir,m_dir);d=Path(root)/'groups'/group_name(obj,acq,model)
    if not d.is_dir() or d.is_symlink() or {x.name for x in d.iterdir()}!={'clean.npy','noisy.npy','receipt.json'}:raise ValueError('invalid group files')
    r=read(d/'receipt.json')
    n=p['config']['n'];A=system_matrix(n,4,TILTS).tocsr()
    truth,fine=full_resolution_pair(OBJECTS[obj]['family'],OBJECTS[obj]['seed'],n)
    clean,noisy=model_measurements(A,truth,fine,n=n,angles=4,model=model,noise_seed=noise_seed(obj,acq,model),noise_fraction=.005)
    th=hashlib.sha256(np.asarray(truth,dtype='<f8').tobytes()).hexdigest()
    expect={'schema':SCHEMA,'namespace':'MULTI_SEED_FIVE_POLICY_ENGINEERING_ONLY','object':obj,'acquisition':acq,'acquisition_seed':ACQUISITIONS[acq], 'noise_seed':noise_seed(obj,acq,model),'model':model,
            'object_seed':OBJECTS[obj]['seed'],'plan_sha256':sha(Path(root)/'plan.json'),
            'truth_sha256':th,'clean_sha256':sha(d/'clean.npy'),'noisy_sha256':sha(d/'noisy.npy'),
            'production_execution_allowed':False,'no_confirmatory_outcomes':True}
    if r!=expect or not np.array_equal(np.load(d/'clean.npy',allow_pickle=False),clean) or not np.array_equal(np.load(d/'noisy.npy',allow_pickle=False),noisy):
        raise ValueError('cross-object or changed shared measurement catalogue')
    return p,A,np.asarray(truth,dtype=np.float64),np.asarray(noisy,dtype=np.float64)

def job_name(obj,acq,model,policy):
    group_name(obj,acq,model)
    if policy not in POLICIES:raise ValueError('unapproved engineering policy')
    return obj+'__'+acq+'__'+model+'__'+policy

def prepare_job(root,aa_dir,m_dir,obj,acq,model,policy):
    p,A,truth,noisy=group_inputs(root,aa_dir,m_dir,obj,acq,model)
    jid=job_name(obj,acq,model,policy);dst=Path(root)/'jobs'/jid
    if dst.exists():
        verify_job(root,aa_dir,m_dir,obj,acq,model,policy)
        return {'verdict':'AN_JOB_REUSED','job_id':jid,'production_execution_allowed':False}
    orders,_=fair_orders(A,n=p['config']['n'],angles=4,seed=ACQUISITIONS[acq],
       budget=p['config']['budget'],warm=p['config']['warm'],pool=16,
       batch=8 if p['config']['n']==8 else 32)
    order=np.asarray(orders[policy],dtype=np.int64)
    if order.shape!=(p['config']['budget'],) or len(np.unique(order))!=len(order):raise ValueError('invalid order')
    if policy=='complete_view' and p['config']['budget']!=2*p['config']['n']**2:raise ValueError('complete view must be two detector views')
    stage=Path(root)/'jobs'/('.stage-'+jid)
    if stage.exists():raise ValueError('uncommitted job staging exists')
    stage.mkdir()
    array(stage/'order.npy',order)
    source={'schema':SCHEMA,'namespace':'MULTI_SEED_FIVE_POLICY_ENGINEERING_ONLY',
           'object':obj,'acquisition':acq,'acquisition_seed':ACQUISITIONS[acq], 'noise_seed':noise_seed(obj,acq,model),'model':model,'policy':policy,'job_id':jid,
           'group_receipt_sha256':sha(Path(root)/'groups'/group_name(obj,acq,model)/'receipt.json'),
           'plan_sha256':sha(Path(root)/'plan.json'),'order_sha256':sha(stage/'order.npy'),
           'n':p['config']['n'],'budget':p['config']['budget'],
           'epochs':p['config']['epochs'],'relaxation':p['config']['relaxation'],
           'truth_sha256':hashlib.sha256(np.asarray(truth,dtype='<f8').tobytes()).hexdigest(),
           'production_execution_allowed':False,'no_confirmatory_outcomes':True}
    write(stage/'source.json',source);(stage/'checkpoints').mkdir();os.replace(stage,dst)
    return {'verdict':'AN_JOB_DISPATCHED','job_id':jid,'production_execution_allowed':False}

def verify_job(root,aa_dir,m_dir,obj,acq,model,policy):
    p,A,truth,noisy=group_inputs(root,aa_dir,m_dir,obj,acq,model)
    jid=job_name(obj,acq,model,policy);d=Path(root)/'jobs'/jid
    if d.is_symlink() or not d.is_dir():raise ValueError('unsafe/missing AN job')
    s=read(d/'source.json');order=np.load(d/'order.npy',allow_pickle=False)
    group=Path(root)/'groups'/group_name(obj,acq,model)
    expected={'schema':SCHEMA,'namespace':'MULTI_SEED_FIVE_POLICY_ENGINEERING_ONLY',
           'object':obj,'acquisition':acq,'acquisition_seed':ACQUISITIONS[acq], 'noise_seed':noise_seed(obj,acq,model),'model':model,'policy':policy,'job_id':jid,
           'group_receipt_sha256':sha(group/'receipt.json'),
           'plan_sha256':sha(Path(root)/'plan.json'),'order_sha256':sha(d/'order.npy'),
           'n':p['config']['n'],'budget':p['config']['budget'],
           'epochs':p['config']['epochs'],'relaxation':p['config']['relaxation'],
           'truth_sha256':hashlib.sha256(np.asarray(truth,dtype='<f8').tobytes()).hexdigest(),
           'production_execution_allowed':False,'no_confirmatory_outcomes':True}
    if s!=expected:raise ValueError('job/object source identity drift')
    orders,_=fair_orders(A,n=s['n'],angles=4,seed=ACQUISITIONS[acq],budget=s['budget'],
                 warm=p['config']['warm'],pool=16,batch=8 if s['n']==8 else 32)
    if not np.array_equal(order,np.asarray(orders[policy])):raise ValueError('cross-object acquisition order mismatch')
    if order.shape!=(s['budget'],) or len(np.unique(order))!=len(order):raise ValueError('order length or distinctness changed')
    if policy=='complete_view' and s['budget']!=2*s['n']**2:raise ValueError('complete-view geometry mismatch')
    selected=A[order].tocsr();measured=noisy[order]
    count,x,last=verify_chain(d,s)
    return s,d,selected,measured,truth,count,x,last

def verify_chain(d,s):
    cps=d/'checkpoints'
    if cps.is_symlink() or not cps.is_dir():raise ValueError('unsafe checkpoint folder')
    done=0;previous='GENESIS';x=None
    for f in sorted(cps.iterdir()):
        if f.is_symlink() or not f.is_dir() or not f.name.startswith('cp_') or {y.name for y in f.iterdir()}!={'state.npy','receipt.json'}:
            raise ValueError('uncommitted or unexpected checkpoint')
        r=read(f/'receipt.json')
        cursor=r.get('rows_done')
        if (not isinstance(cursor,int) or cursor<=done or cursor>s['budget']*s['epochs'] or
            f.name!=f'cp_{cursor:08d}' or r!={'schema':SCHEMA,'job_id':s['job_id'],
            'source_sha256':sha(d/'source.json'),'rows_done':cursor,
            'state_sha256':sha(f/'state.npy'),'previous_receipt_sha256':previous,
            'production_execution_allowed':False,'no_confirmatory_outcomes':True}):
            raise ValueError('cross-job or corrupted checkpoint receipt')
        x=np.load(f/'state.npy',allow_pickle=False)
        if x.shape!=(s['n']**3,) or x.dtype!=np.float64 or not np.isfinite(x).all() or np.any(x<=0):raise ValueError('invalid MART checkpoint state')
        done=cursor;previous=sha(f/'receipt.json')
    return done,x,previous

def commit(d,s,x,cursor,previous):
    state=array_bytes(np.asarray(x,dtype=np.float64))
    r={'schema':SCHEMA,'job_id':s['job_id'],'source_sha256':sha(d/'source.json'),
       'rows_done':cursor,'state_sha256':hashlib.sha256(state).hexdigest(),
       'previous_receipt_sha256':previous,'production_execution_allowed':False,'no_confirmatory_outcomes':True}
    saved=ah.atomic_dir(d/'checkpoints',f'cp_{cursor:08d}',{'state.npy':state,'receipt.json':canonical(r)})
    return sha(saved/'receipt.json')

def worker(root,aa_dir,m_dir,obj,acq,model,policy,stop_after_rows=None):
    if stop_after_rows is not None and stop_after_rows<=0:raise ValueError('invalid row stop')
    s,d,A,y,truth,done,x,previous=verify_job(root,aa_dir,m_dir,obj,acq,model,policy)
    total=s['budget']*s['epochs']
    if (d/'final').exists():
        from experiment_08aj_an_audit import audit_one
        result=audit_one(root,aa_dir,m_dir,obj,acq,model,policy)
        if not result['pass']:raise ValueError('completed evidence failed independent audit')
        return {'verdict':'AN_COMPLETED_JOB_REUSED','job_id':s['job_id'],'rows_done':total,
                'production_execution_allowed':False,'no_confirmatory_outcomes':True}
    if x is None:x=np.full(s['n']**3,.3,dtype=np.float64)
    for i in range(done,total):
        ad.step_row(x,A,y,i%s['budget'],s['relaxation'])
        cursor=i+1
        if cursor%CHECKPOINT_INTERVAL==0 or cursor==total or (stop_after_rows is not None and cursor-done>=stop_after_rows):
            previous=commit(d,s,x,cursor,previous)
        if stop_after_rows is not None and cursor-done>=stop_after_rows:
            return {'verdict':'AN_ENGINEERING_PAUSED','job_id':s['job_id'],'rows_done':cursor,
                    'rows_total':total,'production_execution_allowed':False,'no_confirmatory_outcomes':True}
    done,xx,last=verify_chain(d,s)
    if done!=total or not np.array_equal(xx,x):raise ValueError('final checkpoint disagrees with reconstruction')
    rmse=float(np.sqrt(np.mean((x-truth)**2)))
    b=array_bytes(x)
    r={'schema':SCHEMA,'job_id':s['job_id'],'source_sha256':sha(d/'source.json'),
       'rows_done':total,'last_checkpoint_sha256':last,'reconstruction_sha256':hashlib.sha256(b).hexdigest(),
       'rmse':rmse,'production_execution_allowed':False,'no_confirmatory_outcomes':True}
    ah.atomic_dir(d,'final',{'reconstruction.npy':b,'receipt.json':canonical(r)})
    return {'verdict':'AN_ENGINEERING_JOB_PASS','job_id':s['job_id'],'rows_done':total,
            'rmse':rmse,'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def run(root,aa_dir,m_dir,obj,acq,model,policy,wall_seconds=600,max_mib=8192,stop_after_rows=None):
    verify_job(root,aa_dir,m_dir,obj,acq,model,policy)
    if not 1<=wall_seconds<=7200 or not 256<=max_mib<=65536:raise ValueError('invalid resource limits')
    args=[sys.executable,str(Path(__file__).resolve()),'--mode','worker',
       '--output-dir',str(root),'--aa-dir',str(aa_dir),'--m-dir',str(m_dir),
       '--object',obj,'--acquisition',acq,'--model',model,'--policy',policy,'--max-mib',str(max_mib)]
    if stop_after_rows is not None:args+=['--stop-after-rows',str(stop_after_rows)]
    import psutil
    process=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    start=time.monotonic();peak=0;reason=None
    try:
        while process.poll() is None:
            if time.monotonic()-start>wall_seconds:reason='WALL_TIMEOUT';break
            try:
                rss=psutil.Process(process.pid).memory_info().rss
                peak=max(peak,rss)
                if rss>max_mib*1024**2:reason='RSS_MEMORY_EXCEEDED';break
            except psutil.NoSuchProcess:break
            time.sleep(.05)
        if reason:
            process.kill();process.communicate(timeout=10)
            return {'verdict':'AN_GUARD_STOP','reason':reason,'peak_rss_mib_observed':round(peak/1048576,2),'production_execution_allowed':False}
        out,err=process.communicate(timeout=10)
        if process.returncode:
            return {'verdict':'AN_WORKER_FAILED','worker_error':err[-1600:],'worker_exit':process.returncode,'production_execution_allowed':False}
        result=json.loads(out);result['supervised']=True;result['peak_rss_mib_observed']=round(peak/1048576,2)
        return result
    finally:
        if process.poll() is None:process.kill();process.communicate()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',required=True,choices=('init','check','catalogue','dispatch','run','worker','production-run','unlock','freeze'))
    for key in ('output-dir','aa-dir','m-dir'):ap.add_argument('--'+key,required=True,type=Path)
    ap.add_argument('--n',type=int,choices=(8,32),default=8)
    ap.add_argument('--object',choices=OBJECTS);ap.add_argument('--acquisition',choices=ACQUISITIONS);ap.add_argument('--model',choices=MODELS);ap.add_argument('--policy',choices=POLICIES)
    ap.add_argument('--stop-after-rows',type=int);ap.add_argument('--wall-seconds',type=float,default=600);ap.add_argument('--max-mib',type=int,default=8192)
    a=ap.parse_args()
    if a.mode in ('production-run','unlock','freeze'):ap.error('PROSPECTIVE_EXECUTION_DISABLED')
    args=(a.output_dir,a.aa_dir,a.m_dir)
    if a.mode=='init':r=init(*args,a.n)
    elif a.mode=='check':
        p=check(*args);r={'verdict':'AN_LOCKED_MULTI_SEED_SOURCES_MATCH',
            'groups':len(list((a.output_dir/'groups').iterdir())),
            'jobs':len(list((a.output_dir/'jobs').iterdir())),
            'production_execution_allowed':False}
    elif a.mode=='catalogue':r=catalogue(*args,a.object,a.acquisition,a.model)
    elif a.mode=='dispatch':r=prepare_job(*args,a.object,a.acquisition,a.model,a.policy)
    elif a.mode=='worker':
        handle=ah.enforce_memory_cap(a.max_mib)
        r=worker(*args,a.object,a.acquisition,a.model,a.policy,a.stop_after_rows)
    else:r=run(*args,a.object,a.acquisition,a.model,a.policy,a.wall_seconds,a.max_mib,a.stop_after_rows)
    print(json.dumps(r,indent=2))
    if r['verdict'] in ('AN_GUARD_STOP','AN_WORKER_FAILED'):raise SystemExit(2)
if __name__=='__main__':main()
