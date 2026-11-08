"""08AJ-P2 single-phantom 64^3 MART feasibility; NOT policy validation.

Regenerates and verifies the unchanged 08AJ-P diagonal ray schedule, then
runs one fixed synthetic 04B phantom through the unchanged 05B MART kernel.
No between-policy comparisons or clinical/physical claims.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import platform
import time
import traceback
from pathlib import Path
import numpy as np
from experiment_08m0 import order_sha256, process_memory
from experiment_08aj_p import DEFAULTS

MODULES = ('experiment_08aj_p2.py','experiment_08aj_p.py','experiment_08m0.py',
           'experiment_08k.py','experiment_08j.py','experiment_04b.py','experiment_04g.py',
           'experiment_04h.py','experiment_05b_08b.py','experiment_05b_mart.py')
EPOCHS=16
RELAXATION=.25
NOISE_FRACTION=.005
NOISE_SEED=930021
PEAK_GIB_GATE=8.0


def sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False)+'\n', encoding='utf-8')


def check_order(order, coverage, budget, ray_count, warm):
    order=np.asarray(order,dtype=np.int64)
    if (order.shape!=(budget,) or np.any(order<0) or np.any(order>=ray_count)
            or len(set(order.tolist())) != budget or not np.array_equal(order[:warm],coverage[:warm])):
        raise ValueError('invalid ordered ray sequence')
    return order


def check_prior_fingerprint(preflight_dir, order):
    """Require independent prior geometry-only fingerprint, not a new favorable order."""
    path=Path(preflight_dir)/'order_fingerprints.json'
    if not path.is_file():
        raise FileNotFoundError('08AJ-P order_fingerprints.json missing: '+str(path))
    records=json.loads(path.read_text(encoding='utf-8'))
    if len(records)<2 or len({r['full_order_sha256'] for r in records})!=1:
        raise ValueError('prior geometry-only repeats do not agree')
    digest=order_sha256(order)
    if digest != records[0]['full_order_sha256']:
        raise ValueError('08AJ-P2 order differs from previously recorded 08AJ-P order')
    return digest


def validate_finite_reconstruction(x, n):
    x=np.asarray(x)
    if x.shape!=(n**3,) or not np.isfinite(x).all() or not (x>0).all():
        raise ValueError('MART output must be positive, finite and of expected size')


def run(output_dir, preflight_dir, *, smoke=False, max_peak_gib=PEAK_GIB_GATE):
    if not np.isfinite(max_peak_gib) or max_peak_gib<=0:
        raise ValueError('positive finite memory gate required')
    # Smoke mode deliberately small; skip matching the distinct 64^3 prior fingerprint.
    cfg = dict(size=8,angles=2,budget=64,warm_rays=8,batch=8,pool=4,seed=930011) if smoke else DEFAULTS.copy()
    n=cfg['size']; budget=cfg['budget']
    root=Path(output_dir)
    if root.exists():
        raise FileExistsError('output directory exists: refusing to overwrite pilot evidence')
    root.mkdir(parents=True)
    protocol=dict(stage='08AJ-P2 single-volume engineering MART pilot',smoke=bool(smoke),
        classification='engineering feasibility only; not scientific policy validation',
        geometry_size=n,angles=cfg['angles'],budget=budget,seed=cfg['seed'],
        warm_rays=cfg['warm_rays'],batch=cfg['batch'],pool=cfg['pool'],
        phantom='experiment_04b.phantom_3d fixed synthetic phantom (matched projector)',
        measurement='experiment_05b_08b.nonnegative_noisy_measurements',
        noise_fraction=NOISE_FRACTION,noise_seed=NOISE_SEED,
        mart='experiment_05b_mart.mart_reconstruct unchanged',epochs=EPOCHS,
        relaxation=RELAXATION,initial=.3,max_peak_gib=max_peak_gib,
        source_sha256={p:sha_file(Path(__file__).parent/p) for p in MODULES},
        interpretation='No policy superiority, forward mismatch, physical or dose claims')
    dump(root/'protocol.json',protocol)
    status=dict(complete=False,stage='initialized',no_policy_comparison=True)
    dump(root/'run_status.json',status)
    try:
        from experiment_04b import system_matrix,phantom_3d
        from experiment_04g import TILTS
        from experiment_04h import voxel_coverage_order
        from experiment_08k import select_information
        from experiment_05b_08b import nonnegative_noisy_measurements
        from experiment_05b_mart import mart_reconstruct
        times={}
        t=time.perf_counter()
        A=system_matrix(n,cfg['angles'],TILTS).tocsr()
        times['matrix_construction_seconds']=time.perf_counter()-t
        assert A.shape==(n*n*cfg['angles']*len(TILTS),n**3)
        status['stage']='geometry_built'; dump(root/'run_status.json',status)
        t=time.perf_counter()
        coverage=np.asarray(voxel_coverage_order(A,n,cfg['angles'],len(TILTS),budget,cfg['seed'],cfg['pool']),dtype=np.int64)
        order,_,_=select_information(A,None,n,cfg['angles'],coverage,budget,cfg['seed'],
            warm_rays=cfg['warm_rays'],batch=cfg['batch'],candidate_pool=cfg['pool'])
        times['coverage_plus_diagonal_order_seconds']=time.perf_counter()-t
        order=check_order(order,coverage,budget,A.shape[0],cfg['warm_rays'])
        digest=order_sha256(order)
        if not smoke:
            digest=check_prior_fingerprint(preflight_dir,order)
        status['stage']='verified_order';dump(root/'run_status.json',status)
        print('08AJ-P2 order sha256:',digest,flush=True)
        t=time.perf_counter()
        truth=phantom_3d(n).ravel()
        selected=A[order].tocsr()
        clean=np.asarray(selected @ truth,dtype=np.float64).ravel()
        measured=nonnegative_noisy_measurements(clean,NOISE_FRACTION,NOISE_SEED)
        times['phantom_and_matched_measurements_seconds']=time.perf_counter()-t
        if measured.shape!=(budget,) or not np.isfinite(measured).all():
            raise ValueError('invalid measurements')
        status['stage']='measurements_ready';dump(root/'run_status.json',status)
        before=process_memory()
        t=time.perf_counter()
        reconstructed=mart_reconstruct(selected,measured,epochs=EPOCHS,initial=.3,relaxation=RELAXATION)
        times['mart_seconds']=time.perf_counter()-t
        after=process_memory()
        validate_finite_reconstruction(reconstructed,n)
        residual=np.asarray(selected@reconstructed-measured)
        relative_residual=float(np.linalg.norm(residual)/max(np.linalg.norm(measured),1e-10))
        if not np.isfinite(relative_residual):
            raise ValueError('nonfinite projection residual')
        np.save(root/'reconstruction.npy',reconstructed,allow_pickle=False)
        np.save(root/'acquired_order.npy',order,allow_pickle=False)
        peak=after['peak_working_set_bytes']
        profile=dict(complete=True,scope='one engineering pilot; no policy comparisons',
            size=n,voxels=n**3,candidate_rays=A.shape[0],acquired_rays=budget,
            order_sha256=digest,timings_seconds=times,
            csr_storage_bytes=int(A.data.nbytes+A.indices.nbytes+A.indptr.nbytes),
            acquired_csr_storage_bytes=int(selected.data.nbytes+selected.indices.nbytes+selected.indptr.nbytes),
            memory_before_mart=before,memory_after_mart=after,
            peak_working_set_gib=None if peak is None else peak/(1024**3),
            max_peak_gib=max_peak_gib,
            peak_gate_pass=None if peak is None else bool(peak/(1024**3)<=max_peak_gib),
            relative_projection_residual=relative_residual,
            reconstructed_min=float(reconstructed.min()),reconstructed_max=float(reconstructed.max()),
            reconstructed_mean=float(reconstructed.mean()),
            reconstructed_positive_finite=True,
            reconstruction_sha256=sha_file(root/'reconstruction.npy'),
            acquired_order_file_sha256=sha_file(root/'acquired_order.npy'),
            caveat='Measured projection residual is a numerical sanity check, not evidence of policy accuracy or superiority',
            platform=platform.platform())
        dump(root/'pilot_report.json',profile)
        status.update(complete=True,stage='completed',verdict='PASS' if profile['peak_gate_pass'] is not False else 'RESOURCE_GATE_EXCEEDED',
                      peak_memory_verified=peak is not None)
        dump(root/'run_status.json',status)
        files=('protocol.json','pilot_report.json','run_status.json','reconstruction.npy','acquired_order.npy')
        (root/'manifest.sha256').write_text(''.join(f'{sha_file(root/p)}  {p}\n' for p in files),encoding='utf-8')
        print(json.dumps(profile,indent=2),flush=True)
        return profile
    except Exception as exc:
        status.update(stage='failed',complete=False,error=f'{type(exc).__name__}: {exc}')
        dump(root/'run_status.json',status)
        (root/'failure_traceback.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',required=True)
    p.add_argument('--preflight-dir',default='results/experiment08aj_p/geometry64_first')
    p.add_argument('--smoke',action='store_true')
    p.add_argument('--max-peak-gib',type=float,default=PEAK_GIB_GATE)
    args=p.parse_args()
    run(args.output_dir,args.preflight_dir,smoke=args.smoke,max_peak_gib=args.max_peak_gib)

if __name__=='__main__':main()
