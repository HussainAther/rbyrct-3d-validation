"""08AJ-Q independent engineering replay and artifact integrity auditor.

Does not import 08AJ-Q production runner or its MART wrapper. Recomputes
selection geometry, clean/noisy catalogue, and MART from saved sparse rows.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_08aj_e import full_resolution_pair,model_measurements
from experiment_08aj_g import fair_orders
from experiment_08aj_k_audit import independent_mart

SCHEMA='RBYRCT-08AJ-Q-engineering-per-job-v1'
POLICIES=('information_diag','uniform_multiscale','coverage','stratified_random_04h','complete_view')
MODELS=('same','independent')
ARTIFACTS=('order.npy','measurements.npy','clean_catalogue.npy','noisy_catalogue.npy','csr_data.npy','csr_indices.npy','csr_indptr.npy','reconstruction.npy')
def sha(blob):return hashlib.sha256(blob).hexdigest()
def canonical(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('ascii')
def audit_one(root,policy,model):
    errors=[];delta=None
    try:
        root=Path(root)
        if policy not in POLICIES or model not in MODELS:raise ValueError('unauthorized engineering job')
        blob=(root/'engineering_plan.json').read_bytes();p=json.loads(blob)
        if blob!=canonical(p) or p.get('schema')!=SCHEMA or p.get('frozen') is not False or p.get('execution_allowed') is not False or p.get('confirmatory_execution_allowed') is not False or p.get('no_confirmatory_outcomes') is not True or p.get('engineering_seed')!=970099 or p.get('family')!='smooth_heterogeneity' or p.get('acquisition_seed')!=940411 or p.get('noise_seed')!=970119 or p.get('n') not in (8,32) or p.get('budget')!=(128 if p['n']==8 else 2048) or p.get('mart_epochs')!=(2 if p['n']==8 else 16) or p.get('warm')!=(8 if p['n']==8 else 64) or p.get('relaxation')!=.25 or p.get('noise_fraction')!=.005 or p.get('models')!=list(MODELS) or p.get('policies')!=list(POLICIES):errors.append('invalid engineering plan')
        src=p.get('source_sha256',{})
        if len(src)!=16:errors.append('incomplete source roster')
        for name,h in src.items():
            file=Path(__file__).resolve().parent/name
            if not file.is_file() or file.is_symlink() or sha(file.read_bytes())!=h:errors.append('source mismatch '+name)
        job_id=f'{policy}__{model}';folder=root/'jobs'/job_id
        if folder.is_symlink():errors.append('symlink job')
        recblob=(folder/'receipt.json').read_bytes();rec=json.loads(recblob)
        if recblob!=canonical(rec) or rec.get('schema')!=SCHEMA or rec.get('job_id')!=job_id or rec.get('policy')!=policy or rec.get('model')!=model or rec.get('plan_sha256')!=sha(blob) or rec.get('n')!=p['n'] or rec.get('budget')!=p['budget'] or rec.get('epochs')!=p['mart_epochs'] or rec.get('engineering_only') is not True or rec.get('no_confirmatory_outcomes') is not True:errors.append('invalid job receipt')
        if set(rec.get('artifact_sha256',{}))!=set(ARTIFACTS) or {x.name for x in folder.iterdir()}!=set(ARTIFACTS)|{'receipt.json'}:errors.append('invalid artifact roster')
        arr={}
        for name in ARTIFACTS:
            f=folder/name
            if f.is_symlink():errors.append('symlink array '+name)
            if sha(f.read_bytes())!=rec.get('artifact_sha256',{}).get(name):errors.append('digest mismatch '+name)
            arr[name]=np.load(f,allow_pickle=False)
        n=p['n'];budget=p['budget'];rays=n*n*4*3
        order=arr['order.npy'];measured=arr['measurements.npy'];clean=arr['clean_catalogue.npy'];noisy=arr['noisy_catalogue.npy'];recon=arr['reconstruction.npy']
        if order.shape!=(budget,) or len(np.unique(order))!=budget or np.any(order<0) or np.any(order>=rays) or clean.shape!=(rays,) or noisy.shape!=(rays,) or measured.shape!=(budget,) or recon.shape!=(n**3,) or not np.array_equal(noisy[order],measured):errors.append('invalid measured arrays')
        if any(not np.isfinite(v).all() for v in arr.values()) or np.any(measured<0) or np.any(recon<=0):errors.append('invalid numeric values')
        if not errors:
            A=system_matrix(n,4,TILTS).tocsr()
            expected,_=fair_orders(A,n=n,angles=4,seed=940411,budget=budget,warm=p['warm'],pool=p['pool'],batch=p['batch'])
            if not np.array_equal(expected[policy],order):errors.append('acquisition policy order mismatch')
            truth,fine=full_resolution_pair('smooth_heterogeneity',970099,n)
            expected_clean,expected_noisy=model_measurements(A,truth,fine,n=n,angles=4,model=model,noise_seed=970119,noise_fraction=.005)
            if not np.allclose(clean,expected_clean,rtol=0,atol=1e-11) or not np.array_equal(noisy,expected_noisy):errors.append('forward/noise catalogue mismatch')
            mat=csr_matrix((arr['csr_data.npy'],arr['csr_indices.npy'],arr['csr_indptr.npy']),shape=(budget,n**3))
            if (mat!=A[order]).nnz:errors.append('selected sparse geometry mismatch')
            if not errors:
                replay=independent_mart(mat,measured,epochs=p['mart_epochs'],relaxation=.25)
                delta=float(np.max(np.abs(replay-recon)))
                if not np.isfinite(delta) or delta>1e-11:errors.append('independent MART replay mismatch')
    except Exception as ex:errors.append(type(ex).__name__+': '+str(ex))
    return {'job_id':f'{policy}__{model}','pass':not errors,'errors':errors,'max_abs_replay_error':delta}
def audit(root):
    root=Path(root);jobs=root/'jobs';results=[]
    if not jobs.exists():return {'verdict':'Q_INDEPENDENT_AUDIT_FAIL','pass':False,'errors':['jobs directory absent']}
    for f in sorted(jobs.iterdir()):
        if f.name.startswith('.staging__'):results.append({'job_id':f.name,'pass':False,'errors':['uncommitted staging exists']});continue
        parts=f.name.rsplit('__',1)
        if len(parts)!=2 or parts[0] not in POLICIES or parts[1] not in MODELS:results.append({'job_id':f.name,'pass':False,'errors':['unexpected job']});continue
        results.append(audit_one(root,parts[0],parts[1]))
    ok=bool(results) and all(x['pass'] for x in results)
    return {'verdict':'Q_INDEPENDENT_ENGINEERING_AUDIT_PASS' if ok else 'Q_INDEPENDENT_AUDIT_FAIL','pass':ok,'audited_jobs':len(results),'details':results,'no_confirmatory_outcomes':True,'production_480_job_certified':False}
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output-dir',required=True,type=Path)
    a=ap.parse_args();res=audit(a.output_dir);print(json.dumps(res,indent=2))
    if not res['pass']:raise SystemExit(2)
if __name__=='__main__':main()
