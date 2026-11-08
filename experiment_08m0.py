"""RBYRCT-08M0: 32^3, 4096-ray information-order engineering preflight.

No phantom, detector readings, defect masks, MART reconstructions, or accuracy metrics.
Uses the EXACT experiment_08k.select_information implementation and 08J constants.
Outputs are append-safe, integrity-hashed, and never overwrite existing evidence.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path

import numpy as np
from scipy import sparse

SIZE = 32
ANGLES = 4
BUDGET = 4096
WARM = 64
BATCH = 32
POOL = 16
SEED = 811011  # Engineering-only seed; no scientific object/acquisition seeds.
CHECKPOINTS = (1024, 2048, 4096)
REPEATS = 2


class CommitOnly:
    """A deliberately unreadable observations substitute for acquisition-only profiling."""
    def __init__(self):
        self.committed = []

    def commit(self, ids):
        self.committed.extend(int(i) for i in ids)

    def __getitem__(self, key):
        raise AssertionError("08M0 must not read detector measurements")

    def __getattr__(self, name):
        raise AssertionError("08M0 has no detector observations: " + name)


def order_sha256(order):
    return hashlib.sha256(np.asarray(order, dtype='<i8').tobytes()).hexdigest()


def validate_order(order, warm, budget, ray_count, gate):
    ids = np.asarray(order, dtype=np.int64)
    expected_warm = np.asarray(warm, dtype=np.int64)
    if ids.ndim != 1 or ids.size != budget:
        raise ValueError('incorrect acquired-ray count')
    if np.any(ids < 0) or np.any(ids >= ray_count) or len(set(ids.tolist())) != budget:
        raise ValueError('duplicate or out-of-range selected rays')
    if not np.array_equal(ids[:len(expected_warm)], expected_warm):
        raise ValueError('warm prefix was modified')
    if gate.committed != ids[len(expected_warm):].tolist():
        raise ValueError('commit sequence differs from selected sequence')
    return {str(k): order_sha256(ids[:k]) for k in CHECKPOINTS if k <= budget}


def process_memory():
    """RSS and OS-reported peak working set when psutil supports it."""
    try:
        import psutil
        info = psutil.Process(os.getpid()).memory_info()
        peak = getattr(info, 'peak_wset', None)
        return {'rss_bytes': int(info.rss),
                'peak_working_set_bytes': int(peak) if peak is not None else None,
                'source': 'psutil_peak_wset' if peak is not None else 'psutil_rss_only'}
    except ImportError:
        return {'rss_bytes': None, 'peak_working_set_bytes': None,
                'source': 'psutil_unavailable'}


def dump_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def sha_manifest(root):
    filenames = ('protocol.json', 'profile.json', 'policy_timing.csv',
                 'order_fingerprints.json', 'run_status.json')
    lines = []
    for name in filenames:
        raw = (root/name).read_bytes()
        lines.append(f'{hashlib.sha256(raw).hexdigest()}  {name}')
    (root/'engineering_manifest.sha256').write_text('\n'.join(lines)+'\n', encoding='utf-8')


def run(output_dir, *, size=SIZE, angles=ANGLES, budget=BUDGET,
        warm_rays=WARM, batch=BATCH, pool=POOL, seed=SEED,
        repeats=REPEATS, matrix_builder=None, coverage_builder=None,
        selector=None, tilts=None, prior_variance=None,
        observation_variance=None, allow_test_scale=False):
    """Run with frozen CLI configuration; injected dependencies only for miniature tests."""
    if not allow_test_scale and (size, angles, budget, warm_rays, batch, pool, seed, repeats) != (
            SIZE, ANGLES, BUDGET, WARM, BATCH, POOL, SEED, REPEATS):
        raise ValueError('08M0 engineering protocol is locked')
    if not (size >= 2 and angles >= 1 and 0 < warm_rays < budget and
            min(batch, pool, repeats) >= 1):
        raise ValueError('invalid engineering configuration')

    # Never silently substitute another scoring implementation in production.
    if not allow_test_scale and any(x is not None for x in
        (matrix_builder, coverage_builder, selector, tilts, prior_variance, observation_variance)):
        raise ValueError('production 08M0 disallows dependency overrides')

    if any(x is None for x in (matrix_builder, coverage_builder, selector, tilts,
                                 prior_variance, observation_variance)):
        from experiment_04b import system_matrix
        from experiment_04g import TILTS
        from experiment_04h import voxel_coverage_order
        from experiment_08k import select_information
        from experiment_08j import PRIOR_VARIANCE, OBSERVATION_VARIANCE
        matrix_builder = matrix_builder or system_matrix
        coverage_builder = coverage_builder or voxel_coverage_order
        selector = selector or select_information
        tilts = TILTS if tilts is None else tilts
        prior_variance = PRIOR_VARIANCE if prior_variance is None else prior_variance
        observation_variance = OBSERVATION_VARIANCE if observation_variance is None else observation_variance

    if not (np.isfinite(prior_variance) and prior_variance > 0 and
            np.isfinite(observation_variance) and observation_variance > 0):
        raise ValueError('invalid uncertainty parameters')
    tilt_count = len(tilts)
    n_rays = size*size*angles*tilt_count
    if not (budget <= n_rays and tilt_count > 0):
        raise ValueError('budget exceeds ray geometry')

    root = Path(output_dir)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError('refusing to overwrite a previous engineering run')
    root.mkdir(parents=True, exist_ok=True)
    protocol = dict(stage='08M0 engineering ONLY', size=size, angles=angles,
        tilts=list(map(float, tilts)), budget=budget, warm=warm_rays,
        batch=batch, pool=pool, seed=seed, repeats=repeats,
        prior_variance=float(prior_variance),
        observation_variance=float(observation_variance),
        checkpoints=[x for x in CHECKPOINTS if x <= budget],
        selector='experiment_08k.select_information unchanged; geometric diagonal information score',
        forbidden='no phantom, detector measurements, defect masks, MART reconstruction, or accuracy metrics',
        interpretation='engineering profile only; NOT validation')
    dump_json(root/'protocol.json', protocol)
    status = {'complete': False, 'completed_repeats': 0, 'expected_repeats': repeats}
    dump_json(root/'run_status.json', status)

    t0 = time.perf_counter()
    A = matrix_builder(size, angles, tilts).tocsr()
    matrix_seconds = time.perf_counter() - t0
    if not sparse.isspmatrix_csr(A) or A.shape != (n_rays, size**3) or A.nnz == 0:
        raise ValueError('unexpected projection geometry')
    if not np.isfinite(A.data).all():
        raise ValueError('nonfinite sparse projection matrix')
    mem_after_matrix = process_memory()
    csr_bytes = int(A.data.nbytes + A.indices.nbytes + A.indptr.nbytes)

    t0 = time.perf_counter()
    coverage = np.asarray(coverage_builder(A,size,angles,tilt_count,budget,seed,pool),dtype=np.int64)
    coverage_seconds = time.perf_counter() - t0
    if len(coverage) != budget or len(set(coverage.tolist())) != budget or (coverage<0).any() or (coverage>=n_rays).any():
        raise ValueError('invalid common coverage order')

    fingerprint_rows = []
    timing_rows = []
    for repeat_index in range(repeats):
        gate = CommitOnly()
        t0 = time.perf_counter()
        selected, traces, selector_seconds = selector(A, gate, size, angles, coverage, budget, seed,
            warm_rays=warm_rays,batch=batch,candidate_pool=pool,
            prior_variance=prior_variance,observation_variance=observation_variance)
        measured_seconds = time.perf_counter() - t0
        checkpoints = validate_order(selected, coverage[:warm_rays], budget, n_rays, gate)
        full_digest = order_sha256(selected)
        fingerprint_rows.append({'repeat':repeat_index+1,'full_order_sha256':full_digest,
                                 'checkpoint_sha256':checkpoints})
        mem = process_memory()
        timing_rows.append({'repeat':repeat_index+1,'acquired':budget,
            'information_selection_seconds':float(selector_seconds),
            'measured_selector_call_seconds':float(measured_seconds),
            'selection_plus_common_coverage_seconds':float(measured_seconds+coverage_seconds),
            'coverage_reference_seconds':float(coverage_seconds),
            'rss_bytes':mem['rss_bytes'],'peak_working_set_bytes':mem['peak_working_set_bytes']})
        # Durable partial records even if a later repeat fails.
        with (root/'policy_timing.csv').open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(timing_rows[0]));writer.writeheader();writer.writerows(timing_rows)
        dump_json(root/'order_fingerprints.json',fingerprint_rows)
        status['completed_repeats']=len(fingerprint_rows)
        dump_json(root/'run_status.json',status)
        print(f'08M0 information repeat {repeat_index+1}/{repeats}: {budget} rays, '
              f'select={measured_seconds:.3f}s, sha256={full_digest[:16]}...',flush=True)

    if repeats < 2:
        raise ValueError('two repetitions required for determinism assertion')
    consistent = (len({r['full_order_sha256'] for r in fingerprint_rows})==1 and
        all(r['checkpoint_sha256']==fingerprint_rows[0]['checkpoint_sha256'] for r in fingerprint_rows))
    if not consistent:
        raise AssertionError('information selector produced nondeterministic ray histories')

    final_mem = process_memory()
    profile = dict(size=size,voxels=size**3,candidate_rays=n_rays,
        nnz=int(A.nnz),csr_storage_bytes=csr_bytes,
        matrix_build_s=float(matrix_seconds),
        common_coverage_order_s=float(coverage_seconds),
        information_selection_s=[r['information_selection_seconds'] for r in timing_rows],
        repeat_full_order_identical=True,checkpoint_orders_identical=True,
        memory_after_matrix=mem_after_matrix,memory_final=final_mem,
        coverage_reference_order_sha256=order_sha256(coverage),
        information_order_sha256=fingerprint_rows[0]['full_order_sha256'],
        information_identical_to_coverage=(fingerprint_rows[0]['full_order_sha256']==order_sha256(coverage)),
        python=sys.version,platform=platform.platform(),
        scope='engineering geometry/time/memory/invariants ONLY; no reconstruction accuracy')
    dump_json(root/'profile.json',profile)
    status.update(complete=True, deterministic_repeats=True)
    dump_json(root/'run_status.json',status)
    sha_manifest(root)
    print(json.dumps({'complete':True,'matrix_build_s':matrix_seconds,
        'common_coverage_s':coverage_seconds,
        'information_times_s':[round(r['information_selection_seconds'],4) for r in timing_rows],
        'csr_storage_bytes':csr_bytes,'memory_source':final_mem['source']},indent=2))
    return profile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',required=True)
    args=parser.parse_args()
    run(args.output_dir)


if __name__=='__main__':main()
