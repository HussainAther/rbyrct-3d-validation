"""08AJ-AG: independently checkable row-recovery of fresh AF NONCOHORT engineering input.

Reads pre-existing AF artifacts; never writes to AF. Only the fixed AF engineering
namespace is permitted; the 480-job production roster remains execution-disabled.
"""
from __future__ import annotations
import argparse, json, time
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix
import experiment_08aj_af as af
import experiment_08aj_aa as aa
import experiment_08aj_ad as ad

SCHEMA='RBYRCT-08AJ-AG-fresh-row-recovery-v1'
INPUTS=('csr_data.npy','csr_indices.npy','csr_indptr.npy','measurements.npy','reconstruction.npy','order.npy')

def evidence(root,af_dir,aa_dir,m_dir,policy,model):
    if policy not in aa.POLICIES or model not in aa.MODELS:raise ValueError('invalid engineering template')
    p,A,truth,noisy=af.validate_group(af_dir,aa_dir,m_dir,model)
    if p.get('namespace')!='FRESH_ENGINEERING_ONLY' or p.get('engineering_seed')!=af.SEED or p.get('production_execution_allowed') is not False:
        raise ValueError('AF engineering namespace lock broken')
    jid=policy+'__'+model
    d=Path(af_dir)/'jobs'/jid
    if not d.is_dir() or d.is_symlink() or {x.name for x in d.iterdir()}!=set(af.ARRAY_FILES)|{'receipt.json'}:
        raise ValueError('missing or unexpected AF job evidence')
    r=af.load_json(d/'receipt.json')
    if r.get('namespace')!='FRESH_ENGINEERING_ONLY' or r.get('production_execution_allowed') is not False or r.get('no_confirmatory_outcomes') is not True:
        raise ValueError('AF receipt execution lock broken')
    if r.get('artifact_sha256')!={name:af.sha_file(d/name) for name in af.ARRAY_FILES}:
        raise ValueError('AF job artifact hashes changed')
    if r.get('plan_sha256')!=af.sha_file(Path(af_dir)/'plan.json') or r.get('group_receipt_sha256')!=af.sha_file(Path(af_dir)/'groups'/model/'receipt.json'):
        raise ValueError('AF job/group link changed')
    return p,d,r,truth

def expected_plan(af_dir,aa_dir,m_dir,policy,model):
    p,d,r,truth=evidence(None,af_dir,aa_dir,m_dir,policy,model)
    return {'schema':SCHEMA,'namespace':'FRESH_ENGINEERING_RECOVERY_ONLY',
       'policy':policy,'model':model,'n':p['n'],'budget':p['budget'],
       'epochs':p['epochs'],'relaxation':p['relaxation'],
       'af_plan_sha256':af.sha_file(Path(af_dir)/'plan.json'),
       'af_job_receipt_sha256':af.sha_file(d/'receipt.json'),
       'af_group_receipt_sha256':af.sha_file(Path(af_dir)/'groups'/model/'receipt.json'),
       'af_input_sha256':{name:af.sha_file(d/name) for name in INPUTS},
       'checkpoint_step_rows':ad.CHECKPOINT_STEP,
       'production_jobs_executed':0,'production_480_job_certified':False,
       'production_execution_allowed':False,'resource_policy_approved':False,
       'scientific_signoff':False,'frozen':False,'no_confirmatory_outcomes':True}

def initialize(root,af_dir,aa_dir,m_dir,policy,model):
    root=Path(root)
    if root.exists():raise FileExistsError('AG recovery directory exists; cannot overwrite')
    plan=expected_plan(af_dir,aa_dir,m_dir,policy,model)
    root.mkdir(parents=True)
    ad.create(root/'plan.json',ad.canonical(plan));(root/'checkpoints').mkdir()
    return {'verdict':'AG_FRESH_RECOVERY_PREPARED','job_id':policy+'__'+model,
            'n':plan['n'],'epochs':plan['epochs'],'production_execution_allowed':False,
            'no_confirmatory_outcomes':True}

def verify(root,af_dir,aa_dir,m_dir):
    root=Path(root);plan=ad.load_receipt(root/'plan.json')
    expected=expected_plan(af_dir,aa_dir,m_dir,plan['policy'],plan['model'])
    if plan!=expected:raise ValueError('AG plan/AF source drift')
    d=Path(af_dir)/'jobs'/(plan['policy']+'__'+plan['model'])
    if any(af.sha_file(d/name)!=h for name,h in plan['af_input_sha256'].items()):
        raise ValueError('AF input artifact drift')
    done,x,previous=ad.verify_chain(root,plan)
    return plan,d,done,x,previous

