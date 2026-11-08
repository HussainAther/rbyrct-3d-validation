"""08AJ-AF controlled tests; fixtures are tiny synthetic numeric engineering stubs."""
from __future__ import annotations
import json,sys,types
from pathlib import Path
import numpy as np
import pytest
from scipy.sparse import csr_matrix
import experiment_08aj_af as af
import experiment_08aj_af_audit as auditor

@pytest.fixture
def demo(tmp_path,monkeypatch):
    roster=[]
    for model in af.aa.MODELS:
        for policy in af.aa.POLICIES:
            for j in range(48):
                roster.append({'object_seed':j+100,'acquisition_seed':940411 if j%2==0 else 940829,
                   'execution_allowed':False,'execution_status':'BLOCKED_NOT_EXECUTED','model':model,'policy':policy})
    aa_dir=tmp_path/'aa';aa_dir.mkdir();(aa_dir/'job_specifications.json').write_bytes(af.canonical(roster))
    monkeypatch.setattr(af.aa,'check',lambda *a:({'confirmatory_execution_allowed':False},'test-aa-sha',{str(i):[] for i in range(96)}))
    n=8;nr=12*n*n;nv=n**3
    row=np.arange(nr);col=(row*7)%nv
    matrix=csr_matrix((np.ones(nr,dtype=float),(row,col)),shape=(nr,nv))
    monkeypatch.setattr(af,'system_matrix',lambda *a,**kw:matrix)
    monkeypatch.setattr(af,'TILTS',(0,1,2))
    def make_truth(family,seed,n):
        assert seed==af.SEED and family==af.FAMILY
        tr=np.linspace(.2,.8,n**3)
        return tr,np.ones((2*n,)*3)
    monkeypatch.setattr(af,'full_resolution_pair',make_truth)
    def make_meas(A,truth,fine,*,n,angles,model,noise_seed,noise_fraction):
        clean=np.asarray(A@truth)
        if model=='independent':clean=clean+0.04
        noise=np.random.default_rng(noise_seed).normal(0,.0003,len(clean))
        return clean,np.maximum(clean+noise,0)
    monkeypatch.setattr(af,'model_measurements',make_meas)
    def make_orders(A,*,n,angles,seed,budget,warm,pool,batch):
        base=np.arange(warm)
        policies={}
        for i,p in enumerate(af.aa.POLICIES):
            ids=np.concatenate([base,np.arange(warm+i*budget,warm+i*budget+(budget-warm))])
            if p=='complete_view':ids=np.arange(512,512+budget)
            policies[p]=ids.astype(np.int64)
        return policies,{}
    monkeypatch.setattr(af,'fair_orders',make_orders)
    monkeypatch.setattr(auditor,'fair_orders',make_orders)
    def mart(A,y,epochs,relaxation):
        x=np.full(A.shape[1],.3)
        for epoch in range(epochs):
            for i in range(A.shape[0]):
                sl=A.getrow(i)
                if sl.nnz==0:continue
                cols=sl.indices;w=sl.data
                ratio=max(float(y[i]),1e-10)/max(float(np.dot(w,x[cols])),1e-10)
                x[cols]=np.maximum(x[cols]*np.exp(np.clip(relaxation*w/w.max()*np.log(max(ratio,1e-10)),-12,12)),1e-10)
        return x
    monkeypatch.setattr(af,'checked_mart',lambda A,noisy,order,epochs,relaxation:mart(A[order],noisy[order],epochs,relaxation))
    monkeypatch.setattr(auditor,'independent_mart',mart)
    out=tmp_path/'af';m=tmp_path/'m';m.mkdir()
    return out,aa_dir,m

def setup_group(demo,model='same'):
    out,aa_dir,m=demo
    af.initialize(out,aa_dir,m,8)
    af.build_group(out,aa_dir,m,model)
    return demo

def test_plan_production_lock(demo):
    out,a,m=demo;r=af.initialize(out,a,m,8)
    assert r['production_execution_allowed'] is False
    assert af.check(out,a,m)['production_jobs_executed']==0

def test_fresh_seed_overlap_rejected(demo):
    out,a,m=demo
    rows=af.load_json(a/'job_specifications.json');rows[0]['object_seed']=af.SEED
    (a/'job_specifications.json').write_bytes(af.canonical(rows))
    with pytest.raises(ValueError,match='overlaps'):af.initialize(out,a,m,8)

def test_group_reuse_and_regeneration(demo):
    out,a,m=setup_group(demo)
    assert af.build_group(out,a,m,'same')['verdict']=='AF_SHARED_CATALOGUE_REUSED'
    assert len(af.validate_group(out,a,m,'same')[3])==768

def test_group_tampering_rejected(demo):
    out,a,m=setup_group(demo)
    data=out/'groups'/'same'/'noisy.npy';data.write_bytes(data.read_bytes()+b'0')
    with pytest.raises(ValueError):af.validate_group(out,a,m,'same')

def test_new_job_and_independent_replay(demo):
    out,a,m=setup_group(demo)
    r=af.execute(out,a,m,'information_diag','same')
    assert r['verdict']=='AF_FRESH_ENGINEERING_JOB_PASS'
    audit=auditor.audit(out,a,m)
    assert audit['pass'],audit['errors']
    assert audit['details'][0]['max_abs_replay_error']==0

def test_reuse_does_not_overwrite(demo):
    out,a,m=setup_group(demo);af.execute(out,a,m,'information_diag','same')
    receipt=out/'jobs'/'information_diag__same'/'receipt.json';old=receipt.read_bytes()
    assert af.execute(out,a,m,'information_diag','same')['verdict']=='AF_ENGINEERING_JOB_REUSED'
    assert receipt.read_bytes()==old

def test_job_tamper_rejected(demo):
    out,a,m=setup_group(demo);af.execute(out,a,m,'information_diag','same')
    target=out/'jobs'/'information_diag__same'/'reconstruction.npy';target.write_bytes(target.read_bytes()+b'X')
    assert not auditor.audit(out,a,m)['pass']
    with pytest.raises(ValueError,match='failed independent audit'):af.execute(out,a,m,'information_diag','same')

def test_shared_models_and_policies(demo):
    out,a,m=setup_group(demo)
    af.build_group(out,a,m,'independent')
    for model in af.aa.MODELS:
        for policy in af.aa.POLICIES:af.execute(out,a,m,policy,model)
    result=auditor.audit(out,a,m,require_complete=True)
    assert result['pass'],result['errors']
    assert result['audited_engineering_jobs']==10
    assert result['shared_catalogues_audited']==2

def test_missing_job_full_audit_rejected(demo):
    out,a,m=setup_group(demo);af.execute(out,a,m,'coverage','same')
    r=auditor.audit(out,a,m,require_complete=True)
    assert not r['pass']

def test_bad_policy_or_model_rejected(demo):
    out,a,m=setup_group(demo)
    with pytest.raises(ValueError):af.execute(out,a,m,'unlocked','same')
    with pytest.raises(ValueError):af.execute(out,a,m,'coverage','unlocked')
