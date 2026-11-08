"""Independent validation of AA disabled 480-job specifications and evidence."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import experiment_08aj_m as m

SCHEMA='RBYRCT-08AJ-AA-disabled-numerical-pathway-v1'
IDS={'contract_check','shared_dependency_check','engineering_link_check'}
def sha(b):return hashlib.sha256(b).hexdigest()
def canon(v):return (json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('ascii')

def audit(root,m_dir,z_dir=None,require_rehearsal=False,require_z=False):
    root=Path(root);m_dir=Path(m_dir);errors=[];count=0;groups_count=0
    try:
        contract,mhash=m.check(m_dir)
        rb=(m_dir/'jobs.json').read_bytes();roster=json.loads(rb)
        specblob=(root/'job_specifications.json').read_bytes();specs=json.loads(specblob)
        manifestblob=(root/'aa_manifest.json').read_bytes();manifest=json.loads(manifestblob)
        if specblob!=canon(specs) or manifestblob!=canon(manifest):errors.append('noncanonical evidence')
        if manifest.get('schema')!=SCHEMA or manifest.get('contract_sha256')!=mhash or manifest.get('roster_sha256')!=sha(rb) or manifest.get('spec_sha256')!=sha(specblob):errors.append('manifest/contract mismatch')
        if any(manifest.get(key) is not False for key in ('scientific_signoff','resource_policy_approved','frozen','confirmatory_execution_allowed','production_numerical_certified')) or manifest.get('no_confirmatory_outcomes') is not True:errors.append('execution gate invalid')
        if manifest.get('job_count')!=480 or manifest.get('shared_catalogues')!=96 or len(specs)!=480 or len(roster)!=480:errors.append('invalid counts')
        for name,saved_sha in manifest.get('source_sha256',{}).items():
            if name not in {'experiment_08aj_aa.py','experiment_08aj_aa_audit.py'} or sha((Path(__file__).resolve().parent/name).read_bytes())!=saved_sha:errors.append('source mismatch '+name)
        if set(manifest.get('source_sha256',{}))!={'experiment_08aj_aa.py','experiment_08aj_aa_audit.py'}:errors.append('source inventory mismatch')
        groups={};identities=set()
        for expected,s in zip(roster,specs):
            identity=expected['job_id'];count+=1
            if s.get('job_id')!=identity or identity in identities:errors.append('duplicate/job mismatch '+identity)
            identities.add(identity)
            if s.get('schema')!='RBYRCT-08AJ-AA-job-spec-v1' or s.get('execution_allowed') is not False or s.get('execution_status')!='BLOCKED_NOT_EXECUTED' or s.get('no_confirmatory_outcomes') is not True:errors.append('unlocked job '+identity)
            for key in ('family','object_seed','acquisition_seed','model','policy'):
                if s.get(key)!=expected.get(key):errors.append('job input mismatch '+identity+' '+key)
            if (s.get('n'),s.get('ray_budget'),s.get('mart_epochs'),s.get('relaxation'))!=(32,2048,16,.25):errors.append('settings mismatch '+identity)
            if s.get('acquisition_unit')!=('full_view' if s.get('policy')=='complete_view' else 'individual_ray'):errors.append('acquisition rule mismatch '+identity)
            if s.get('warm_prefix')!=(None if s.get('policy')=='complete_view' else 64):errors.append('prefix mismatch '+identity)
            key=f"{s['family']}__{s['object_seed']}__{s['acquisition_seed']}__{s['model']}"
            if s.get('shared_catalogue_key')!=key:errors.append('shared key mismatch '+identity)
            groups.setdefault(key,set()).add(s['policy'])
            required=set(m.REQUIRED_JOB_ARRAYS)|{'receipt.json','truth_sha256','rmse'}
            if set(s.get('required_artifacts',[]))!=required:errors.append('artifacts mismatch '+identity)
        groups_count=len(groups)
        for key,policies in groups.items():
            if policies!={'information_diag','uniform_multiscale','coverage','stratified_random_04h','complete_view'}:errors.append('group mismatch '+key)
        if groups_count!=96:errors.append('expected 96 shared catalogues')
        receipts=root/'rehearsal_receipts'
        if not receipts.is_dir() or receipts.is_symlink():errors.append('missing/unsafe rehearsal dir')
        else:
            present={x.stem for x in receipts.iterdir()}
            if not present.issubset(IDS):errors.append('unauthorized rehearsal')
            if require_rehearsal and present!=IDS:errors.append('rehearsal incomplete')
            for p in receipts.iterdir():
                if not p.is_file() or p.is_symlink() or p.suffix!='.json':errors.append('unsafe rehearsal file');continue
                b=p.read_bytes();r=json.loads(b)
                expected={'schema':'RBYRCT-08AJ-AA-engineering-rehearsal-v1',
                    'rehearsal_id':p.stem,'manifest_sha256':sha(manifestblob),
                    'engineered_receipt_only':True,'no_numerical_reconstruction':True,'no_confirmatory_outcomes':True}
                if b!=canon(r) or r!=expected:errors.append('rehearsal receipt changed '+p.stem)
        link=root/'engineering_link'
        if not link.is_dir() or link.is_symlink():errors.append('missing/unsafe link dir')
        else:
            files={f.name for f in link.iterdir()}
            if not files.issubset({'z_receipt.json'}):errors.append('unexpected link')
            if require_z and 'z_receipt.json' not in files:errors.append('Z link missing')
            if 'z_receipt.json' in files:
                from experiment_08aj_z_audit import audit as audit_z
                if z_dir is None:errors.append('--z-dir required for Z link audit')
                else:
                    zres=audit_z(z_dir,m_dir,require_complete=True)
                    if not zres['pass'] or zres['audited_engineering_jobs']!=10:errors.append('Z audit failed')
                    f=link/'z_receipt.json';b=f.read_bytes();r=json.loads(b)
                    expected={'schema':'RBYRCT-08AJ-AA-Z-link-v1','manifest_sha256':sha(manifestblob),
                        'z_plan_sha256':sha((Path(z_dir)/'z_plan.json').read_bytes()),
                        'z_independently_audited_jobs':10,'z_engineering_only':True,
                        'no_production_execution':True,'no_confirmatory_outcomes':True}
                    if f.is_symlink() or b!=canon(r) or r!=expected:errors.append('Z evidence link changed')
    except Exception as e:errors.append(type(e).__name__+': '+str(e))
    return {'verdict':'AA_INDEPENDENT_DISABLED_PATH_AUDIT_PASS' if not errors else 'AA_INDEPENDENT_DISABLED_PATH_AUDIT_FAIL',
        'pass':not errors,'errors':errors,'job_specifications_audited':count,
        'shared_measurement_groups_audited':groups_count,'production_jobs_executed':0,
        'production_numerical_certified':False,'confirmatory_execution_allowed':False,
        'no_confirmatory_outcomes':True}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--m-dir',type=Path,required=True);ap.add_argument('--z-dir',type=Path)
    ap.add_argument('--require-rehearsal',action='store_true');ap.add_argument('--require-z',action='store_true')
    a=ap.parse_args();result=audit(a.output_dir,a.m_dir,a.z_dir,a.require_rehearsal,a.require_z)
    print(json.dumps(result,indent=2));
    if not result['pass']:raise SystemExit(2)
if __name__=='__main__':main()
