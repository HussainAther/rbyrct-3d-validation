"""08AJ-O: disabled full-study integration contract, noncohort replay link, and receipt recovery.

No production numerical execution, outcome generation, unlock, or source freeze is possible.
"""
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path
from experiment_08aj_m import check as check_m, roster as roster_m, canonical, exclusive
N_FILES=("order.npy","measurements.npy","csr_data.npy","csr_indices.npy","csr_indptr.npy","clean_catalogue.npy","noisy_catalogue.npy","reconstruction_epoch08.npy","reconstruction_epoch16.npy")
N_MODELS=("same","independent")

SCHEMA='RBYRCT-08AJ-O-disabled-integration-v1'
BLOCKERS=(
 'Scientific review of generator/morphology independence across historic cohorts',
 'Scientific approval of bootstrap precision, primary rule and practical relevance benchmark',
 'Approve wall-clock/memory ceilings and transparent computational failure policy',
 'Implement and independently test real per-policy production job numerical executor',
 'Independently audit full 480-job output and establish immutable signed source/protocol lock',
)

def sha(blob):return hashlib.sha256(blob).hexdigest()
def load_canonical(path):
    path=Path(path)
    if path.is_symlink():raise ValueError('unsafe symbolic link: '+str(path))
    blob=path.read_bytes();obj=json.loads(blob)
    if blob!=canonical(obj):raise ValueError('noncanonical JSON '+str(path))
    return obj,blob

def contract(m_root):
    m,ms=check_m(m_root)
    jobs=roster_m()
    if len(jobs)!=480 or any(j['execution_allowed'] is not False for j in jobs):
        raise AssertionError('M execution contract invalid')
    return {'schema':SCHEMA,'m_contract_sha256':ms,'m_roster_sha256':sha((Path(m_root)/'jobs.json').read_bytes()),
            'production_job_count':480,'mart_epochs':16,'n':32,'rays':2048,
            'target_schema':'PROPOSED_NUMERICAL_JOB_V1_NOT_IMPLEMENTED',
            'required_saved_inputs':['order.npy','measurements.npy','csr_data.npy','csr_indices.npy','csr_indptr.npy','clean_catalogue.npy','noisy_catalogue.npy'],
            'required_numerical_output':['reconstruction_epoch16.npy'],
            'future_receipt_fields':['job_id','contract_sha256','source_sha256','solver','artifact_sha256','state'],
            'gate':{'execution_allowed':False,'production_executor_implemented':False,'freeze_allowed':False,
                    'outcome_analysis_allowed':False,'scientific_approval':False},
            'allowed_operations':['prepare','check','simulate-recovery','attach-n-engineering','audit'],
            'open_review':list(BLOCKERS),'no_confirmatory_outcomes':True,'frozen':False}

def prepare(root,m_root):
    root=Path(root)
    if root.exists():raise FileExistsError('refusing to overwrite O integration evidence')
    obj=contract(m_root)
    root.mkdir(parents=True)
    exclusive(root/'integration_contract.json',canonical(obj))
    exclusive(root/'run_status.json',canonical({'verdict':'O_CONTRACT_PREPARED','jobs':480,'frozen':False,
             'execution_allowed':False,'no_confirmatory_outcomes':True}))
    (root/'engineering_links').mkdir();(root/'recovery_fixture').mkdir()
    return {'verdict':'O_CONTRACT_PREPARED','jobs':480,'execution_allowed':False,
            'frozen':False,'no_confirmatory_outcomes':True,'integration_sha256':sha(canonical(obj))}

def check(root,m_root):
    root=Path(root);obj,blob=load_canonical(root/'integration_contract.json')
    if obj!=contract(m_root):raise ValueError('O contract/source or M reference mismatch')
    status,_=load_canonical(root/'run_status.json')
    if status!={'verdict':'O_CONTRACT_PREPARED','jobs':480,'frozen':False,
                 'execution_allowed':False,'no_confirmatory_outcomes':True}:
        raise ValueError('invalid O run status')
    if set(p.name for p in root.iterdir())!={'integration_contract.json','run_status.json','engineering_links','recovery_fixture'}:
        raise ValueError('unexpected O output files')
    return obj,sha(blob)

