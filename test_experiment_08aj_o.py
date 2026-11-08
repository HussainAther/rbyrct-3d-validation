"""08AJ-O contract, gate, recovery and integrity regression tests."""
import json
import pytest
from experiment_08aj_m import SOURCE_FILES,prepare as m_prepare
from experiment_08aj_o import prepare,check,simulate_recovery,canonical
from experiment_08aj_o_audit import audit

@pytest.fixture
def source_fixture(tmp_path):
    source=tmp_path/'source';source.mkdir()
    for n in SOURCE_FILES:(source/n).write_text('test-only '+n+'\n')
    m=tmp_path/'M';m_prepare(m,code_root=source)
    # For O tests, patch M code hash lookup to the fixture source; do not alter M evidence.
    import experiment_08aj_m as mod
    original=mod.code_hashes
    mod.code_hashes=lambda code_root=None:original(source)
    try:yield m,source
    finally:mod.code_hashes=original

def test_prepare_and_gate(tmp_path,source_fixture):
    m,_=source_fixture;o=tmp_path/'O';status=prepare(o,m)
    assert status['jobs']==480 and status['execution_allowed'] is False
    c,_=check(o,m)
    assert c['gate']['production_executor_implemented'] is False
    # Auditor default code path points to test modules; separate M auditor is tested in its own suite.

def test_overwrite_refused(tmp_path,source_fixture):
    m,_=source_fixture;o=tmp_path/'O';prepare(o,m)
    with pytest.raises(FileExistsError):prepare(o,m)

def test_recovery_and_reuse(tmp_path,source_fixture):
    m,_=source_fixture;o=tmp_path/'O';prepare(o,m)
    with pytest.raises(RuntimeError):simulate_recovery(o,m,stop_after=0)
    result=simulate_recovery(o,m)
    assert result['created']==2 and result['reused']==1
    assert simulate_recovery(o,m)['reused']==3

def test_tamper_receipt_refused(tmp_path,source_fixture):
    m,_=source_fixture;o=tmp_path/'O';prepare(o,m);simulate_recovery(o,m)
    p=o/'recovery_fixture'/'operational_0.json';p.write_bytes(b'corrupt')
    with pytest.raises(ValueError):simulate_recovery(o,m)

def test_tamper_gate_refused(tmp_path,source_fixture):
    m,_=source_fixture;o=tmp_path/'O';prepare(o,m)
    p=o/'integration_contract.json';x=json.loads(p.read_bytes());x['gate']['execution_allowed']=True
    p.write_bytes(canonical(x))
    with pytest.raises(ValueError):check(o,m)

def test_m_source_tamper_refused(tmp_path,source_fixture):
    m,source=source_fixture;o=tmp_path/'O';prepare(o,m)
    (source/'experiment_04b.py').write_text('modified')
    with pytest.raises(ValueError):check(o,m)

def test_auditor_requires_n(tmp_path,source_fixture,monkeypatch):
    m,source=source_fixture;o=tmp_path/'O';prepare(o,m)
    import experiment_08aj_o_audit as a
    monkeypatch.setattr(a,'audit_m',lambda *args,**kwargs:{'pass':True,'errors':[]})
    assert not audit(o,m,require_n=True)['pass']
    assert audit(o,m)['pass']

def test_auditor_detects_receipt_tampering(tmp_path,source_fixture,monkeypatch):
    m,source=source_fixture;o=tmp_path/'O';prepare(o,m);simulate_recovery(o,m)
    import experiment_08aj_o_audit as a
    monkeypatch.setattr(a,'audit_m',lambda *args,**kwargs:{'pass':True,'errors':[]})
    assert audit(o,m,require_recovery=True)['pass']
    p=o/'recovery_fixture'/'operational_1.json';x=json.loads(p.read_bytes());x['numerical']=True
    p.write_bytes(canonical(x))
    assert not audit(o,m)['pass']

