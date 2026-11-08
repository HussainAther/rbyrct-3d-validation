"""08AJ-AI: engineering-only resource-failure fault injection and locked roster linkage.

No object-seed dispatch, no production run, no confirmatory arrays or output.
Failure workers operate exclusively in an AI-owned sandbox; AF/AH/AA are read-only.
"""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys, time, uuid
from pathlib import Path
import psutil

SCHEMA = 'RBYRCT-08AJ-AI-failure-injection-v1'
CASES = ('wall', 'memory', 'atomic-stage')


def canonical(obj): return (json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode()
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write_once(path, data):
    path=Path(path)
    with path.open('xb') as f: f.write(data); f.flush(); os.fsync(f.fileno())

def tree_manifest(path):
    """Inventory all evidence files, reject symlinks, and hash each file."""
    path=Path(path)
    if not path.is_dir() or path.is_symlink(): raise ValueError('evidence directory absent or unsafe')
    result={}
    for entry in sorted(path.rglob('*')):
        if entry.is_symlink():raise ValueError('unsafe evidence symlink')
        rel=entry.relative_to(path).as_posix()
        result[rel] = {'kind':'dir'} if entry.is_dir() else {'kind':'file','sha256':sha(entry)}
    return result

def expected(aa_dir,m_dir,ah_dir,af_dir):
    import experiment_08aj_aa as aa
    import experiment_08aj_ah as ah
    manifest, manifest_hash, groups = aa.check(aa_dir,m_dir)
    hp,_,done,_,_ = ah.verify(ah_dir,af_dir,aa_dir,m_dir)
    if hp['source']['n']!=32 or done!=32768:
        raise ValueError('AH must be a completed 32^3 engineering reference')
    from experiment_08aj_ah_audit import audit
    # Structural reference check, plus the previously independently verified AH final
    # receipt; the full numerical replay is run separately by AH's own auditor.
    final=Path(ah_dir)/'final'/'receipt.json'
    if not final.is_file(): raise ValueError('AH final receipt missing')
    rec=json.loads(final.read_bytes())
    if rec.get('production_execution_allowed') is not False or rec.get('rows_done')!=done:
        raise ValueError('not a completed locked AH engineering reference')
    specs=json.loads((Path(aa_dir)/'job_specifications.json').read_bytes())
    models={x['model'] for x in specs}
    policy_models=sorted({(x['policy'],x['model']) for x in specs})
    if len(specs)!=480 or len(groups)!=96 or len(policy_models)!=10 or models!={'same','independent'}:
        raise ValueError('AA full roster inconsistency')
    if any(x['execution_allowed'] is not False for x in specs):
        raise ValueError('production execution unexpectedly permitted')
    return {'schema':SCHEMA,'namespace':'NONCOHORT_FAULT_INJECTION_ONLY',
        'aa_manifest_sha256':manifest_hash,'aa_specs_sha256':sha(Path(aa_dir)/'job_specifications.json'),
        'ah_plan_sha256':sha(Path(ah_dir)/'plan.json'),
        'ah_final_receipt_sha256':sha(final),
        'ah_evidence_tree':tree_manifest(ah_dir),
        'ah_source_sha256':sha(Path(ah.__file__)),
        'ai_source_sha256':sha(Path(__file__)),
        'aa_job_specifications':480,'aa_shared_groups':96,
        'engineering_templates':[{'policy':p,'model':m} for p,m in policy_models],
        'resource_limits_proposed_not_approved':True,
        'scientific_signoff':False,'resource_policy_approved':False,'frozen':False,
        'production_480_job_certified':False,'production_execution_allowed':False,
        'no_confirmatory_outcomes':True}

def prepare(root,aa_dir,m_dir,ah_dir,af_dir):
    root=Path(root)
    if root.exists():raise FileExistsError('AI output already exists; no overwriting')
    plan=expected(aa_dir,m_dir,ah_dir,af_dir)
    root.mkdir(parents=True)
    write_once(root/'plan.json',canonical(plan))
    (root/'cases').mkdir()
    return {'verdict':'AI_LOCKED_FAILURE_GATE_PREPARED','engineering_templates':10,
            'roster_specs_linked':480,'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def check(root,aa_dir,m_dir,ah_dir,af_dir):
    root=Path(root)
    p=json.loads((root/'plan.json').read_bytes())
    if p!=expected(aa_dir,m_dir,ah_dir,af_dir) or (root/'plan.json').read_bytes()!=canonical(p):
        raise ValueError('AI source or protected evidence changed')
    cases=root/'cases'
    if not cases.is_dir() or cases.is_symlink():raise ValueError('missing cases directory')
    for c in cases.iterdir():
        if c.is_symlink() or not c.is_dir() or c.name not in CASES:
            raise ValueError('unexpected case artifact')
    return p

def _install_memory_cap(max_mib):
    """Standalone fault-worker OS cap; same Windows API as AH, no imaging imports."""
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes
        ULONG_PTR=ctypes.c_size_t
        class IO_COUNTERS(ctypes.Structure):
            _fields_=[('ReadOperationCount',ctypes.c_uint64),('WriteOperationCount',ctypes.c_uint64),('OtherOperationCount',ctypes.c_uint64),('ReadTransferCount',ctypes.c_uint64),('WriteTransferCount',ctypes.c_uint64),('OtherTransferCount',ctypes.c_uint64)]
        class BASIC(ctypes.Structure):
            _fields_=[('PerProcessUserTimeLimit',ctypes.c_int64),('PerJobUserTimeLimit',ctypes.c_int64),('LimitFlags',wintypes.DWORD),('MinimumWorkingSetSize',ULONG_PTR),('MaximumWorkingSetSize',ULONG_PTR),('ActiveProcessLimit',wintypes.DWORD),('Affinity',ULONG_PTR),('PriorityClass',wintypes.DWORD),('SchedulingClass',wintypes.DWORD)]
        class EXTENDED(ctypes.Structure):
            _fields_=[('BasicLimitInformation',BASIC),('IoInfo',IO_COUNTERS),('ProcessMemoryLimit',ULONG_PTR),('JobMemoryLimit',ULONG_PTR),('PeakProcessMemoryUsed',ULONG_PTR),('PeakJobMemoryUsed',ULONG_PTR)]
        k=ctypes.WinDLL('kernel32',use_last_error=True)
        k.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR];k.CreateJobObjectW.restype=wintypes.HANDLE
        k.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD];k.SetInformationJobObject.restype=wintypes.BOOL
        k.GetCurrentProcess.argtypes=[];k.GetCurrentProcess.restype=wintypes.HANDLE
        k.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE];k.AssignProcessToJobObject.restype=wintypes.BOOL
        job=k.CreateJobObjectW(None,None)
        if not job:raise OSError(ctypes.get_last_error(),'CreateJobObjectW')
        info=EXTENDED();info.BasicLimitInformation.LimitFlags=0x100|0x2000
        info.ProcessMemoryLimit=max_mib*1048576
        if not k.SetInformationJobObject(job,9,ctypes.byref(info),ctypes.sizeof(info)):
            raise OSError(ctypes.get_last_error(),'SetInformationJobObject')
        if not k.AssignProcessToJobObject(job,k.GetCurrentProcess()):
            raise OSError(ctypes.get_last_error(),'AssignProcessToJobObject')
        return job
    import resource
    soft,hard=resource.getrlimit(resource.RLIMIT_AS)
    requested=max_mib*1048576
    if hard!=resource.RLIM_INFINITY:requested=min(requested,hard)
    resource.setrlimit(resource.RLIMIT_AS,(requested,hard))
    return None

