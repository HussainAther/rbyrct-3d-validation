"""08AJ-M: execution-disabled 480-job contract and verified engineering evidence link.

Planning/lock preparation only. There is deliberately no code path that executes
prospective objects or accepts a production result commit.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
from experiment_08aj_d import FAMILIES, SEEDS, ACQUISITION_SEEDS, MODELS, POLICIES

SCHEMA='RBYRCT-08AJ-M-disabled-contract-v1'
ROSTER_SCHEMA='RBYRCT-08AJ-M-job-v1'
SOURCE_FILES=(
 'experiment_04b.py','experiment_04g.py','experiment_04h.py','experiment_04qa.py',
 'experiment_05b_08b.py','experiment_05b_mart.py','experiment_08j.py','experiment_08k.py',
 'experiment_08aj_b.py','experiment_08aj_c_view.py','experiment_08aj_d.py',
 'experiment_08aj_d_analysis.py','experiment_08aj_e.py','experiment_08aj_f.py',
 'experiment_08aj_g.py','experiment_08aj_h.py','experiment_08aj_i.py',
 'experiment_08aj_j.py','experiment_08aj_j_audit.py','experiment_08aj_k.py',
 'experiment_08aj_k_audit.py','experiment_08aj_l.py','experiment_08aj_l_audit.py',
 'experiment_08aj_m.py','experiment_08aj_m_audit.py')
REQUIRED_JOB_ARRAYS=(
 'order.npy','measurements.npy','csr_data.npy','csr_indices.npy','csr_indptr.npy',
 'reconstruction.npy','clean_catalogue.npy','noisy_catalogue.npy')

def canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('ascii')

def sha(b): return hashlib.sha256(b).hexdigest()

def exclusive(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f:
        f.write(data);f.flush();os.fsync(f.fileno())

def code_hashes(code_root=None):
    root=Path(code_root) if code_root is not None else Path(__file__).resolve().parent
    result={}
    for name in SOURCE_FILES:
        p=root/name
        if not p.is_file() or p.is_symlink():
            raise FileNotFoundError('missing/unsafe source: '+str(p))
        result[name]=sha(p.read_bytes())
    return result

def roster():
    result=[]
    for family in FAMILIES:
        for seed in SEEDS[family]:
            for acq in ACQUISITION_SEEDS:
                for model in MODELS:
                    for policy in POLICIES:
                        identity=f'{family}__{seed}__{acq}__{model}__{policy}'
                        result.append({'schema':ROSTER_SCHEMA,'job_id':identity,'family':family,
                                       'object_seed':int(seed),'acquisition_seed':int(acq),
                                       'model':model,'policy':policy,'n':32,'ray_budget':2048,
                                       'mart_epochs':16,'relaxation':0.25,
                                       'status':'DISABLED','execution_allowed':False})
    if len(result)!=480 or len({x['job_id'] for x in result})!=480:
        raise AssertionError('invalid plan cardinality')
    return result

def proposed_contract():
    return {
      'version':'08AJ-M-PROPOSED-NOT-FROZEN', 'state':'EXECUTION_DISABLED',
      'unit_of_inference':'object; 24 objects, 8 in each of 3 families',
      'jobs':480,'primary_checkpoint_rays':2048,
      'primary_comparison':'information_diag vs uniform_multiscale',
      'forward_models':list(MODELS),'acquisition_seeds':list(ACQUISITION_SEEDS),
      'phantom_truth':'08AJ-F 64^3 phantom then deterministic 2^3 block-average to 32^3',
      'paired_noise':'one deterministic full catalogue per object/acquisition seed/model, reused by every policy',
      'individual_policy_warm_prefix':64,'complete_view_exception':True,
      'checkpoint_contract':{
        'artifact_names':list(REQUIRED_JOB_ARRAYS),
        'receipt':'canonical JSON; plan hash, job ID, exact source/parameter fingerprint, artifact hashes',
        'durability':'write staging files, fsync, validate, then atomically commit; no replacement of committed files',
        'resume':'verify existing artifact digest and independent replay before reuse; reject invalid evidence',
        'failure':'preserve failure evidence; no imputation or outcome-based stopping'},
      'statistics':{
        'primary_gain':'1 - RMSE(information_diag)/RMSE(uniform_multiscale) per paired condition',
        'aggregation':'average four conditions per object, then average 24 objects',
        'CI':'family-stratified object bootstrap, 20000 reps, seed 941007, percentile 95%',
        'directional_rule':'lower 95% confidence bound > 0 (draft pending scientific sign-off)'},
      'execution_gate':{
        'enabled':False,'unlock_command_exists':False,
        'science_approval':False,'signed_git_source_lock':False,
        'independent_480_job_audit_certified':False,
        'full_16_epoch_production_numerical_replay_certified':False},
      'open_review':[
        'Independent expert review of morphology/generator novelty',
        'Primary inferential precision/power and practical effect sign-off',
        'Total execution time and memory ceilings and retry policy sign-off',
        'Full 16-epoch numerical replay and live 480-job code/audit unimplemented',
        'Formal immutable source lock, approval identities and authorizing gate pending'],
      'out_of_scope':'64^3 2048-ray complete-view infeasible; any 64^3 full view requires >=4096 rays',
      'no_confirmatory_outcomes':True,'frozen':False}

def prepare(root,*,code_root=None):
    root=Path(root)
    if root.exists(): raise FileExistsError('refusing to overwrite existing M planning directory')
    sources=code_hashes(code_root)
    jobs=roster()
    jobs_blob=canonical(jobs)
    contract=proposed_contract()
    contract.update({'schema':SCHEMA,'roster_sha256':sha(jobs_blob),'source_sha256':sources})
    contract_blob=canonical(contract)
    status={'verdict':'M_CONTRACT_PREPARED','planned_jobs':480,
            'roster_sha256':sha(jobs_blob),'contract_sha256':sha(contract_blob),
            'frozen':False,'execution_allowed':False,'no_confirmatory_outcomes':True,
            'production_numerical_certified':False}
    # Allocate exclusively and never update original files.
    root.mkdir(parents=True)
    exclusive(root/'jobs.json',jobs_blob)
    exclusive(root/'production_contract_draft.json',contract_blob)
    exclusive(root/'run_status.json',canonical(status))
    (root/'engineering_evidence').mkdir()
    return status

def check(root,*,code_root=None):
    root=Path(root)
    jobs_blob=(root/'jobs.json').read_bytes()
    contract_blob=(root/'production_contract_draft.json').read_bytes()
    status_blob=(root/'run_status.json').read_bytes()
    jobs=json.loads(jobs_blob);contract=json.loads(contract_blob);status=json.loads(status_blob)
    if jobs_blob!=canonical(jobs) or jobs!=roster():raise ValueError('M roster mismatch')
    if contract_blob!=canonical(contract):raise ValueError('M contract noncanonical')
    expected=proposed_contract();expected.update({'schema':SCHEMA,
        'roster_sha256':sha(jobs_blob),'source_sha256':code_hashes(code_root)})
    if contract!=expected:raise ValueError('M contract/source mismatch')
    if status_blob!=canonical(status) or status.get('verdict')!='M_CONTRACT_PREPARED' or status.get('roster_sha256')!=sha(jobs_blob) or status.get('contract_sha256')!=sha(contract_blob):
        raise ValueError('M status corrupted')
    if status.get('execution_allowed') is not False or status.get('frozen') is not False:
        raise ValueError('M execution gate invalid')
    return contract,sha(contract_blob)

def attach_engineering(root,l_root,*,code_root=None):
    """Reference existing separately audited 08AJ-L 32^3 TWO-EPOCH evidence; no MART run."""
    from experiment_08aj_l_audit import audit
    root=Path(root);l_root=Path(l_root)
    _,contract_sha=check(root,code_root=code_root)
    audit_report=audit(l_root)
    if not audit_report['pass'] or any(x.get('max_abs_replay_error') is None for x in audit_report['details']):
        raise ValueError('L independent numerical audit failed')
    pblob=(l_root/'protocol_review_draft.json').read_bytes()
    evidence={}
    for model in ('same','independent'):
        folder=l_root/'engineering_jobs'/model
        files=sorted(p for p in folder.iterdir() if p.is_file() and not p.is_symlink())
        if not files or {p.name for p in files}!={*REQUIRED_JOB_ARRAYS,'receipt.json'}:
            raise ValueError('incomplete/unsafe L numerical evidence')
        evidence[model]={p.name:sha(p.read_bytes()) for p in files}
    receipt={'schema':'RBYRCT-08AJ-M-engineering-attachment-v1',
             'contract_sha256':contract_sha,'l_protocol_sha256':sha(pblob),
             'l_artifacts_sha256':evidence,
             'l_independent_replay':{x['model']:x['max_abs_replay_error'] for x in audit_report['details']},
             'models':['same','independent'],'n':32,'mart_epochs':2,
             'engineering_only':True,'no_confirmatory_outcomes':True,
             'production_certification':False}
    dest=root/'engineering_evidence'/'l_replay_receipt.json'
    data=canonical(receipt)
    if dest.exists():
        if dest.read_bytes()!=data:raise ValueError('cannot replace prior evidence link')
        verdict='M_ENGINEERING_ATTACHMENT_REUSED'
    else:
        exclusive(dest,data)
        verdict='M_ENGINEERING_ATTACHMENT_PASS'
    return {'verdict':verdict,'l_replays':2,'mart_epochs':2,
            'no_confirmatory_outcomes':True,'production_certification':False}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',required=True,type=Path)
    parser.add_argument('--mode',required=True,choices=('prepare','check','attach-engineering','execute','freeze','commit','unlock'))
    parser.add_argument('--l-dir',type=Path)
    a=parser.parse_args()
    if a.mode in ('execute','freeze','commit','unlock'):
        parser.error('EXECUTION_DISABLED: no signed source lock, scientific approval or audited full runner')
    if a.mode=='prepare': result=prepare(a.output_dir)
    elif a.mode=='check':
        _,h=check(a.output_dir)
        result={'verdict':'M_CONTRACT_SOURCE_MATCH','contract_sha256':h,'execution_allowed':False}
    else:
        if not a.l_dir:parser.error('--l-dir required for attach-engineering')
        result=attach_engineering(a.output_dir,a.l_dir)
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__=='__main__':main()
