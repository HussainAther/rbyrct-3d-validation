"""08AJ-AC: fail-closed production-readiness assessment and bounded ENGINEERING launcher.

Never executes prospective objects. Readiness evidence is a *candidate*, not a
freeze, a scientific approval, or a certification of 480 numerical jobs.
"""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys, time
from pathlib import Path
import experiment_08aj_aa as aa
import experiment_08aj_ab as ab

SCHEMA='RBYRCT-08AJ-AC-readiness-candidate-v1'
FILES=('experiment_08aj_ac.py','experiment_08aj_ac_audit.py',
       'experiment_08aj_ab.py','experiment_08aj_ab_audit.py',
       'experiment_08aj_aa.py','experiment_08aj_aa_audit.py',
       'experiment_08aj_m.py','experiment_08aj_z.py','experiment_08aj_z_audit.py',
       'experiment_08aj_y.py','experiment_08aj_y_audit.py',
       'experiment_08aj_q.py','experiment_08aj_g.py','experiment_08aj_e.py',
       'experiment_04b.py','experiment_04g.py','experiment_04qa.py','experiment_05b_mart.py')
CEILINGS={'max_job_wall_seconds':600,'max_process_tree_rss_bytes':8*1024**3,
          'max_retries':0,'stop_on_missing_monitor':True,'no_outcome_driven_stopping':True,
          'status':'PROPOSED_NOT_APPROVED'}
GAPS=[
 ('G1','Synthetic phantom scope and independence','SCIENTIFIC_SIGNOFF_REQUIRED'),
 ('G2','Primary estimand, conditional inference and effect threshold','SCIENTIFIC_SIGNOFF_REQUIRED'),
 ('G3','Sample precision and statistical decision rule','SCIENTIFIC_SIGNOFF_REQUIRED'),
 ('G4','Operational resource/failure policy and hard-ceiling validation','APPROVAL_AND_VALIDATION_REQUIRED'),
 ('G5','All-roster numerical executor, independent audit and immutable source freeze','IMPLEMENTATION_AND_SIGNOFF_REQUIRED')]

def canonical(obj):return (json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False,ensure_ascii=True)+'\n').encode('ascii')
def sha(b):return hashlib.sha256(b).hexdigest()
def filehash(p):
    p=Path(p)
    if not p.is_file() or p.is_symlink():raise ValueError('missing/unsafe source or artifact: '+str(p))
    return sha(p.read_bytes())
def write_new(p,obj):
    with Path(p).open('xb') as f:f.write(canonical(obj));f.flush();os.fsync(f.fileno())
def load_canonical(p):
    raw=Path(p).read_bytes();value=json.loads(raw)
    if raw!=canonical(value):raise ValueError('noncanonical evidence '+str(p))
    return value

def validate_locks(aa_dir,m_dir,ab8_dir,ab32_dir,y_dir,z_dir):
    import experiment_08aj_m as m
    mplan,_=m.check(m_dir)
    if mplan['execution_gate']['enabled'] is not False:raise ValueError('production contract enabled')
    _,aa_sha,groups=aa.check(aa_dir,m_dir)
    p8,p8sha=ab.check(ab8_dir,aa_dir,m_dir)
    p32,p32sha=ab.check(ab32_dir,aa_dir,m_dir)
    if p8['n']!=8 or p32['n']!=32:raise ValueError('engineering fixture sizes mismatch')
    if any(p.get('production_execution_allowed') is not False or p.get('no_confirmatory_outcomes') is not True for p in (p8,p32)):
        raise ValueError('engineering source unlocked')
    ys=load_canonical(Path(y_dir)/'run_status.json')
    if ys.get('verdict')!='Y_GAP_REGISTER_PREPARED' or ys.get('blocking_gates')!=5 or ys.get('frozen') is not False or ys.get('scientific_signoff') is not False or ys.get('confirmatory_execution_allowed') is not False:
        raise ValueError('scientific decision gate was changed')
    zp=load_canonical(Path(z_dir)/'z_plan.json')
    if zp.get('resource_failure_policy',{}).get('approval')!='PROPOSED_NOT_APPROVED' or zp.get('confirmatory_execution_allowed') is not False:
        raise ValueError('resource approval missing or execution gate changed')
    if len(groups)!=96:raise ValueError('96 measurement groups required')
    return {'aa_manifest_sha256':aa_sha,'ab8_plan_sha256':p8sha,'ab32_plan_sha256':p32sha,
            'y_status_sha256':filehash(Path(y_dir)/'run_status.json'),
            'y_register_sha256':filehash(Path(y_dir)/'scientific_decision_register.json'),
            'z_plan_sha256':filehash(Path(z_dir)/'z_plan.json')}