def inputs(folder,plan):
    arr={name:np.load(folder/name,allow_pickle=False) for name in INPUTS}
    if any(not np.isfinite(x).all() for x in arr.values()):raise ValueError('nonfinite AF input')
    A=csr_matrix((arr['csr_data.npy'],arr['csr_indices.npy'],arr['csr_indptr.npy']),shape=(plan['budget'],plan['n']**3))
    y=np.asarray(arr['measurements.npy'],dtype=np.float64)
    ref=np.asarray(arr['reconstruction.npy'],dtype=np.float64)
    if y.shape!=(plan['budget'],) or ref.shape!=(plan['n']**3,) or len(arr['order.npy'])!=plan['budget']:
        raise ValueError('AF input geometry mismatch')
    return A,y,ref

def run(root,af_dir,aa_dir,m_dir,stop_after_rows=None,wall_seconds=600):
    if stop_after_rows is not None and stop_after_rows<1:raise ValueError('positive stop-after-rows required')
    if not 1<=wall_seconds<=7200:raise ValueError('invalid wall budget')
    plan,d,done,x,previous=verify(root,af_dir,aa_dir,m_dir)
    A,y,ref=inputs(d,plan)
    total=plan['budget']*plan['epochs'];root=Path(root)
    if (root/'final.json').exists():
        from experiment_08aj_ag_audit import audit
        r=audit(root,af_dir,aa_dir,m_dir)
        if not r['pass']:raise ValueError('existing AG result failed independent audit')
        return {'verdict':'AG_FRESH_RECOVERY_REUSED','rows_done':total,'production_execution_allowed':False}
    if done<total:
        if x is None:x=np.full(plan['n']**3,.3,dtype=np.float64)
        since=0;started=time.monotonic()
        for cursor in range(done,total):
            if time.monotonic()-started>wall_seconds:raise TimeoutError('AG wall guard exceeded; last checkpoint preserved')
            ad.step_row(x,A,y,cursor%plan['budget'],plan['relaxation'])
            now=cursor+1;since+=1
            if now%plan['checkpoint_step_rows']==0 or now==total or (stop_after_rows is not None and since>=stop_after_rows):
                previous=ad.checkpoint(root,plan,x,now,previous)
            if stop_after_rows is not None and since>=stop_after_rows:
                return {'verdict':'AG_FRESH_ENGINEERING_PAUSED','rows_done':now,'rows_total':total,
                        'production_execution_allowed':False,'no_confirmatory_outcomes':True}
    done,x,previous=ad.verify_chain(root,plan)
    if done!=total:raise ValueError('incomplete AG work')
    discrepancy=float(np.max(np.abs(x-ref)))
    if discrepancy>1e-11:raise ValueError('fresh AF reference differs from recovered MART: '+str(discrepancy))
    f=root/'final_reconstruction.npy';ad.save_array(f,x)
    record={'schema':SCHEMA,'plan_sha256':ad.sha(root/'plan.json'),
            'final_reconstruction_sha256':ad.sha(f),
            'last_checkpoint_receipt_sha256':previous,'rows_done':done,
            'max_abs_error_vs_af':discrepancy,'production_execution_allowed':False,
            'no_confirmatory_outcomes':True}
    ad.create(root/'final.json',ad.canonical(record))
    return {'verdict':'AG_FRESH_ENGINEERING_RESUME_PASS','rows_done':done,'rows_total':total,
            'max_abs_error_vs_af':discrepancy,'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',choices=('init','check','run','production-run','unlock','freeze'),required=True)
    for name in ('output-dir','af-dir','aa-dir','m-dir'):ap.add_argument('--'+name,required=True,type=Path)
    ap.add_argument('--policy',choices=aa.POLICIES);ap.add_argument('--model',choices=aa.MODELS)
    ap.add_argument('--stop-after-rows',type=int);ap.add_argument('--wall-seconds',type=float,default=600)
    a=ap.parse_args()
    if a.mode in ('production-run','unlock','freeze'):ap.error('PROSPECTIVE_EXECUTION_DISABLED')
    if a.mode=='init':
        if not a.policy or not a.model:ap.error('init needs policy/model')
        r=initialize(a.output_dir,a.af_dir,a.aa_dir,a.m_dir,a.policy,a.model)
    elif a.mode=='check':
        p,d,done,x,previous=verify(a.output_dir,a.af_dir,a.aa_dir,a.m_dir)
        r={'verdict':'AG_FRESH_SOURCE_AND_CHAIN_PASS','rows_done':done,'rows_total':p['budget']*p['epochs'],'production_execution_allowed':False}
    else:r=run(a.output_dir,a.af_dir,a.aa_dir,a.m_dir,a.stop_after_rows,a.wall_seconds)
    print(json.dumps(r,indent=2))
if __name__=='__main__':main()
