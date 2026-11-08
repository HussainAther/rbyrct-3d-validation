"""05B-09 frozen order and source verification tests."""
import csv
import json
from pathlib import Path

import numpy as np
import pytest

from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_05b_09 import analyze_fixed_orders, load_source, ray_digest
from experiment_05b_mart import mart_reconstruct


def test_frozen_orders_unchanged_and_anchor_equivalent():
    n=4
    A=system_matrix(n,2,TILTS).tocsr()
    truth=np.full(n**3,.25)
    observed=A@truth
    orders={policy:np.arange(12+i, dtype=np.int64) for i,policy in enumerate(
        ('coverage','gradient','capped_gradient','delayed_48'))}
    saved={name:order.copy() for name,order in orders.items()}
    grid=[(2,.15),(4,.25)]
    rows=analyze_fixed_orders(A,observed,truth,orders,grid)
    assert len(rows)==8
    for name, order in orders.items():
        assert np.array_equal(order,saved[name])
        row=next(r for r in rows if r['policy']==name and r['epochs']==4 and r['relaxation']==.25)
        reference=mart_reconstruct(A[order],observed[order],4,relaxation=.25)
        assert row['rmse']==pytest.approx(np.sqrt(np.mean((reference-truth)**2)))
        assert row['ray_order_sha256']==ray_digest(saved[name])


def test_bad_orders_rejected():
    A=system_matrix(4,2,TILTS).tocsr()
    truth=np.full(64,.25)
    observed=A@truth
    orders={policy:np.array([1,2,3]) for policy in ('coverage','gradient','capped_gradient','delayed_48')}
    orders['gradient']=np.array([1,1,3])
    with pytest.raises(ValueError,match='invalid frozen'):
        analyze_fixed_orders(A,observed,truth,orders,[(2,.25)])


def test_source_protocol_mismatch_rejected(tmp_path):
    from types import SimpleNamespace
    params={'size':8,'angles':4,'factor':2,'families':['inclusions'],
            'objects_per_family':1,'object_seed_base':900001,'seeds':[104729],
            'models':['same'],'noise_fractions':[0.0],'offset':.15,'step':.25,
            'budget':128,'warm_rays':16,'batch':8,'candidate_pool':16,
            'provisional_epochs':4,'mart_epochs':16,'mart_relaxation':.25,'feature_cap':3.}
    (tmp_path/'protocol.json').write_text(json.dumps({'parameters':params}))
    (tmp_path/'matched_cases.csv').write_text('object_id,model,noise_fraction,acquisition_seed,policy,rmse\n')
    a=SimpleNamespace(**dict(params,size=16))
    with pytest.raises(ValueError,match='source parameter mismatch'):
        load_source(tmp_path,a)


def test_regenerated_08b_anchor_smoke(tmp_path):
    from experiment_05b_08b import main as original_main
    from experiment_05b_09 import main as audit_main
    source=tmp_path/'source'
    output=tmp_path/'audit'
    common=['--size','4','--angles','2','--factor','2','--families','inclusions',
            '--objects-per-family','1','--seeds','104729','--models','same',
            '--noise-fractions','0','--budget','56','--warm-rays','16','--batch','8',
            '--candidate-pool','8','--provisional-epochs','2','--mart-epochs','2',
            '--mart-relaxation','.25','--feature-cap','3']
    original_main(common+['--output-dir',str(source)])
    rows=audit_main(common+['--final-epochs','2','4','--final-relaxations','.15','.25',
                            '--source-dir',str(source),'--output-dir',str(output)])
    assert len(rows)==16
    assert json.loads((output/'protocol.json').read_text())['source_verified_records']==4
    with (output/'ray_fingerprints.csv').open(newline='') as f:
        fingerprints=list(csv.DictReader(f))
    assert len(fingerprints)==4
    assert len({r['ray_order_sha256'] for r in fingerprints})>=1
