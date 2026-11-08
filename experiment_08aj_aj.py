"""08AJ-AJ: kill a REAL engineering MART worker after an atomic checkpoint.

This is deliberately separate from the prospective roster and from completed AH
runs. No production, freeze, or unlock operation exists. Failure artifacts are
immutable and resumptions use the existing independently audited AH backend.
"""
from __future__ import annotations
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
import psutil
import experiment_08aj_ah as ah
import experiment_08aj_aa as aa

SCHEMA='RBYRCT-08AJ-AJ-live-worker-kill-v1'
WORKER='experiment_08aj_aj_worker.py'

def canonical(r): return (json.dumps(r,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('ascii')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_once(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as f:
        f.write(canonical(obj));f.flush();os.fsync(f.fileno())

def plan(af_dir,aa_dir,m_dir,policy,model):
    if policy not in aa.POLICIES or model not in aa.MODELS:raise ValueError('invalid engineering template')
    manifest,_,groups=aa.check(aa_dir,m_dir)
    if len(groups)!=96 or manifest['job_count']!=480 or manifest['confirmatory_execution_allowed'] is not False:
        raise ValueError('AA prospective gate invalid')
    source=ah.plan_for(af_dir,aa_dir,m_dir,policy,model)
    if source['namespace']!='FRESH_ENGINEERING_RESOURCE_GUARD_ONLY' or source['production_execution_allowed'] is not False:
        raise ValueError('AH source not engineering-only')
    return {'schema':SCHEMA,'namespace':'LIVE_ENGINEERING_FAULT_TEST_ONLY',
            'policy':policy,'model':model,
            'source_sha256':hashlib.sha256(canonical(source)).hexdigest(),
            'aa_manifest_sha256':sha(Path(aa_dir)/'aa_manifest.json'),
            'source_modules':{n:sha(Path(__file__).resolve().parent/n) for n in ('experiment_08aj_aj.py',WORKER,'experiment_08aj_aj_audit.py')},
            'job_specs_audited':480,'shared_groups':96,
            'production_execution_allowed':False,'production_480_job_certified':False,
            'resource_policy_approved':False,'scientific_signoff':False,
            'frozen':False,'no_confirmatory_outcomes':True}

def init(root,af_dir,aa_dir,m_dir,policy,model):
    root=Path(root)
    if root.exists():raise FileExistsError('AJ output exists: preserve previous evidence')
    p=plan(af_dir,aa_dir,m_dir,policy,model)
    root.mkdir(parents=True)
    write_once(root/'plan.json',p)
    ah.init(root/'worker',af_dir,aa_dir,m_dir,policy,model)
    return {'verdict':'AJ_LIVE_ENGINEERING_GATE_PREPARED','job_id':policy+'__'+model,
            'n':ah.receipt(root/'worker'/'plan.json')['source']['n'],
            'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def check(root,af_dir,aa_dir,m_dir):
    root=Path(root)
    p=ah.receipt(root/'plan.json')
    if p.get('schema')!=SCHEMA or p.get('namespace')!='LIVE_ENGINEERING_FAULT_TEST_ONLY':raise ValueError('invalid AJ namespace')
    if p!=plan(af_dir,aa_dir,m_dir,p['policy'],p['model']):raise ValueError('AJ plan/source drift')
    ahplan,folder,done,x,prev=ah.verify(root/'worker',af_dir,aa_dir,m_dir)
    extras={z.name for z in root.iterdir()}-{'plan.json','worker','fault.json','resume.json'}
    if extras:raise ValueError('unexpected AJ artifacts: '+str(extras))
    return p,done,prev

def _kill_tree(proc):
    try:
        parent=psutil.Process(proc.pid)
        for c in parent.children(recursive=True):
            try:c.kill()
            except psutil.NoSuchProcess:pass
        try:parent.kill()
        except psutil.NoSuchProcess:pass
    except psutil.NoSuchProcess:pass
    try:proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill();proc.communicate(timeout=10)

def inject(root,af_dir,aa_dir,m_dir,target_rows=256,wall_seconds=120,max_mib=8192):
    root=Path(root)
    if (root/'fault.json').exists() or (root/'resume.json').exists():raise FileExistsError('immutable fault evidence already exists')
    p,initial,previous=check(root,af_dir,aa_dir,m_dir)
    if initial!=0:raise ValueError('fault test must start before any MART updates')
    src=ah.receipt(root/'worker'/'plan.json')['source']
    total=src['budget']*src['epochs']
    if not (128<=target_rows<total and target_rows%ah.STEP==0):raise ValueError('target must be valid committed checkpoint')
    if not (2<=wall_seconds<=1200):raise ValueError('invalid deadline')
    args=[sys.executable,str(Path(__file__).resolve().parent/WORKER),
          '--worker-dir',str(root/'worker'),'--af-dir',str(af_dir),
          '--aa-dir',str(aa_dir),'--m-dir',str(m_dir),'--max-mib',str(max_mib),
          '--post-commit-hold','0.4']
    proc=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    started=time.monotonic();detected=None;exit_before=False
    try:
        while time.monotonic()-started<wall_seconds:
            cps=sorted((root/'worker'/'checkpoints').glob('cp_*'))
            if cps:
                numbers=[int(x.name[3:]) for x in cps if x.is_dir() and x.name[3:].isdigit()]
                if numbers and max(numbers)>=target_rows:
                    if proc.poll() is not None:exit_before=True
                    else:detected=max(numbers)
                    break
            if proc.poll() is not None:exit_before=True;break
            time.sleep(.015)
    finally:
        _kill_tree(proc)
    # A checkpoint must have been fully committed before fault intervention.
    _,done,last=check(root,af_dir,aa_dir,m_dir)
    if detected is None or done<target_rows or done>=total or exit_before:
        raise RuntimeError('LIVE_KILL_NOT_VERIFIED: preserved checkpoints; no success receipt written')
    checkpoint=Path(root)/'worker'/'checkpoints'/f'cp_{done:08d}'
    r={'schema':SCHEMA,'verdict':'AJ_REAL_MART_WORKER_KILLED',
       'target_rows':target_rows,'committed_rows_after_kill':done,
       'rows_total':total,'checkpoint_receipt_sha256':sha(checkpoint/'receipt.json'),
       'checkpoint_state_sha256':sha(checkpoint/'state.npy'),
       'worker_was_running_at_intervention':True,
       'prior_AH_evidence_modified':False,'production_jobs_executed':0,
       'production_execution_allowed':False,'no_confirmatory_outcomes':True}
    write_once(root/'fault.json',r)
    return r

def resume(root,af_dir,aa_dir,m_dir,wall_seconds=600,max_mib=8192):
    root=Path(root);p,done,last=check(root,af_dir,aa_dir,m_dir)
    if not (root/'fault.json').exists():raise ValueError('live worker fault receipt required')
    if (root/'resume.json').exists():raise FileExistsError('resume receipt already committed')
    f=ah.receipt(root/'fault.json')
    cp=root/'worker'/'checkpoints'/f'cp_{f["committed_rows_after_kill"]:08d}'
    if done!=f['committed_rows_after_kill'] or last!=sha(cp/'receipt.json') or f['checkpoint_state_sha256']!=sha(cp/'state.npy'):
        raise ValueError('committed checkpoint changed since worker kill')
    response=ah.supervise(root/'worker',af_dir,aa_dir,m_dir,wall_seconds,max_mib)
    if response['verdict']!='AH_ENGINEERING_RECOVERY_PASS':
        return {'verdict':'AJ_RESUME_NOT_COMPLETE','worker':response,'production_execution_allowed':False}
    from experiment_08aj_ah_audit import audit
    outcome=audit(root/'worker',af_dir,aa_dir,m_dir)
    if not outcome['pass']:raise ValueError('AH independent numerical audit did not pass')
    r={'schema':SCHEMA,'verdict':'AJ_REAL_WORKER_RECOVERY_PASS',
       'rows_done':response['rows_done'],'max_abs_error_vs_af':response['max_abs_error_vs_af'],
       'max_abs_replay_error':outcome['max_abs_replay_error'],
       'abs_rmse_difference':outcome['abs_rmse_difference'],
       'fault_receipt_sha256':sha(root/'fault.json'),
       'final_receipt_sha256':sha(root/'worker'/'final'/'receipt.json'),
       'production_jobs_executed':0,'production_execution_allowed':False,'no_confirmatory_outcomes':True}
    write_once(root/'resume.json',r)
    return r

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',choices=('init','check','kill-worker','resume','production-run','unlock','freeze'),required=True)
    for name in ('output-dir','af-dir','aa-dir','m-dir'):ap.add_argument('--'+name,required=True,type=Path)
    ap.add_argument('--policy',choices=aa.POLICIES);ap.add_argument('--model',choices=aa.MODELS)
    ap.add_argument('--target-rows',type=int,default=256)
    ap.add_argument('--wall-seconds',type=float,default=600)
    ap.add_argument('--max-mib',type=int,default=8192)
    a=ap.parse_args()
    if a.mode in ('production-run','unlock','freeze'):ap.error('PRODUCTION_EXECUTION_DISABLED')
    if a.mode=='init':
        if not a.policy or not a.model:ap.error('init requires policy/model')
        r=init(a.output_dir,a.af_dir,a.aa_dir,a.m_dir,a.policy,a.model)
    elif a.mode=='check':
        _,n,_=check(a.output_dir,a.af_dir,a.aa_dir,a.m_dir)
        r={'verdict':'AJ_ENGINEERING_SOURCE_AND_CHECKPOINT_PASS','rows_done':n,'production_execution_allowed':False}
    elif a.mode=='kill-worker':r=inject(a.output_dir,a.af_dir,a.aa_dir,a.m_dir,a.target_rows,a.wall_seconds,a.max_mib)
    else:r=resume(a.output_dir,a.af_dir,a.aa_dir,a.m_dir,a.wall_seconds,a.max_mib)
    print(json.dumps(r,indent=2))

if __name__=='__main__':main()
