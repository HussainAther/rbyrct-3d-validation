"""05B-10 geometry, error-ROI, acquired-only and source-replay tests."""
import csv
import json
from pathlib import Path
import numpy as np
import pytest
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_05b_10 import (coverage_gini, geometry_metrics, error_metrics,
    diagnostic_pool, audit_candidates, read_fingerprints, main)
from experiment_05b_08b import main as source_main
from experiment_05b_09 import main as frozen_main


def test_gini_and_geometry_validations():
    assert coverage_gini([1,1,1,1]) == pytest.approx(0)
    assert coverage_gini([0,0,0,4]) == pytest.approx(.75)
    with pytest.raises(ValueError): coverage_gini([-1,2])
    A=system_matrix(4,2,TILTS).tocsr()
    metrics=geometry_metrics(A,[0,1,2,3],4,2)
    assert 0 <= metrics['touched_fraction'] <= 1
    assert 0 <= metrics['view_entropy'] <= 1
    with pytest.raises(ValueError): geometry_metrics(A,[1,1],4,2)


def test_roi_squared_error_accounting():
    truth=np.linspace(.01,1.,64)
    x=truth.copy(); x[-1]+=2
    data=error_metrics(x,truth)
    assert data['top_quartile_error_share']==pytest.approx(1)
    assert data['remainder_rmse']==pytest.approx(0)
    assert data['rmse']>0
    assert error_metrics(np.ones(64),np.ones(64))['top_quartile_rmse']>=0


def test_candidate_pool_and_offline_scores_guarded():
    A=system_matrix(4,2,TILTS).tocsr()
    truth=np.full(64,.2)
    measured=A@truth
    prefix=np.arange(12)
    candidates=diagnostic_pool(A.shape[0],prefix,17,21,0,0,12,4)
    assert len(candidates)==4
    assert len(set(candidates)&set(prefix))==0
    assert np.array_equal(candidates,diagnostic_pool(A.shape[0],prefix,17,21,0,0,12,4))
    rows,ranks=audit_candidates(A,measured,truth,prefix,candidates,4,2,
                                provisional_epochs=2,epochs=2,relaxation=.25,feature_cap=3)
    assert len(rows)==4 and len(ranks)==4
    assert all(r['regret'] >= -1e-12 for r in ranks)
    with pytest.raises(ValueError): audit_candidates(A,measured,truth,prefix,np.array([1]),4,2,
                                provisional_epochs=2,epochs=2,relaxation=.25,feature_cap=3)


def test_duplicate_fingerprint_rejected(tmp_path):
    f=tmp_path/'ray_fingerprints.csv'
    f.write_text('object_id,model,noise_fraction,seed,policy,ray_order_sha256\n'
                 'a,same,0,17,coverage,aaa\na,same,0,17,coverage,bbb\n')
    with pytest.raises(ValueError,match='duplicate'): read_fingerprints(f)


def test_replayed_source_smoke(tmp_path):
    common=['--size','4','--angles','2','--factor','2','--families','inclusions',
            '--objects-per-family','1','--seeds','104729','--models','same',
            '--noise-fractions','0','--budget','56','--warm-rays','16','--batch','8',
            '--candidate-pool','8','--provisional-epochs','2','--mart-epochs','2',
            '--mart-relaxation','.25','--feature-cap','3']
    source=tmp_path/'08b'; frozen=tmp_path/'09'; result=tmp_path/'10'
    source_main(common+['--output-dir',str(source)])
    frozen_main(common+['--final-epochs','2','4','--final-relaxations','.15','.25',
                       '--source-dir',str(source),'--output-dir',str(frozen)])
    geometry,error,candidates,rankings=main(common+['--source-dir',str(source),
         '--fingerprints-dir',str(frozen),'--checkpoints','16','48',
         '--audit-candidates','3','--output-dir',str(result)])
    assert (len(geometry),len(error),len(candidates),len(rankings))==(4,4,12,16)
    protocol=json.loads((result/'protocol.json').read_text())
    assert protocol['source_08b_anchors_verified']==4
    assert protocol['source_09_fingerprints_verified']==4
