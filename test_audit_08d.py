import csv
import hashlib
import json
import numpy as np
import pytest
from scipy.sparse import csr_matrix
from audit_08d import (sha_ids, path_statistics, check_orders, summarize_pairs,
                       descriptive_correlations, verify_archive, read_csv)


def test_intersection_and_coverage_metrics():
    A=csr_matrix(np.array([[1.,0.,0.,0.],[0.,2.,0.,0.],[1.,1.,0.,0.],[0.,0.,1.,1.]]))
    mask=np.array([True,False,False,False])
    a=path_statistics(A,[0,1,2],mask)
    assert a['defect_hit_count']==2
    assert np.isclose(a['defect_hit_fraction'],2/3)
    assert np.isclose(a['defect_path_fraction'],2/5)
    assert np.isclose(a['defect_voxel_coverage_fraction'],1)
    assert a['spatial_coverage_cv']>0


def test_invalid_ray_histories_and_masks():
    A=csr_matrix(np.eye(4))
    mask=np.array([True,False,False,False])
    for ids in ([],[0,0],[4],[-1]):
        with pytest.raises(ValueError): path_statistics(A,ids,mask)
    with pytest.raises(ValueError):path_statistics(A,[0],np.ones(4,dtype=bool))


def test_sha_order_integer_encoding():
    assert sha_ids([1,2,3])==hashlib.sha256(np.array([1,2,3],dtype='<i8').tobytes()).hexdigest()
    assert sha_ids([1,2,3])!=sha_ids([2,1,3])


def test_check_orders_checkpoint_hash():
    orders=[dict(size='4',object_id='o',model='same',policy=p,acquired_index=str(i+1),ray_id=str(i))
            for p in ('coverage','gradient','incremental_25') for i in range(4)]
    rec=[dict(size='4',object_id='o',model='same',policy=p,acquired='2',order_sha256=sha_ids([0,1]))
         for p in ('coverage','gradient','incremental_25')]
    proto={'configs':{'4':{'budget':4,'checkpoints':[2]}}}
    assert len(check_orders(orders,rec,proto,{4:10}))==3
    rec[1]['order_sha256']='corrupt'
    with pytest.raises(ValueError,match='fingerprint'):check_orders(orders,rec,proto,{4:10})


def test_pairstats_object_unit_and_different_directions():
    all_rows=[]
    for obj, d in [('o1',.2),('o2',-.1),('o3',.1)]:
        for policy in ('coverage','gradient','incremental_25'):
            all_rows.append(dict(size=4,object_id=obj,model='same',acquired=24,policy=policy,
                defect_hit_fraction=.3+(d if policy!='coverage' else 0),
                defect_path_fraction=.1+(d/2 if policy!='coverage' else 0),
                spatial_coverage_cv=.5+(d if policy!='coverage' else 0),
                defect_voxel_coverage_fraction=.5,
                mean_defect_coverage=.2,global_rmse=.1,defect_region_rmse=.2,
                gain_vs_coverage=0,defect_gain_vs_coverage=(d if policy!='coverage' else 0)))
    pairs=summarize_pairs(all_rows)
    assert len(pairs)==6
    obj, summary=descriptive_correlations(pairs)
    assert len(obj)==6 and len(summary)==2
    assert all(s['n_objects']==3 for s in summary)


def test_sha_manifest_rejects_tampering_and_incomplete(tmp_path):
    (tmp_path/'run_status.json').write_text(json.dumps(dict(complete=True)))
    (tmp_path/'x.csv').write_text('a\n1\n')
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.iterdir()}
    (tmp_path/'sha256.json').write_text(json.dumps(files))
    assert verify_archive(tmp_path)[1]==2
    (tmp_path/'x.csv').write_text('a\n2\n')
    with pytest.raises(ValueError,match='hash mismatch'):verify_archive(tmp_path)
