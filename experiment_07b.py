"""RBYRCT-07B: profiling-only feasibility of the existing CPU 3D MART pipeline.

NO reconstruction-error evaluation, phantom comparison, optimization, or
claim of imaging advantage. Production protocol: 32^3, one deterministic
synthetic signal, 4 azimuths and existing 3 tilts, 128 rays, 3 policies.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
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

SIZE=32
ANGLES=4
BUDGET=128
WARM=32
BATCH=16
POOL=16
PROVISIONAL_EPOCHS=2
FINAL_EPOCHS=4
RELAXATION=.25
SEED=707031
GUARD_ETA=.05
POLICIES=('coverage','gradient','guarded_05')


def current_rss_bytes():
    """Best-effort live process resident set size, not a peak."""
    try:
        import psutil
        return int(psutil.Process(os.getpid()).memory_info().rss), 'psutil'
    except ImportError:
        pass
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),
                     ('PeakWorkingSetSize',ctypes.c_size_t),('WorkingSetSize',ctypes.c_size_t),
                     ('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),
                     ('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),
                     ('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t)]
        c=Counters();c.cb=ctypes.sizeof(Counters)
        ok=ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(),
                  ctypes.byref(c),ctypes.sizeof(c))
        if ok:return int(c.WorkingSetSize),'winapi'
    elif sys.platform.startswith('linux'):
        try:
            with open('/proc/self/statm',encoding='ascii') as f:
                pages=int(f.read().split()[1])
            return pages*os.sysconf('SC_PAGE_SIZE'),'procfs'
        except (OSError,ValueError,IndexError):pass
    return None,'unavailable'


def peak_rss_bytes():
    """OS-reported process peak if supported. Includes matrix build spikes."""
    try:
        import psutil
        m=psutil.Process(os.getpid()).memory_info()
        if hasattr(m,'peak_wset'):return int(m.peak_wset),'psutil_peak_wset'
    except ImportError:pass
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),
                     ('PeakWorkingSetSize',ctypes.c_size_t),('WorkingSetSize',ctypes.c_size_t),
                     ('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),
                     ('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),
                     ('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t)]
        c=Counters();c.cb=ctypes.sizeof(Counters)
        if ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(),ctypes.byref(c),ctypes.sizeof(c)):
            return int(c.PeakWorkingSetSize),'winapi_peak'
    if sys.platform.startswith('linux'):
        try:
            import resource
            # Linux ru_maxrss is KiB; not a stage-specific delta.
            return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*1024,'linux_ru_maxrss'
        except (ImportError,OSError):pass
    return None,'unavailable'


def deterministic_signal(n):
    """One manufactured positive 3D signal, used only for timing, not accuracy."""
    q=(np.arange(n,dtype=np.float64)+.5-n/2)/(n/2)
    z,y,x=np.meshgrid(q,q,q,indexing='ij')
    host=np.exp(-2.2*((x/.82)**2+(y/.72)**2+(z/.78)**2))
    structure=.12*np.exp(-((x-.24)**2+(y+.12)**2+(z-.14)**2)/.025)
    return np.maximum(.025+.6*host-structure,.005).ravel()


def csr_bytes(A):
    return int(A.data.nbytes+A.indices.nbytes+A.indptr.nbytes)


def validate_config(n,angles,budget,warm,batch,pool,provisional_epochs,final_epochs,
                    relaxation,seed,eta,allow_test_scale):
    if not allow_test_scale and (n,angles,budget,warm,batch,pool,provisional_epochs,final_epochs,relaxation,seed,eta) != (
        SIZE,ANGLES,BUDGET,WARM,BATCH,POOL,PROVISIONAL_EPOCHS,FINAL_EPOCHS,RELAXATION,SEED,GUARD_ETA):
        raise ValueError('07B production protocol fixed; use --test-scale for tests only')
    if not (4<=n<=SIZE and angles>=2 and 1<warm<budget<=n*n*angles*len(TILTS)
        and batch>0 and pool>0 and provisional_epochs>0 and final_epochs>0
        and 0<relaxation<=1 and eta==GUARD_ETA and seed>=0):
        raise ValueError('invalid or unsafe 07B configuration')


def benchmark(outdir,n=SIZE,angles=ANGLES,budget=BUDGET,warm=WARM,batch=BATCH,
              pool=POOL,provisional_epochs=PROVISIONAL_EPOCHS,final_epochs=FINAL_EPOCHS,
              relaxation=RELAXATION,seed=SEED,eta=GUARD_ETA,allow_test_scale=False):
    validate_config(n,angles,budget,warm,batch,pool,provisional_epochs,
                    final_epochs,relaxation,seed,eta,allow_test_scale)
    out=Path(outdir)
    if out.exists() and any(out.iterdir()):raise ValueError('refusing to overwrite nonempty output directory')
    out.mkdir(parents=True,exist_ok=True)
    config=dict(experiment='RBYRCT-07B CPU engineering feasibility ONLY',n=n,
         angles=angles,tilts=list(map(float,TILTS)),budget=budget,warm=warm,
         batch=batch,pool=pool,provisional_epochs=provisional_epochs,
         final_epochs=final_epochs,relaxation=relaxation,seed=seed,guard_eta=eta,
         policies=list(POLICIES),synthetic_signal='deterministic manufactured positive blob',
         no_error_or_performance_comparison=True,test_scale=allow_test_scale,
         caution='one process; process peak includes imports; CSR excludes construction intermediates')
    (out/'protocol.json').write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
    before,source=current_rss_bytes();peakbefore,peaksource=peak_rss_bytes()
    t=time.perf_counter();A=system_matrix(n,angles,TILTS).tocsr();matrix_build_s=time.perf_counter()-t
    after_build,_=current_rss_bytes();peak_build,_=peak_rss_bytes()
    if A.shape!=(n*n*angles*len(TILTS),n**3) or A.nnz<=0 or not np.isfinite(A.data).all() or (A.data<0).any():
        raise RuntimeError('matrix geometry/weights invalid')
    signal=deterministic_signal(n)
    measurement=np.asarray(A@signal).reshape(-1)
    if not np.isfinite(measurement).all() or (measurement<0).any():raise RuntimeError('bad manufactured measurements')
    t=time.perf_counter();warm_order=voxel_coverage_order(A,n,angles,len(TILTS),budget,seed,pool);warm_s=time.perf_counter()-t
    warm_order=np.asarray(warm_order,dtype=np.int64)
    rows=[]
    for policy in POLICIES:
        oracle=AcquiredOnly(measurement);oracle.commit(warm_order[:warm])
        if policy=='coverage':
            start=time.perf_counter()
            order=np.asarray(warm_order,dtype=np.int64)
            select_s=time.perf_counter()-start
            guard_batches=0
        elif policy=='gradient':
            order,trace,select_s=select_order(A,oracle,n,angles,warm_order,budget,seed,
                   policy='gradient',warm_rays=warm,batch=batch,candidate_pool=pool,
                   provisional_epochs=provisional_epochs,relaxation=relaxation)
            guard_batches=0
        else:
            order,trace,select_s=acquire_guarded(A,oracle,n,angles,warm_order,budget,seed,
                   eta=eta,warm_rays=warm,batch=batch,candidate_pool=pool,
                   provisional_epochs=provisional_epochs,relaxation=relaxation)
            guard_batches=len(trace)
        if len(order)!=budget or len(np.unique(order))!=budget or not np.all((order>=0)&(order<A.shape[0])):
            raise RuntimeError('duplicate or invalid ray selection')
        t=time.perf_counter()
        estimate=mart_reconstruct(A[order],measurement[order],final_epochs,relaxation=relaxation)
        reconstruct_s=time.perf_counter()-t
        if not np.isfinite(estimate).all() or (estimate<=0).any():raise RuntimeError('invalid MART output')
        rss,src=current_rss_bytes();peak,psrc=peak_rss_bytes()
        rows.append(dict(policy=policy,unique_rays=budget,warm_coverage_s=warm_s,selection_s=select_s,
              total_selection_including_common_warm_s=warm_s+select_s,
              final_reconstruction_s=reconstruct_s,guard_batches=guard_batches,
              row_order_sha256=hashlib.sha256(np.asarray(order,dtype='<i8').tobytes()).hexdigest(),
              rss_after_policy_bytes=rss,process_peak_rss_so_far_bytes=peak))
        print(f'{policy:12s} rays={budget} selection_total={warm_s+select_s:.3f}s final_MART={reconstruct_s:.3f}s',flush=True)
    profile=dict(size=n,voxels=n**3,candidate_rays=A.shape[0],nnz=int(A.nnz),
        csr_storage_bytes=csr_bytes(A),matrix_build_s=matrix_build_s,
        warm_coverage_selection_s=warm_s,
        rss_before_matrix_bytes=before,rss_after_matrix_bytes=after_build,
        process_peak_before_matrix_bytes=peakbefore,process_peak_after_matrix_bytes=peak_build,
        process_peak_final_bytes=peak_rss_bytes()[0],memory_source=source,
        peak_memory_source=peaksource,operations='CPU sparse projection, MART; NOT an accuracy experiment')
    (out/'profile.json').write_text(json.dumps(profile,indent=2)+'\n',encoding='utf-8')
    import csv
    with (out/'policy_timing.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (out/'environment.json').write_text(json.dumps(dict(python=sys.version,platform=platform.platform(),
        numpy=np.__version__,scipy=__import__('scipy').__version__),indent=2)+'\n',encoding='utf-8')
    return profile,rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--test-scale',action='store_true',help='unit-test/engineering-only size override')
    p.add_argument('--size',type=int,default=SIZE)
    p.add_argument('--angles',type=int,default=ANGLES)
    p.add_argument('--budget',type=int,default=BUDGET)
    p.add_argument('--warm',type=int,default=WARM)
    p.add_argument('--batch',type=int,default=BATCH)
    p.add_argument('--pool',type=int,default=POOL)
    p.add_argument('--provisional-epochs',type=int,default=PROVISIONAL_EPOCHS)
    p.add_argument('--final-epochs',type=int,default=FINAL_EPOCHS)
    a=p.parse_args()
    profile,rows=benchmark(a.output_dir,n=a.size,angles=a.angles,budget=a.budget,
        warm=a.warm,batch=a.batch,pool=a.pool,provisional_epochs=a.provisional_epochs,
        final_epochs=a.final_epochs,allow_test_scale=a.test_scale)
    print(json.dumps(profile,indent=2))


if __name__=='__main__':main()
