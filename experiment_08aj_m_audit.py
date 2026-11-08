"""Independent 08AJ-M auditor: verifies disabled contract and linked L evidence.

Does not import 08AJ-M, does not run or approve any confirmatory object.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from experiment_08aj_d import FAMILIES, SEEDS, ACQUISITION_SEEDS, MODELS, POLICIES

def digest(blob):return hashlib.sha256(blob).hexdigest()
def canonical(obj):return (json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('ascii')
def load_exact(path):
    if path.is_symlink():raise ValueError('symlink prohibited: '+str(path))
    blob=path.read_bytes(); data=json.loads(blob)
    if blob!=canonical(data):raise ValueError('noncanonical JSON: '+str(path))
    return data,blob

def audit(root,*,l_root=None,code_root=None,require_link=False):
    errors=[]; linked=False
    root=Path(root)
    code_root=Path(code_root) if code_root is not None else Path(__file__).resolve().parent
    try:
        jobs,jblob=load_exact(root/'jobs.json')
        proto,pblob=load_exact(root/'production_contract_draft.json')
        status,sblob=load_exact(root/'run_status.json')
        expected=[(f,int(s),int(a),m,p) for f in FAMILIES for s in SEEDS[f] for a in ACQUISITION_SEEDS for m in MODELS for p in POLICIES]
        actual=[(x['family'],x['object_seed'],x['acquisition_seed'],x['model'],x['policy']) for x in jobs]
        if len(expected)!=480 or actual!=expected or len(set(actual))!=480:errors.append('480-job roster mismatch')
        if any(x.get('execution_allowed') is not False or x.get('status')!='DISABLED' or x.get('mart_epochs')!=16 or x.get('n')!=32 or x.get('ray_budget')!=2048 for x in jobs):
            errors.append('job execution permission or parameters changed')
        if proto.get('schema')!='RBYRCT-08AJ-M-disabled-contract-v1' or proto.get('state')!='EXECUTION_DISABLED' or proto.get('frozen') is not False or proto.get('roster_sha256')!=digest(jblob):
            errors.append('invalid contract / roster digest')
        gates=proto.get('execution_gate',{})
        if gates.get('enabled') is not False or gates.get('unlock_command_exists') is not False or proto.get('no_confirmatory_outcomes') is not True:
            errors.append('production gate invalid')
        hashes=proto.get('source_sha256',{})
        if len(hashes)<25:errors.append('incomplete source roster')
        for name,want in hashes.items():
            if '/' in name or '\\' in name or not name.endswith('.py'):
                errors.append('invalid source name '+name);continue
            p=code_root/name
            if not p.is_file() or p.is_symlink() or digest(p.read_bytes())!=want:
                errors.append('source mismatch '+name)
        if status.get('verdict')!='M_CONTRACT_PREPARED' or status.get('contract_sha256')!=digest(pblob) or status.get('roster_sha256')!=digest(jblob) or status.get('execution_allowed') is not False:
            errors.append('invalid status')
        if {p.name for p in root.iterdir()}!={'jobs.json','production_contract_draft.json','run_status.json','engineering_evidence'}:
            errors.append('unexpected root artifacts')
        evidence=root/'engineering_evidence'
        if evidence.is_symlink():errors.append('unsafe engineering directory')
        if {p.name for p in evidence.iterdir()}-{'l_replay_receipt.json'}:errors.append('unexpected engineering artifacts')
        receipt=evidence/'l_replay_receipt.json'
        if receipt.exists():
            if l_root is None:errors.append('link present but --l-dir not supplied')
            else:
                link,_=load_exact(receipt)
                if link.get('schema')!='RBYRCT-08AJ-M-engineering-attachment-v1' or link.get('contract_sha256')!=digest(pblob) or link.get('mart_epochs')!=2 or link.get('engineering_only') is not True or link.get('production_certification') is not False:
                    errors.append('invalid engineering evidence receipt')
                l_root=Path(l_root)
                if digest((l_root/'protocol_review_draft.json').read_bytes())!=link.get('l_protocol_sha256'):
                    errors.append('L protocol mismatch')
                for model in ('same','independent'):
                    folder=l_root/'engineering_jobs'/model
                    expected_files=link.get('l_artifacts_sha256',{}).get(model,{})
                    if len(expected_files)!=9 or {x.name for x in folder.iterdir()}!=set(expected_files):
                        errors.append('L artifact roster mismatch '+model)
                    for name,want in expected_files.items():
                        p=folder/name
                        if p.is_symlink() or digest(p.read_bytes())!=want:
                            errors.append('L artifact hash mismatch '+model+'/'+name)
                    if link.get('l_independent_replay',{}).get(model) is None:
                        errors.append('missing L replay '+model)
                if not errors:
                    # Re-run independent numerical audit rather than trusting the old receipt.
                    from experiment_08aj_l_audit import audit as independent_l_audit
                    result=independent_l_audit(l_root)
                    if not result['pass']:errors.append('independent L numerical replay failed')
                    else:linked=True
        elif require_link:errors.append('engineering evidence link missing')
    except Exception as exc:errors.append(type(exc).__name__+': '+str(exc))
    good=not errors
    return {'verdict':'M_INDEPENDENT_CONTRACT_AUDIT_PASS' if good else 'M_INDEPENDENT_CONTRACT_AUDIT_FAIL',
            'pass':good,'errors':errors,'planned_jobs':480 if good else None,
            'l_engineering_link_verified':linked,'production_numerical_certified':False,
            'execution_allowed':False,'frozen':False,'no_confirmatory_outcomes':True}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--l-dir',type=Path)
    p.add_argument('--require-link',action='store_true')
    a=p.parse_args();result=audit(a.output_dir,l_root=a.l_dir,require_link=a.require_link)
    print(json.dumps(result,indent=2,sort_keys=True))
    if not result['pass']:raise SystemExit(2)
if __name__=='__main__':main()
