"""Independent per-job numerical replay and cross-object/seed/model audit for 08AJ-AN."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
from experiment_08aj_k_audit import independent_mart
import experiment_08aj_an as an


def audit_one(root,aa_dir,m_dir,obj,acq,model,policy):
    errors=[];replay=None;delta=None
    jid=an.job_name(obj,acq,model,policy)
    try:
        s,d,A,y,truth,done,x,last=an.verify_job(root,aa_dir,m_dir,obj,acq,model,policy)
        if done!=s['budget']*s['epochs']:raise ValueError('job incomplete')
        final=d/'final'
        if final.is_symlink() or not final.is_dir() or {v.name for v in final.iterdir()}!={'receipt.json','reconstruction.npy'}:
            raise ValueError('invalid final directory')
        r=an.read(final/'receipt.json')
        required={'schema':an.SCHEMA,'job_id':jid,'source_sha256':an.sha(d/'source.json'),
                  'rows_done':done,'last_checkpoint_sha256':last,
                  'reconstruction_sha256':an.sha(final/'reconstruction.npy'),
                  'rmse':r.get('rmse'),'production_execution_allowed':False,'no_confirmatory_outcomes':True}
        if r!=required:raise ValueError('final cross-object/seed receipt mismatch')
        saved=np.load(final/'reconstruction.npy',allow_pickle=False)
        if not np.array_equal(saved,x):raise ValueError('last checkpoint differs from final')
        independent=np.asarray(independent_mart(A,y,epochs=s['epochs'],relaxation=s['relaxation']),dtype=np.float64)
        replay=float(np.max(np.abs(saved-independent)))
        rmse=float(np.sqrt(np.mean((saved-truth)**2)))
        delta=abs(rmse-float(r['rmse']))
        if replay>1e-11 or delta>1e-12:raise ValueError('independent MART / RMSE mismatch')
    except Exception as e:errors.append(type(e).__name__+': '+str(e))
    return {'job_id':jid,'pass':not errors,'errors':errors,'max_abs_replay_error':replay,'abs_rmse_difference':delta}


def audit(root,aa_dir,m_dir,require_complete=False):
    errors=[];details=[];groups=[];p=None
    try:
        p=an.check(root,aa_dir,m_dir)
        for obj in an.OBJECTS:
            for acq in an.ACQUISITIONS:
                for model in an.MODELS:
                    g=Path(root)/'groups'/an.group_name(obj,acq,model)
                    if not g.exists():continue
                    an.group_inputs(root,aa_dir,m_dir,obj,acq,model)
                    r=an.read(g/'receipt.json')
                    groups.append({'object':obj,'acquisition':acq,'model':model,
                        'truth_sha256':r['truth_sha256'],'noisy_sha256':an.sha(g/'noisy.npy'),
                        'noise_seed':r['noise_seed']})
                    for policy in an.POLICIES:
                        j=Path(root)/'jobs'/an.job_name(obj,acq,model,policy)
                        if j.exists():details.append(audit_one(root,aa_dir,m_dir,obj,acq,model,policy))
        if len({r['truth_sha256'] for r in groups})!=len({r['object'] for r in groups}):
            errors.append('truth hashes do not uniquely identify objects')
        for obj in an.OBJECTS:
            same=[r['truth_sha256'] for r in groups if r['object']==obj]
            if len(set(same))>1:errors.append('one object changed across acquisition seeds or models')
        for field in ('noise_seed','noisy_sha256'):
            if len({r[field] for r in groups})!=len(groups):errors.append('cross-group '+field+' collision')
        # All four individual-ray policies MUST share an initial prefix. Whole-view policy is exempt.
        for group in groups:
            o,a,m=group['object'],group['acquisition'],group['model']
            orders={}
            for policy in an.POLICIES:
                j=Path(root)/'jobs'/an.job_name(o,a,m,policy)
                if j.exists():orders[policy]=np.load(j/'order.npy',allow_pickle=False)
            individual=[x for x in an.POLICIES if x!='complete_view' and x in orders]
            if len(individual)>=2:
                warm=p['config']['warm']
                initial=orders[individual[0]][:warm]
                if any(not np.array_equal(initial,orders[pol][:warm]) for pol in individual[1:]):
                    errors.append('individual-ray common warm-prefix failure: '+an.group_name(o,a,m))
            if 'complete_view' in orders:
                n=p['config']['n']; cv=orders['complete_view']
                if len(cv)!=2*n*n or len(set(map(int,cv)))!=len(cv):
                    errors.append('complete_view budget/distinctness failure')
                # The order consists of two complete view blocks of n*n rays each.
                views=[set(map(int,cv[i:i+n*n]//(n*n))) for i in (0,n*n)]
                if any(len(v)!=1 for v in views) or views[0]==views[1]:
                    errors.append('complete_view is not two complete detector views')
        if require_complete and (len(groups)!=8 or len(details)!=40):
            errors.append('require-complete expects eight groups and forty engineering jobs')
        if not details and not groups:errors.append('no engineering evidence')
    except Exception as e:errors.append(type(e).__name__+': '+str(e))
    errors.extend(d['job_id']+': '+str(d['errors']) for d in details if not d['pass'])
    return {'verdict':'AN_INDEPENDENT_MULTI_SEED_AUDIT_PASS' if not errors else 'AN_MULTI_SEED_AUDIT_FAIL',
        'pass':not errors,'errors':errors,'engineering_objects':len({r['object'] for r in groups}),
        'acquisition_seeds':len({r['acquisition'] for r in groups}),
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