def failure_worker(kind,sandbox):
    """Deliberately nonclinical, nonnumerical process failure worker."""
    if kind=='wall':
        time.sleep(90)
    elif kind=='atomic-stage':
        stage=Path(sandbox)/('.stage-'+uuid.uuid4().hex)
        stage.mkdir()
        write_once(stage/'partial.bin',b'ENGINEERING-FAULT-INJECTION-UNCOMMITTED\n')
        time.sleep(90)
    elif kind=='memory':
        # Standalone controlled cap, matching AH's OS-level enforcement mode.
        job=_install_memory_cap(256)
        blocks=[]
        try:
            for _ in range(32):
                b=bytearray(32*1024*1024)
                b[0]=1;b[-1]=1;blocks.append(b)
        except MemoryError:
            print(json.dumps({'verdict':'AI_OS_MEMORY_DENIAL_OBSERVED',
                              'memory_cap_mib':256,'production_execution_allowed':False}),flush=True)
            return
        raise RuntimeError('memory cap failed to reject 1024 MiB allocation')
    else:raise ValueError('invalid worker kind')

def _kill_tree(proc):
    try:
        parent=psutil.Process(proc.pid)
        children=parent.children(recursive=True)
        for c in children: c.kill()
        parent.kill()
    except psutil.NoSuchProcess:pass
    finally:
        try:proc.kill()
        except ProcessLookupError:pass

