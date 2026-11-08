"""Independent 08AJ-AH atomic-checkpoint engineering numerical audit."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
from experiment_08aj_k_audit import independent_mart
import experiment_08aj_ah as ah
import experiment_08aj_ag as ag
import experiment_08aj_af as af

def audit(root,af_dir,aa_dir,m_dir):
    errors=[];n=0;replay=None;rmse=None;quarantined=0
    try:
        root=Path(root)
        p,d,n,x,last=ah.verify(root,af_dir,aa_dir,m_dir)
        src=p['source'];total=src['epochs']*src['budget']
        if n!=total:raise ValueError('reconstruction not finished')
        names={f.name for f in root.iterdir()}
        if names not in ({'plan.json','checkpoints','final'},
                         {'plan.json','checkpoints','final','quarantine'}):
            raise ValueError('unexpected/missing AH top-level artifacts')
        if 'quarantine' in names:
            q=root/'quarantine'
            if q.is_symlink() or not q.is_dir():raise ValueError('unsafe quarantine')
            log=ah.receipt(q/'quarantine_manifest.json')
            staged=sorted(f.name for f in q.iterdir() if f.name!='quarantine_manifest.json')
            if log!={'schema':ah.SCHEMA,'stages':staged,'no_confirmatory_outcomes':True}:
                raise ValueError('quarantine manifest mismatch')
            if any(not name.startswith('.stage-') or (q/name).is_symlink() for name in staged):
                raise ValueError('unsafe quarantined item')
            quarantined=len(staged)
        final=root/'final'
        if final.is_symlink() or {f.name for f in final.iterdir()}!={'reconstruction.npy','receipt.json'}:
            raise ValueError('invalid atomic final artifact')
        r=ah.receipt(final/'receipt.json')
        expected={'schema':ah.SCHEMA,'plan_sha256':ah.sha(root/'plan.json'),
                  'rows_done':n,'last_checkpoint_receipt_sha256':last,
                  'final_reconstruction_sha256':ah.sha(final/'reconstruction.npy'),
                  'max_abs_error_vs_af':r.get('max_abs_error_vs_af'),
                  'production_execution_allowed':False,'no_confirmatory_outcomes':True}
        if r!=expected:raise ValueError('final receipt mismatch')
        saved=np.load(final/'reconstruction.npy',allow_pickle=False)
        if saved.shape!=(src['n']**3,) or saved.dtype!=np.float64 or not np.array_equal(saved,x):
            raise ValueError('final differs from last atomic checkpoint')
        A,y,reference=ag.inputs(d,src)
        independently=np.asarray(independent_mart(A,y,epochs=src['epochs'],relaxation=src['relaxation']),dtype=np.float64)
        replay=float(np.max(np.abs(saved-independently)))
        diff=float(np.max(np.abs(saved-reference)))
        if replay>1e-11 or diff>1e-11 or abs(r['max_abs_error_vs_af']-diff)>1e-12:
            raise ValueError('independent MART replay/source mismatch')
        _,_,_,truth=ag.evidence(None,af_dir,aa_dir,m_dir,src['policy'],src['model'])
        computed=float(np.sqrt(np.mean((saved-truth)**2)))
        source_receipt=af.load_json(d/'receipt.json')
        rmse=abs(computed-float(source_receipt['rmse']))
        if rmse>1e-12:raise ValueError('independent RMSE mismatch')
    except Exception as exc:
        errors.append(type(exc).__name__+': '+str(exc))
    return {'verdict':'AH_INDEPENDENT_ATOMIC_RECOVERY_AUDIT_PASS' if not errors else 'AH_ATOMIC_RECOVERY_AUDIT_FAIL',
            'pass':not errors,'errors':errors,'rows_audited':n,
            'max_abs_replay_error':replay,'abs_rmse_difference':rmse,
            'quarantined_incomplete_stages':quarantined,
            'production_480_job_certified':False,'resource_policy_approved':False,
            'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for v in ('output-dir','af-dir','aa-dir','m-dir'):ap.add_argument('--'+v,required=True,type=Path)
    a=ap.parse_args()
    r=audit(a.output_dir,a.af_dir,a.aa_dir,a.m_dir)
    print(json.dumps(r,indent=2))
    if not r['pass']:raise SystemExit(2)
if __name__=='__main__':main()
