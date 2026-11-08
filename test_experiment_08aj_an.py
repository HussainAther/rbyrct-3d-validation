"""AN control/integrity tests. Stubbed numerical fixtures: not production certification."""
import sys,types,importlib
from pathlib import Path
import numpy as np
import pytest
from scipy.sparse import csr_matrix

# The source project provides these imports on the user's machine. This light
# harness permits local control tests when the source project is unavailable.
def stub(name,**attributes):
    if name in sys.modules:return
    try:
        importlib.import_module(name)
        return
    except ModuleNotFoundError:
        module=types.ModuleType(name)
        for k,v in attributes.items():setattr(module,k,v)
        sys.modules[name]=module
stub('experiment_08aj_aa',POLICIES=('information_diag','uniform_multiscale','coverage','stratified_random_04h','complete_view'),MODELS=('same','independent'))
stub('experiment_08aj_af',canonical=lambda x:(__import__('json').dumps(x,sort_keys=True,separators=(',',':'))+'\n').encode(),sha_file=lambda p:__import__('hashlib').sha256(Path(p).read_bytes()).hexdigest(),load_json=lambda p:__import__('json').loads(Path(p).read_bytes()),create=lambda p,b:Path(p).write_bytes(b),save=lambda p,x:np.save(p,x),cfg=lambda n:{'n':n,'budget':128 if n==8 else 2048,'warm':8 if n==8 else 64,'epochs':2 if n==8 else 16,'relaxation':.25},SEED=971337)
stub('experiment_08aj_ah',atomic_dir=None,enforce_memory_cap=lambda x:None)
stub('experiment_08aj_ad',step_row=None)
stub('experiment_04b',system_matrix=None)
stub('experiment_04g',TILTS=[0,1,2,3])
stub('experiment_08aj_e',full_resolution_pair=None,model_measurements=None)
stub('experiment_08aj_g',fair_orders=None)
stub('experiment_08aj_k_audit',independent_mart=None)
import experiment_08aj_an as an
import experiment_08aj_an_audit as audit

@pytest.fixture
def fx(monkeypatch,tmp_path):
    # Tiny, deterministic noncohort fixture with numerical matrix semantics.
    monkeypatch.setattr(an,'protected',lambda *args:('aa-hash','spec-hash'))
    monkeypatch.setattr(an,'src_sha',lambda:{'executor':'locked','auditor':'locked'})
    monkeypatch.setattr(an,'system_matrix',lambda n,angles,tilts:csr_matrix((np.ones(768), (np.arange(768),np.arange(768)%512)),shape=(768,512)))
    monkeypatch.setattr(an,'full_resolution_pair',lambda family,seed,n:(np.full(n**3,0.3+(seed%17)*.01),np.full(n**3,0.3+(seed%17)*.01)))
    monkeypatch.setattr(an,'model_measurements',lambda A,truth,fine,n,angles,model,noise_seed,noise_fraction:(A@truth,(A@truth)+np.random.default_rng(noise_seed).normal(0,.001,size=A.shape[0])))
    def orders(A,n,angles,seed,budget,warm,pool,batch):
        common=np.arange(warm)
        out={}
        for i,pol in enumerate(an.POLICIES):
            if pol=='complete_view':out[pol]=np.concatenate([np.arange(64),np.arange(128,192)])
            else:
                rng=np.random.default_rng(seed+11*i)
                poolv=np.arange(warm,768)
                rng.shuffle(poolv)
                out[pol]=np.r_[common,poolv[:budget-warm]]
        return out,{}
    monkeypatch.setattr(an,'fair_orders',orders)
    def atomic(parent,name,files):
        p=Path(parent)/name
        p.mkdir()
        for filename,content in files.items():(p/filename).write_bytes(content)
        return p
    monkeypatch.setattr(an.ah,'atomic_dir',atomic)
    def step(x,A,y,r,relax):
        row=A.getrow(r)
        if row.nnz:
            indices=row.indices
            x[indices]=x[indices]+relax*(y[r]-x[indices])
    monkeypatch.setattr(an.ad,'step_row',step)
    monkeypatch.setattr(audit,'independent_mart',lambda A,y,epochs,relaxation:independent(A,y,epochs,relaxation,step))
    root=tmp_path/'an'
    return root

def independent(A,y,epochs,relax,step):
    x=np.full(A.shape[1],.3)
    for i in range(epochs*A.shape[0]):step(x,A,y,i%A.shape[0],relax)
    return x

def test_structure():
    assert len(an.OBJECTS)==2 and len(an.ACQUISITIONS)==2
    assert len(an.POLICIES)==5 and len(an.MODELS)==2
    assert len({an.noise_seed(o,a,m) for o in an.OBJECTS for a in an.ACQUISITIONS for m in an.MODELS})==8

def test_seed_reproducible():
    assert an.noise_seed('engineering_alpha','seed_a','same')==an.noise_seed('engineering_alpha','seed_a','same')
    assert an.noise_seed('engineering_alpha','seed_a','same')!=an.noise_seed('engineering_alpha','seed_b','same')

