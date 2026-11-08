"""Independent 08AJ-AI audit of protected evidence, injected faults, and locked AA roster."""
import argparse,json
from pathlib import Path
import experiment_08aj_ai as ai


def audit(root,aa_dir,m_dir,ah_dir,af_dir,require_all=False):
    errors=[];details=[];root=Path(root)
    try: plan=ai.check(root,aa_dir,m_dir,ah_dir,af_dir)
    except Exception as exc:
        return {'verdict':'AI_INDEPENDENT_GUARD_AUDIT_FAIL','pass':False,
                'errors':['source/protected evidence: '+str(exc)],'production_execution_allowed':False}
    existing={d.name for d in (root/'cases').iterdir()}
    if require_all and existing!=set(ai.CASES):errors.append('not all three fault cases exercised')
    for kind in sorted(existing):
        directory=root/'cases'/kind
        try:
            result=json.loads((directory/'result.json').read_bytes())
            if (directory/'result.json').read_bytes()!=ai.canonical(result):raise ValueError('noncanonical case receipt')
            if result.get('schema')!=ai.SCHEMA or result.get('case')!=kind or result.get('production_execution_allowed') is not False or result.get('production_jobs_executed')!=0:
                raise ValueError('case identifier/execution lock invalid')
            sandbox=directory/'sandbox'
            actual=ai.tree_manifest(sandbox)
            if kind=='atomic-stage' and (directory/'quarantine.json').exists():
                q=json.loads((directory/'quarantine.json').read_bytes())
                if ai.canonical(q)!=(directory/'quarantine.json').read_bytes() or q.get('schema')!=ai.SCHEMA:
                    raise ValueError('invalid quarantine manifest')
                if ai.tree_manifest(directory/'quarantine')!=q['quarantine_tree']:
                    raise ValueError('quarantine bytes changed')
                original=result['sandbox_tree']
                if len(original)!=2 or sorted(x.split('/')[0] for x in original)!=sorted([q['original_stage_name']]*2):
                    raise ValueError('original orphan staging evidence mismatch')
                actual={}
            if actual!=({} if kind=='atomic-stage' and (directory/'quarantine.json').exists() else result['sandbox_tree']):
                raise ValueError('sandbox evidence changed')
            accepted={'wall':'WALL_TIMEOUT_WORKER_TERMINATED',
                      'memory':'OS_MEMORY_DENIAL_CONFIRMED',
                      'atomic-stage':'WALL_TIMEOUT_WORKER_TERMINATED'}
            verified=result['verdict']==accepted[kind]
            if not verified:errors.append(kind+' failure not demonstrated: '+str(result['verdict']))
            if kind in ('wall','atomic-stage') and not result.get('timed_out'):errors.append(kind+' did not time out')
            if kind=='memory' and (result.get('timed_out') or result.get('memory_cap_mib')!=256):errors.append('memory evidence invalid')
            details.append({'case':kind,'verdict':result['verdict'],'pass':verified})
        except Exception as exc:errors.append(kind+' receipt/integrity: '+str(exc))
    if not existing:errors.append('no fault cases exercised')
    return {'verdict':'AI_INDEPENDENT_GUARD_AUDIT_PASS' if not errors else 'AI_INDEPENDENT_GUARD_AUDIT_FAIL',
      'pass':not errors,'errors':errors,'audited_fault_cases':len(details),
      'roster_specs':plan['aa_job_specifications'],'shared_groups':plan['aa_shared_groups'],
      'protected_ah_evidence_unchanged':True,
      'details':details,'production_480_job_certified':False,'resource_policy_approved':False,
      'production_execution_allowed':False,'no_confirmatory_outcomes':True}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('output-dir','aa-dir','m-dir','ah-dir','af-dir'):p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--require-all',action='store_true')
    a=p.parse_args();r=audit(a.output_dir,a.aa_dir,a.m_dir,a.ah_dir,a.af_dir,a.require_all)
    print(json.dumps(r,indent=2));raise SystemExit(0 if r['pass'] else 1)
if __name__=='__main__':main()
