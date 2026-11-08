"""Independent standard-library 08AJ-J plan and engineering-receipt verifier.

Does not import the runner, and does NOT certify production numerical outputs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

EXPECTED=('ENGINEERING_DEMO_A','ENGINEERING_DEMO_B','ENGINEERING_DEMO_C')

def raw_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def audit_demo(root):
    root=Path(root)
    errors=[]
    try:
        plan=json.loads((root/'plan.json').read_text(encoding='ascii'))
        plan_sha=raw_hash(root/'plan.json')
        if plan.get('schema')!='RBYRCT-08AJ-J-planning-v1' or plan.get('execution_allowed') is not False or plan.get('frozen') is not False:
            errors.append('invalid plan permission/schema')
        if (root/'plan.json').read_bytes()!=(json.dumps(plan,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('ascii'):
            errors.append('noncanonical plan encoding')
        source_dir=Path(__file__).resolve().parent
        for filename, recorded in plan.get('source_sha256',{}).items():
            if Path(filename).name!=filename or not (source_dir/filename).is_file():
                errors.append('missing/invalid source: '+filename)
            elif raw_hash(source_dir/filename)!=recorded:
                errors.append('source digest mismatch: '+filename)
        status=json.loads((root/'run_status.json').read_text(encoding='ascii'))
        if status.get('plan_sha256')!=plan_sha:
            errors.append('plan digest differs from status')
        manifest={}
        for line in (root/'manifest.sha256').read_text(encoding='ascii').splitlines():
            checksum,filename=line.split('  ',1)
            if filename in manifest: errors.append('duplicate manifest file: '+filename)
            manifest[filename]=checksum
        if set(manifest)!={'plan.json','run_status.json'}:
            errors.append('unexpected manifest file set')
        for name,sha in manifest.items():
            if sha!=raw_hash(root/name):
                errors.append('manifest digest mismatch: '+name)
        all_jobs=plan.get('jobs',[])
        if len(all_jobs)!=480 or len({j.get('job_id') for j in all_jobs})!=480:
            errors.append('job roster missing or duplicate')
        counts={}
        for j in all_jobs:
            counts[j.get('family')]=counts.get(j.get('family'),0)+1
            if j.get('status')!='PLANNED_ONLY' or j.get('execution_allowed') is not False:
                errors.append('unpermitted execution status in plan')
        if counts!={'localized_defects':160,'smooth_heterogeneity':160,'irregular_inclusions':160}:
            errors.append('family counts wrong')
        receipts=root/'engineering_recovery_fixture'/'receipts'
        files=list(receipts.glob('*.json')) if receipts.exists() else []
        if {f.stem for f in files}!=set(EXPECTED):
            errors.append('missing/extra engineering receipts')
        if any(f.is_symlink() for f in files):
            errors.append('symlink receipt prohibited')
        for path in files:
            record=json.loads(path.read_text(encoding='ascii'))
            jid=path.stem
            expected_sha=hashlib.sha256(('fixture|'+jid+'|'+plan_sha).encode('ascii')).hexdigest()
            if record!={'schema':'RBYRCT-08AJ-J-engineering-receipt-v1',
                        'job_id':jid,'plan_sha256':plan_sha,'fixture_digest_sha256':expected_sha,
                        'no_reconstruction':True,'no_rmse':True,'no_confirmatory_outcomes':True}:
                errors.append('tampered receipt: '+jid)
        # Any artifacts named like actual study results are prohibited in this rehearsal.
        for unwanted in ('rmse.csv','reconstructions','results.csv','outcomes.json'):
            if (root/unwanted).exists():
                errors.append('unexpected study outcome artifact: '+unwanted)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        errors.append(type(exc).__name__+': '+str(exc))
    return {'verdict':'INDEPENDENT_DEMO_AUDIT_PASS' if not errors else 'INDEPENDENT_DEMO_AUDIT_FAIL',
            'pass':not errors,'errors':errors,'engineering_receipts':len(files) if 'files' in locals() else 0,
            'no_production_numerical_audit':True,'no_confirmatory_outcomes':True}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir',type=Path,required=True)
    args=ap.parse_args()
    result=audit_demo(args.output_dir)
    print(json.dumps(result,indent=2))
    if not result['pass']:
        raise SystemExit(2)
if __name__=='__main__':
    main()
