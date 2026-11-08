"""Focused structural, geometry, and tamper-detection tests for read-only 08V."""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from scipy import sparse

from experiment_08v import (CHECKPOINTS, POLICIES, gini, geometry_metrics,
    load_reconstruction_summary, normalized_entropy, ray_order_from_csv,
    sampled_pair_cosine, sha_order, validate_archive_hashes, check_prefix_hashes,
    run, write_csv)


def test_sha_sensitive_to_ray_order():
    assert sha_order([1,2,3]) != sha_order([3,2,1])


def test_entropy_edge_cases():
    assert normalized_entropy([0,0,0]) == 0
    assert normalized_entropy([1,1,1]) == pytest.approx(1)
    assert normalized_entropy([1,0,0]) == pytest.approx(0)


def test_gini_and_bad_negative():
    assert gini([1,1,1]) == pytest.approx(0)
    assert gini([0,0,3]) == pytest.approx(2/3)
    with pytest.raises(ValueError): gini([1,-1])


def test_sparse_ray_cosines():
    A = sparse.eye(4,format='csr')
    assert sampled_pair_cosine(A,[0,1,2,3]) == pytest.approx(0)
    A = sparse.csr_matrix(np.ones((4,3)))
    assert sampled_pair_cosine(A,[0,1,2,3]) == pytest.approx(1)


def test_geometry_metrics_on_four_voxel_system():
    A = sparse.csr_matrix(np.column_stack((np.eye(4), np.zeros((4,4)))))
    metrics = geometry_metrics(A,[0,1],size=2,angles=1,ntilts=1,max_pairs=2)
    assert metrics['visited_voxel_fraction'] == pytest.approx(.25)
    assert metrics['voxel_visit_mean'] == pytest.approx(.25)
    assert metrics['voxel_visit_cv'] == pytest.approx(np.sqrt(3))
    assert metrics['voxel_visit_gini'] == pytest.approx(.75)
    assert metrics['sampled_ray_cosine'] == pytest.approx(0.)
    with pytest.raises(ValueError): geometry_metrics(A,[0,0],size=2,angles=1,ntilts=1)


def test_read_order_validates_hash_index_and_uniqueness(tmp_path):
    path=tmp_path/'orders.csv'
    def rows(seq):
        return [dict(policy='coverage',acquired_index=i+1,ray_id=v,order_sha256=sha_order(seq))
                for i,v in enumerate(seq)]
    write_csv(path,rows([0,2,3]))
    assert ray_order_from_csv(path,expected_policies=('coverage',),budget=3,nrays=4)['coverage'].tolist()==[0,2,3]
    wrong=rows([0,2,3]);wrong[1]['ray_id']='1';write_csv(path,wrong)
    with pytest.raises(ValueError,match='fingerprint'):ray_order_from_csv(path,expected_policies=('coverage',),budget=3,nrays=4)
    wrong=rows([0,2,3]);wrong[1]['acquired_index']=1;write_csv(path,wrong)
    with pytest.raises(ValueError,match='indices'):ray_order_from_csv(path,expected_policies=('coverage',),budget=3,nrays=4)


def test_archive_hash_detects_mutation(tmp_path):
    (tmp_path/'one.csv').write_text('first\n')
    h=hashlib.sha256((tmp_path/'one.csv').read_bytes()).hexdigest()
    (tmp_path/'sha256.json').write_text(json.dumps({'one.csv':h}))
    assert validate_archive_hashes(tmp_path)==1
    (tmp_path/'one.csv').write_text('changed\n')
    with pytest.raises(ValueError,match='hash mismatch'):validate_archive_hashes(tmp_path)


def test_prefix_hash_check_tamper():
    orders={p:np.arange(288,dtype=np.int64) for p in POLICIES}
    rows=[dict(object_id=oid,model=model,policy=p,acquired=k,order_sha256=sha_order(orders[p][:k]))
          for oid in ('a','b','c') for model in ('same','independent')
          for p in POLICIES for k in CHECKPOINTS]
    check_prefix_hashes(rows,orders)
    rows[0]['order_sha256']='0'*64
    with pytest.raises(ValueError,match='fingerprint'):check_prefix_hashes(rows,orders)


def test_aggregate_requires_three_objects(tmp_path):
    path=tmp_path/'agg.csv'
    rows=[dict(policy=p,acquired=k,n_objects=3) for p in POLICIES for k in CHECKPOINTS]
    write_csv(path,rows)
    assert len(load_reconstruction_summary(path))==6
    rows[0]['n_objects']=4;write_csv(path,rows)
    with pytest.raises(ValueError,match='three independent'):load_reconstruction_summary(path)


def test_real_archive_if_available():
    # Optional when a verified archive is placed in the test working directory.
    archive=Path('results/experiment08u/reconstruction_third')
    if not archive.is_dir():
        archive=Path('../rbyrct-results/experiment08u/reconstruction_third')
    if not archive.is_dir():
        pytest.skip('08U archived results available on Windows; unit tests remain valid')
    assert validate_archive_hashes(archive)>=5
    orders=ray_order_from_csv(archive/'acquisition_orders.csv',budget=288)
    check_prefix_hashes(__import__('experiment_08v').load_csv(archive/'prefix_reconstructions.csv'),orders)
