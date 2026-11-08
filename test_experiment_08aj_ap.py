import json
from pathlib import Path
import pytest
import experiment_08aj_ap as ap
import experiment_08aj_ap_audit as audit


def save(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(ap.canonical(value))

@pytest.fixture
def setup(tmp_path):
    aa=tmp_path/'aa';an=tmp_path/'an';ao=tmp_path/'ao';a8=tmp_path/'audit8.json';a32=tmp_path/'audit32.json'
    specs=[]
    for o in range(24):
        for seed in (940411,940829):
            for model in ap.MODELS:
                for pol in ap.POLICIES:
                    specs.append({'job_id':f'j{o}_{seed}_{model}_{pol}','family':('a','b','c')[o%3],'object_seed':o+1000,'acquisition_seed':seed,
                                  'model':model,'policy':pol,'shared_catalogue_key':f'g{o}_{seed}_{model}',
                                  'n':32,'ray_budget':2048,'mart_epochs':16,'relaxation':.25,
                                  'warm_prefix':None if pol=='complete_view' else 64,
                                  'acquisition_unit':'full_view' if pol=='complete_view' else 'individual_ray',
                                  'execution_allowed':False,'execution_status':'BLOCKED_NOT_EXECUTED','no_confirmatory_outcomes':True})
    save(aa/'job_specifications.json',specs)
    save(aa/'aa_manifest.json',dict(job_count=480,shared_catalogues=96,spec_sha256=ap.digest(aa/'job_specifications.json'),
         scientific_signoff=False,resource_policy_approved=False,frozen=False,confirmatory_execution_allowed=False,
         production_numerical_certified=False,no_confirmatory_outcomes=True))
    for root,n,expected,apath in ((an,8,40,a8),(ao,32,20,a32)):
        save(root/'plan.json',dict(namespace='MULTI_SEED_FIVE_POLICY_ENGINEERING_ONLY',config={'n':n},engineering_jobs=40,engineering_groups=8,
            policies=list(ap.POLICIES),models=list(ap.MODELS),objects={o:{} for o in ap.OBJECTS},acquisition_seeds={s:0 for s in ap.SEEDS},
            production_execution_allowed=False,production_480_job_certified=False,scientific_signoff=False,resource_policy_approved=False,
            frozen=False,no_confirmatory_outcomes=True,aa_manifest_sha256=ap.digest(aa/'aa_manifest.json'),aa_spec_sha256=ap.digest(aa/'job_specifications.json')))
        names=[f'{o}__{s}__{m}__{p}' for o in ap.OBJECTS for s in ap.SEEDS for m in ap.MODELS for p in ap.POLICIES]
        if n==32:names=[x for x in names if ('engineering_alpha__seed_a__same__' in x or 'engineering_alpha__seed_b__independent__' in x or 'engineering_beta__seed_a__independent__' in x or 'engineering_beta__seed_b__same__' in x)]
        details=[]
        for name in names:
            save(root/'jobs'/name/'final'/'receipt.json',{'job_id':name,'production_execution_allowed':False,'no_confirmatory_outcomes':True,'rows_done':256 if n==8 else 32768})
            details.append({'job_id':name,'pass':True,'errors':[],'max_abs_replay_error':0.0,'abs_rmse_difference':0.0})
        assert len(names)==expected
        save(apath,{'verdict':'AN_INDEPENDENT_MULTI_SEED_AUDIT_PASS','pass':True,'errors':[],
                    'engineering_jobs_audited':expected,'shared_groups_audited':8,'engineering_objects':2,'acquisition_seeds':2,
                    'production_jobs_executed':0,'production_execution_allowed':False,'production_480_job_certified':False,'no_confirmatory_outcomes':True,'details':details})
    return [aa,an,ao,a8,a32]

def test_reconciliation(setup,tmp_path):
    r=ap.inspect(*setup)
    assert r['evidence']['aa_count']==480 and r['gates_blocked']==5
    path=tmp_path/'qualification_report.json';save(path,r)
    assert audit.audit(path)['pass']

@pytest.mark.parametrize('field,value', [('execution_allowed',True),('warm_prefix',65),('ray_budget',1024)])
def test_reject_mutated_spec(setup,field,value):
    p=setup[0]/'job_specifications.json';data=ap.load(p);data[0][field]=value;save(p,data)
    manifest=ap.load(setup[0]/'aa_manifest.json');manifest['spec_sha256']=ap.digest(p);save(setup[0]/'aa_manifest.json',manifest)
    with pytest.raises(ValueError):ap.inspect(*setup)

def test_reject_approval(setup):
    p=setup[0]/'aa_manifest.json';m=ap.load(p);m['resource_policy_approved']=True;save(p,m)
    with pytest.raises(ValueError):ap.inspect(*setup)

def test_reject_missing_audit_job(setup):
    p=setup[4];a=ap.load(p);a['details'].pop();save(p,a)
    with pytest.raises(ValueError):ap.inspect(*setup)

def test_reject_broken_replay(setup):
    p=setup[3];a=ap.load(p);a['details'][0]['max_abs_replay_error']=1e-5;save(p,a)
    with pytest.raises(ValueError):ap.inspect(*setup)

def test_reject_wrong_ao_group(setup):
    p=setup[4];a=ap.load(p);a['details'][0]['job_id']='engineering_alpha__seed_a__independent__information_diag';save(p,a)
    with pytest.raises(ValueError):ap.inspect(*setup)

def test_reject_missing_receipt(setup):
    p=next((setup[2]/'jobs').rglob('receipt.json'));p.unlink()
    with pytest.raises(ValueError):ap.inspect(*setup)

def test_report_structure_rejects_unlock(setup,tmp_path):
    r=ap.inspect(*setup);r['production_execution_allowed']=True
    p=tmp_path/'qualification_report.json';save(p,r)
    assert audit.audit(p)['pass'] is False

def test_reject_aa_link_drift(setup):
    p=setup[1]/'plan.json';r=ap.load(p);r['aa_spec_sha256']='f'*64;save(p,r)
    with pytest.raises(ValueError):ap.inspect(*setup)


def test_accept_machine_precision_replay(setup):
    for path in (setup[3], setup[4]):
        report = ap.load(path)
        report['details'][0]['max_abs_replay_error'] = 1.8e-15
        report['details'][0]['abs_rmse_difference'] = 1e-14
        save(path, report)
    result = ap.inspect(*setup)
    assert result['gates_blocked'] == 5
    assert result['production_execution_allowed'] is False


@pytest.mark.parametrize('bad', [
    None, True, -1e-15, 1e-5
])
def test_reject_invalid_numerical_replay(setup, bad):
    path = setup[4]
    report = ap.load(path)
    report['details'][0]['max_abs_replay_error'] = bad
    save(path, report)
    with pytest.raises(ValueError):
        ap.inspect(*setup)


@pytest.mark.parametrize('bad', [
    None, False, -1e-15, 1e-6
])
def test_reject_invalid_rmse_difference(setup, bad):
    path = setup[4]
    report = ap.load(path)
    report['details'][0]['abs_rmse_difference'] = bad
    save(path, report)
    with pytest.raises(ValueError):
        ap.inspect(*setup)


@pytest.mark.parametrize('bad', [
    float('nan'), float('inf'), float('-inf')
])
@pytest.mark.parametrize('tolerance', [1e-11, 1e-12])
def test_reject_nonfinite_numerical_difference(bad, tolerance):
    assert ap.valid_numerical_difference(bad, tolerance) is False
