"""Independent 08AJ-AD recovery verifier; reconstruction replays from row zero."""
import argparse, json
from pathlib import Path
import numpy as np
from experiment_08aj_ad import (SCHEMA,check_inputs,verify_chain,source_arrays,sha,load_receipt)

def independent_row_update(x, matrix, measured, row, relaxation):
    """Independent sequential-row MART implementation, not importing AD step_row."""
    left=int(matrix.indptr[row]);right=int(matrix.indptr[row+1])
    if right<=left:return
    ids=matrix.indices[left:right]
    weights=matrix.data[left:right]
    largest=float(weights.max())
    if largest<=0:return
    prediction=float(np.dot(weights, x[ids]))
    residual=np.log(max(max(float(measured[row]),1e-10)/max(prediction,1e-10),1e-10))
    factor=np.exp(np.maximum(-12,np.minimum(12,relaxation*weights/largest*residual)))
    x[ids]=np.maximum(x[ids]*factor,1e-10)

def audit(out,ab_dir,aa_dir,m_dir):
    errors=[];delta=None;rmse_delta=None
    try:
        root=Path(out);p,folder=check_inputs(out,ab_dir,aa_dir,m_dir)
        total=p['budget']*p['epochs'];done,state,last=verify_chain(root,p)
        if done!=total:errors.append('reconstruction not finished')
        f=root/'final.json';arr=root/'final_reconstruction.npy'
        if f.is_symlink() or arr.is_symlink():raise ValueError('final symlink')
        rec=load_receipt(f)
        if (rec.get('schema')!=SCHEMA or rec.get('plan_sha256')!=sha(root/'plan.json') or
          rec.get('rows_done')!=total or rec.get('last_checkpoint_receipt_sha256')!=last or
          rec.get('final_reconstruction_sha256')!=sha(arr) or
          rec.get('production_execution_allowed') is not False or rec.get('no_confirmatory_outcomes') is not True):
            errors.append('final receipt mismatch')
        result=np.load(arr,allow_pickle=False)
        if result.shape!=(p['n']**3,) or not np.isfinite(result).all() or np.any(result<=0):errors.append('final array invalid')
        A,y,reference=source_arrays(folder,p['budget'],p['n'])
        if not errors:
            independent=np.full(p['n']**3,.3,dtype=np.float64)
            for cursor in range(total):independent_row_update(independent,A,y,cursor%p['budget'],p['relaxation'])
            delta=float(np.max(np.abs(independent-result)))
            ref_delta=float(np.max(np.abs(reference-result)))
            if delta>1e-11 or ref_delta>1e-11 or not np.array_equal(result,state):errors.append('independent replay/reference/last-state mismatch')
            if not np.isclose(rec.get('max_abs_error_vs_ab',np.nan),ref_delta,atol=1e-12,rtol=0):errors.append('reported replay error mismatch')
            from experiment_08aj_e import full_resolution_pair
            truth,_=full_resolution_pair('smooth_heterogeneity',970099,p['n'])
            r1=float(np.sqrt(np.mean((result-truth)**2)))
            r2=float(np.sqrt(np.mean((reference-truth)**2)))
            rmse_delta=abs(r1-r2)
            if rmse_delta>1e-12:errors.append('RMSE reference mismatch')
    except Exception as exc:errors.append(type(exc).__name__+': '+str(exc))
    passed=not errors
    return {'verdict':'AD_INDEPENDENT_ROW_RECOVERY_AUDIT_PASS' if passed else 'AD_RECOVERY_AUDIT_FAIL',
      'pass':passed,'errors':errors,'rows_audited':done if 'done' in locals() else 0,
      'max_abs_replay_error':delta,'abs_rmse_difference':rmse_delta,
      'production_480_job_certified':False,'production_execution_allowed':False,
      'no_confirmatory_outcomes':True}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('output-dir','ab-dir','aa-dir','m-dir'):ap.add_argument('--'+name,type=Path,required=True)
    x=ap.parse_args();res=audit(x.output_dir,x.ab_dir,x.aa_dir,x.m_dir)
    print(json.dumps(res,indent=2))
    if not res['pass']:raise SystemExit(2)
if __name__=='__main__':main()
