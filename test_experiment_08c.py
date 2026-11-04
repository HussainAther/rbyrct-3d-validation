import csv
import json
import numpy as np
import pytest
from experiment_08c import run, validate, object_summary, POLICIES, OBJECT_SEEDS, CONFIGS


def miniature(tmp_path):
    return run(tmp_path/'small',sizes=(4,),object_seeds={4:(808701,)},
       configs={4:dict(budget=40,checkpoints=(24,40),warm=8,batch=4,pool=8,epochs=1,final_epochs=2)},
       models=('same',),acquisition_seed=808711,allow_test_scale=True)


def test_production_locked(tmp_path):
    with pytest.raises(ValueError):
        run(tmp_path/'x',sizes=(12,),allow_test_scale=False)


def test_reserved_seeds_rejected():
    with pytest.raises(ValueError):
        validate((12,),{12:(2077001,)},{12:CONFIGS[12]},('same',),808611)
    with pytest.raises(ValueError):
        validate((12,),{12:(808401,808401)},{12:CONFIGS[12]},('same',),808611)


def test_miniature_end_to_end_and_gain_arithmetic(tmp_path):
    out=tmp_path/'small';summary=miniature(tmp_path)
    assert len(summary)==6
    status=json.loads((out/'run_status.json').read_text())
    assert status['complete'] and status['completed_histories']==3 and status['completed_reconstructions']==6
    with (out/'prefix_reconstructions.csv').open(newline='') as f:rows=list(csv.DictReader(f))
    for r in rows:
        if r['policy']=='coverage':
            assert float(r['gain_vs_coverage'])==0
        else:
            base=next(b for b in rows if b['policy']=='coverage' and b['acquired']==r['acquired'])
            for metric,gain in [('global_rmse','gain_vs_coverage'),('defect_region_rmse','defect_gain_vs_coverage'),('nondefect_rmse','nondefect_gain_vs_coverage')]:
                expected=(float(base[metric])-float(r[metric]))/float(base[metric])
                assert np.isclose(float(r[gain]),expected)
    assert set(r['policy'] for r in rows)==set(POLICIES)
    assert (out/'sha256.json').exists()


def test_no_overwrite(tmp_path):
    miniature(tmp_path)
    with pytest.raises(FileExistsError):miniature(tmp_path)


def test_object_balanced_summary():
    rows=[dict(size=4,object_id='a',acquired=24,policy=p,
               gain_vs_coverage=0,defect_gain_vs_coverage=0,nondefect_gain_vs_coverage=0)
          for p in POLICIES]
    assert len(object_summary(rows))==3
