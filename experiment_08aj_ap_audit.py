"""Independent structural review of AP qualification report (does NOT replay MART)."""
import argparse, hashlib, json
from pathlib import Path

EXPECTED={'G1_phantom_population','G2_estimand_inference','G3_resource_failure_policy','G4_480_job_executor_auditor','G5_signoff_source_freeze'}

def audit(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    errors=[]
    def check(test,reason):
        if not test:errors.append(reason)
    check(data.get('schema')=='RBYRCT-08AJ-AP-read-only-qualification-v1','unexpected AP schema')
    check(data.get('verdict')=='AP_READ_ONLY_EVIDENCE_RECONCILED_NOT_APPROVED','unexpected approval/verdict')
    check(set(data.get('gates',{}))==EXPECTED and all(v not in ('APPROVED','PASS') for v in data.get('gates',{}).values()),'missing or unlocked gates')
    check(data.get('gates_blocked')==5,'blocked count changed')
    for k in ('production_480_job_certified','resource_policy_approved','scientific_signoff','frozen','production_execution_allowed'):
        check(data.get(k) is False,'AP unexpectedly enabled '+k)
    check(data.get('production_jobs_executed')==0 and data.get('no_confirmatory_outcomes') is True,'invalid outcome guard')
    e=data.get('evidence',{})
    check(e.get('aa_count')==480 and e.get('aa_groups')==96 and e.get('aa_objects')==24 and e.get('aa_acquisition_seeds')==2,'AA contract dimensions')
    checks=e.get('engineering_audits',[])
    check(len(checks)==2 and {(c.get('stage'),c.get('resolution_n'),c.get('reported_jobs_audited')) for c in checks}=={('AN_8',8,40),('AO_32',32,20)},'engineering coverage')
    check(all(c.get('numerical_replay_performed_by_AP') is False for c in checks),'AP replay incorrectly claimed')
    check(all(isinstance(e.get(k),str) and len(e[k])==64 for k in ('aa_manifest_sha256','aa_spec_sha256')),'missing hashes')
    return {'verdict':'AP_INDEPENDENT_REPORT_STRUCTURE_PASS' if not errors else 'AP_REPORT_STRUCTURE_FAIL','pass':not errors,'errors':errors,
            'report_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'numerical_replay_performed':False,'production_execution_allowed':False}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output-dir',type=Path,required=True);args=ap.parse_args()
    result=audit(args.output_dir/'qualification_report.json');print(json.dumps(result,indent=2))
    if not result['pass']:raise SystemExit(2)
if __name__=='__main__':main()
