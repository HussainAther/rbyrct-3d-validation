"""Focused numerical and integrity tests for read-only 08F."""
import csv
import hashlib
import json
from pathlib import Path
import pytest
from audit_08f import analyze, calculate_pool, run, spearman


def rows(policy='gradient'):
    scores=[3.,2.,1.]
    global_gains=[.01,.04,.02]
    defect_gains=[-.02,.03,.01]
    output=[]
    for i in range(3):
        output.append(dict(size='12',object_seed='1',policy=policy,acquired_before='24',
            candidate_ray=str(i+10),gradient_score=str(scores[i]),score_rank=str(i+1),
            eligible=str(1 if policy=='gradient' or i!=1 else 0),chosen=str(int(i==0)),
            reference=str(int(i==0)),defect_hit=str(int(i==1)),
            defect_path_fraction=str(0.1*i),prior_path_coverage=str(i),
            one_ray_global_gain=str(global_gains[i]),one_ray_defect_gain=str(defect_gains[i])))
    return output


def test_selected_regret_and_guard_decomposition():
    a=calculate_pool(rows('gradient'))
    assert a['defect_regret_all']==pytest.approx(.05)
    assert a['defect_regret_eligible']==pytest.approx(.05)
    assert a['defect_restriction_gap']==pytest.approx(0)
    b=calculate_pool(rows('incremental_25'))
    assert b['defect_regret_all']==pytest.approx(.05)
    assert b['defect_regret_eligible']==pytest.approx(.03)
    assert b['defect_restriction_gap']==pytest.approx(.02)
    assert b['selected_is_score_top']==1
    assert b['selected_is_defect_best']==0


def test_reject_tampering():
    bad=rows();bad[1]['score_rank']='1'
    with pytest.raises(ValueError,match='rank'):calculate_pool(bad)
    bad=rows();bad[1]['candidate_ray']=bad[0]['candidate_ray']
    with pytest.raises(ValueError,match='duplicate'):calculate_pool(bad)
    bad=rows();bad[0]['eligible']='0'
    with pytest.raises(ValueError,match='eligible'):calculate_pool(bad)
    bad=rows();bad[2]['chosen']='1'
    with pytest.raises(ValueError,match='one selected'):calculate_pool(bad)


def test_object_balanced_and_run_integrity():
    first=rows(); second=[dict(x,object_seed='2') for x in rows()]
    manifest=[dict(size='12',object_seed=str(i),policy='gradient',probes='1',evaluated_candidates='3') for i in (1,2)]
    pools,summary=analyze(first+second,manifest,dict(runs=2,probed_candidate_rows=6))
    assert len(pools)==2 and summary[0]['n_objects']==2
    assert summary[0]['mean_defect_regret_all']==pytest.approx(.05)
    with pytest.raises(ValueError,match='candidate count'):
        analyze(first+second,manifest,dict(runs=2,probed_candidate_rows=7))


def test_spearman_ties_and_degeneracy():
    assert spearman([1,2,3],[3,2,1])==pytest.approx(-1)
    assert spearman([2,2,2],[1,2,3]) is None
    assert spearman([1,1,3],[1,1,3])==pytest.approx(1)


def test_read_only_and_hash_verification(tmp_path):
    root=tmp_path/'08e';root.mkdir()
    items={'candidate_probes.csv':rows(), 'acquisition_manifest.csv':[
        dict(size='12',object_seed='1',policy='gradient',probes='1',evaluated_candidates='3')],
        'descriptive_summary.csv':[dict(size='12',policy='gradient',n_candidates='3')]}
    for fname,data in items.items():
        with (root/fname).open('w',newline='',encoding='utf8') as f:
            writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
    (root/'run_status.json').write_text(json.dumps(dict(complete=True,evaluation_only_confirmed=True,runs=1,probed_candidate_rows=3)))
    (root/'protocol.json').write_text('{}')
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}
    (root/'sha256.json').write_text(json.dumps(hashes))
    old={p.name:p.read_bytes() for p in root.iterdir()}
    report,summaries=run(root,tmp_path/'08f')
    assert report['verdict']=='PASS' and report['candidate_pools']==1
    assert all((root/name).read_bytes()==blob for name,blob in old.items())
    with pytest.raises(FileExistsError):run(root,tmp_path/'08f')
    (root/'candidate_probes.csv').write_text('tampered')
    with pytest.raises(ValueError,match='hash mismatch'):run(root,tmp_path/'08f2')
    assert not (tmp_path/'08f2').exists()


def test_reject_unsafe_output_path(tmp_path):
    root=tmp_path/'08e';root.mkdir()
    with pytest.raises(ValueError,match='separate'):
        run(root,root/'bad')
