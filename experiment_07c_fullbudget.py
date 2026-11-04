"""RBYRCT-07C full-budget engineering preflight: 4096 rays at 32^3.

Uses the same manufactured signal and acquisition settings as 07C preflight.
Timing and memory only; no error metric, phantom comparison or optimization.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import platform
import sys
import time
from pathlib import Path
import numpy as np

from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_05b_04 import select_order
from experiment_05b_gate import AcquiredOnly
from experiment_05b_mart import mart_reconstruct
from experiment_06a import acquire_guarded
from experiment_07b import deterministic_signal, current_rss_bytes, peak_rss_bytes, csr_bytes
from experiment_07c_preflight import (SIZE, ANGLES, LARGE_BUDGET, WARM, BATCH, POOL,
    PROVISIONAL_EPOCHS, FINAL_EPOCHS, RELAXATION, GUARD_ETA, SEED)

POLICIES = ('coverage', 'gradient', 'guarded_05')


def validate_config(n, angles, budget, warm, batch, pool, provisional_epochs,
                    final_epochs, relaxation, eta, seed, allow_test_scale):
    candidate_count = n * n * angles * len(TILTS)
    expected = (SIZE, ANGLES, LARGE_BUDGET, WARM, BATCH, POOL,
                PROVISIONAL_EPOCHS, FINAL_EPOCHS, RELAXATION, GUARD_ETA, SEED)
    supplied = (n, angles, budget, warm, batch, pool, provisional_epochs,
                final_epochs, relaxation, eta, seed)
    if not allow_test_scale and supplied != expected:
        raise ValueError('production 07C full-budget profile configuration fixed')
    if not (4 <= n <= SIZE and angles >= 2 and 0 < warm < budget <= candidate_count
            and (budget-warm) % batch == 0 and min(batch,pool,provisional_epochs,final_epochs) >= 1
            and 0 < relaxation <= 1 and eta == GUARD_ETA and seed >= 0):
        raise ValueError('invalid full-budget profiling configuration')


def check_acquisition(order, oracle, budget, A):
    order = np.asarray(order, dtype=np.int64)
    if (order.shape != (budget,) or len(np.unique(order)) != budget or
        np.any(order < 0) or np.any(order >= A.shape[0]) or
        oracle.allowed != set(map(int, order))):
        raise RuntimeError('invalid acquired-only or unique-ray invariant')
    return order


def run(output_dir, *, n=SIZE, angles=ANGLES, budget=LARGE_BUDGET,
        warm=WARM, batch=BATCH, pool=POOL,
        provisional_epochs=PROVISIONAL_EPOCHS, final_epochs=FINAL_EPOCHS,
        relaxation=RELAXATION, eta=GUARD_ETA, seed=SEED,
        allow_test_scale=False):
    validate_config(n,angles,budget,warm,batch,pool,provisional_epochs,
                    final_epochs,relaxation,eta,seed,allow_test_scale)
    output=Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise ValueError('refusing overwrite of nonempty directory')
    output.mkdir(parents=True,exist_ok=True)
    config = dict(stage='07C full-budget engineering-only preflight',
        n=n,angles=angles,budget=budget,warm=warm,batch=batch,pool=pool,
        provisional_epochs=provisional_epochs,final_epochs=final_epochs,
        relaxation=relaxation,eta=eta,seed=seed,
        policies=list(POLICIES),tilts=list(map(float,TILTS)),
        signal='deterministic_signal from experiment_07b',
        no_reconstruction_accuracy_assessment=True,
        no_ground_truth_defect_evaluation=True,allow_test_scale=allow_test_scale)
    (output/'protocol.json').write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
    before,src=current_rss_bytes(); peak_before,peak_src=peak_rss_bytes()
    start=time.perf_counter()
    A=system_matrix(n,angles,TILTS).tocsr()
    matrix_s=time.perf_counter()-start
    if A.shape!=(n*n*angles*len(TILTS),n**3) or A.nnz==0 or (A.data < 0).any():
        raise RuntimeError('invalid sparse system matrix')
    rss_after_matrix,_=current_rss_bytes();peak_after_matrix,_=peak_rss_bytes()
    signal=deterministic_signal(n)
    measured=np.asarray(A@signal).ravel()
    start=time.perf_counter()
    coverage_order=np.asarray(voxel_coverage_order(A,n,angles,len(TILTS),budget,seed,pool),dtype=np.int64)
    common_s=time.perf_counter()-start
    if len(np.unique(coverage_order))!=budget:raise RuntimeError('duplicate coverage-order rays')
    profile=dict(size=n,voxels=n**3,candidate_rays=A.shape[0],
        nnz=int(A.nnz),csr_storage_bytes=csr_bytes(A),matrix_build_s=matrix_s,
        common_coverage_order_s=common_s,full_budget_adaptive_measured=False,
        rss_before_matrix_bytes=before,rss_after_matrix_bytes=rss_after_matrix,
        process_peak_before_matrix_bytes=peak_before,
        process_peak_after_matrix_bytes=peak_after_matrix,
        process_peak_final_bytes=peak_rss_bytes()[0],
        memory_source=src,peak_memory_source=peak_src,
        scope='engineering runtime, sparse memory and acquisition invariants only; no accuracy results')
    (output/'profile.json').write_text(json.dumps(profile,indent=2)+'\n',encoding='utf-8')
    (output/'environment.json').write_text(json.dumps(dict(python=sys.version,
        platform=platform.platform(),numpy=np.__version__),indent=2)+'\n',encoding='utf-8')
    records=[]
    for policy in POLICIES:
        oracle=AcquiredOnly(measured)
        oracle.commit(coverage_order[:warm])
        if policy=='coverage':
            order=coverage_order.copy()
            oracle.commit(order[warm:])
            trace=[]; additional_s=0.
        elif policy=='gradient':
            order,trace,additional_s=select_order(A,oracle,n,angles,coverage_order,budget,seed,
                policy='gradient',warm_rays=warm,batch=batch,candidate_pool=pool,
                provisional_epochs=provisional_epochs,relaxation=relaxation)
        else:
            order,trace,additional_s=acquire_guarded(A,oracle,n,angles,coverage_order,budget,seed,
                eta=eta,warm_rays=warm,batch=batch,candidate_pool=pool,
                provisional_epochs=provisional_epochs,relaxation=relaxation)
        order=check_acquisition(order,oracle,budget,A)
        start=time.perf_counter()
        x=mart_reconstruct(A[order],oracle[order],final_epochs,relaxation=relaxation)
        reconstruction_s=time.perf_counter()-start
        if np.asarray(x).size!=n**3 or not np.isfinite(x).all() or (x<=0).any():
            raise RuntimeError('invalid final MART output')
        rss,_=current_rss_bytes();peak,_=peak_rss_bytes()
        records.append(dict(policy=policy,acquired=budget,
            common_coverage_order_s=common_s,additional_policy_selection_s=additional_s,
            total_selection_including_common_s=common_s+additional_s,
            final_reconstruction_s=reconstruction_s,
            acquisition_batches=len(trace),unique_rays=len(order),
            ray_order_sha256=hashlib.sha256(order.astype('<i8').tobytes()).hexdigest(),
            acquired_only_pass=True,positive_finite_MART_pass=True,
            rss_after_policy_bytes=rss,process_peak_so_far_bytes=peak))
        with (output/'policy_timing.csv').open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
        (output/'run_status.json').write_text(json.dumps(dict(
            complete=False,completed_policies=[r['policy'] for r in records],
            pending_policies=list(POLICIES[len(records):]),
            note='A partial run is an engineering result, not full-policy certification'),indent=2)+'\n',encoding='utf-8')
        print(f'{policy:12s} rays={budget} selection_total={common_s+additional_s:.2f}s '
              f'final_MART={reconstruction_s:.2f}s',flush=True)
    profile=dict(size=n,voxels=n**3,candidate_rays=A.shape[0],
        nnz=int(A.nnz),csr_storage_bytes=csr_bytes(A),matrix_build_s=matrix_s,
        common_coverage_order_s=common_s,full_budget_adaptive_measured=True,
        rss_before_matrix_bytes=before,rss_after_matrix_bytes=rss_after_matrix,
        process_peak_before_matrix_bytes=peak_before,
        process_peak_after_matrix_bytes=peak_after_matrix,
        process_peak_final_bytes=peak_rss_bytes()[0],
        memory_source=src,peak_memory_source=peak_src,
        scope='engineering runtime, sparse memory and acquisition invariants only; no accuracy results')
    (output/'profile.json').write_text(json.dumps(profile,indent=2)+'\n',encoding='utf-8')
    with (output/'policy_timing.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    (output/'run_status.json').write_text(json.dumps(dict(
        complete=True,completed_policies=list(POLICIES),pending_policies=[]),indent=2)+'\n',encoding='utf-8')
    return profile,records


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    profile,records=run(args.output_dir)
    print(json.dumps(dict(profile=profile,policy_runs=len(records)),indent=2))

if __name__=='__main__':main()
