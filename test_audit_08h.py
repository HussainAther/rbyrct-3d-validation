import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.sparse import csr_matrix

from audit_08h import analyze_pool, geometry_diagnostics, run, verify_archive, spearman


def make_pool(source, obj=10, size=12, policy='gradient'):
    result=[]
    for j in range(4):
        row=dict(size=size, object_seed=obj, policy=policy, acquired_before=24,
            candidate_ray=j, gradient_score=4-j, score_rank=j+1,
            chosen=int(j==0), eligible=1,reference=int(j==3),
            defect_hit=int(j==2), defect_path_fraction=.5 if j==2 else 0,
            prior_path_coverage=j*.1,
            one_ray_global_gain=.002*j, one_ray_defect_gain=.02*j)
        if source=='08G':row['disagreement_score']=j
        result.append(row)
    return result


def make_archive(root,source,obj):
    root.mkdir()
    file='candidate_probes.csv' if source=='08E' else 'candidate_diagnostics.csv'
    rows=make_pool(source,obj)
    for name,records in ((file,rows),('acquisition_manifest.csv',[
        dict(size=12,object_seed=obj,policy='gradient',probes=1,
             evaluated_candidates=4,n_candidates=4)])):
        with (root/name).open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    (root/'protocol.json').write_text('{}\n')
    status=dict(complete=True,runs=1,probed_candidate_rows=4,evaluation_only_confirmed=True) if source=='08E' else dict(complete=True,histories=1,candidate_rows=4,pools=1)
    (root/'run_status.json').write_text(json.dumps(status))
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}
    (root/'sha256.json').write_text(json.dumps(hashes))


def test_pool_detects_available_but_not_selected_and_regret():
    result=analyze_pool(make_pool('08E'),'08E')
    assert result['has_defect_candidate']==1
    assert result['hit_missed_when_available']==1
    assert result['selected_defect_hit']==0
    assert result['defect_regret']==pytest.approx(.06)
    assert result['global_regret']==pytest.approx(.006)
    assert result['defect_guard_exclusion_gap']==0


def test_disagreement_rank_different_from_gradient():
    result=analyze_pool(make_pool('08G'),'08G')
    assert result['disagreement_top_ray']==3
    assert result['gradient_top_ray']==0
    assert result['disagreement_defect_regret']==pytest.approx(0)
    assert result['disagreement_top_defect_hit']==0


def test_geometry_cosine_and_selection():
    A=csr_matrix(np.array([[1,0,0],[1,0,0],[0,1,0],[0,0,1]],dtype=float))
    result=geometry_diagnostics(A,[0,1,2,3],0,3)
    assert result['mean_pairwise_cosine']==pytest.approx(1/6)
    assert result['pool_path_diversity']==pytest.approx(5/6)
    assert result['selected_mean_cosine']==pytest.approx(1/3)
    assert result['defect_best_mean_cosine']==pytest.approx(0)


def test_duplicate_candidates_and_invalid_selection_rejected():
    rows=make_pool('08E');rows[2]['candidate_ray']=0
    with pytest.raises(ValueError,match='duplicate'):analyze_pool(rows,'08E')
    rows=make_pool('08E');rows[0]['chosen']=0
    with pytest.raises(ValueError,match='selected'):analyze_pool(rows,'08E')


def test_complete_archives_run_readonly_and_balance(tmp_path):
    e=tmp_path/'e';g=tmp_path/'g';o=tmp_path/'out'
    make_archive(e,'08E',10);make_archive(g,'08G',20)
    before={p.name:p.read_bytes() for p in e.iterdir()}
    A=csr_matrix(np.array([[1,0,0],[1,0,0],[0,1,0],[0,0,1]],dtype=float))
    report,summary=run(e,g,o,matrix_provider=lambda n:A)
    assert report['verdict']=='PASS' and report['pools']==2
    assert len(summary)==2
    assert (o/'pool_diagnostics.csv').is_file()
    assert before=={p.name:p.read_bytes() for p in e.iterdir()}
    with pytest.raises(FileExistsError):run(e,g,o,matrix_provider=lambda n:A)


def test_reject_tampered_hash_and_shared_objects(tmp_path):
    e=tmp_path/'e';g=tmp_path/'g'
    make_archive(e,'08E',10);make_archive(g,'08G',10)
    with pytest.raises(ValueError,match='shared object seeds'):run(e,g,tmp_path/'out',geometry=False)
    (e/'candidate_probes.csv').write_text('tampered')
    with pytest.raises(ValueError,match='hash mismatch'):verify_archive(e,'08E')


def test_spearman_constant_omitted():
    assert spearman([1,2,3],[1,2,3])==pytest.approx(1)
    assert spearman([1,1,1],[1,2,3]) is None
