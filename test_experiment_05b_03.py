"""Small, deterministic 05B-03 matched-prefix safety checks."""
import csv
import json
import numpy as np
import pytest
from experiment_05b_03 import main


def test_matched_prefix_replays_and_writes_metrics(tmp_path):
    out = tmp_path/'pilot'
    result = main(['--size','4','--angles','2','--factor','2',
                   '--phantoms','branches','--representations','replicated',
                   '--seeds','271828','--budget','24','--warm-rays','12',
                   '--batch','4','--candidate-pool','8','--switches','16',
                   '--provisional-epochs','2','--diagnostic-epochs','2',
                   '--mart-epochs','4','--mart-relaxation','.25',
                   '--output-dir',str(out)])
    assert len(result) == 2
    assert {row['source_policy'] for row in result} == {'adaptive','off'}
    assert all(np.isfinite(row['heldout_nrmse']) for row in result)
    assert all(np.isfinite(row['gain_feedback']) for row in result)
    assert all(0 <= row['continuation_set_divergence'] <= 1 for row in result)
    with (out/'matched_prefix_diagnostics.csv').open(newline='',encoding='utf8') as f:
        assert len(list(csv.DictReader(f))) == 2
    assert json.loads((out/'protocol.json').read_text())['parameters']['mart_relaxation']==.25


def test_invalid_switch_boundary_is_rejected(tmp_path):
    with pytest.raises(SystemExit):
        main(['--size','4','--angles','2','--budget','24','--warm-rays','12',
              '--batch','4','--switches','15','--output-dir',str(tmp_path/'bad')])
