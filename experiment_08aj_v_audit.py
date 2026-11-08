"""Independent structural and hash audit of outcome-free 08AJ-V calibration evidence."""
import argparse
import hashlib
import json
from pathlib import Path

METHODS = {'stratified_percentile','stratified_basic','stratified_bootstrap_t','stratified_welch_t'}
SCENARIOS = {'normal_equal','skewed_centered','heavy_tail_t3','heteroscedastic_family'}


def audit(root):
    root = Path(root)
    errors = []
    raw = (root / 'statistical_calibration_evidence.json').read_bytes()
    status = json.loads((root / 'run_status.json').read_text())
    data = json.loads(raw)
    if hashlib.sha256(raw).hexdigest() != status.get('calibration_sha256'):
        errors.append('evidence SHA mismatch')
    if data.get('schema') != 'RBYRCT-08AJ-V-hypothetical-inference-calibration-v1':
        errors.append('unexpected schema')
    for source in (data,status):
        if source.get('frozen') is not False or source.get('confirmatory_execution_allowed') is not False:
            errors.append('unauthorized protocol status')
        if source.get('no_confirmatory_outcomes') is not True:
            errors.append('confirmatory outcome flag invalid')
    if status.get('method_approved') is not False or data.get('scientific_signoff') is not False:
        errors.append('unauthorized method approval')
    rows = data.get('rows',[])
    expected = {(s,mu,sd,m) for s in SCENARIOS for mu in (0.,.01,.02)
                for sd in (.01,.03,.06) for m in METHODS}
    found=set()
    for row in rows:
        key=(row['scenario'],row['true_mean'],row['object_sd'],row['method'])
        if key in found:errors.append('duplicate setting')
        found.add(key)
        for name in ('simulated_coverage','prob_ci_lower_above_zero','prob_ci_lower_above_2pct'):
            value=row[name]
            if not isinstance(value,(float,int)) or not 0<=value<=1:
                errors.append('invalid probability')
        if row['median_ci_width']<=0:errors.append('invalid width')
    if found!=expected or len(rows)!=len(expected):errors.append('missing or unexpected settings')
    if status.get('settings')!=len(expected):errors.append('status setting mismatch')
    if data.get('n_objects')!=24 or data.get('objects_per_family')!=8:
        errors.append('wrong hypothetical sampling design')
    return {'verdict':'V_INDEPENDENT_CALIBRATION_AUDIT_PASS' if not errors else 'V_CALIBRATION_AUDIT_FAIL',
            'pass':not errors,'errors':errors,'settings_audited':len(rows),
            'no_confirmatory_outcomes':True,'method_approved':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args()
    result=audit(a.output_dir)
    print(json.dumps(result,indent=2))
    if not result['pass']:raise SystemExit(1)

if __name__=='__main__':main()