def snapshot(root):
    jobs=Path(root)/'jobs'
    if not jobs.is_dir() or jobs.is_symlink():raise ValueError('missing jobs directory')
    records={}
    for child in sorted(jobs.iterdir()):
        if child.is_symlink() or not child.is_dir() or child.name.startswith('.staging__'):
            raise ValueError('unfinished or unsafe job artifact '+child.name)
        parts=child.name.rsplit('__',1)
        if len(parts)!=2 or parts[0] not in ab.POLICIES or parts[1] not in ab.MODELS:
            raise ValueError('unknown engineering job '+child.name)
        names=sorted(p.name for p in child.iterdir())
        expected=sorted([*ab.FILES,'receipt.json'])
        if names!=expected:raise ValueError('unexpected/incomplete engineering evidence '+child.name)
        records[child.name]={name:filehash(child/name) for name in expected}
    return records

def candidate(aa_dir,m_dir,ab8_dir,ab32_dir,y_dir,z_dir):
    linked=validate_locks(aa_dir,m_dir,ab8_dir,ab32_dir,y_dir,z_dir)
    a8=snapshot(ab8_dir);a32=snapshot(ab32_dir)
    if not a8 or not a32:raise ValueError('both engineering sizes must contain completed jobs')
    source_dir=Path(__file__).resolve().parent
    sources={name:filehash(source_dir/name) for name in FILES}
    return {'schema':SCHEMA,'source_sha256':sources,'linked_evidence_sha256':linked,
            'engineering_evidence_sha256':{'n8':a8,'n32':a32},
            'numerical_jobs_attested_not_yet_replayed':len(a8)+len(a32),
            'production_job_specs':480,'shared_measurement_groups':96,
            'proposed_guarded_launch_limits':CEILINGS,
            'remaining_gates':[{'gate':i,'title':title,'status':status} for i,title,status in GAPS],
            'mid_job_resume_implemented':False,'hard_os_memory_limit_implemented':False,
            'production_480_job_executor_implemented':False,
            'scientific_signoff':False,'resource_policy_approved':False,'frozen':False,
            'confirmatory_execution_allowed':False,'no_confirmatory_outcomes':True,
            'readiness_verdict':'AC_NOT_READY_FOR_CONFIRMATORY_EXECUTION'}

def prepare(out,aa_dir,m_dir,ab8_dir,ab32_dir,y_dir,z_dir):
    out=Path(out)
    if out.exists():raise FileExistsError('no overwrite of AC evidence')
    c=candidate(aa_dir,m_dir,ab8_dir,ab32_dir,y_dir,z_dir)
    out.mkdir(parents=True)
    write_new(out/'ac_candidate.json',c)
    return {'verdict':'AC_READINESS_CANDIDATE_PREPARED','engineering_jobs_recorded':c['numerical_jobs_attested_not_yet_replayed'],
            'blocking_gates':len(GAPS),'scientific_signoff':False,'frozen':False,'confirmatory_execution_allowed':False,
            'no_confirmatory_outcomes':True}

def check(out,aa_dir,m_dir,ab8_dir,ab32_dir,y_dir,z_dir):
    existing=load_canonical(Path(out)/'ac_candidate.json')
    expected=candidate(aa_dir,m_dir,ab8_dir,ab32_dir,y_dir,z_dir)
    if existing!=expected:raise ValueError('AC_SOURCE_OR_EVIDENCE_DRIFT')
    return {'verdict':'AC_SOURCE_AND_BLOCKER_GATE_MATCH','candidate_sha256':filehash(Path(out)/'ac_candidate.json'),
            'blocking_gates':len(GAPS),'confirmatory_execution_allowed':False}

