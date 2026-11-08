"""08AJ-J outcome-free run-plan and resumability protocol rehearsal.

No MART, no RMSE, no measurements or confirmatory object evaluation.
A production execution command is deliberately NOT implemented.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
from experiment_08aj_d import FAMILIES, SEEDS, ACQUISITION_SEEDS, MODELS, POLICIES
from experiment_08aj_h import statistical_rules

SCHEMA='RBYRCT-08AJ-J-planning-v1'
STAGE='08AJ-J outcome-free runner and independent-audit rehearsal'
REQUIRED_SOURCES=(
 'experiment_04b.py','experiment_04g.py','experiment_04h.py','experiment_04qa.py',
 'experiment_05b_08b.py','experiment_05b_mart.py','experiment_08j.py','experiment_08k.py',
 'experiment_08aj_b.py','experiment_08aj_c_view.py','experiment_08aj_d.py',
 'experiment_08aj_d_analysis.py','experiment_08aj_e.py','experiment_08aj_f.py',
 'experiment_08aj_g.py','experiment_08aj_h.py','experiment_08aj_i.py',
 'experiment_08aj_j.py','experiment_08aj_j_audit.py',
)


def canonical(data):
    return (json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('ascii')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_once(path:Path, data:bytes):
    """Exclusive create; never replace prior evidence."""
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def source_hashes(root=None):
    root=Path(root) if root else Path(__file__).resolve().parent
    hashes={}
    for filename in REQUIRED_SOURCES:
        p=root/filename
        if not p.is_file():
            raise FileNotFoundError('required source missing: '+str(p))
        hashes[filename]=digest(p.read_bytes())
    return hashes


def jobs():
    result=[]
    for f in FAMILIES:
        for object_seed in SEEDS[f]:
            for acquisition_seed in ACQUISITION_SEEDS:
                for model in MODELS:
                    for policy in POLICIES:
                        key=f'{f}__{object_seed}__{acquisition_seed}__{model}__{policy}'
                        result.append({'job_id':key,'family':f,'object_seed':int(object_seed),
                             'acquisition_seed':int(acquisition_seed),'model':model,
                             'policy':policy,'ray_budget':2048,'reconstruction_n':32,
                             'execution_allowed':False,'status':'PLANNED_ONLY'})
    assert len(result)==480 and len({j['job_id'] for j in result})==480
    return result


def create_plan(root:Path, *, code_root=None):
    root=Path(root)
    if root.exists():
        raise FileExistsError('refusing to overwrite run directory')
    sources=source_hashes(code_root)
    planned=jobs()
    proposal={'schema':SCHEMA,'stage':STAGE,'frozen':False,'execution_allowed':False,
              'no_confirmatory_outcomes':True,'primary_checkpoint':2048,
              'planned_objects':24,'planned_conditions_per_object':4,
              'planned_policies':5,'planned_jobs':len(planned),
              'jobs':planned,'source_sha256':sources,
              'statistical_rules':statistical_rules(),
              'blockers':['Structural and generator independence review',
                          'Statistical precision and resource-limit scientific approval',
                          'Independent production numerical auditor and live runner unimplemented',
                          'Formal approved protocol and signed source lock pending'],
              'policy_execution':'DISABLED: do not use this draft to run confirmatory results'}
    blob=canonical(proposal)
    write_once(root/'plan.json',blob)
    plan_hash=digest(blob)
    status={'verdict':'PLAN_ONLY_PASS','complete':True,'frozen':False,
            'execution_allowed':False,'no_confirmatory_outcomes':True,
            'planned_jobs':len(planned),'plan_sha256':plan_hash,
            'lock_readiness':'NOT_READY'}
    write_once(root/'run_status.json',canonical(status))
    write_once(root/'manifest.sha256',(plan_hash+'  plan.json\n'+digest(canonical(status))+'  run_status.json\n').encode('ascii'))
    return status


def load_plan(root:Path, *, code_root=None):
    root=Path(root)
    plan_bytes=(root/'plan.json').read_bytes()
    plan=json.loads(plan_bytes)
    if plan_bytes!=canonical(plan):
        raise ValueError('plan is not canonical')
    if plan.get('schema')!=SCHEMA or plan.get('execution_allowed') is not False or plan.get('frozen') is not False:
        raise ValueError('unexpected plan schema or permission')
    if plan['jobs']!=jobs() or plan['planned_jobs']!=480:
        raise ValueError('plan roster mismatch')
    if plan['source_sha256']!=source_hashes(code_root):
        raise ValueError('SOURCE_LOCK_MISMATCH: code differs from recorded plan')
    return plan,digest(plan_bytes)


def demo_recovery(root:Path, *, code_root=None, fail_after_claim=False):
    """Demonstrate exclusive receipts and recovery with engineering fixture ONLY.

    No job or seed from the prospective 24-object roster is used.
    """
    from experiment_08aj_j_audit import audit_demo
    root=Path(root)
    plan,plan_hash=load_plan(root,code_root=code_root)
    demo=root/'engineering_recovery_fixture'
    demo.mkdir(exist_ok=True)
    fixture_ids=('ENGINEERING_DEMO_A','ENGINEERING_DEMO_B','ENGINEERING_DEMO_C')
    receipts=demo/'receipts';receipts.mkdir(exist_ok=True)
    for job in fixture_ids:
        dest=receipts/(job+'.json')
        if dest.exists():
            existing=json.loads(dest.read_bytes())
            if existing!=demo_receipt(job,plan_hash):
                raise ValueError('immutable receipt mismatch: '+job)
            continue
        if fail_after_claim and job=='ENGINEERING_DEMO_B':
            # Simulates interrupted work *before* commit, leaving no result receipt.
            write_once(demo/'interruption.marker',b'ENGINEERING_FIXTURE_ONLY\n') if not (demo/'interruption.marker').exists() else None
            raise RuntimeError('SIMULATED_INTERRUPTION_BEFORE_COMMIT')
        write_once(dest,canonical(demo_receipt(job,plan_hash)))
    result=audit_demo(root)
    if not result['pass']:
        raise AssertionError('demo audit failed')
    return {'verdict':'RECOVERY_FIXTURE_PASS','fixtures_complete':len(fixture_ids),
            'existing_receipts_reused':True,'no_confirmatory_outcomes':True,
            'plan_sha256':plan_hash}


def demo_receipt(job,plan_hash):
    if job not in ('ENGINEERING_DEMO_A','ENGINEERING_DEMO_B','ENGINEERING_DEMO_C'):
        raise ValueError('not an engineering fixture ID')
    return {'schema':'RBYRCT-08AJ-J-engineering-receipt-v1',
            'job_id':job,'plan_sha256':plan_hash,
            'fixture_digest_sha256':digest(('fixture|'+job+'|'+plan_hash).encode('ascii')),
            'no_reconstruction':True,'no_rmse':True,'no_confirmatory_outcomes':True}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--mode',choices=('plan','check','demo-recovery','simulate-interruption','execute'),default='plan')
    args=p.parse_args()
    if args.mode=='execute':
        raise RuntimeError('EXECUTION_DISABLED: protocol not frozen, production runner not implemented')
    if args.mode=='plan':
        outcome=create_plan(args.output_dir)
    elif args.mode=='check':
        _,sha=load_plan(args.output_dir)
        outcome={'verdict':'PLAN_SOURCE_MATCH','plan_sha256':sha,'no_confirmatory_outcomes':True}
    else:
        outcome=demo_recovery(args.output_dir,fail_after_claim=args.mode=='simulate-interruption')
    print(json.dumps(outcome,indent=2,sort_keys=True))

if __name__=='__main__':
    main()
