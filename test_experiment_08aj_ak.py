from pathlib import Path
import json
import pytest
import experiment_08aj_ak as ak
import experiment_08aj_ak_audit as auditor

@pytest.fixture
def mock_sources(monkeypatch,tmp_path):
    af=tmp_path/'af';aa=tmp_path/'aa';m=tmp_path/'m'
    for x in (af,aa,m):x.mkdir()
    def fake_expected(*args):
        return {'schema':ak.SCHEMA,'namespace':'LOCKED_ENGINEERING_SHADOW_ONLY',
          'entries':[{'job_id':p+'__'+model,'policy':p,'model':model} for model in ak.MODELS for p in ak.POLICIES],
          'shadow_jobs':4,'production_execution_allowed':False,'no_confirmatory_outcomes':True}
    monkeypatch.setattr(ak,'expected',fake_expected)
    monkeypatch.setattr(ak.ah,'init',lambda root,*args: (Path(root).mkdir(),(Path(root)/'plan.json').write_text('fixture')))
    monkeypatch.setattr(ak.ah,'verify',lambda *args: ({'source':{'policy':args[0].parent.name.split('__')[0],
        'model':args[0].parent.name.split('__')[1]}},None,0,None,None))
    monkeypatch.setattr(ak.ah,'supervise',lambda *args: {'verdict':'AH_ENGINEERING_PAUSED','rows_done':128})
    return tmp_path/'output',af,aa,m

def test_prepare_and_check(mock_sources):
    root,*dirs=mock_sources
    assert ak.prepare(root,*dirs)['engineering_jobs']==4
    assert len(ak.check(root,*dirs)['entries'])==4

def test_duplicate_preserves(mock_sources):
    root,*dirs=mock_sources;ak.prepare(root,*dirs)
    with pytest.raises(FileExistsError):ak.prepare(root,*dirs)

def test_dispatch_and_reuse(mock_sources):
    root,*dirs=mock_sources;ak.prepare(root,*dirs)
    assert ak.dispatch(root,*dirs,'information_diag','same')['verdict']=='AK_ENGINEERING_JOB_DISPATCHED'
    assert ak.dispatch(root,*dirs,'information_diag','same')['verdict']=='AK_ENGINEERING_DISPATCH_REUSED'

def test_invalid_policy_rejected(mock_sources):
    root,*dirs=mock_sources;ak.prepare(root,*dirs)
    with pytest.raises(ValueError):ak.dispatch(root,*dirs,'production_object','same')

def test_invalid_model_rejected(mock_sources):
    root,*dirs=mock_sources;ak.prepare(root,*dirs)
    with pytest.raises(ValueError):ak.dispatch(root,*dirs,'information_diag','prospective')

def test_source_drift_rejected(mock_sources,monkeypatch):
    root,*dirs=mock_sources;ak.prepare(root,*dirs)
    old=ak.expected
    monkeypatch.setattr(ak,'expected',lambda *args:{**old(*args),'production_execution_allowed':True})
    with pytest.raises(ValueError,match='drift'):ak.check(root,*dirs)

def test_noncanonical_receipt_rejected(mock_sources):
    root,*dirs=mock_sources;ak.prepare(root,*dirs)
    p=root/'plan.json';p.write_text(json.dumps(ak.load(p)))
    with pytest.raises(ValueError,match='noncanonical'):ak.check(root,*dirs)

def test_dispatch_tamper_rejected(mock_sources):
    root,*dirs=mock_sources;ak.prepare(root,*dirs)
    ak.dispatch(root,*dirs,'information_diag','same')
    p=root/'jobs'/'information_diag__same'/'dispatch.json';r=ak.load(p);r['production_execution_allowed']=True
    p.write_bytes(ak.canonical(r))
    with pytest.raises(ValueError,match='dispatch'):ak.check(root,*dirs)

def test_run_requires_dispatch(mock_sources):
    root,*dirs=mock_sources;ak.prepare(root,*dirs)
    with pytest.raises(ValueError,match='dispatch first'):ak.run(root,*dirs,'information_diag','same')

def test_run_pause(mock_sources):
    root,*dirs=mock_sources;ak.prepare(root,*dirs);ak.dispatch(root,*dirs,'information_diag','same')
    assert ak.run(root,*dirs,'information_diag','same')['verdict']=='AK_ENGINEERING_JOB_PAUSED'

def test_partial_audit(mock_sources):
    root,*dirs=mock_sources;ak.prepare(root,*dirs)
    assert auditor.audit(root,*dirs)['pass']
    assert not auditor.audit(root,*dirs,require_complete=True)['pass']

def test_unauthorized_file_rejected(mock_sources):
    root,*dirs=mock_sources;ak.prepare(root,*dirs)
    (root/'jobs'/'prospective_seed').mkdir()
    with pytest.raises(ValueError,match='unexpected'):ak.check(root,*dirs)