def exercise(root,kind,wall_seconds=0.5):
    """Run a single fault in an isolated child; never launch a numerical job."""
    if kind not in CASES:raise ValueError('unknown controlled failure kind')
    if not 0.1<=wall_seconds<=20:raise ValueError('fault-test timeout must be 0.1..20s')
    root=Path(root);folder=root/'cases'/kind
    if folder.exists(): raise FileExistsError('case immutable: '+kind)
    folder.mkdir()
    sandbox=folder/'sandbox';sandbox.mkdir()
    args=[sys.executable,str(Path(__file__).resolve()),'--mode','_worker',
          '--kind',kind,'--sandbox',str(sandbox)]
    started=time.monotonic()
    proc=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    timed_out=False
    try:
        try:out,err=proc.communicate(timeout=wall_seconds)
        except subprocess.TimeoutExpired:
            timed_out=True;_kill_tree(proc);out,err=proc.communicate(timeout=10)
    finally:
        if proc.poll() is None:_kill_tree(proc);proc.communicate()
    # For memory: an observed cap refusal or worker nonzero exit is recorded,
    # but only an explicit denial marker counts as confirmed enforcement.
    explicit='AI_OS_MEMORY_DENIAL_OBSERVED' in out
    if kind=='memory':
        observed='OS_MEMORY_DENIAL_CONFIRMED' if explicit and proc.returncode==0 else 'MEMORY_ENFORCEMENT_NOT_CONFIRMED'
    elif timed_out:observed='WALL_TIMEOUT_WORKER_TERMINATED'
    else:observed='FAILURE_NOT_OBSERVED'
    if kind=='atomic-stage':
        staged=[x for x in sandbox.iterdir() if x.name.startswith('.stage-')]
        if len(staged)!=1 or not (staged[0]/'partial.bin').is_file():
            observed='INCOMPLETE_STAGE_NOT_OBSERVED'
    result={'schema':SCHEMA,'case':kind,'verdict':observed,
        'worker_exit':proc.returncode,'timed_out':timed_out,
        'elapsed_seconds':round(time.monotonic()-started,3),
        'memory_cap_mib':256 if kind=='memory' else None,
        'sandbox_tree':tree_manifest(sandbox),
        'production_jobs_executed':0,'production_execution_allowed':False,
        'no_confirmatory_outcomes':True}
    # Store metadata, not full subprocess traces. Failure is evidence, not a reason
    # to overwrite/retry a case. An unconfirmed case is retained for diagnosis.
    write_once(folder/'result.json',canonical(result))
    return result

def quarantine(root):
    root=Path(root);folder=root/'cases'/'atomic-stage'
    rec=json.loads((folder/'result.json').read_bytes())
    if rec['verdict']!='WALL_TIMEOUT_WORKER_TERMINATED':raise ValueError('atomic stage not correctly exercised')
    staged=[x for x in (folder/'sandbox').iterdir() if x.name.startswith('.stage-')]
    if len(staged)!=1:raise ValueError('expected one orphan staging directory')
    dest=folder/'quarantine'
    if dest.exists():raise FileExistsError('quarantine immutable')
    os.replace(staged[0],dest)
    write_once(folder/'quarantine.json',canonical({'schema':SCHEMA,'original_stage_name':staged[0].name,
                 'quarantine_tree':tree_manifest(dest),'no_confirmatory_outcomes':True}))
    return {'verdict':'AI_ORPHAN_STAGE_QUARANTINED','quarantined_stages':1,
            'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',choices=('prepare','check','exercise','quarantine','_worker','production-run','unlock','freeze'),required=True)
    for name in ('output-dir','aa-dir','m-dir','ah-dir','af-dir'):ap.add_argument('--'+name,type=Path)
    ap.add_argument('--kind',choices=CASES);ap.add_argument('--sandbox',type=Path)
    ap.add_argument('--wall-seconds',type=float,default=0.5)
    a=ap.parse_args()
    if a.mode in ('production-run','unlock','freeze'):ap.error('PRODUCTION_EXECUTION_DISABLED')
    if a.mode=='_worker':
        if a.kind not in CASES or not a.sandbox or not a.sandbox.is_dir():ap.error('invalid isolated worker')
        failure_worker(a.kind,a.sandbox);return
    if any(getattr(a,n) is None for n in ('output_dir','aa_dir','m_dir','ah_dir','af_dir')):
        ap.error('all five evidence/output directories required')
    if a.mode=='prepare':r=prepare(a.output_dir,a.aa_dir,a.m_dir,a.ah_dir,a.af_dir)
    else:
        check(a.output_dir,a.aa_dir,a.m_dir,a.ah_dir,a.af_dir)
        if a.mode=='check':r={'verdict':'AI_LOCKED_SOURCES_AND_CHECKPOINTS_MATCH','production_execution_allowed':False}
        elif a.mode=='exercise':
            if not a.kind:ap.error('--kind required')
            r=exercise(a.output_dir,a.kind,a.wall_seconds)
        else:r=quarantine(a.output_dir)
    print(json.dumps(r,indent=2))
if __name__=='__main__':main()
