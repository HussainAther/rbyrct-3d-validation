"""08AJ-AH: fail-closed ENGINEERING-ONLY atomic checkpoints and supervised MART.

Source is an existing audited AF engineering job. No prospective object IDs, seeds,
production work, approval, freeze, or unlock functionality is implemented.
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys, time, uuid
from pathlib import Path
import numpy as np
import experiment_08aj_ag as ag
import experiment_08aj_ad as ad

SCHEMA = 'RBYRCT-08AJ-AH-atomic-engineering-v1'
STEP = 128

def canonical(obj): return ad.canonical(obj)
def sha(path): return ad.sha(path)
def receipt(path): return ad.load_receipt(path)
def _create(path,data): ad.create(path,data)

def atomic_dir(parent, name, files):
    """Write/fsync all files in private directory; publish with one rename."""
    parent=Path(parent)
    target=parent/name
    if target.exists(): raise FileExistsError('immutable checkpoint exists: '+str(target))
    stage=parent/('.stage-'+uuid.uuid4().hex)
    stage.mkdir(mode=0o700)
    try:
        for fname,data in files.items(): _create(stage/fname,data)
        # On POSIX, sync the directory before publishing. Windows fsync on
        # directories is not generally supported; rename is still atomic on NTFS.
        if os.name!='nt':
            fd=os.open(stage,os.O_RDONLY)
            try: os.fsync(fd)
            finally: os.close(fd)
        os.replace(stage,target)
        if os.name!='nt':
            fd=os.open(parent,os.O_RDONLY)
            try: os.fsync(fd)
            finally: os.close(fd)
    except Exception:
        # Preserve staging on errors for diagnosis. The independent integrity
        # checker will refuse to resume until operator quarantines it.
        raise
    return target

def array_bytes(x):
    import io
    b=io.BytesIO();np.save(b,x,allow_pickle=False);return b.getvalue()

def plan_for(af_dir,aa_dir,m_dir,policy,model):
    p=ag.expected_plan(af_dir,aa_dir,m_dir,policy,model)
    return {'schema':SCHEMA,'namespace':'FRESH_ENGINEERING_RESOURCE_GUARD_ONLY',
            'source':p,'checkpoint_step_rows':STEP,
            'implementation_sha256':{name:sha(Path(__file__).resolve().parent/name)
                for name in ('experiment_08aj_ah.py','experiment_08aj_ah_audit.py')},
            'production_jobs_executed':0,
            'production_480_job_certified':False,'production_execution_allowed':False,
            'scientific_signoff':False,'resource_policy_approved':False,
            'frozen':False,'no_confirmatory_outcomes':True}

def init(root,af_dir,aa_dir,m_dir,policy,model):
    root=Path(root)
    if root.exists():raise FileExistsError('AH directory already exists; refusing overwrite')
    p=plan_for(af_dir,aa_dir,m_dir,policy,model)
    root.mkdir(parents=True)
    try:
        _create(root/'plan.json',canonical(p))
        (root/'checkpoints').mkdir()
    except Exception:
        raise
    return {'verdict':'AH_ENGINEERING_GUARD_PREPARED','job_id':policy+'__'+model,
            'n':p['source']['n'],'epochs':p['source']['epochs'],
            'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def _checkpoint_names(root):
    d=Path(root)/'checkpoints'
    if not d.is_dir() or d.is_symlink(): raise ValueError('missing or unsafe checkpoint directory')
    paths=sorted(d.iterdir())
    for x in paths:
        if x.is_symlink() or not x.is_dir() or not x.name.startswith('cp_') or len(x.name)!=11:
            raise ValueError('unexpected or interrupted staging artifact: '+x.name)
    return paths

def verify_chain(root,p):
    root=Path(root);source=p['source'];total=source['budget']*source['epochs']
    previous='GENESIS';count=0;x=None
    for d in _checkpoint_names(root):
        if {f.name for f in d.iterdir()}!={'state.npy','receipt.json'}:
            raise ValueError('checkpoint artifact not atomically committed')
        r=receipt(d/'receipt.json')
        if r.get('schema')!=SCHEMA or r.get('plan_sha256')!=sha(root/'plan.json') or r.get('previous_receipt_sha256')!=previous:
            raise ValueError('checkpoint receipt/hash chain mismatch')
        n=r.get('rows_done')
        if not isinstance(n,int) or n<=count or n>total or d.name!=f'cp_{n:08d}':
            raise ValueError('checkpoint cursor invalid')
        if r.get('state_sha256')!=sha(d/'state.npy') or r.get('no_confirmatory_outcomes') is not True:
            raise ValueError('checkpoint state SHA mismatch')
        x=np.load(d/'state.npy',allow_pickle=False)
        if x.shape!=(source['n']**3,) or x.dtype!=np.float64 or not np.isfinite(x).all() or np.any(x<=0):
            raise ValueError('invalid checkpoint reconstruction state')
        count=n;previous=sha(d/'receipt.json')
    return count,x,previous

def verify(root,af_dir,aa_dir,m_dir):
    root=Path(root)
    p=receipt(root/'plan.json')
    if p.get('schema')!=SCHEMA or p.get('namespace')!='FRESH_ENGINEERING_RESOURCE_GUARD_ONLY':
        raise ValueError('invalid AH engineering namespace')
    s=p['source'];expected=plan_for(af_dir,aa_dir,m_dir,s['policy'],s['model'])
    if p!=expected:raise ValueError('AH plan or AF engineering source changed')
    _,folder,_,_=ag.evidence(None,af_dir,aa_dir,m_dir,s['policy'],s['model'])
    count,x,previous=verify_chain(root,p)
    return p,folder,count,x,previous

def commit(root,p,x,n,previous):
    cpdir=Path(root)/'checkpoints'
    state=array_bytes(x)
    r={'schema':SCHEMA,'plan_sha256':sha(Path(root)/'plan.json'),
       'rows_done':n,'state_sha256':hashlib.sha256(state).hexdigest(),
       'previous_receipt_sha256':previous,'no_confirmatory_outcomes':True}
    d=atomic_dir(cpdir,f'cp_{n:08d}',{'state.npy':state,'receipt.json':canonical(r)})
    return sha(d/'receipt.json')

def worker_run(root,af_dir,aa_dir,m_dir,stop_after_rows=None):
    if stop_after_rows is not None and stop_after_rows<1:raise ValueError('positive stop-after-rows required')
    p,d,done,x,previous=verify(root,af_dir,aa_dir,m_dir)
    s=p['source'];total=s['budget']*s['epochs']
    A,y,reference=ag.inputs(d,s)
    if (Path(root)/'final').exists():
        from experiment_08aj_ah_audit import audit
        result=audit(root,af_dir,aa_dir,m_dir)
        if not result['pass']:raise ValueError('existing AH result not auditable')
        return {'verdict':'AH_ENGINEERING_RESULT_REUSED','rows_done':total,'production_execution_allowed':False}
    if x is None:x=np.full(s['n']**3,.3,dtype=np.float64)
    since=0
    for cursor in range(done,total):
        ad.step_row(x,A,y,cursor%s['budget'],s['relaxation'])
        n=cursor+1;since+=1
        if n%STEP==0 or n==total or (stop_after_rows is not None and since>=stop_after_rows):
            previous=commit(root,p,x,n,previous)
        if stop_after_rows is not None and since>=stop_after_rows:
            return {'verdict':'AH_ENGINEERING_PAUSED','rows_done':n,'rows_total':total,
                    'production_execution_allowed':False,'no_confirmatory_outcomes':True}
    done,x,previous=verify_chain(root,p)
    if done!=total:raise ValueError('cannot finalize incomplete run')
    discrepancy=float(np.max(np.abs(x-reference)))
    if discrepancy>1e-11:raise ValueError('reference mismatch: '+str(discrepancy))
    array=array_bytes(x)
    r={'schema':SCHEMA,'plan_sha256':sha(Path(root)/'plan.json'),
       'rows_done':done,'last_checkpoint_receipt_sha256':previous,
       'final_reconstruction_sha256':hashlib.sha256(array).hexdigest(),
       'max_abs_error_vs_af':discrepancy,'production_execution_allowed':False,
       'no_confirmatory_outcomes':True}
    atomic_dir(root,'final',{'reconstruction.npy':array,'receipt.json':canonical(r)})
    return {'verdict':'AH_ENGINEERING_RECOVERY_PASS','rows_done':done,'rows_total':total,
            'max_abs_error_vs_af':discrepancy,'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def quarantine_staging(root):
    # Operator-only recovery after an abnormal termination; never touch committed
    # checkpoints. Move incomplete private directories out of the live chain.
    root=Path(root);cps=root/'checkpoints';bad=[x for x in cps.iterdir() if x.name.startswith('.stage-')]
    if not bad: return {'verdict':'AH_NO_STAGING_TO_QUARANTINE','quarantined':0}
    q=root/'quarantine'
    if q.exists():raise ValueError('quarantine already present; refuse collision')
    q.mkdir()
    for x in bad:
        if x.is_symlink() or not x.is_dir():raise ValueError('unsafe staging item')
        os.replace(x,q/x.name)
    _create(q/'quarantine_manifest.json',canonical({'schema':SCHEMA,
        'stages':sorted(x.name for x in bad),'no_confirmatory_outcomes':True}))
    return {'verdict':'AH_INTERRUPTED_STAGING_QUARANTINED','quarantined':len(bad),
            'production_execution_allowed':False}

def _limit_memory_windows(limit_bytes):
    """Set OS Job Object per-process memory limit in the worker (Windows only)."""
    import ctypes
    from ctypes import wintypes
    ULONG_PTR=ctypes.c_size_t
    class IO_COUNTERS(ctypes.Structure):
        _fields_=[('ReadOperationCount',ctypes.c_uint64),('WriteOperationCount',ctypes.c_uint64),('OtherOperationCount',ctypes.c_uint64),('ReadTransferCount',ctypes.c_uint64),('WriteTransferCount',ctypes.c_uint64),('OtherTransferCount',ctypes.c_uint64)]
    class BASIC(ctypes.Structure):
        _fields_=[('PerProcessUserTimeLimit',ctypes.c_int64),('PerJobUserTimeLimit',ctypes.c_int64),('LimitFlags',wintypes.DWORD),('MinimumWorkingSetSize',ULONG_PTR),('MaximumWorkingSetSize',ULONG_PTR),('ActiveProcessLimit',wintypes.DWORD),('Affinity',ULONG_PTR),('PriorityClass',wintypes.DWORD),('SchedulingClass',wintypes.DWORD)]
    class EXTENDED(ctypes.Structure):
        _fields_=[('BasicLimitInformation',BASIC),('IoInfo',IO_COUNTERS),('ProcessMemoryLimit',ULONG_PTR),('JobMemoryLimit',ULONG_PTR),('PeakProcessMemoryUsed',ULONG_PTR),('PeakJobMemoryUsed',ULONG_PTR)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR];kernel.CreateJobObjectW.restype=wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD];kernel.SetInformationJobObject.restype=wintypes.BOOL
    kernel.GetCurrentProcess.argtypes=[];kernel.GetCurrentProcess.restype=wintypes.HANDLE
    kernel.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE];kernel.AssignProcessToJobObject.restype=wintypes.BOOL
    job=kernel.CreateJobObjectW(None,None)
    if not job:raise OSError(ctypes.get_last_error(),'CreateJobObjectW')
    info=EXTENDED();info.BasicLimitInformation.LimitFlags=0x100|0x2000 # PROCESS_MEMORY, KILL_ON_JOB_CLOSE
    info.ProcessMemoryLimit=limit_bytes
    if not kernel.SetInformationJobObject(job,9,ctypes.byref(info),ctypes.sizeof(info)):
        raise OSError(ctypes.get_last_error(),'SetInformationJobObject')
    if not kernel.AssignProcessToJobObject(job,kernel.GetCurrentProcess()):
        raise OSError(ctypes.get_last_error(),'AssignProcessToJobObject (possibly existing job restriction)')
    return job

def enforce_memory_cap(max_mib):
    if max_mib<256 or max_mib>65536:raise ValueError('memory cap must be 256..65536 MiB')
    if os.name=='nt':
        # Worker installs job object before loading AF arrays, fails closed if
        # Windows cannot assign the limit (e.g., incompatible nested job).
        return _limit_memory_windows(int(max_mib)*1024**2)
    import resource
    # RLIMIT_AS can block mmap and virtual address allocations, not an RSS cap.
    soft,hard=resource.getrlimit(resource.RLIMIT_AS)
    bound=int(max_mib)*1024**2
    if hard!=resource.RLIM_INFINITY:bound=min(bound,hard)
    resource.setrlimit(resource.RLIMIT_AS,(bound,hard))
    return None

def supervise(root,af_dir,aa_dir,m_dir,wall_seconds=600,max_mib=8192,stop_after_rows=None):
    if not 1<=wall_seconds<=7200:raise ValueError('wall limit must be 1..7200 seconds')
    if not 256<=max_mib<=65536:raise ValueError('memory cap outside engineering range')
    # Never launch any subprocess without validating the fixed source and chain.
    verify(root,af_dir,aa_dir,m_dir)
    args=[sys.executable,str(Path(__file__).resolve()),'--mode','worker',
          '--output-dir',str(root),'--af-dir',str(af_dir),'--aa-dir',str(aa_dir),
          '--m-dir',str(m_dir),'--max-mib',str(max_mib)]
    if stop_after_rows is not None:args+=['--stop-after-rows',str(stop_after_rows)]
    import psutil
    proc=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    clock=time.monotonic();reason=None;peak=0
    try:
        while proc.poll() is None:
            if time.monotonic()-clock>wall_seconds:
                reason='WALL_TIMEOUT';break
            try:
                mem=psutil.Process(proc.pid).memory_info().rss
                peak=max(peak,mem)
                if mem>max_mib*1024**2:reason='RSS_MEMORY_EXCEEDED';break
            except psutil.NoSuchProcess:break
            time.sleep(.05)
        if reason:
            proc.kill();proc.communicate(timeout=10)
            return {'verdict':'AH_ENGINEERING_GUARD_STOP','reason':reason,
                    'peak_rss_mib_observed':round(peak/1048576,2),
                    'production_execution_allowed':False,'no_confirmatory_outcomes':True}
        out,err=proc.communicate(timeout=10)
        if proc.returncode:
            return {'verdict':'AH_ENGINEERING_WORKER_FAILED','worker_exit':proc.returncode,
                    'worker_error':err[-1500:],
                    'peak_rss_mib_observed':round(peak/1048576,2),
                    'production_execution_allowed':False,'no_confirmatory_outcomes':True}
        r=json.loads(out)
        r['peak_rss_mib_observed']=round(peak/1048576,2)
        r['supervised']=True
        return r
    finally:
        if proc.poll() is None:
            proc.kill();proc.communicate()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('init','check','run','worker','quarantine-staging','production-run','unlock','freeze'),required=True)
    for v in ('output-dir','af-dir','aa-dir','m-dir'):parser.add_argument('--'+v,required=True,type=Path)
    parser.add_argument('--policy');parser.add_argument('--model')
    parser.add_argument('--stop-after-rows',type=int)
    parser.add_argument('--wall-seconds',type=float,default=600)
    parser.add_argument('--max-mib',type=int,default=8192)
    a=parser.parse_args()
    if a.mode in ('production-run','unlock','freeze'):parser.error('PROSPECTIVE_EXECUTION_DISABLED')
    if a.mode=='init':
        if not a.policy or not a.model:parser.error('init requires policy and model')
        r=init(a.output_dir,a.af_dir,a.aa_dir,a.m_dir,a.policy,a.model)
    elif a.mode=='check':
        p,d,n,x,previous=verify(a.output_dir,a.af_dir,a.aa_dir,a.m_dir)
        r={'verdict':'AH_SOURCE_AND_ATOMIC_CHAIN_PASS','rows_done':n,
           'rows_total':p['source']['budget']*p['source']['epochs'],
           'production_execution_allowed':False}
    elif a.mode=='quarantine-staging':r=quarantine_staging(a.output_dir)
    elif a.mode=='run':
        r=supervise(a.output_dir,a.af_dir,a.aa_dir,a.m_dir,a.wall_seconds,a.max_mib,a.stop_after_rows)
    else:
        # Worker is internal, but still validates input namespace; controls
        # are installed BEFORE any large numerical source arrays are loaded.
        job_handle=enforce_memory_cap(a.max_mib)
        r=worker_run(a.output_dir,a.af_dir,a.aa_dir,a.m_dir,a.stop_after_rows)
    print(json.dumps(r,indent=2))
if __name__=='__main__': main()
