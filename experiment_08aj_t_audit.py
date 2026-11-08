"""08AJ-T separate read-only candidate verifier; never unlocks or runs studies."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from experiment_08aj_t import (GATES, REVIEW_FILE, canonical, safe_read, sha, source_snapshot, review_check, SCHEMA)

def audit(root,code_root):
    errors=[]
    try:
        blob=safe_read(root/'freeze_candidate.json')
        record=json.loads(blob)
        status_blob=safe_read(root/'run_status.json')
        status=json.loads(status_blob)
        review_bytes=safe_read(root/'review_source.json')
        review=review_check(json.loads(review_bytes))
        if blob!=canonical(record):errors.append('candidate noncanonical')
        if status_blob!=canonical(status):errors.append('status noncanonical')
        if record.get('schema')!=SCHEMA:errors.append('schema mismatch')
        if record.get('review_filename')!=REVIEW_FILE or record.get('review_sha256')!=sha(review_bytes):errors.append('review hash mismatch')
        if record.get('review_decision_ids')!=review.get('decision_ids'):errors.append('decision IDs mismatch')
        if record.get('source_hashes')!=source_snapshot(code_root):errors.append('source hash mismatch')
        if record.get('planned_jobs')!=480:errors.append('job cardinality mismatch')
        if record.get('locks')!=[{'id':i,'title':t,'status':s,'required_evidence':e} for i,t,s,e in GATES]:errors.append('blocking gates changed')
        if any(record.get(k) is not False for k in ('frozen','confirmatory_execution_allowed','production_480_job_certified','freeze_authorized')):errors.append('unauthorized execution/freeze flag')
        if record.get('status')!='FREEZE_BLOCKED' or record.get('scientific_approvals')!=[] or record.get('source_commit') is not None:errors.append('unapproved signoff')
        if status.get('candidate_sha256')!=sha(blob) or status.get('blocking_gates')!=len(GATES):errors.append('status fingerprint/gate mismatch')
        if status.get('freeze_ready') is not False or status.get('frozen') is not False or status.get('confirmatory_execution_allowed') is not False:errors.append('status flags changed')
    except (OSError,ValueError,TypeError,KeyError,AttributeError) as ex:
        errors.append(type(ex).__name__+': '+str(ex))
    return {'verdict':'T_INDEPENDENT_FREEZE_GATE_AUDIT_PASS' if not errors else 'T_INDEPENDENT_FREEZE_GATE_AUDIT_FAIL',
            'pass':not errors,'errors':errors,'blocking_gates':len(GATES),'frozen':False,
            'confirmatory_execution_allowed':False,'no_confirmatory_outcomes':True}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--code-root',type=Path,default=Path(__file__).resolve().parent)
    a=p.parse_args()
    result=audit(a.output_dir,a.code_root)
    print(json.dumps(result,indent=2))
    if not result['pass']:raise SystemExit(2)
if __name__=='__main__':main()
