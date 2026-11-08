"""08AJ-K independent engineering-artifact auditor and independently coded MART replay.

Does not import the 08AJ-K runner, checked_mart, or mart_reconstruct.
Replay checks the actual MART per-ray update against saved numerical inputs;
provenance checks confirm source and artifact hashes. Engineering only.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix

SOURCE_FILES=('experiment_04b.py','experiment_04g.py','experiment_04h.py',
              'experiment_04qa.py','experiment_05b_08b.py','experiment_05b_mart.py',
              'experiment_08aj_b.py','experiment_08aj_c_view.py',
              'experiment_08aj_d.py','experiment_08aj_e.py','experiment_08aj_g.py',
              'experiment_08aj_k.py','experiment_08aj_k_audit.py')
SCHEMA='RBYRCT-08AJ-K-engineering-v1'
EXPECTED=('order.npy','measurements.npy','csr_data.npy','csr_indices.npy',
          'csr_indptr.npy','reconstruction.npy','clean_catalogue.npy','noisy_catalogue.npy')


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def independent_mart(A,measured,epochs=2,relaxation=.25):
    """Separate implementation of the fixed MART recurrence, sequential rows."""
    x=np.full(A.shape[1],.3,dtype=np.float64)
    for _ in range(epochs):
        for row in range(A.shape[0]):
            s,e=int(A.indptr[row]),int(A.indptr[row+1])
            if s==e: continue
            cols=A.indices[s:e]; w=A.data[s:e]
            wmax=float(np.max(w))
            if wmax<=0: continue
            predicted=float(np.dot(w,x[cols]))
            ratio=max(float(measured[row]),1e-10)/max(predicted,1e-10)
            delta=np.clip((relaxation*w/wmax)*np.log(max(ratio,1e-10)),-12,12)
            x[cols]=np.maximum(x[cols]*np.exp(delta),1e-10)
    return x


def audit_one(root,model,replay=True):
    root=Path(root); errors=[]
    try:
        if model not in ('same','independent'): raise ValueError('invalid model')
        plan_blob=(root/'engineering_plan.json').read_bytes()
        plan=json.loads(plan_blob)
        if plan.get('schema')!=SCHEMA or plan.get('frozen') is not False or plan.get('execution_allowed') is not False or plan.get('object_seed')!=970099 or plan.get('n')!=8 or plan.get('budget')!=128:
            errors.append('engineering plan settings invalid')
        canonical=(json.dumps(plan,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('ascii')
        if plan_blob!=canonical: errors.append('noncanonical plan')
        sources=plan.get('source_sha256',{})
        if set(sources)!=set(SOURCE_FILES): errors.append('source file list mismatch')
        for name in SOURCE_FILES:
            path=Path(__file__).resolve().parent/name
            if not path.is_file() or sources.get(name)!=digest(path.read_bytes()):
                errors.append('source digest mismatch: '+name)
        folder=root/'jobs'/model
        if folder.is_symlink(): errors.append('symlink checkpoint')
        receipt_blob=(folder/'receipt.json').read_bytes()
        receipt=json.loads(receipt_blob)
        if receipt_blob!=(json.dumps(receipt,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('ascii'):
            errors.append('noncanonical receipt')
        if (receipt.get('schema')!=SCHEMA or receipt.get('model')!=model or
            receipt.get('plan_sha256')!=digest(plan_blob) or receipt.get('engineering_only') is not True or
            receipt.get('no_confirmatory_outcomes') is not True or receipt.get('matrix_shape')!=[128,512]):
            errors.append('receipt context mismatch')
        if set(receipt.get('array_sha256',{}))!=set(EXPECTED):
            errors.append('unexpected artifact roster')
        actual={f.name for f in folder.iterdir()}
        if actual!=set(EXPECTED)|{'receipt.json'}: errors.append('unexpected/missing artifacts')
        arrays={}
        for name in EXPECTED:
            f=folder/name
            if f.is_symlink(): errors.append('symlink array: '+name)
            blob=f.read_bytes()
            if digest(blob)!=receipt.get('array_sha256',{}).get(name):
                errors.append('artifact hash mismatch: '+name)
            arrays[name]=np.load(f,allow_pickle=False)
        order=arrays['order.npy']; meas=arrays['measurements.npy']; rec=arrays['reconstruction.npy']
        clean=arrays['clean_catalogue.npy']; noisy=arrays['noisy_catalogue.npy']
        if (order.shape!=(128,) or len(np.unique(order))!=128 or np.any(order<0) or np.any(order>=768)
            or clean.shape!=(768,) or noisy.shape!=(768,) or meas.shape!=(128,) or rec.shape!=(512,)):
            errors.append('numeric shape/order invalid')
        elif not np.array_equal(meas,noisy[order]):
            errors.append('paired acquisition measurements differ from catalogue')
        if not all(np.isfinite(a).all() for a in arrays.values()) or np.any(meas<0) or np.any(rec<=0):
            errors.append('nonfinite/nonpositive numeric data')
        mat=csr_matrix((arrays['csr_data.npy'],arrays['csr_indices.npy'],arrays['csr_indptr.npy']),shape=(128,512))
        if replay and not errors:
            again=independent_mart(mat,meas)
            delta=float(np.max(np.abs(again-rec)))
            if delta>1e-11 or not np.isfinite(delta):
                errors.append('independent numerical replay discrepancy')
        else:
            delta=None
    except Exception as exc:
        errors.append(type(exc).__name__+': '+str(exc))
        delta=None
    return {'model':model,'pass':not errors,'errors':errors,'max_abs_replay_error':delta}


def audit_all(root):
    root=Path(root)
    records=[audit_one(root,m) for m in ('same','independent')]
    extra={p.name for p in (root/'jobs').iterdir()}-{'same','independent'} if (root/'jobs').exists() else set()
    if extra:
        records.append({'model':'unexpected','pass':False,'errors':['unexpected job directories: '+repr(sorted(extra))]})
    good=all(r['pass'] for r in records)
    return {'verdict':'INDEPENDENT_NUMERICAL_AUDIT_PASS' if good else 'INDEPENDENT_NUMERICAL_AUDIT_FAIL',
            'pass':good,'replayed_models':sum(r['pass'] for r in records),
            'details':records,'no_confirmatory_outcomes':True,'production_validation_certified':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args();result=audit_all(a.output_dir)
    print(json.dumps(result,indent=2))
    if not result['pass']: raise SystemExit(2)

if __name__=='__main__':
    main()
