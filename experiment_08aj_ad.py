"""08AJ-AD: engineering-only, row-checkpoint MART restart proof over an audited AB job.

No production ID, cohort input, source-freeze, or authorization operation is exposed.
Checkpoints are append-only per row position; complete on-disk hash chain is checked
before resumed arithmetic. Work uses AB's preexisting engineering input arrays.
"""
from __future__ import annotations
import argparse, hashlib, json, os, time
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix

SCHEMA = 'RBYRCT-08AJ-AD-row-recovery-engineering-v1'
SEED = 970099
CHECKPOINT_STEP = 128

def canonical(x):
    return (json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode('ascii')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(b):return hashlib.sha256(b).hexdigest()
def create(p,b):
    with Path(p).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def save_array(p,x):
    with Path(p).open('xb') as f:np.save(f,x,allow_pickle=False);f.flush();os.fsync(f.fileno())
def load_receipt(p):
    b=Path(p).read_bytes(); x=json.loads(b)
    if b!=canonical(x):raise ValueError('noncanonical receipt '+str(p))
    return x

def validate_ab(ab_dir,aa_dir,m_dir,policy,model):
    import experiment_08aj_ab as ab
    from experiment_08aj_ab_audit import audit_one
    ab.job_id(policy,model)
    plan,ph=ab.check(ab_dir,aa_dir,m_dir)
    if plan['engineering_seed']!=SEED or plan['n'] not in (8,32):raise ValueError('non-engineering AB plan')
    folder=Path(ab_dir)/'jobs'/ab.job_id(policy,model)
    if not folder.is_dir() or folder.is_symlink():raise ValueError('missing AB completed job')
    result=audit_one(ab_dir,aa_dir,m_dir,policy,model)
    if not result['pass']:raise ValueError('AB numerical audit failed: '+repr(result['errors']))
    receipt=load_receipt(folder/'receipt.json')
    return plan,ph,folder,receipt

def params_from_ab(plan,ph,folder,receipt,policy,model):
    fnames=('csr_data.npy','csr_indices.npy','csr_indptr.npy','measurements.npy','reconstruction.npy')
    hashes={n:sha(folder/n) for n in fnames}
    return {'schema':SCHEMA,'namespace':'ENGINEERING_SHADOW_ONLY', 'seed':SEED,
       'ab_plan_sha256':ph,'ab_receipt_sha256':sha(folder/'receipt.json'),
       'ab_inputs_sha256':hashes,'policy':policy,'model':model,'n':plan['n'],
       'budget':plan['budget'],'epochs':plan['epochs'],'relaxation':plan['relaxation'],
       'checkpoint_step_rows':CHECKPOINT_STEP,'production_jobs_executed':0,
       'production_execution_allowed':False,'resource_policy_approved':False,
       'scientific_signoff':False,'frozen':False,'no_confirmatory_outcomes':True}

def source_arrays(folder,budget,n):
    arrays={name:np.load(folder/name,allow_pickle=False) for name in ('csr_data.npy','csr_indices.npy','csr_indptr.npy','measurements.npy','reconstruction.npy')}
    a=csr_matrix((arrays['csr_data.npy'], arrays['csr_indices.npy'],arrays['csr_indptr.npy']),shape=(budget,n**3))
    y=np.asarray(arrays['measurements.npy'],dtype=np.float64)
    ref=np.asarray(arrays['reconstruction.npy'],dtype=np.float64)
    if a.shape!=(budget,n**3) or y.shape!=(budget,) or ref.shape!=(n**3,) or not np.isfinite(y).all() or not np.isfinite(ref).all():raise ValueError('invalid AB inputs')
    return a,y,ref

def step_row(x,a,y,row,relaxation):
    s,e=int(a.indptr[row]),int(a.indptr[row+1])
    if s==e:return
    cols=a.indices[s:e];w=a.data[s:e];wmax=float(np.max(w))
    if wmax<=0:return
    predicted=float(np.dot(w,x[cols]))
    ratio=max(float(y[row]),1e-10)/max(predicted,1e-10)
    delta=np.clip((relaxation*w/wmax)*np.log(max(ratio,1e-10)),-12,12)
    x[cols]=np.maximum(x[cols]*np.exp(delta),1e-10)

def checkpoints(root):
    return sorted((Path(root)/'checkpoints').glob('cp_*.json'))

def verify_chain(root,plan):
    root=Path(root);cpdir=root/'checkpoints'; names=checkpoints(root)
    if not cpdir.is_dir() or cpdir.is_symlink():raise ValueError('bad checkpoint directory')
    raw=list(cpdir.iterdir())
    if len(raw)!=2*len(names):raise ValueError('orphan or unexpected checkpoint artifact')
    previous='GENESIS';current=0;last=None
    for p in names:
        if p.is_symlink():raise ValueError('checkpoint symlink')
        r=load_receipt(p)
        expected_name=f'cp_{r["rows_done"]:08d}.json'; npy=p.with_suffix('.npy')
        if p.name!=expected_name or npy.is_symlink() or not npy.is_file():raise ValueError('checkpoint filename invalid')
        if (r.get('schema')!=SCHEMA or r.get('plan_sha256')!=sha(root/'plan.json') or
            r.get('previous_receipt_sha256')!=previous or r.get('rows_done')<=current or
            r.get('state_sha256')!=sha(npy) or r.get('no_confirmatory_outcomes') is not True):
            raise ValueError('checkpoint identity/chain/hash failure')
        state=np.load(npy,allow_pickle=False)
        if state.shape!=(plan['n']**3,) or state.dtype!=np.float64 or not np.isfinite(state).all() or np.any(state<=0):raise ValueError('invalid checkpoint numerical state')
        current=r['rows_done'];previous=sha(p);last=state
    if current>plan['budget']*plan['epochs']:raise ValueError('checkpoint past final row')
    return current,last,previous

def checkpoint(root,plan,x,rows_done,previous):
    root=Path(root);cpdir=root/'checkpoints';base=f'cp_{rows_done:08d}'
    arr=cpdir/(base+'.npy');meta=cpdir/(base+'.json')
    save_array(arr,x)
    r={'schema':SCHEMA,'plan_sha256':sha(root/'plan.json'),'rows_done':rows_done,
       'state_sha256':sha(arr),'previous_receipt_sha256':previous,
       'no_confirmatory_outcomes':True}
    create(meta,canonical(r))
    return sha(meta)

def initialize(out,ab_dir,aa_dir,m_dir,policy,model):
    root=Path(out)
    if root.exists():raise FileExistsError('AD evidence exists; refusing overwrite')
    plan,ph,folder,receipt=validate_ab(ab_dir,aa_dir,m_dir,policy,model)
    p=params_from_ab(plan,ph,folder,receipt,policy,model)
    root.mkdir(parents=True)
    create(root/'plan.json',canonical(p));(root/'checkpoints').mkdir()
    return {'verdict':'AD_ENGINEERING_RECOVERY_PREPARED','n':p['n'],'epochs':p['epochs'], 'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def check_inputs(out,ab_dir,aa_dir,m_dir):
    root=Path(out);p=load_receipt(root/'plan.json')
    plan,ph,folder,receipt=validate_ab(ab_dir,aa_dir,m_dir,p['policy'],p['model'])
    if p!=params_from_ab(plan,ph,folder,receipt,p['policy'],p['model']):raise ValueError('AD plan or AB source changed')
    for name,h in p['ab_inputs_sha256'].items():
        if sha(folder/name)!=h:raise ValueError('AB input altered: '+name)
    return p,folder

def run(out,ab_dir,aa_dir,m_dir,stop_after_rows=None,wall_seconds=600):
    p,folder=check_inputs(out,ab_dir,aa_dir,m_dir)
    if stop_after_rows is not None and stop_after_rows<1:raise ValueError('positive stop-after-rows required')
    if not 1<=wall_seconds<=7200:raise ValueError('wall budget outside engineering guard')
    A,y,reference=source_arrays(folder,p['budget'],p['n'])
    total=p['budget']*p['epochs'];done,x,previous=verify_chain(out,p)
    if (Path(out)/'final.json').exists():
        from experiment_08aj_ad_audit import audit
        result=audit(out,ab_dir,aa_dir,m_dir)
        if not result['pass']:raise ValueError('existing AD final failed audit')
        return {'verdict':'AD_ENGINEERING_JOB_REUSED','rows_done':total,'production_execution_allowed':False}
    if done==total:
        pass
    else:
        if x is None:x=np.full(p['n']**3,.3,dtype=np.float64)
        start=time.monotonic();since=0
        for cursor in range(done,total):
            if time.monotonic()-start>wall_seconds:raise TimeoutError('engineering wall-clock guard exceeded; last checkpoint preserved')
            step_row(x,A,y,cursor%p['budget'],p['relaxation'])
            since+=1
            now=cursor+1
            if now%p['checkpoint_step_rows']==0 or now==total or (stop_after_rows is not None and since>=stop_after_rows):
                previous=checkpoint(out,p,x,now,previous)
            if stop_after_rows is not None and since>=stop_after_rows:
                return {'verdict':'AD_ENGINEERING_INTERRUPTED_AT_CHECKPOINT','rows_done':now,'rows_total':total,'production_execution_allowed':False,'no_confirmatory_outcomes':True}
        done=total
    # Final derived from latest saved snapshot, never solely an in-memory answer.
    done,x,previous=verify_chain(out,p)
    if done!=total:raise ValueError('cannot finalize unfinished reconstruction')
    discrepancy=float(np.max(np.abs(x-reference)))
    # Fail closed rather than declaring incompatible MART kernels identical.
    if discrepancy>1e-11:raise ValueError('AB uninterrupted replay mismatch '+str(discrepancy))
    f=Path(out)/'final_reconstruction.npy';save_array(f,x)
    receipt={'schema':SCHEMA,'plan_sha256':sha(Path(out)/'plan.json'),
      'final_reconstruction_sha256':sha(f),'last_checkpoint_receipt_sha256':previous,
      'rows_done':done,'max_abs_error_vs_ab':discrepancy,
      'production_execution_allowed':False,'no_confirmatory_outcomes':True}
    create(Path(out)/'final.json',canonical(receipt))
    return {'verdict':'AD_ENGINEERING_RESUME_PASS','rows_done':done,'rows_total':total,
       'max_abs_error_vs_ab':discrepancy,'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',choices=('init','run','check'),required=True)
    ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--ab-dir',type=Path,required=True)
    ap.add_argument('--aa-dir',type=Path,required=True)
    ap.add_argument('--m-dir',type=Path,required=True)
    ap.add_argument('--policy',choices=('information_diag','uniform_multiscale','coverage','stratified_random_04h','complete_view'))
    ap.add_argument('--model',choices=('same','independent'))
    ap.add_argument('--stop-after-rows',type=int)
    ap.add_argument('--wall-seconds',type=float,default=600)
    args=ap.parse_args()
    if args.mode=='init':
        if args.policy is None or args.model is None:ap.error('init requires --policy and --model')
        out=initialize(args.output_dir,args.ab_dir,args.aa_dir,args.m_dir,args.policy,args.model)
    elif args.mode=='run':out=run(args.output_dir,args.ab_dir,args.aa_dir,args.m_dir,args.stop_after_rows,args.wall_seconds)
    else:
        p,folder=check_inputs(args.output_dir,args.ab_dir,args.aa_dir,args.m_dir)
        done,_,_=verify_chain(args.output_dir,p)
        out={'verdict':'AD_SOURCE_AND_CHECKPOINT_CHAIN_PASS','rows_done':done,'rows_total':p['budget']*p['epochs'],'production_execution_allowed':False}
    print(json.dumps(out,indent=2))
if __name__=='__main__':main()