def simulate_recovery(root,m_root,*,stop_after=None):
    """Only operational, non-numerical receipts. No 480 cohort job IDs or outcomes."""
    root=Path(root);_,h=check(root,m_root)
    folder=root/'recovery_fixture'
    if folder.is_symlink():raise ValueError('unsafe fixture directory')
    reused=created=0
    for i in range(3):
        path=folder/f'operational_{i}.json'
        receipt={'schema':'RBYRCT-08AJ-O-operational-fixture-v1','fixture_index':i,
                 'integration_sha256':h,'state':'RECEIPT_ONLY','numerical':False,
                 'no_confirmatory_outcomes':True}
        data=canonical(receipt)
        if path.exists():
            if path.is_symlink() or path.read_bytes()!=data:raise ValueError('corrupt committed receipt '+str(i))
            reused+=1
        else:
            exclusive(path,data);created+=1
        if stop_after==i:raise RuntimeError('SIMULATED_INTERRUPTION')
    return {'verdict':'O_RECOVERY_FIXTURE_PASS','receipts':3,'created':created,'reused':reused,
            'no_confirmatory_outcomes':True}

def attach_n(root,m_root,n_root):
    from experiment_08aj_n_audit import audit as n_audit
    root=Path(root);n_root=Path(n_root)
    _,o_hash=check(root,m_root)
    report=n_audit(n_root)
    if not report['pass'] or len(report['details'])!=2:raise ValueError('N independent numerical replay failed')
    p=n_root/'engineering_plan.json';nplan,pblob=load_canonical(p)
    if nplan.get('mart_epochs')!=16 or nplan.get('engineering_seed')!=970099 or nplan.get('execution_allowed') is not False:
        raise ValueError('N link is not a disabled 16-epoch noncohort engineering run')
    fingerprints={}
    for model in N_MODELS:
        folder=n_root/'jobs'/model
        if folder.is_symlink():raise ValueError('unsafe N job folder')
        needed=set(N_FILES)|{'receipt.json'}
        if {x.name for x in folder.iterdir()}!=needed:raise ValueError('N artifacts incomplete')
        fingerprints[model]={filename:sha((folder/filename).read_bytes()) for filename in sorted(needed)}
    receipt={'schema':'RBYRCT-08AJ-O-engineering-N-link-v1','o_integration_sha256':o_hash,
             'n_plan_sha256':sha(pblob),'n_evidence_sha256':fingerprints,
             'n_independent_errors':{x['model']:x['max_abs_replay_errors'] for x in report['details']},
             'models':list(N_MODELS),'n':32,'epochs':[8,16], 'engineering_only':True,
             'production_480_job_certified':False,'no_confirmatory_outcomes':True}
    dest=root/'engineering_links'/'n_16epoch_link.json'
    if dest.exists():
        if dest.is_symlink() or dest.read_bytes()!=canonical(receipt):raise ValueError('committed N evidence mismatch')
        verdict='O_N_ENGINEERING_LINK_REUSED'
    else:exclusive(dest,canonical(receipt));verdict='O_N_ENGINEERING_LINK_PASS'
    return {'verdict':verdict,'replayed_models':2,'epochs':[8,16],
            'production_480_job_certified':False,'no_confirmatory_outcomes':True}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--m-dir',type=Path,required=True)
    p.add_argument('--n-dir',type=Path)
    p.add_argument('--mode',required=True,choices=['prepare','check','simulate-recovery','attach-n-engineering',
                                                  'execute','freeze','unlock','analyze'])
    a=p.parse_args()
    if a.mode in ('execute','freeze','unlock','analyze'):
        p.error('REFUSED: confirmatory execution and source freeze are not implemented/authorized')
    if a.mode=='prepare':result=prepare(a.output_dir,a.m_dir)
    elif a.mode=='check':result={'verdict':'O_CONTRACT_SOURCE_MATCH','integration_sha256':check(a.output_dir,a.m_dir)[1], 'execution_allowed':False}
    elif a.mode=='simulate-recovery':result=simulate_recovery(a.output_dir,a.m_dir)
    else:
        if a.n_dir is None:p.error('--n-dir required')
        result=attach_n(a.output_dir,a.m_dir,a.n_dir)
    print(json.dumps(result,indent=2,sort_keys=True))
if __name__=='__main__':main()
