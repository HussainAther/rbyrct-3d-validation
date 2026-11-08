"""Independent structural and numerical-summary audit of 08AJ-W hypothetical evidence."""
import argparse, hashlib, json, math
from pathlib import Path
from collections import Counter

NAMES={'stratified_percentile','stratified_basic','stratified_bootstrap_t','stratified_welch_t'}

def audit(root):
    root=Path(root)
    errors=[]
    try:
        raw=(root/'statistical_method_review.json').read_bytes()
        doc=json.loads(raw)
        status=json.loads((root/'run_status.json').read_bytes())
    except (OSError,ValueError) as exc:
        return {'verdict':'W_INDEPENDENT_AUDIT_FAIL','pass':False,'errors':[str(exc)]}
    try:
        if hashlib.sha256(raw).hexdigest()!=status['review_sha256']:errors.append('review hash mismatch')
        if doc['schema']!='RBYRCT-08AJ-W-prespecified-hypothetical-calibration-v1':errors.append('schema mismatch')
        for k in ('method_approved','frozen','confirmatory_execution_allowed'):
            if doc[k] or status[k]:errors.append('unauthorized gate '+k)
        if not doc['no_confirmatory_outcomes'] or not status['no_confirmatory_outcomes']:errors.append('confirmatory evidence prohibition violated')
        if doc['decision']['status']!='CONDITIONAL_RECOMMENDATION_NOT_APPROVED':errors.append('approval status changed')
        rows=doc['rows']; expected=doc['simulations']['settings']; trials=doc['simulations']['trials_per_setting']
        if len(rows)!=expected:errors.append('row count mismatch')
        dimensions=Counter()
        for row in rows:
            key=(row['scenario'],row['latent_family_shock_rho'],row['hypothetical_sd'],row['true_mean'],row['method'])
            dimensions[key]+=1
            if row['method'] not in NAMES:errors.append('invalid method')
            for field in ('coverage','prob_lower_above_zero','prob_lower_above_2pct'):
                val=row[field]
                if not (math.isfinite(val) and 0<=val<=1):errors.append('invalid probability')
                if abs(val*trials-round(val*trials))>1e-7:errors.append('probability not trial count')
            p=row['coverage']
            if abs(row['coverage_mcse']-math.sqrt(p*(1-p)/trials))>1e-10:errors.append('mcse mismatch')
            if not math.isfinite(row['median_width']) or row['median_width']<=0:errors.append('invalid interval width')
        if len(dimensions)!=expected or any(n!=1 for n in dimensions.values()):errors.append('duplicate or missing settings')
        for method in NAMES:
            relevant=[r['coverage'] for r in rows if r['method']==method and r['latent_family_shock_rho']==0.0]
            summary=doc['decision']['method_summary_rho_zero'][method]
            if abs(summary['mean_coverage']-sum(relevant)/len(relevant))>1e-10:errors.append('summary mismatch')
        if status['settings']!=len(rows):errors.append('status setting mismatch')
    except (KeyError,TypeError,ZeroDivisionError) as exc:errors.append('malformed evidence: '+str(exc))
    return {'verdict':'W_INDEPENDENT_AUDIT_PASS' if not errors else 'W_INDEPENDENT_AUDIT_FAIL',
     'pass':not errors,'errors':errors,'settings_audited':len(doc.get('rows',[])),
     'method_approved':False,'no_confirmatory_outcomes':True}

def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();print(json.dumps(audit(a.output_dir),indent=2))
if __name__=='__main__':main()
