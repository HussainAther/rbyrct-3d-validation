"""Independent numeric and isolation audit for 08AJ-AL's noncohort objects."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
from experiment_08aj_k_audit import independent_mart
import experiment_08aj_al as al

def audit_one(root,aa_dir,m_dir,obj,model,policy):
    errors=[];replay=None;delta=None
    try:
        s,d,A,y,truth,done,x,last=al.verify_job(root,aa_dir,m_dir,obj,model,policy)
        if done!=s['budget']*s['epochs']:raise ValueError('job incomplete')
        final=d/'final'
        if final.is_symlink() or not final.is_dir() or {v.name for v in final.iterdir()}!={'receipt.json','reconstruction.npy'}:raise ValueError('invalid final directory')
        r=al.read(final/'receipt.json')
        required={'schema':al.SCHEMA,'job_id':s['job_id'],'source_sha256':al.sha(d/'source.json'),
                  'rows_done':done,'last_checkpoint_sha256':last,
                  'reconstruction_sha256':al.sha(final/'reconstruction.npy'),
                  'rmse':r.get('rmse'),'production_execution_allowed':False,'no_confirmatory_outcomes':True}
        if r!=required:raise ValueError('final cross-object receipt mismatch')
        saved=np.load(final/'reconstruction.npy',allow_pickle=False)
        if not np.array_equal(saved,x):raise ValueError('last checkpoint differs from final')
        independent=np.asarray(independent_mart(A,y,epochs=s['epochs'],relaxation=s['relaxation']),dtype=np.float64)
        replay=float(np.max(np.abs(saved-independent)))
        rmse=float(np.sqrt(np.mean((saved-truth)**2)))
        delta=abs(rmse-float(r['rmse']))
        if replay>1e-11 or delta>1e-12:raise ValueError('independent MART / RMSE mismatch')
    except Exception as e:errors.append(type(e).__name__+': '+str(e))
    return {'job_id':al.job_name(obj,model,policy),'pass':not errors,'errors':errors,
            'max_abs_replay_error':replay,'abs_rmse_difference':delta}

def audit(root,aa_dir,m_dir,require_complete=False):
    errors=[];details=[];groups=[]
    try:
        al.check(root,aa_dir,m_dir)
        for obj in al.OBJECTS:
            for model in al.MODELS:
                group=Path(root)/'groups'/al.group_name(obj,model)
                if group.exists():
                    p,A,truth,noisy=al.group_inputs(root,aa_dir,m_dir,obj,model)
                    groups.append({'object':obj,'model':model,'truth_sha256':al.read(group/'receipt.json')['truth_sha256'],
                                   'noisy_sha256':al.sha(group/'noisy.npy')})
                    for policy in al.POLICIES:
                        if (Path(root)/'jobs'/al.job_name(obj,model,policy)).exists():
                            details.append(audit_one(root,aa_dir,m_dir,obj,model,policy))
        if len(set(x['truth_sha256'] for x in groups))<2 and len({x['object'] for x in groups})==2:
            errors.append('engineering objects have identical truth hashes')
        for obj in al.OBJECTS:
            matched=[v for v in groups if v['object']==obj]
            if len(matched)==2 and len(set(v['truth_sha256'] for v in matched))!=1:
                errors.append('one object changed truth across models')
        if len({x['noisy_sha256'] for x in groups})!=len(groups):
            errors.append('measurement catalogue collision across object/model groups')
        if require_complete and (len(groups)!=4 or len(details)!=8):errors.append('require-complete expects four groups and eight jobs')
        if not details:errors.append('no completed engineering jobs')
        for obj in al.OBJECTS:
            for model in al.MODELS:
                group=Path(root)/'groups'/al.group_name(obj,model)
                if not group.exists():continue
                sampled=[]
                for policy in al.POLICIES:
                    d=Path(root)/'jobs'/al.job_name(obj,model,policy)
                    if d.is_dir():sampled.append(np.load(d/'order.npy',allow_pickle=False))
                if len(sampled)==2:
                    warm=al.read(Path(root)/'plan.json')['config']['warm']
                    if not np.array_equal(sampled[0][:warm],sampled[1][:warm]):errors.append('common warm-prefix failure')
    except Exception as e:errors.append(type(e).__name__+': '+str(e))
    errors.extend(x['job_id']+': '+str(x['errors']) for x in details if not x['pass'])
    return {'verdict':'AL_INDEPENDENT_MULTI_OBJECT_AUDIT_PASS' if not errors else 'AL_MULTI_OBJECT_AUDIT_FAIL',
            'pass':not errors,'errors':errors,'engineering_objects':len({x['object'] for x in groups}),
            'shared_groups_audited':len(groups),'engineering_jobs_audited':len(details),
            'details':details,'production_jobs_executed':0,'production_480_job_certified':False,
            'resource_policy_approved':False,'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('output-dir','aa-dir','m-dir'):ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--require-complete',action='store_true')
    a=ap.parse_args();r=audit(a.output_dir,a.aa_dir,a.m_dir,a.require_complete)
    print(json.dumps(r,indent=2))
    if not r['pass']:raise SystemExit(2)
if __name__=='__main__':main()