def guarded_run(ab_dir,aa_dir,m_dir,policy,model,attempt_dir,wall_seconds=600,rss_bytes=8*1024**3):
    """One engineering child, hard wall bound and monitored RSS; never retries.
    No permanent AC scientific unlock exists; every attempt is immutably recorded.
    """
    if not (1<=wall_seconds<=600) or not (1024**2<=rss_bytes<=8*1024**3):
        raise ValueError('cannot relax proposed maximum ceilings')
    plan,_=ab.check(ab_dir,aa_dir,m_dir)
    jid=ab.job_id(policy,model)
    if plan['n'] not in (8,32):raise ValueError('not engineering')
    dst=Path(attempt_dir)
    if dst.exists():raise FileExistsError('attempt already exists: no retry/overwrite')
    try:import psutil
    except ImportError as e:raise RuntimeError('psutil required: fail closed if monitoring unavailable') from e
    dst.mkdir(parents=True)
    args=[sys.executable,str(Path(ab.__file__).resolve()),'--output-dir',str(Path(ab_dir).resolve()),
          '--aa-dir',str(Path(aa_dir).resolve()),'--m-dir',str(Path(m_dir).resolve()),
          '--mode','run','--policy',policy,'--model',model]
    begin=time.monotonic();out=b'';err=b'';peak=0;reason=None;returncode=None
    kwargs={}
    if os.name=='nt':kwargs['creationflags']=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0)
    else:kwargs['start_new_session']=True
    proc=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,**kwargs)
    try:
        while proc.poll() is None:
            elapsed=time.monotonic()-begin
            if elapsed>=wall_seconds:
                reason='HARD_WALL_TIMEOUT';break
            try:
                parent=psutil.Process(proc.pid)
                processes=[parent]+parent.children(recursive=True)
                mem=sum(p.memory_info().rss for p in processes if p.is_running())
                peak=max(peak,mem)
                if mem>rss_bytes:reason='PROCESS_TREE_RSS_EXCEEDED';break
            except psutil.NoSuchProcess:pass
            except Exception as e:reason='RESOURCE_MONITOR_FAILED:'+type(e).__name__;break
            time.sleep(.05)
        if reason:
            try:
                parent=psutil.Process(proc.pid)
                children=parent.children(recursive=True)
                for p in children:p.kill()
                parent.kill()
            except psutil.NoSuchProcess:pass
            except Exception:proc.kill()
        out,err=proc.communicate(timeout=10)
        returncode=proc.returncode
    finally:
        if proc.poll() is None:proc.kill();proc.communicate()
    receipt={'schema':'RBYRCT-08AJ-AC-engineering-guard-attempt-v1','job_id':jid,
             'engineering_n':plan['n'],'wall_limit_seconds':wall_seconds,'rss_limit_bytes':rss_bytes,
             'observed_elapsed_seconds':time.monotonic()-begin,'observed_peak_tree_rss_bytes':peak,
             'reason':reason,'exit_code':returncode,'stdout_sha256':sha(out),'stderr_sha256':sha(err),
             'production_execution_allowed':False,'no_confirmatory_outcomes':True}
    write_new(dst/'attempt_receipt.json',receipt)
    if reason or returncode!=0:
        raise RuntimeError('guarded engineering attempt failed; inspect immutable receipt: '+str(reason or returncode))
    # Committed output must pass independent numerical replay before reporting success.
    from experiment_08aj_ab_audit import audit_one
    report=audit_one(ab_dir,aa_dir,m_dir,policy,model)
    if not report['pass']:raise RuntimeError('guarded engineering output failed independent audit: '+str(report['errors']))
    return {'verdict':'AC_GUARDED_ENGINEERING_JOB_PASS','job_id':jid,'replay_max_abs_error':report['max_abs_replay_error'],
            'engineering_only':True,'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',required=True,choices=('prepare','check','guarded-run','freeze','production-run','unlock'))
    for arg in ('output-dir','aa-dir','m-dir','ab8-dir','ab32-dir','y-dir','z-dir','ab-dir','attempt-dir'):
        p.add_argument('--'+arg,type=Path)
    p.add_argument('--policy',choices=ab.POLICIES);p.add_argument('--model',choices=ab.MODELS)
    p.add_argument('--wall-seconds',type=int,default=600);p.add_argument('--rss-bytes',type=int,default=8*1024**3)
    v=p.parse_args()
    if v.mode in ('freeze','production-run','unlock'):p.error('AC_BLOCKED: no authorization, source freeze or production executor')
    if v.mode=='guarded-run':
        if not all((v.ab_dir,v.aa_dir,v.m_dir,v.policy,v.model,v.attempt_dir)):p.error('guarded-run requires --ab-dir --aa-dir --m-dir --policy --model --attempt-dir')
        result=guarded_run(v.ab_dir,v.aa_dir,v.m_dir,v.policy,v.model,v.attempt_dir,v.wall_seconds,v.rss_bytes)
    else:
        req=[v.output_dir,v.aa_dir,v.m_dir,v.ab8_dir,v.ab32_dir,v.y_dir,v.z_dir]
        if not all(req):p.error('prepare/check requires --output-dir --aa-dir --m-dir --ab8-dir --ab32-dir --y-dir --z-dir')
        result=prepare(*req) if v.mode=='prepare' else check(*req)
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
