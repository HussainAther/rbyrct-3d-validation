"""Independent 08AJ-N 8/16-epoch MART replay and engineering artifact audit.

This auditor does not import the 08AJ-N runner or the production MART wrapper.
It independently replays sequential MART using saved sparse rows and measurements.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix
from experiment_08aj_k_audit import independent_mart

SCHEMA='RBYRCT-08AJ-N-engineering-16epoch-v1'
EXPECTED=('order.npy','measurements.npy','csr_data.npy','csr_indices.npy',
          'csr_indptr.npy','clean_catalogue.npy','noisy_catalogue.npy',
          'reconstruction_epoch08.npy','reconstruction_epoch16.npy')
MODELS=('same','independent')
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(obj):return (json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('utf-8')
def audit_one(root,model):
    errors=[];deltas={}
    try:
        root=Path(root)
        if model not in MODELS:raise ValueError('invalid model')
        blob=(root/'engineering_plan.json').read_bytes();plan=json.loads(blob)
        if blob!=canonical(plan) or plan.get('schema')!=SCHEMA or plan.get('frozen') is not False or plan.get('execution_allowed') is not False or plan.get('no_confirmatory_outcomes') is not True or plan.get('mart_epochs')!=16 or plan.get('checkpoint_epochs')!=[8,16] or plan.get('n')!=32 or plan.get('budget')!=2048 or plan.get('engineering_seed')!=970099 or plan.get('family')!='smooth_heterogeneity' or plan.get('policy')!='information_diag':
            errors.append('invalid engineering plan')
        source=plan.get('source_sha256',{})
        if len(source)<15:errors.append('incomplete source roster')
        for name,expected in source.items():
            f=Path(__file__).resolve().parent/name
            if not f.is_file() or f.is_symlink() or sha(f.read_bytes())!=expected:
                errors.append('source integrity failure '+name)
        folder=root/'jobs'/model
        if folder.is_symlink():errors.append('symlink job folder')
        receipt_blob=(folder/'receipt.json').read_bytes();receipt=json.loads(receipt_blob)
        if receipt_blob!=canonical(receipt) or receipt.get('schema')!=SCHEMA or receipt.get('model')!=model or receipt.get('plan_sha256')!=sha(blob) or receipt.get('engineering_only') is not True or receipt.get('no_confirmatory_outcomes') is not True or receipt.get('frozen') is not False or receipt.get('matrix_shape')!=[2048,32768] or receipt.get('epochs')!=[8,16]:
            errors.append('invalid receipt context')
        if set(receipt.get('artifact_sha256',{}))!=set(EXPECTED):errors.append('artifact roster mismatch')
        if {p.name for p in folder.iterdir()}!=set(EXPECTED)|{'receipt.json'}:errors.append('missing or unexpected artifact')
        arrays={}
        for name in EXPECTED:
            p=folder/name
            if p.is_symlink():errors.append('symlink artifact '+name)
            if sha(p.read_bytes())!=receipt.get('artifact_sha256',{}).get(name):errors.append('hash mismatch '+name)
            arrays[name]=np.load(p,allow_pickle=False)
        order=arrays['order.npy'];clean=arrays['clean_catalogue.npy'];noisy=arrays['noisy_catalogue.npy'];measured=arrays['measurements.npy']
        rec8=arrays['reconstruction_epoch08.npy'];rec16=arrays['reconstruction_epoch16.npy']
        if order.shape!=(2048,) or len(np.unique(order))!=2048 or np.any(order<0) or np.any(order>=12288) or clean.shape!=(12288,) or noisy.shape!=(12288,) or measured.shape!=(2048,) or rec8.shape!=(32768,) or rec16.shape!=(32768,) or not np.array_equal(measured,noisy[order]):errors.append('invalid measurement geometry')
        if any(not np.isfinite(v).all() for v in arrays.values()) or np.any(noisy<0) or np.any(rec8<=0) or np.any(rec16<=0):errors.append('invalid numerical values')
        matrix=csr_matrix((arrays['csr_data.npy'],arrays['csr_indices.npy'],arrays['csr_indptr.npy']),shape=(2048,32768))
        if not errors:
            for epochs,reconstruction in ((8,rec8),(16,rec16)):
                replay=independent_mart(matrix,measured,epochs=epochs,relaxation=.25)
                delta=float(np.max(np.abs(replay-reconstruction)))
                deltas[str(epochs)]=delta
                if not np.isfinite(delta) or delta>1e-11:errors.append('replay mismatch epoch '+str(epochs))
    except Exception as exc:errors.append(type(exc).__name__+': '+str(exc))
    return {'model':model,'pass':not errors,'errors':errors,'max_abs_replay_errors':deltas}
def audit(root):
    root=Path(root)
    records=[audit_one(root,m) for m in MODELS]
    jobs=root/'jobs'
    if jobs.exists():
        extra={p.name for p in jobs.iterdir()}-set(MODELS)
        if extra:records.append({'model':'unexpected','pass':False,'errors':['unexpected folders '+str(sorted(extra))]})
    passed=all(x['pass'] for x in records)
    return {'verdict':'N_INDEPENDENT_16_EPOCH_REPLAY_PASS' if passed else 'N_INDEPENDENT_16_EPOCH_REPLAY_FAIL',
            'pass':passed,'details':records,'frozen':False,'no_confirmatory_outcomes':True,
            'production_480_job_certified':False}
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir',type=Path,required=True)
    args=ap.parse_args();result=audit(args.output_dir)
    print(json.dumps(result,indent=2))
    if not result['pass']:raise SystemExit(2)
if __name__=='__main__':main()
