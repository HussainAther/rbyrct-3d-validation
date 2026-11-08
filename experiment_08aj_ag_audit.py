"""Independent complete-chain and MART replay audit for 08AJ-AG engineering recovery."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
from experiment_08aj_k_audit import independent_mart
import experiment_08aj_ad as ad
import experiment_08aj_ag as ag
import experiment_08aj_af as af

def audit(root,af_dir,aa_dir,m_dir):
    errors=[];replay_delta=None;rmse_delta=None;rows=0
    try:
        root=Path(root)
        p,d,rows,x,previous=ag.verify(root,af_dir,aa_dir,m_dir)
        total=p['budget']*p['epochs']
        if rows!=total:raise ValueError('reconstruction not finished')
        if {f.name for f in root.iterdir()}!={'plan.json','checkpoints','final.json','final_reconstruction.npy'}:
            raise ValueError('unexpected/missing AG artifacts')
        record=ad.load_receipt(root/'final.json')
        expected={'schema':ag.SCHEMA,'plan_sha256':ad.sha(root/'plan.json'),
           'final_reconstruction_sha256':ad.sha(root/'final_reconstruction.npy'),
           'last_checkpoint_receipt_sha256':previous,'rows_done':rows,
           'max_abs_error_vs_af':record.get('max_abs_error_vs_af'),
           'production_execution_allowed':False,'no_confirmatory_outcomes':True}
        if record!=expected:raise ValueError('final hash/receipt mismatch')
        saved=np.load(root/'final_reconstruction.npy',allow_pickle=False)
        if saved.dtype!=np.float64 or saved.shape!=(p['n']**3,) or not np.array_equal(saved,x):
            raise ValueError('final and latest checkpoint disagree')
        A,y,af_reference=ag.inputs(d,p)
        independent=np.asarray(independent_mart(A,y,epochs=p['epochs'],relaxation=p['relaxation']),dtype=np.float64)
        replay_delta=float(np.max(np.abs(saved-independent)))
        ref_delta=float(np.max(np.abs(saved-af_reference)))
        if replay_delta>1e-11 or ref_delta>1e-11 or abs(record['max_abs_error_vs_af']-ref_delta)>1e-12:
            raise ValueError('independent replay/AF reference mismatch')
        pp,_,_,truth=ag.evidence(None,af_dir,aa_dir,m_dir,p['policy'],p['model'])
        computed=float(np.sqrt(np.mean((saved-truth)**2)))
        af_receipt=af.load_json(d/'receipt.json')
        rmse_delta=abs(computed-float(af_receipt['rmse']))
        if rmse_delta>1e-12:raise ValueError('fresh AF independent RMSE mismatch')
    except Exception as e:errors.append(type(e).__name__+': '+str(e))
    return {'verdict':'AG_INDEPENDENT_FRESH_ROW_RECOVERY_AUDIT_PASS' if not errors else 'AG_RECOVERY_AUDIT_FAIL',
            'pass':not errors,'errors':errors,'rows_audited':rows,
            'max_abs_replay_error':replay_delta,'abs_rmse_difference':rmse_delta,
            'production_480_job_certified':False,'production_execution_allowed':False,
            'no_confirmatory_outcomes':True}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('output-dir','af-dir','aa-dir','m-dir'):ap.add_argument('--'+name,required=True,type=Path)
    a=ap.parse_args()
    r=audit(a.output_dir,a.af_dir,a.aa_dir,a.m_dir)
    print(json.dumps(r,indent=2))
    if not r['pass']:raise SystemExit(2)
if __name__=='__main__':main()
