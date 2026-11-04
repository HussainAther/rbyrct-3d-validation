"""08M lock, prospective-unit aggregation, source integrity, and non-overwrite tests."""
import json
from pathlib import Path
import numpy as np
import pytest
import experiment_08m as m


def test_protocol_is_prespecified():
    p=m.protocol()
    assert p['schema']=='RBYRCT-08M-LOCK-v1'
    assert p['primary']['budget']==2048
    assert p['primary']['policy']=='information_diag'
    assert p['primary']['unit'].startswith('independent phantom')
    assert p['configs']['32']['checkpoints']==(1024,2048,4096) or p['configs']['32']['checkpoints']==[1024,2048,4096]


def test_eight_new_objects_and_two_acquisition_seeds():
    assert len(m.OBJECT_SEEDS[32])==len(set(m.OBJECT_SEEDS[32]))==8
    assert len(m.ACQUISITION_SEEDS)==len(set(m.ACQUISITION_SEEDS))==2
    m.validate((32,),m.OBJECT_SEEDS,m.CONFIGS,m.MODELS,m.ACQUISITION_SEEDS)
    assert len(m.POLICIES)==4 and len(m.MODELS)==2


def test_lock_roundtrip_and_no_overwrite(tmp_path):
    path=tmp_path/'locked.json'
    frozen=m.freeze(path)
    assert m.verify_lock(path)==frozen
    with pytest.raises(FileExistsError):m.freeze(path)


def test_lock_refuses_changed_primary(tmp_path):
    path=tmp_path/'locked.json'
    data=m.freeze(path)
    data['primary']['budget']=1024
    path.write_text(json.dumps(data))
    with pytest.raises(RuntimeError,match='primary'):m.verify_lock(path)


def test_lock_refuses_changed_code_hash(tmp_path):
    path=tmp_path/'locked.json'
    data=m.freeze(path)
    data['source_hashes']['experiment_08k']='0'*64
    path.write_text(json.dumps(data))
    with pytest.raises(RuntimeError,match='source_hashes'):m.verify_lock(path)


def test_missing_lock_prevents_run_and_output_creation(tmp_path):
    output=tmp_path/'forbidden'
    with pytest.raises(FileNotFoundError):m.run(output,lock_path=tmp_path/'missing.json')
    assert not output.exists()


def test_object_balancing_not_pseudoreplication():
    rows=[]
    for obj,gain in [('first',.2),('second',-.1)]:
        for seed in (1,2):
            for model in m.MODELS:
                for policy in m.POLICIES:
                    rows.append(dict(size=32,object_id=obj,acquired=2048,policy=policy,
                                     model=model,acquisition_seed=seed,
                                     gain_vs_coverage=gain if policy=='information_diag' else 0,
                                     defect_gain_vs_coverage=2*gain if policy=='information_diag' else 0,
                                     nondefect_gain_vs_coverage=0.))
    summary=m.object_summary(rows)
    info=[x for x in summary if x['policy']=='information_diag']
    assert len(info)==2 and all(x['n_conditions']==4 for x in info)
    assert np.isclose(np.mean([x['mean_global_gain'] for x in info]),.05)


def test_duplicate_condition_cannot_inflate_object_weight():
    rows=[]
    for policy in m.POLICIES:
        rows.append(dict(size=32,object_id='a',acquired=2048,policy=policy,
          model='same',acquisition_seed=7,gain_vs_coverage=0,
          defect_gain_vs_coverage=0,nondefect_gain_vs_coverage=0))
    rows.append(rows[-1].copy())
    with pytest.raises(ValueError,match='duplicated'):m.object_summary(rows)


def test_missing_pair_rejected():
    rows=[]
    for policy in m.POLICIES[:-1]:
        rows.append(dict(size=32,object_id='a',acquired=2048,policy=policy,
          model='same',acquisition_seed=7,gain_vs_coverage=0,
          defect_gain_vs_coverage=0,nondefect_gain_vs_coverage=0))
    with pytest.raises(ValueError):m.object_summary(rows)


def test_information_selector_is_exact_08k_function():
    from experiment_08k import select_information
    assert m.select_information is select_information


def test_lock_requires_all_sources(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'SOURCE_MODULES',('missing_module_for_08m_audit_123456',))
    with pytest.raises(FileNotFoundError,match='missing source'):m.freeze(tmp_path/'lock.json')
    assert not (tmp_path/'lock.json').exists()
