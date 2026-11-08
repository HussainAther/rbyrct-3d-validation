"""Independent 08AJ-R multi-job engineering auditor.

No confirmatory data, no inferential results. Replays each completed job via
08AJ-Q's independent numerical auditor and checks cross-policy invariants.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from experiment_08aj_q_audit import audit_one, POLICIES, MODELS, canonical

SCHEMA='RBYRCT-08AJ-R-multi-policy-engineering-v1'
JOB_IDS=tuple(f'{p}__{m}' for m in MODELS for p in POLICIES)
INDIVIDUAL=('information_diag','uniform_multiscale','coverage','stratified_random_04h')
SOURCES=('experiment_08aj_r.py','experiment_08aj_r_audit.py')

def sha(blob):return hashlib.sha256(blob).hexdigest()
def audit(directory,require_complete=False):
    root=Path(directory);errors=[];details=[];cross={}
    try:
        blob=(root/'multi_job_plan.json').read_bytes();m=json.loads(blob)
        qroot=root/'q_jobs';qblob=(qroot/'engineering_plan.json').read_bytes();qp=json.loads(qblob)
        expected={'schema':SCHEMA,'q_plan_sha256':sha(qblob),'n':qp['n'],
                  'budget':qp['budget'],'epochs':qp['mart_epochs'],
                  'engineering_seed':970099,'acquisition_seed':940411,'noise_seed':970119,
                  'job_ids':list(JOB_IDS),'number_of_jobs':10,
                  'execution_allowed':'ENGINEERING_ONLY','confirmatory_execution_allowed':False,
                  'frozen':False,'no_confirmatory_outcomes':True,'production_480_job_certified':False,
                  'source_sha256':{name:sha((Path(__file__).resolve().parent/name).read_bytes()) for name in SOURCES}}
        if blob!=canonical(m) or m!=expected:errors.append('multi-job plan/source/permission mismatch')
        if qp.get('engineering_seed')!=970099 or qp.get('family')!='smooth_heterogeneity' or qp.get('frozen') is not False or qp.get('execution_allowed') is not False or qp.get('confirmatory_execution_allowed') is not False or qp.get('no_confirmatory_outcomes') is not True or qp.get('mart_epochs')!= (2 if qp.get('n')==8 else 16):errors.append('Q engineering gate mismatch')
        # Independent source checks for Q (no dependency on the R executor's check function).
        for name,h in qp.get('source_sha256',{}).items():
            f=Path(__file__).resolve().parent/name
            if not f.is_file() or f.is_symlink() or sha(f.read_bytes())!=h:errors.append('Q source mismatch '+name)
        jobs=qroot/'jobs'
        present={f.name for f in jobs.iterdir()}
        if any(x not in JOB_IDS for x in present):errors.append('unexpected or uncommitted engineering job')
        if require_complete and present!=set(JOB_IDS):errors.append('not all 10 engineering jobs completed')
        for model in MODELS:
            found={p:{} for p in POLICIES}
            for policy in POLICIES:
                job=f'{policy}__{model}'
                if job not in present:continue
                d=audit_one(qroot,policy,model)
                details.append(d)
                if not d['pass']:errors.append('independent replay failed '+job);continue
                folder=jobs/job
                found[policy]={name:np.load(folder/(name+'.npy'),allow_pickle=False)
                               for name in ('order','measurements','clean_catalogue','noisy_catalogue')}
            checked=[p for p in POLICIES if found[p]]
            for i,p in enumerate(checked):
                a=found[p]
                for other in checked[i+1:]:
                    b=found[other]
                    if not np.array_equal(a['clean_catalogue'],b['clean_catalogue']) or not np.array_equal(a['noisy_catalogue'],b['noisy_catalogue']):errors.append('nonpaired catalogue '+model+' '+p+' '+other)
                    shared=np.intersect1d(a['order'],b['order'])
                    if len(shared):
                        am=dict(zip(a['order'].tolist(),a['measurements'].tolist()))
                        bm=dict(zip(b['order'].tolist(),b['measurements'].tolist()))
                        if any(am[x]!=bm[x] for x in shared.tolist()):errors.append('shared-ray noise mismatch '+model+' '+p+' '+other)
            individuals=[p for p in INDIVIDUAL if found[p]]
            if individuals:
                warm=qp['warm'];prefix=found[individuals[0]]['order'][:warm]
                if any(not np.array_equal(found[p]['order'][:warm],prefix) for p in individuals[1:]):errors.append('warm prefix mismatch '+model)
            if found['complete_view']:
                order=found['complete_view']['order'];n=qp['n'];view_size=n*n
                view_ids=np.unique(order//view_size)
                if len(view_ids)*view_size!=len(order) or any(np.count_nonzero(order//view_size==v)!=view_size for v in view_ids):errors.append('complete-view violation '+model)
            cross[model]={'jobs_present':len(checked),'shared_catalogue_verified':len(checked)>1,
                          'warm_prefix_checked':len(individuals),'complete_view_checked':bool(found['complete_view'])}
        if len(details)==0:errors.append('no numerical jobs found')
    except Exception as exc:errors.append(type(exc).__name__+': '+str(exc))
    okay=not errors
    return {'verdict':'R_INDEPENDENT_MULTI_JOB_AUDIT_PASS' if okay else 'R_INDEPENDENT_MULTI_JOB_AUDIT_FAIL',
            'pass':okay,'errors':errors,'audited_jobs':len(details),'all_ten_required':require_complete,
            'cross_policy':cross,'max_abs_replay_error':max((x['max_abs_replay_error'] or 0 for x in details),default=None),
            'no_confirmatory_outcomes':True,'production_480_job_certified':False}

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--output-dir',required=True,type=Path)
    a.add_argument('--require-complete',action='store_true')
    p=a.parse_args();out=audit(p.output_dir,p.require_complete);print(json.dumps(out,indent=2))
    if not out['pass']:raise SystemExit(2)
if __name__=='__main__':main()
