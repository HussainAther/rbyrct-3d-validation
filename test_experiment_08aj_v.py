import json
import numpy as np
import pytest
from experiment_08aj_v import (SCENARIOS, METHODS, generate_gain_sample, intervals,
                                stratified_se, calibrate, report, main, sha)


def test_generators_shapes():
    rng = np.random.default_rng(12)
    for name in SCENARIOS:
        x = generate_gain_sample(rng, name, .02, .03)
        assert x.shape == (3, 8) and np.all(np.isfinite(x))


def test_unknown_generator_rejected():
    with pytest.raises(ValueError):
        generate_gain_sample(np.random.default_rng(1), 'bad', .02, .03)


def test_se_equal_variance_formula():
    x = np.tile(np.arange(8, dtype=float), (3, 1))
    expected = np.sqrt(np.var(x[0], ddof=1) / 24)
    assert np.isclose(stratified_se(x), expected)


def test_interval_structure_and_bounds():
    x = np.random.default_rng(2).normal(.02, .03, (3, 8))
    results = intervals(x, bootstrap_count=300, rng=np.random.default_rng(3))
    assert set(results) == set(METHODS)
    for lo, hi in results.values():
        assert np.isfinite(lo) and np.isfinite(hi) and lo < hi


def test_seeded_determinism_and_no_overfit():
    kwargs = dict(trials=50, bootstrap_count=200, scenarios=('normal_equal',), sds=(.03,), means=(.02,))
    assert calibrate(seed=47, **kwargs) == calibrate(seed=47, **kwargs)


def test_sensitivity_is_not_outcomes():
    out = report(trials=50, bootstrap_count=200)
    assert len(out['rows']) == 4 * 3 * 3 * 4
    assert out['no_confirmatory_outcomes'] and not out['frozen']
    assert not out['confirmatory_execution_allowed'] and not out['scientific_signoff']
    assert out['interpretation']['method_selection'].startswith('NO_METHOD_APPROVED')


def test_overwrite_refusal(tmp_path):
    p = tmp_path / 'existing'; p.mkdir()
    with pytest.raises(FileExistsError):
        main(['--output-dir', str(p), '--trials', '50', '--bootstraps', '200'])


def test_cli_artifact_hash(tmp_path):
    p = tmp_path / 'v'
    main(['--output-dir', str(p), '--trials', '50', '--bootstraps', '200'])
    raw = (p / 'statistical_calibration_evidence.json').read_bytes()
    status = json.loads((p / 'run_status.json').read_text())
    assert status['calibration_sha256'] == sha(raw)
    assert status['settings'] == 144 and not status['method_approved']


def test_independent_auditor_pass_and_hash_failure(tmp_path):
    from experiment_08aj_v_audit import audit
    p=tmp_path/'audit'
    main(['--output-dir',str(p),'--trials','50','--bootstraps','200'])
    assert audit(p)['pass']
    evidence=p/'statistical_calibration_evidence.json'
    evidence.write_bytes(evidence.read_bytes()+b' ')
    assert not audit(p)['pass']