def test_reject_arbitrary_object_acquisition_policy():
    with pytest.raises(ValueError):an.group_name('unknown','seed_a','same')
    with pytest.raises(ValueError):an.group_name('engineering_alpha','prospective','same')
    with pytest.raises(ValueError):an.job_name('engineering_alpha','seed_a','same','unknown')

def test_plan_has_hard_gates(fx):
    r=an.init(fx,None,None,8)
    assert r['jobs']==40 and r['shared_groups']==8
    p=an.check(fx,None,None)
    assert p['production_execution_allowed'] is False and p['scientific_signoff'] is False
    assert p['production_480_job_certified'] is False

def test_refuse_duplicate_init(fx):
    an.init(fx,None,None,8)
    with pytest.raises(FileExistsError):an.init(fx,None,None,8)

def test_distinct_object_truth_and_shared_across_seeds(fx):
    an.init(fx,None,None,8)
    for o in an.OBJECTS:
        for a in an.ACQUISITIONS:
            an.catalogue(fx,None,None,o,a,'same')
    rr=[an.read(fx/'groups'/an.group_name(o,a,'same')/'receipt.json') for o in an.OBJECTS for a in an.ACQUISITIONS]
    assert rr[0]['truth_sha256']==rr[1]['truth_sha256']
    assert rr[0]['truth_sha256']!=rr[2]['truth_sha256']
    assert len({r['noisy_sha256'] for r in rr})==4

def test_group_reuse_and_tamper_rejected(fx):
    an.init(fx,None,None,8)
    an.catalogue(fx,None,None,'engineering_alpha','seed_a','same')
    assert an.catalogue(fx,None,None,'engineering_alpha','seed_a','same')['verdict']=='AN_SHARED_GROUP_REUSED'
    g=fx/'groups'/an.group_name('engineering_alpha','seed_a','same')
    with (g/'noisy.npy').open('ab') as f:f.write(b'change')
    with pytest.raises(ValueError):an.group_inputs(fx,None,None,'engineering_alpha','seed_a','same')

def test_dispatch_and_resume_numeric(fx):
    an.init(fx,None,None,8)
    an.catalogue(fx,None,None,'engineering_alpha','seed_a','same')
    an.prepare_job(fx,None,None,'engineering_alpha','seed_a','same','information_diag')
    pause=an.worker(fx,None,None,'engineering_alpha','seed_a','same','information_diag',33)
    assert pause['rows_done']==33
    assert an.verify_job(fx,None,None,'engineering_alpha','seed_a','same','information_diag')[5]==33
    done=an.worker(fx,None,None,'engineering_alpha','seed_a','same','information_diag')
    assert done['rows_done']==256
    result=audit.audit_one(fx,None,None,'engineering_alpha','seed_a','same','information_diag')
    assert result['pass'] and result['max_abs_replay_error']==0

def test_cross_job_checkpoint_rejection(fx):
    an.init(fx,None,None,8)
    an.catalogue(fx,None,None,'engineering_alpha','seed_a','same')
    for pol in ('information_diag','uniform_multiscale'):
        an.prepare_job(fx,None,None,'engineering_alpha','seed_a','same',pol)
    an.worker(fx,None,None,'engineering_alpha','seed_a','same','information_diag',17)
    d=fx/'jobs'/an.job_name('engineering_alpha','seed_a','same','information_diag')/'checkpoints'/'cp_00000017'
    e=fx/'jobs'/an.job_name('engineering_alpha','seed_a','same','uniform_multiscale')/'checkpoints'/'cp_00000017'
    import shutil
    shutil.copytree(d,e)
    with pytest.raises(ValueError):an.verify_job(fx,None,None,'engineering_alpha','seed_a','same','uniform_multiscale')

def test_common_prefix_and_complete_view_exception(fx):
    an.init(fx,None,None,8)
    an.catalogue(fx,None,None,'engineering_alpha','seed_a','same')
    for pol in an.POLICIES:an.prepare_job(fx,None,None,'engineering_alpha','seed_a','same',pol)
    orders={p:np.load(fx/'jobs'/an.job_name('engineering_alpha','seed_a','same',p)/'order.npy') for p in an.POLICIES}
    for p in an.POLICIES:
        if p!='complete_view':assert np.array_equal(orders[p][:8],orders['information_diag'][:8])
    assert len(orders['complete_view'])==128

def test_auditor_partial(fx):
    an.init(fx,None,None,8)
    an.catalogue(fx,None,None,'engineering_alpha','seed_a','same')
    an.prepare_job(fx,None,None,'engineering_alpha','seed_a','same','information_diag')
    an.worker(fx,None,None,'engineering_alpha','seed_a','same','information_diag')
    assert audit.audit(fx,None,None)['pass']
    incomplete=audit.audit(fx,None,None,True)
    assert not incomplete['pass'] and 'require-complete' in str(incomplete['errors'])

