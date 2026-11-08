"""Independent 08AJ-O audit: verifies disabled M contract, operational receipts and N link.

No import of the O runner and no confirmatory execution.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from experiment_08aj_m_audit import audit as audit_m
from experiment_08aj_n_audit import audit as audit_n

def sha(x):return hashlib.sha256(x).hexdigest()
def canon(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('ascii')
def read(p):
    p=Path(p)
    if p.is_symlink():raise ValueError('symlink forbidden '+str(p))
    b=p.read_bytes();x=json.loads(b)
    if canon(x)!=b:raise ValueError('noncanonical JSON '+str(p))
    return x,b

def audit(root,m_root,n_root=None,*,l_root=None,require_n=False,require_recovery=False):
    errors=[];linked=False
    root=Path(root);m_root=Path(m_root)
    try:
        m_report=audit_m(m_root,l_root=l_root,require_link=(m_root/'engineering_evidence'/'l_replay_receipt.json').exists())
        if not m_report['pass']:errors.extend('M: '+str(x) for x in m_report['errors'])
        m_contract,m_blob=read(m_root/'production_contract_draft.json')
        m_jobs,jblob=read(m_root/'jobs.json')
        o,oblob=read(root/'integration_contract.json');status,_=read(root/'run_status.json')
        if o.get('schema')!='RBYRCT-08AJ-O-disabled-integration-v1' or o.get('m_contract_sha256')!=sha(m_blob) or o.get('m_roster_sha256')!=sha(jblob):
            errors.append('M-O contract fingerprint mismatch')
        if o.get('production_job_count')!=480 or len(m_jobs)!=480 or o.get('mart_epochs')!=16 or o.get('rays')!=2048 or o.get('n')!=32:
            errors.append('invalid O numerical settings')
        gate=o.get('gate',{})
        if any(gate.get(k) is not False for k in ('execution_allowed','production_executor_implemented','freeze_allowed','outcome_analysis_allowed','scientific_approval')):
            errors.append('O gate enabled or missing')
        if o.get('frozen') is not False or o.get('no_confirmatory_outcomes') is not True or len(o.get('open_review',[]))<4:
            errors.append('O scientific lock limitations missing')
        if status!={'verdict':'O_CONTRACT_PREPARED','jobs':480,'frozen':False,'execution_allowed':False,'no_confirmatory_outcomes':True}:
            errors.append('unexpected O run status')
        if {p.name for p in root.iterdir()}!={'integration_contract.json','run_status.json','engineering_links','recovery_fixture'}:
            errors.append('unexpected O output files')
        fixture=root/'recovery_fixture'
        if fixture.is_symlink():errors.append('unsafe fixture directory')
        names={p.name for p in fixture.iterdir()}
        if names-{f'operational_{i}.json' for i in range(3)}:errors.append('unexpected operational receipt')
        if require_recovery and len(names)!=3:errors.append('incomplete recovery fixture')
        for i in range(3):
            p=fixture/f'operational_{i}.json'
            if p.exists():
                x,_=read(p)
                if x!={'schema':'RBYRCT-08AJ-O-operational-fixture-v1','fixture_index':i,
                    'integration_sha256':sha(oblob),'state':'RECEIPT_ONLY','numerical':False,'no_confirmatory_outcomes':True}:
                    errors.append('invalid operational receipt '+str(i))
        links=root/'engineering_links'
        if links.is_symlink():errors.append('unsafe link folder')
        if {p.name for p in links.iterdir()}-{'n_16epoch_link.json'}:errors.append('unexpected engineering link')
        p=links/'n_16epoch_link.json'
        if p.exists():
            if n_root is None:errors.append('N link exists but --n-dir absent')
            else:
                link,_=read(p);n_root=Path(n_root)
                np_,npblob=read(n_root/'engineering_plan.json')
                if link.get('schema')!='RBYRCT-08AJ-O-engineering-N-link-v1' or link.get('o_integration_sha256')!=sha(oblob) or link.get('n_plan_sha256')!=sha(npblob) or link.get('epochs')!=[8,16] or link.get('models')!=['same','independent'] or link.get('production_480_job_certified') is not False or link.get('engineering_only') is not True or link.get('no_confirmatory_outcomes') is not True:
                    errors.append('N link contract mismatch')
                if np_.get('mart_epochs')!=16 or np_.get('engineering_seed')!=970099 or np_.get('execution_allowed') is not False:
                    errors.append('N plan invalid')
                expected_files={'order.npy','measurements.npy','csr_data.npy','csr_indices.npy','csr_indptr.npy','clean_catalogue.npy','noisy_catalogue.npy','reconstruction_epoch08.npy','reconstruction_epoch16.npy','receipt.json'}
                for model in ('same','independent'):
                    folder=n_root/'jobs'/model
                    if folder.is_symlink() or {x.name for x in folder.iterdir()}!=expected_files:errors.append('N artifact names invalid '+model)
                    for name,want in link.get('n_evidence_sha256',{}).get(model,{}).items():
                        f=folder/name
                        if f.is_symlink() or sha(f.read_bytes())!=want:errors.append('N evidence changed '+model+'/'+name)
                    if set(link.get('n_evidence_sha256',{}).get(model,{}))!=expected_files:errors.append('N artifact digest roster invalid '+model)
                    if link.get('n_independent_errors',{}).get(model)!={'8':0.0,'16':0.0}:errors.append('N replay receipt not exact '+model)
                if not errors:
                    nr=audit_n(n_root)
                    if not nr['pass']:errors.append('N numerical replay failed')
                    else:linked=True
        elif require_n:errors.append('N evidence required but missing')
    except Exception as exc:errors.append(type(exc).__name__+': '+str(exc))
    return {'verdict':'O_INDEPENDENT_INTEGRATION_AUDIT_PASS' if not errors else 'O_INDEPENDENT_INTEGRATION_AUDIT_FAIL',
            'pass':not errors,'errors':errors,'planned_jobs':480,'n_engineering_link_verified':linked,
            'production_executor_certified':False,'execution_allowed':False,'frozen':False,'no_confirmatory_outcomes':True}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--m-dir',type=Path,required=True)
    p.add_argument('--n-dir',type=Path)
    p.add_argument('--l-dir',type=Path)
    p.add_argument('--require-n',action='store_true')
    p.add_argument('--require-recovery',action='store_true')
    a=p.parse_args()
    r=audit(a.output_dir,a.m_dir,a.n_dir,l_root=a.l_dir,require_n=a.require_n,require_recovery=a.require_recovery)
    print(json.dumps(r,indent=2,sort_keys=True))
    if not r['pass']:raise SystemExit(2)
if __name__=='__main__':main()
