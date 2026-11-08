"""AR control tests use AN stubbed numerical fixture; not production certification."""
from pathlib import Path
import json, shutil
import pytest
from test_experiment_08aj_an import fx as an_fx
import experiment_08aj_an as an
import experiment_08aj_ar as ar
import experiment_08aj_ar_audit as aud

@pytest.fixture
def ctx(monkeypatch,an_fx,tmp_path):
    aa_dir=tmp_path/'aa';aa_dir.mkdir()
    m_dir=tmp_path/'m';m_dir.mkdir()
    specs=[{'object_seed':1000+i} for i in range(480)]
    (aa_dir/'job_specifications.json').write_bytes(ar.canonical(specs))
    monkeypatch.setattr(ar.aa,'check',lambda *_:({'confirmatory_execution_allowed':False},'aa-locked-hash',{str(i):None for i in range(96)}),raising=False)
    root=tmp_path/'ar'
    return root,aa_dir,m_dir

def prepare(c):return ar.prepare(*c,8)
def first():return ar.identifier('engineering_alpha','seed_a','same','information_diag')

def test_fixed_roster():
    items=ar.fixed_roster()
    assert len(items)==40 and len({x['job_id'] for x in items})==40
    assert len({x['group_id'] for x in items})==8
    assert all(x['production_execution_allowed'] is False for x in items)

def test_prepare_and_check(ctx):
    assert prepare(ctx)['jobs']==40
    p=ar.check(*ctx)
    assert p['aa_contract_jobs']==480 and p['production_execution_allowed'] is False

def test_refuse_overwrite(ctx):
    prepare(ctx)
    with pytest.raises(FileExistsError):prepare(ctx)

def test_reject_unlisted_id(ctx):
    prepare(ctx)
    with pytest.raises(ValueError,match='allowlisted'):ar.dispatch(*ctx,'prospective__940411__same__information_diag','catalogue')

def test_manifest_tamper_rejected(ctx):
    prepare(ctx)
    p=ctx[0]/'ar_manifest.json';v=ar.plain(p)
    v['production_execution_allowed']=True
    p.write_bytes(ar.canonical(v))
    with pytest.raises(ValueError,match='manifest'):ar.check(*ctx)

def test_manifest_source_hash_rejected(ctx):
    prepare(ctx)
    p=ctx[0]/'ar_manifest.json';v=ar.plain(p)
    v['source_sha256']['experiment_08aj_ar.py']='0'*64
    p.write_bytes(ar.canonical(v))
    with pytest.raises(ValueError,match='manifest'):ar.check(*ctx)

def test_noncanonical_rejected(ctx):
    prepare(ctx)
    p=ctx[0]/'ar_manifest.json'
    p.write_text(json.dumps(json.loads(p.read_text()),indent=2))
    with pytest.raises(ValueError,match='noncanonical'):ar.check(*ctx)

def test_engineering_numeric_worker_and_audit(ctx):
    prepare(ctx);jid=first()
    assert ar.dispatch(*ctx,jid,'catalogue')['engine_result']['verdict']=='AN_SHARED_GROUP_PREPARED'
    ar.dispatch(*ctx,jid,'dispatch')
    # Direct test of numerical checkpoint worker: real Windows run uses supervised AR run.
    an.worker(ctx[0]/'engine',ctx[1],ctx[2],'engineering_alpha','seed_a','same','information_diag',33)
    an.worker(ctx[0]/'engine',ctx[1],ctx[2],'engineering_alpha','seed_a','same','information_diag')
    r=aud.audit(*ctx)
    assert r['pass'] and r['engineering_jobs_numerically_audited']==1
    assert r['details'][0]['max_abs_replay_error']==0

def test_reject_cross_job_checkpoint(ctx):
    prepare(ctx)
    for policy in ('information_diag','uniform_multiscale'):
        jid=ar.identifier('engineering_alpha','seed_a','same',policy)
        ar.dispatch(*ctx,jid,'catalogue');ar.dispatch(*ctx,jid,'dispatch')
    engine=ctx[0]/'engine'
    an.worker(engine,ctx[1],ctx[2],'engineering_alpha','seed_a','same','information_diag',17)
    source=engine/'jobs'/'engineering_alpha__seed_a__same__information_diag'/'checkpoints'/'cp_00000017'
    dest=engine/'jobs'/'engineering_alpha__seed_a__same__uniform_multiscale'/'checkpoints'/'cp_00000017'
    shutil.copytree(source,dest)
    result=aud.audit(*ctx)
    assert not result['pass']

def test_require_complete_fails_partial(ctx):
    prepare(ctx)
    assert not aud.audit(*ctx,require_complete=True)['pass']

