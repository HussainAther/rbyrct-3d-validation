"""08AJ-X independent structural/evidence audit. No numerical outcomes."""
import argparse,hashlib,json
from pathlib import Path
from experiment_08aj_x import DEPENDENCIES, SCHEMA, canonical

def audit(out,source_root):
    errors=[]; out=Path(out); source_root=Path(source_root)
    try:
        review_raw=(out/'estimand_review.json').read_bytes()
        status_raw=(out/'run_status.json').read_bytes()
        review=json.loads(review_raw); status=json.loads(status_raw)
        if canonical(review)!=review_raw: errors.append('noncanonical_review')
        if canonical(status)!=status_raw: errors.append('noncanonical_status')
        if review.get('schema')!=SCHEMA: errors.append('schema_mismatch')
        if hashlib.sha256(review_raw).hexdigest()!=status.get('review_sha256'):errors.append('review_hash_mismatch')
        if status.get('decisions_pending')!=len(review.get('decisions',[])) or len(review.get('decisions',[]))!=7:errors.append('decision_count_mismatch')
        if len(set(x.get('id') for x in review.get('decisions',[])))!=7:errors.append('duplicate_decision_ids')
        if any(x.get('approval')!='PENDING' for x in review.get('decisions',[])):errors.append('unapproved_decision_changed')
        for flag in ('frozen','confirmatory_execution_allowed','scientific_signoff'):
            if status.get(flag) is not False or review.get(flag) is not False: errors.append('unauthorized_'+flag)
        for flag in ('no_confirmatory_outcomes',):
            if status.get(flag) is not True or review.get(flag) is not True: errors.append('invalid_'+flag)
        if review.get('design',{}).get('objects')!=24 or review.get('design',{}).get('objects_per_family')!=8: errors.append('object_roster_mismatch')
        if review.get('targets',{}).get('fixed_cohort',{}).get('uncertainty','').startswith('no sampling') is False:errors.append('fixed_cohort_inference_mismatch')
        if review.get('analysis',{}).get('inference_recommendation','').find('conditional')<0:errors.append('inferential_scope_mismatch')
        if sorted(review.get('source_sha256',{}))!=sorted(DEPENDENCIES):errors.append('source_list_mismatch')
        for name in DEPENDENCIES:
            f=source_root/name
            if not f.exists() or hashlib.sha256(f.read_bytes()).hexdigest()!=review.get('source_sha256',{}).get(name):errors.append('source_mismatch_'+name)
    except (OSError,ValueError,TypeError,KeyError) as e: errors.append(type(e).__name__+':'+str(e))
    return {'verdict':'X_INDEPENDENT_ESTIMAND_AUDIT_PASS' if not errors else 'X_INDEPENDENT_ESTIMAND_AUDIT_FAIL',
            'pass':not errors,'errors':errors,'decisions_pending':7 if not errors else None,
            'no_confirmatory_outcomes':True if not errors else None}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parent)
    a=p.parse_args(); result=audit(a.output_dir,a.source_root); print(json.dumps(result,indent=2));
    if not result['pass']:raise SystemExit(1)
if __name__=='__main__':main()
