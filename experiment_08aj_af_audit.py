"""08AJ-AF independent fresh-object engineering numerical and shared-catalogue audit."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix
from experiment_08aj_g import fair_orders
from experiment_08aj_k_audit import independent_mart
import experiment_08aj_aa as aa
import experiment_08aj_af as af

def audit_one(root,aa_dir,m_dir,policy,model):
    errors=[];maximum=None;rmse_delta=None
    jid=policy+'__'+model
    try:
        p,A,truth,noisy=af.validate_group(root,aa_dir,m_dir,model)
        d=Path(root)/'jobs'/jid
        if not d.is_dir() or d.is_symlink() or {x.name for x in d.iterdir()}!=set(af.ARRAY_FILES)|{'receipt.json'}:
            raise ValueError('invalid job artifacts')
        r=af.load_json(d/'receipt.json')
        expected={'schema':af.SCHEMA,'namespace':'FRESH_ENGINEERING_ONLY','job_id':jid,
          'plan_sha256':af.sha_file(Path(root)/'plan.json'),
          'group_receipt_sha256':af.sha_file(Path(root)/'groups'/model/'receipt.json'),
          'artifact_sha256':{k:af.sha_file(d/k) for k in af.ARRAY_FILES},
          'truth_sha256':af.sha_bytes(np.asarray(truth,dtype='<f8').tobytes()),
          'rmse':r.get('rmse'),'production_execution_allowed':False,'no_confirmatory_outcomes':True}
        if r!=expected:errors.append('receipt or hash mismatch')
        arrays={k:np.load(d/k,allow_pickle=False) for k in af.ARRAY_FILES}
        order=arrays['order.npy'];recon=arrays['reconstruction.npy'];selected=arrays['measurements.npy']
        if (order.shape!=(p['budget'],) or not np.issubdtype(order.dtype,np.integer)
            or len(np.unique(order))!=p['budget'] or np.any(order<0) or np.any(order>=len(noisy))
            or recon.shape!=(p['n']**3,) or selected.shape!=(p['budget'],)):
            errors.append('shape/ray identity mismatch')
        if any(not np.isfinite(x).all() for x in arrays.values()) or np.any(recon<=0):errors.append('nonfinite reconstruction')
        if not errors:
            orders,_=fair_orders(A,n=p['n'],angles=4,seed=af.ACQ,budget=p['budget'],warm=p['warm'],pool=16,batch=8 if p['n']==8 else 32)
            if not np.array_equal(order,np.asarray(orders[policy])):errors.append('policy ordering mismatch')
            if not np.array_equal(selected,noisy[order]):errors.append('shared noise catalogue mismatch')
            csr=csr_matrix((arrays['csr_data.npy'],arrays['csr_indices.npy'],arrays['csr_indptr.npy']),shape=(p['budget'],p['n']**3))
            if (csr!=A[order]).nnz:errors.append('selected CSR mismatch')
            if not errors:
                independent=independent_mart(csr,selected,epochs=p['epochs'],relaxation=p['relaxation'])
                maximum=float(np.max(np.abs(independent-recon)))
                rmse=float(np.sqrt(np.mean((recon-truth)**2)))
                rmse_delta=abs(rmse-r['rmse'])
                if maximum>1e-11:errors.append('independent MART reconstruction mismatch')
                if rmse_delta>1e-12:errors.append('independent RMSE mismatch')
    except Exception as e:errors.append(type(e).__name__+': '+str(e))
    return {'job_id':jid,'pass':not errors,'errors':errors,
      'max_abs_replay_error':maximum,'abs_rmse_difference':rmse_delta}

def audit(root,aa_dir,m_dir,require_complete=False):
    errors=[];details=[];models=[]
    try:
        p=af.check(root,aa_dir,m_dir)
        for model in aa.MODELS:
            if (Path(root)/'groups'/model).exists():
                af.validate_group(root,aa_dir,m_dir,model);models.append(model)
        for path in sorted((Path(root)/'jobs').iterdir()):
            a=path.name.rsplit('__',1)
            if len(a)!=2 or a[0] not in aa.POLICIES or a[1] not in aa.MODELS:
                errors.append('unrecognized or incomplete job: '+path.name)
            else:details.append(audit_one(root,aa_dir,m_dir,*a))
        if require_complete and (len(details)!=10 or len(models)!=2):errors.append('require-complete needs ten jobs and both model catalogues')
        if not details:errors.append('no completed jobs')
        for model in aa.MODELS:
            items=[x for x in details if x['job_id'].endswith('__'+model)]
            if len(items)>1 and all(x['pass'] for x in items):
                for x in items:
                    folder=Path(root)/'jobs'/x['job_id']
                    ids=np.load(folder/'order.npy',allow_pickle=False)
                    measured=np.load(folder/'measurements.npy',allow_pickle=False)
                    noisy=np.load(Path(root)/'groups'/model/'noisy.npy',allow_pickle=False)
                    if not np.array_equal(measured,noisy[ids]):errors.append('cross-policy shared noise violation')
                individuals=[x for x in items if not x['job_id'].startswith('complete_view__')]
                if len(individuals)>1:
                    prefixes=[np.load(Path(root)/'jobs'/x['job_id']/'order.npy',allow_pickle=False)[:p['warm']] for x in individuals]
                    if any(not np.array_equal(prefixes[0],v) for v in prefixes[1:]):errors.append('common warm prefix violation')
    except Exception as e:errors.append(type(e).__name__+': '+str(e))
    errors.extend(x['job_id']+': '+str(x['errors']) for x in details if not x['pass'])
    return {'verdict':'AF_INDEPENDENT_FRESH_INPUT_AUDIT_PASS' if not errors else 'AF_FRESH_INPUT_AUDIT_FAIL',
      'pass':not errors,'errors':errors,'audited_engineering_jobs':len(details),
      'shared_catalogues_audited':len(models),'details':details,
      'production_jobs_executed':0,'production_480_job_certified':False,
      'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for k in ('output-dir','aa-dir','m-dir'):ap.add_argument('--'+k,required=True,type=Path)
    ap.add_argument('--require-complete',action='store_true')
    a=ap.parse_args();r=audit(a.output_dir,a.aa_dir,a.m_dir,a.require_complete)
    print(json.dumps(r,indent=2))
    if not r['pass']:raise SystemExit(2)
if __name__=='__main__':main()
