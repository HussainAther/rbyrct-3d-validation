import csv
import hashlib
import json
from pathlib import Path

import pytest

from audit_08i import analyze_ranking_pool, object_balance, run, _midranks_desc


def sample_pool(source='08E', object_seed=10):
    out=[]
    for i in range(4):
        row=dict(size=12,object_seed=object_seed,policy='gradient',acquired_before=24,
                 candidate_ray=i,gradient_score=4-i,score_rank=i+1,
                 chosen=int(i==0),eligible=1,reference=int(i==3),
                 defect_hit=int(i in (2,3)), prior_path_coverage=i*.1,
                 one_ray_global_gain=i*.001,one_ray_defect_gain=i*.02)
        if source=='08G':row['disagreement_score']=i
        out.append(row)
    return out


def archive(root,source,seed):
    root.mkdir()
    fname='candidate_probes.csv' if source=='08E' else 'candidate_diagnostics.csv'
    rows=sample_pool(source,seed)
    manifest=[dict(size=12,object_seed=seed,policy='gradient',probes=1,evaluated_candidates=4,n_candidates=4)]
    for name,records in ((fname,rows),('acquisition_manifest.csv',manifest)):
        with (root/name).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    (root/'protocol.json').write_text('{}')
    stat=(dict(complete=True,runs=1,probed_candidate_rows=4,evaluation_only_confirmed=True)
          if source=='08E' else dict(complete=True,histories=1,candidate_rows=4,pools=1))
    (root/'run_status.json').write_text(json.dumps(stat))
    (root/'sha256.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}))


def test_rank_contrast_and_oracle_hit():
    r=analyze_ranking_pool(sample_pool(),'08E')
    assert r['n_hit']==2 and r['n_nonhit']==2
    assert r['hit_minus_nonhit_rank']==pytest.approx(2)
    assert r['hit_score_pairwise_win_fraction']==0
    assert r['defect_oracle_hit']==1
    assert r['best_hit_beats_selected']==1
    assert r['gradient_top_hit']==0
    assert r['hit_minus_nonhit_defect_gain']==pytest.approx(.04)


def test_disagreement_ranking():
    r=analyze_ranking_pool(sample_pool('08G'),'08G')
    assert r['disagreement_top_hit']==1
    assert r['disagreement_top_is_defect_oracle']==1
    assert r['hit_disagreement_pairwise_win_fraction']==1


def test_tie_midrank_and_pairwise():
    assert _midranks_desc([4,4,1,0]) == [1.5,1.5,3,4]
    rows=sample_pool();rows[0]['gradient_score']=2;rows[1]['gradient_score']=2
    # 08E stored ranks require consistency with new score, so use 08G
    g=sample_pool('08G');g[0]['gradient_score']=2;g[1]['gradient_score']=2
    r=analyze_ranking_pool(g,'08G')
    assert 0 <= r['hit_score_pairwise_win_fraction'] <= 1


def test_absent_hit_class_is_undefined_not_zero():
    g=sample_pool('08G')
    for row in g:row['defect_hit']=0
    r=analyze_ranking_pool(g,'08G')
    assert r['available_hit']==0 and r['hit_minus_nonhit_rank'] is None
    assert r['best_hit_beats_selected'] is None
    assert r['defect_oracle_hit']==0


def test_validation_duplicate_and_selection():
    g=sample_pool('08G');g[2]['candidate_ray']=0
    with pytest.raises(ValueError,match='duplicate'):analyze_ranking_pool(g,'08G')
    g=sample_pool('08G');g[0]['chosen']=0
    with pytest.raises(ValueError,match='selected'):analyze_ranking_pool(g,'08G')


def test_end_to_end_readonly(tmp_path):
    e,g,out=tmp_path/'e',tmp_path/'g',tmp_path/'out'
    archive(e,'08E',10);archive(g,'08G',20)
    before={p.name:p.read_bytes() for p in e.iterdir()}
    report,summary=run(e,g,out)
    assert report['verdict']=='PASS' and report['candidate_pools']==2
    assert len(summary)==2
    assert (out/'object_balanced_summary.csv').is_file()
    assert before=={p.name:p.read_bytes() for p in e.iterdir()}
    with pytest.raises(FileExistsError):run(e,g,out)


def test_reject_hash_tampering_and_overlapping_seeds(tmp_path):
    e,g=tmp_path/'e',tmp_path/'g'
    archive(e,'08E',10);archive(g,'08G',10)
    with pytest.raises(ValueError,match='overlap'):run(e,g,tmp_path/'out')
    (e/'candidate_probes.csv').write_text('tampered')
    with pytest.raises(ValueError,match='hash mismatch'):run(e,g,tmp_path/'out')


def test_object_balance():
    r=analyze_ranking_pool(sample_pool(),'08E')
    a=dict(source='08E',size=12,policy='gradient',object_seed=1,**r)
    b=dict(source='08E',size=12,policy='gradient',object_seed=2,**r)
    summary=object_balance([a,b])[0]
    assert summary['n_objects']==2 and summary['n_pools']==2
    assert summary['pools_hit_beats_selected']==2
