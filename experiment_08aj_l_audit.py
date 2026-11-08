"""Independent 08AJ-L engineering numerical auditor; no prospective outcome access.

Audits hashes, shapes, recorded noise samples and replays the fixed MART recurrence
with an implementation separate from the production MART wrapper.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix
from experiment_08aj_k_audit import independent_mart

SCHEMA='RBYRCT-08AJ-L-draft-v1'
EXPECTED=('order.npy','measurements.npy','csr_data.npy','csr_indices.npy',
          'csr_indptr.npy','reconstruction.npy','clean_catalogue.npy','noisy_catalogue.npy')

def digest(blob):return hashlib.sha256(blob).hexdigest()
def canonical(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('utf-8')

def audit_one(root,model):
    errors=[];delta=None
    try:
        root=Path(root)
        if model not in ('same','independent'):raise ValueError('invalid model')
        proto_blob=(root/'protocol_review_draft.json').read_bytes()
        proto=json.loads(proto_blob)
        if proto_blob!=canonical(proto) or proto.get('schema')!=SCHEMA or proto.get('frozen') is not False or proto.get('execution_allowed') is not False:
            errors.append('invalid protocol')
        # Audit source fingerprint without importing the L runner.
        sources=proto.get('source_sha256',{})
        for name,claimed in sources.items():
            path=Path(__file__).resolve().parent/name
            if not path.is_file() or digest(path.read_bytes())!=claimed:errors.append('source mismatch '+name)
        if len(sources)<20:errors.append('source roster incomplete')
        folder=root/'engineering_jobs'/model
        if folder.is_symlink(): errors.append('symlink job folder')
        receipt_blob=(folder/'receipt.json').read_bytes(); receipt=json.loads(receipt_blob)
        if receipt_blob!=canonical(receipt) or receipt.get('schema')!=SCHEMA or receipt.get('model')!=model or receipt.get('protocol_sha256')!=digest(proto_blob) or receipt.get('engineering_only') is not True or receipt.get('no_confirmatory_outcomes') is not True or receipt.get('matrix_shape')!=[2048,32768]:
            errors.append('receipt context invalid')
        if set(receipt.get('artifact_sha256',{}))!=set(EXPECTED):errors.append('artifact roster invalid')
        if {p.name for p in folder.iterdir()}!=set(EXPECTED)|{'receipt.json'}:errors.append('unexpected/missing artifact')
        a={}
        for name in EXPECTED:
            p=folder/name
            if p.is_symlink():errors.append('symlink array '+name)
            if digest(p.read_bytes())!=receipt.get('artifact_sha256',{}).get(name):errors.append('artifact hash mismatch '+name)
            a[name]=np.load(p,allow_pickle=False)
        order=a['order.npy']; clean=a['clean_catalogue.npy']; noisy=a['noisy_catalogue.npy']
        meas=a['measurements.npy']; rec=a['reconstruction.npy']
        if (order.shape!=(2048,) or len(np.unique(order))!=2048 or np.any(order<0) or np.any(order>=12288)
            or clean.shape!=(12288,) or noisy.shape!=(12288,) or meas.shape!=(2048,) or rec.shape!=(32768,)
            or not np.array_equal(meas,noisy[order])):errors.append('numeric geometry/order invalid')
        if any(not np.isfinite(v).all() for v in a.values()) or np.any(noisy<0) or np.any(rec<=0):errors.append('invalid numerical values')
        mat=csr_matrix((a['csr_data.npy'],a['csr_indices.npy'],a['csr_indptr.npy']),shape=(2048,32768))
        if not errors:
            again=independent_mart(mat,meas,epochs=2,relaxation=.25)
            delta=float(np.max(np.abs(again-rec)))
            if not np.isfinite(delta) or delta>1e-11:errors.append('independent MART replay discrepancy')
    except Exception as exc:errors.append(type(exc).__name__+': '+str(exc))
    return {'model':model,'pass':not errors,'errors':errors,'max_abs_replay_error':delta}

def audit(root):
    root=Path(root)
    records=[audit_one(root,m) for m in ('same','independent')]
    folder=root/'engineering_jobs'
    extra={p.name for p in folder.iterdir()}-{'same','independent'} if folder.exists() else set()
    if extra:records.append({'model':'unexpected','pass':False,'errors':['unexpected directories '+repr(sorted(extra))]})
    good=all(x['pass'] for x in records)
    return {'verdict':'L_INDEPENDENT_REPLAY_PASS' if good else 'L_INDEPENDENT_REPLAY_FAIL',
            'pass':good,'details':records,'frozen':False,
            'no_confirmatory_outcomes':True,'production_validation_certified':False}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir',required=True,type=Path)
    a=ap.parse_args();report=audit(a.output_dir);print(json.dumps(report,indent=2))
    if not report['pass']:raise SystemExit(2)

if __name__=='__main__':main()
