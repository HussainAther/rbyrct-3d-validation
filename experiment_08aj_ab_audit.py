"""Independent numerical replay and RMSE auditor for 08AJ-AB engineering shadow jobs."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_08aj_e import full_resolution_pair,model_measurements
from experiment_08aj_g import fair_orders
from experiment_08aj_k_audit import independent_mart
import experiment_08aj_ab as ab

def audit_one(root,aa_dir,m_dir,policy,model):
    errors=[];error=None
    try:
        jid=ab.job_id(policy,model)
        root=Path(root);plan,ph=ab.check(root,aa_dir,m_dir)
        folder=root/'jobs'/jid
        if not folder.is_dir() or folder.is_symlink():raise ValueError('invalid job folder')
        rb=(folder/'receipt.json').read_bytes();rec=json.loads(rb)
        if rb!=ab.canonical(rec) or rec.get('schema')!=ab.SCHEMA or rec.get('job_id')!=jid or rec.get('plan_sha256')!=ph or rec.get('production_execution_allowed') is not False or rec.get('engineering_only') is not True:
            errors.append('receipt identity/schema/gate mismatch')
        n=plan['n'];budget=plan['budget']
        if rec.get('n')!=n or rec.get('budget')!=budget or rec.get('epochs')!=plan['epochs'] or not np.isfinite(rec.get('rmse',np.nan)):
            errors.append('receipt numerical parameters mismatch')
        arrays={}
        if set(rec.get('artifact_sha256',{}))!=set(ab.FILES):errors.append('artifact manifest differs')
        for name in ab.FILES:
            p=folder/name
            if p.is_symlink() or ab.file_sha(p)!=rec.get('artifact_sha256',{}).get(name):errors.append('artifact hash mismatch '+name)
            arrays[name]=np.load(p,allow_pickle=False)
        order=arrays['order.npy'];noisy=arrays['noisy_catalogue.npy'];clean=arrays['clean_catalogue.npy']
        selected=arrays['measurements.npy'];recon=arrays['reconstruction.npy']
        if order.shape!=(budget,) or len(set(order.tolist()))!=budget or np.any(order<0) or np.any(order>=12*n*n) or selected.shape!=(budget,) or clean.shape!=(12*n*n,) or noisy.shape!=(12*n*n,) or recon.shape!=(n**3,):
            errors.append('invalid array shapes or ray identities')
        if any(not np.isfinite(arr).all() for arr in arrays.values()) or np.any(recon<=0) or np.any(selected<0):errors.append('invalid array numerical values')
        if not np.array_equal(selected,noisy[order]):errors.append('selected measurement catalogue mismatch')
        if not errors:
            A=system_matrix(n,4,TILTS).tocsr()
            expected_orders,_=fair_orders(A,n=n,angles=4,seed=plan['acquisition_seed'],budget=budget,
                warm=plan['warm'],pool=16,batch=8 if n==8 else 32)
            if not np.array_equal(order,expected_orders[policy]):errors.append('policy ray-order mismatch')
            truth,fine=full_resolution_pair(plan['family'],plan['engineering_seed'],n)
            cc,nn=model_measurements(A,truth,fine,n=n,angles=4,model=model,
                     noise_seed=plan['noise_seed'],noise_fraction=plan['noise_fraction'])
            if not np.allclose(clean,cc,rtol=0,atol=1e-11) or not np.array_equal(noisy,nn):errors.append('independent full-catalogue mismatch')
            csr=csr_matrix((arrays['csr_data.npy'],arrays['csr_indices.npy'],arrays['csr_indptr.npy']),shape=(budget,n**3))
            if (csr!=A[order]).nnz:errors.append('sparse selected geometry mismatch')
            hashtruth=ab.digest(np.asarray(truth,dtype='<f8').tobytes())
            if rec['truth_sha256']!=hashtruth:errors.append('truth hash mismatch')
            rmse=float(np.sqrt(np.mean((recon-truth)**2)))
            if not np.isclose(rec['rmse'],rmse,atol=1e-12,rtol=0):errors.append('RMSE mismatch')
            if not errors:
                replay=independent_mart(csr,selected,epochs=plan['epochs'],relaxation=.25)
                error=float(np.max(np.abs(replay-recon)))
                if not np.isfinite(error) or error>1e-11:errors.append('independent MART mismatch')
    except Exception as ex:errors.append(type(ex).__name__+': '+str(ex))
    return {'job_id':policy+'__'+model,'pass':not errors,'errors':errors,'max_abs_replay_error':error}

def audit(root,aa_dir,m_dir,require_complete=False):
    details=[];errors=[]
    try:
        plan,_=ab.check(root,aa_dir,m_dir)
        jobs=Path(root)/'jobs'
        for item in sorted(jobs.iterdir()):
            if item.name.startswith('.staging__'):
                errors.append('unfinished staging: '+item.name);continue
            bits=item.name.rsplit('__',1)
            if len(bits)!=2 or bits[0] not in ab.POLICIES or bits[1] not in ab.MODELS:
                errors.append('unrecognized job '+item.name);continue
            details.append(audit_one(root,aa_dir,m_dir,*bits))
        if require_complete and len(details)!=10:errors.append('ten jobs required')
        if not details:errors.append('no completed engineering jobs')
        # Cross-policy shared measurement values and common acquisition prefix.
        for model in ab.MODELS:
            matching=[x for x in details if x['job_id'].endswith('__'+model)]
            if len(matching)>=2 and all(x['pass'] for x in matching):
                base=Path(root)/'jobs'/matching[0]['job_id']
                first=np.load(base/'noisy_catalogue.npy',allow_pickle=False)
                for item in matching[1:]:
                    folder=Path(root)/'jobs'/item['job_id']
                    if not np.array_equal(first,np.load(folder/'noisy_catalogue.npy',allow_pickle=False)):
                        errors.append('shared noisy catalogue mismatch '+model)
                indiv=[x for x in matching if x['job_id'].split('__')[0]!='complete_view']
                if len(indiv)>1:
                    prefix=None
                    for item in indiv:
                        order=np.load(Path(root)/'jobs'/item['job_id']/'order.npy',allow_pickle=False)[:plan['warm']]
                        if prefix is None:prefix=order
                        elif not np.array_equal(prefix,order):errors.append('warm prefix mismatch '+model)
    except Exception as ex:errors.append(type(ex).__name__+': '+str(ex))
    errors.extend(e['job_id']+': '+str(e['errors']) for e in details if not e['pass'])
    passed=not errors
    return {'verdict':'AB_INDEPENDENT_SHADOW_AUDIT_PASS' if passed else 'AB_SHADOW_AUDIT_FAIL',
            'pass':passed,'errors':errors,'audited_engineering_jobs':len(details),
            'details':details,'production_jobs_executed':0,'production_execution_allowed':False,
            'no_confirmatory_outcomes':True}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir',required=True,type=Path)
    ap.add_argument('--aa-dir',required=True,type=Path)
    ap.add_argument('--m-dir',required=True,type=Path)
    ap.add_argument('--require-complete',action='store_true')
    x=ap.parse_args();report=audit(x.output_dir,x.aa_dir,x.m_dir,x.require_complete)
    print(json.dumps(report,indent=2))
    if not report['pass']:raise SystemExit(2)
if __name__=='__main__':main()