def test_prospective_seed_overlap_rejected(ctx):
    seed=an.OBJECTS['engineering_alpha']['seed']
    p=ctx[1]/'job_specifications.json'
    d=ar.plain(p);d[0]['object_seed']=seed;p.write_bytes(ar.canonical(d))
    with pytest.raises(ValueError,match='overlap'):prepare(ctx)

def test_aa_gate_rejected(ctx,monkeypatch):
    monkeypatch.setattr(ar.aa,'check',lambda *_:({'confirmatory_execution_allowed':True},'hash',{str(i):None for i in range(96)}),raising=False)
    with pytest.raises(ValueError,match='gate drift'):prepare(ctx)


def test_real_numerical_ar_two_object_manifest_dispatch(tmp_path):
    """Real AR dispatch for two noncohort objects with independent replay.

    Subprocesses isolate this test from the existing monkeypatched fixtures.
    No prospective object or production execution is permitted.
    """
    import subprocess
    import sys

    project = Path(__file__).resolve().parent

    m_dir = tmp_path / "m"
    aa_dir = tmp_path / "aa"
    ar_dir = tmp_path / "ar"

    def invoke(script, *args, expect_success=True):
        command = [
            sys.executable,
            str(project / script),
            *[str(x) for x in args],
        ]
        result = subprocess.run(
            command,
            cwd=project,
            capture_output=True,
            text=True,
            timeout=240,
        )
        if expect_success:
            assert result.returncode == 0, (
                f"{command}\\n{result.stdout}\\n{result.stderr}"
            )
        return result

    def output(script, *args):
        return json.loads(invoke(script, *args).stdout)

    output(
        "experiment_08aj_m.py",
        "--mode", "prepare",
        "--output-dir", m_dir,
    )
    output(
        "experiment_08aj_aa.py",
        "--mode", "prepare",
        "--output-dir", aa_dir,
        "--m-dir", m_dir,
    )

    shared = [
        "--output-dir", ar_dir,
        "--aa-dir", aa_dir,
        "--m-dir", m_dir,
    ]

    manifest = output(
        "experiment_08aj_ar.py",
        "--mode", "prepare",
        *shared,
        "--n", 8,
    )
    assert manifest["jobs"] == 40
    assert manifest["production_execution_allowed"] is False

    objects = ("engineering_alpha", "engineering_beta")
    job_ids = []

    for obj in objects:
        jid = f"{obj}__seed_a__same__information_diag"
        job_ids.append(jid)

        for mode in ("catalogue", "dispatch", "run"):
            extra = (
                ["--wall-seconds", 180, "--max-mib", 8192]
                if mode == "run" else []
            )
            result = output(
                "experiment_08aj_ar.py",
                "--mode", mode,
                *shared,
                "--job-id", jid,
                *extra,
            )
            assert result["manifest_job_id"] == jid
            assert result["production_execution_allowed"] is False
            if mode == "run":
                assert result["engine_result"]["verdict"] == (
                    "AN_ENGINEERING_JOB_PASS"
                )
                assert result["engine_result"]["rows_done"] == 256

    engine = ar_dir / "engine"

    receipts = [
        json.loads(
            (
                engine / "groups" / f"{obj}__seed_a__same"
                / "receipt.json"
            ).read_text()
        )
        for obj in objects
    ]
    assert receipts[0]["truth_sha256"] != receipts[1]["truth_sha256"]
    assert receipts[0]["noisy_sha256"] != receipts[1]["noisy_sha256"]

    audit_args = [
        "--output-dir", ar_dir,
        "--aa-dir", aa_dir,
        "--m-dir", m_dir,
    ]

    audit = output("experiment_08aj_ar_audit.py", *audit_args)

    assert audit["pass"] is True, audit["errors"]
    assert audit["engineering_groups_audited"] == 2
    assert audit["engineering_jobs_numerically_audited"] == 2
    assert {d["job_id"] for d in audit["details"]} == set(job_ids)
    assert all(d["pass"] for d in audit["details"])
    assert all(
        d["max_abs_replay_error"] <= 1e-11
        and d["abs_rmse_difference"] <= 1e-12
        for d in audit["details"]
    )

    assert audit["production_jobs_executed"] == 0
    assert audit["production_480_job_certified"] is False
    assert audit["production_execution_allowed"] is False

    # Negative control: corrupt one disposable checkpoint and
    # require the independent auditor to reject the evidence.
    checkpoints = sorted(
        (
            engine / "jobs" / job_ids[0] / "checkpoints"
        ).glob("cp_*")
    )
    assert checkpoints

    state = checkpoints[0] / "state.npy"
    with state.open("ab") as handle:
        handle.write(b"deliberate-test-corruption")

    rejected = invoke(
        "experiment_08aj_ar_audit.py",
        *audit_args,
        expect_success=False,
    )
    assert rejected.returncode != 0

    failure = json.loads(rejected.stdout)
    assert failure["pass"] is False
    assert failure["errors"]
    assert failure["production_execution_allowed"] is False