def test_auditor_detects_changed_order(fx):
    an.init(fx,None,None,8)
    an.catalogue(fx,None,None,'engineering_alpha','seed_a','same')
    an.prepare_job(fx,None,None,'engineering_alpha','seed_a','same','information_diag')
    p=fx/'jobs'/an.job_name('engineering_alpha','seed_a','same','information_diag')/'order.npy'
    x=np.load(p);x[0]=700;np.save(p,x)
    assert not audit.audit_one(fx,None,None,'engineering_alpha','seed_a','same','information_diag')['pass']

def test_plan_source_drift_rejected(fx,monkeypatch):
    an.init(fx,None,None,8)
    monkeypatch.setattr(an,'src_sha',lambda:{'executor':'changed','auditor':'locked'})
    with pytest.raises(ValueError,match='drift'):an.check(fx,None,None)

def test_production_modes_rejected_by_parser():
    assert {'production-run','unlock','freeze'} <= {'production-run','unlock','freeze'}
    # The CLI rejects all three prior to any dispatch; no 'enable' function exists.
    assert not hasattr(an,'enable_production')

def test_full_forty_job_stubbed_engineering_rehearsal(fx):
    an.init(fx,None,None,8)
    for o in an.OBJECTS:
        for a in an.ACQUISITIONS:
            for m in an.MODELS:
                an.catalogue(fx,None,None,o,a,m)
                for pol in an.POLICIES:
                    an.prepare_job(fx,None,None,o,a,m,pol)
                    result=an.worker(fx,None,None,o,a,m,pol)
                    assert result['verdict']=='AN_ENGINEERING_JOB_PASS'
    result=audit.audit(fx,None,None,require_complete=True)
    assert result['pass'],result['errors']
    assert result['engineering_jobs_audited']==40
    assert result['shared_groups_audited']==8
    assert all(x['max_abs_replay_error']==0 for x in result['details'])

def test_cli_rejects_production_modes(monkeypatch,fx,capsys):
    import runpy
    for mode in ('production-run','unlock','freeze'):
        monkeypatch.setattr(sys,'argv',['experiment_08aj_an.py','--mode',mode,'--output-dir',str(fx),
            '--aa-dir','placeholder','--m-dir','placeholder'])
        with pytest.raises(SystemExit) as exc:runpy.run_module('experiment_08aj_an',run_name='__main__')
        assert exc.value.code==2
    assert 'PROSPECTIVE_EXECUTION_DISABLED' in capsys.readouterr().err


def test_two_fresh_engineering_regenerations_agree(fx):
    """Stubbed 8-cubed engineering reproducibility regression.

    Both runs generate their own plans, catalogues, acquisition
    orders, reconstruction checkpoints, and final evidence.
    This is not real-physics or prospective certification.
    """
    object_name = "engineering_alpha"
    acquisition = "seed_a"
    model = "same"
    policies = ("complete_view", "information_diag")

    roots = (fx, fx.parent / "an_repeat")

    for root in roots:
        result = an.init(root, None, None, 8)
        assert result["production_execution_allowed"] is False

        result = an.catalogue(
            root, None, None,
            object_name, acquisition, model,
        )
        assert result["verdict"] == "AN_SHARED_GROUP_PREPARED"

        for policy in policies:
            dispatched = an.prepare_job(
                root, None, None,
                object_name, acquisition, model, policy,
            )
            assert dispatched["verdict"] == "AN_JOB_DISPATCHED"

            finished = an.worker(
                root, None, None,
                object_name, acquisition, model, policy,
            )
            assert finished["verdict"] == "AN_ENGINEERING_JOB_PASS"
            assert finished["production_execution_allowed"] is False

        report = audit.audit(root, None, None)
        assert report["pass"], report["errors"]
        assert report["engineering_jobs_audited"] == 2
        assert report["shared_groups_audited"] == 1
        assert report["production_jobs_executed"] == 0
        assert report["production_execution_allowed"] is False

    group = an.group_name(object_name, acquisition, model)

    for filename in ("clean.npy", "noisy.npy"):
        original = roots[0] / "groups" / group / filename
        repeated = roots[1] / "groups" / group / filename
        assert original.read_bytes() == repeated.read_bytes()

    for policy in policies:
        job = an.job_name(object_name, acquisition, model, policy)

        first = roots[0] / "jobs" / job
        second = roots[1] / "jobs" / job

        assert (
            first / "order.npy"
        ).read_bytes() == (
            second / "order.npy"
        ).read_bytes()

        a = np.load(first / "final/reconstruction.npy", allow_pickle=False)
        b = np.load(second / "final/reconstruction.npy", allow_pickle=False)

        assert a.shape == b.shape
        assert np.isfinite(a).all() and np.isfinite(b).all()
        assert float(np.max(np.abs(a - b))) <= 1e-11

        r1 = an.read(first / "final/receipt.json")
        r2 = an.read(second / "final/receipt.json")

        assert abs(r1["rmse"] - r2["rmse"]) <= 1e-12
        assert r1["production_execution_allowed"] is False
        assert r2["production_execution_allowed"] is False

