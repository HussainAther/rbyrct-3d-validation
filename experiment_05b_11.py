"""05B-11 Stage 1: frozen, engineering-only 12^3 MART feasibility pilot.

No policy parameter search; pilot reconstruction errors MUST NOT be used to tune
policies or decide which policy advances. The 12^3 confirmatory study is NOT run.
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
import scipy

from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_05b_07 import select_delayed_order
from experiment_05b_08b import new_phantom, nonnegative_noisy_measurements
from experiment_05b_gate import AcquiredOnly
from experiment_05b_mart import mart_reconstruct
from experiment_05b_resources import validate_grid

POLICIES = ('coverage', 'gradient', 'delayed_48')
FAMILIES = ('inclusions', 'laminae')
OBJECT_SEEDS = {'inclusions': 950101, 'laminae': 950202}  # new, not 05B-08B
ACQUISITION_SEED = 170141
NOISE_FRACTION = .005


def sha_order(order):
    return hashlib.sha256(np.asarray(order, dtype='<i8').tobytes()).hexdigest()


def save_csv(path, rows, columns):
    with path.open('w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)


def validate_pilot_settings(n, angles, factor, budget, checkpoints, warm_rays,
                            batch, candidate_pool, provisional_epochs, final_epochs,
                            relaxation):
    validate_grid(n, factor)
    if (angles < 2 or factor != 2 or budget > n*n*angles*len(TILTS)
        or not 1 <= warm_rays < 48 < budget
        or not (warm_rays % batch == 0 and (48-warm_rays) % batch == 0)
        or (budget-warm_rays) % batch != 0
        or not checkpoints or sorted(set(checkpoints)) != list(checkpoints)
        or any(k < warm_rays or k > budget or (k-warm_rays) % batch for k in checkpoints)
        or checkpoints[-1] != budget or min(batch,candidate_pool,provisional_epochs,final_epochs) < 1
        or not 0 < relaxation <= 1):
        raise ValueError('invalid Stage-1 05B-11 pilot parameters')


def run_pilot(*, size=12, angles=4, factor=2, budget=288,
              checkpoints=(144,288), warm_rays=36, batch=12, candidate_pool=24,
              provisional_epochs=4, final_epochs=16, relaxation=.25,
              output_dir=Path('results/experiment05b/feasibility_11_pilot'),
              families=FAMILIES, acquisition_seed=ACQUISITION_SEED):
    validate_pilot_settings(size,angles,factor,budget,checkpoints,warm_rays,batch,
                            candidate_pool,provisional_epochs,final_epochs,relaxation)
    if len(set(families)) != len(families) or not families or not set(families).issubset(FAMILIES):
        raise ValueError('invalid pilot phantom family selection')
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError('refusing to overwrite any nonempty output directory')
    output_dir.mkdir(parents=True,exist_ok=True)
    settings=dict(stage='05B-11 Stage 1 engineering feasibility pilot',size=size,
       angles=angles,tilts=list(map(float,TILTS)),factor=factor,budget=budget,
       checkpoints=list(checkpoints),warm_rays=warm_rays,batch=batch,
       candidate_pool=candidate_pool,provisional_epochs=provisional_epochs,
       final_epochs=final_epochs,relaxation=relaxation,policies=list(POLICIES),
       families=list(families),object_seeds={k:OBJECT_SEEDS[k] for k in families},
       acquisition_seed=acquisition_seed,noise_fraction=NOISE_FRACTION,
       model='same (coarse projector A @ coarse target)',
       delayed_activation='48 absolute acquired rays; a batch boundary',
       pilot_decision='engineering-only: DO NOT select or tune policies based on RMSE',
       comparisons='descriptive pilot diagnostics, not confirmatory claims')
    protocol_string=json.dumps(settings,sort_keys=True,separators=(',',':'))
    settings['protocol_sha256']=hashlib.sha256(protocol_string.encode()).hexdigest()
    (output_dir/'protocol.json').write_text(json.dumps(settings,indent=2)+'\n',encoding='utf-8')
    source_note='Source checkout: '+str(Path(__file__).resolve().parent)+'\n'
    try:
        import subprocess
        revision=subprocess.run(['git','rev-parse','HEAD'],cwd=Path(__file__).resolve().parent,
              capture_output=True,text=True,timeout=3)
        source_note+='Git HEAD: '+(revision.stdout.strip() if revision.returncode==0 else 'unavailable')+'\n'
    except (OSError,TimeoutError):
        source_note+='Git HEAD: unavailable\n'
    (output_dir/'environment.txt').write_text(source_note+f'Python: {sys.version}\n'
       f'OS: {platform.platform()}\nNumPy: {np.__version__}\nSciPy: {scipy.__version__}\n'
       f'CPU count: {os.cpu_count()}\n',encoding='utf-8')
    matrix_start=time.perf_counter()
    A=system_matrix(size,angles,TILTS).tocsr()
    if A.shape != (size*size*angles*len(TILTS),size**3):
        raise RuntimeError('3D geometry matrix shape mismatch')
    if not np.isfinite(A.data).all() or np.any(A.data<0):
        raise RuntimeError('invalid projector matrix')
    matrix_seconds=time.perf_counter()-matrix_start
    matrix_bytes=A.data.nbytes+A.indices.nbytes+A.indptr.nbytes
    warm_start=time.perf_counter()
    warm=voxel_coverage_order(A,size,angles,len(TILTS),budget,acquisition_seed,candidate_pool)
    warm_seconds=time.perf_counter()-warm_start
    outcomes=[]; orders=[]; manifest=[]; times=[]
    for family in families:
        seed=OBJECT_SEEDS[family]
        truth,_=new_phantom(size,factor,family,seed)
        if truth.size!=size**3 or not np.isfinite(truth).all() or (truth<=0).any():
            raise RuntimeError('invalid 3D phantom')
        clean=np.asarray(A@truth).ravel()
        noise_seed=(seed*37+17011)%(2**32)  # 08B noise-seed convention, same model
        measured=nonnegative_noisy_measurements(clean,NOISE_FRACTION,noise_seed)
        if measured.size!=A.shape[0] or not np.isfinite(measured).all() or (measured<0).any():
            raise RuntimeError('invalid measurement data')
        object_id=f'{family}_{seed}'
        manifest.append(dict(object_id=object_id,family=family,object_seed=seed,
                             noise_seed=noise_seed,mean_attenuation=float(truth.mean()),
                             max_attenuation=float(truth.max())))
        family_orders={}
        for policy in POLICIES:
            oracle=AcquiredOnly(measured)
            oracle.commit(warm[:warm_rays])
            selected,trace,selection_s=select_delayed_order(A,oracle,size,angles,warm,budget,
                 acquisition_seed,policy=policy,warm_rays=warm_rays,batch=batch,
                 candidate_pool=candidate_pool,provisional_epochs=provisional_epochs,
                 relaxation=relaxation)
            selected=np.asarray(selected,dtype=np.int64)
            if len(selected)!=budget or len(set(selected.tolist()))!=budget:
                raise RuntimeError('incomplete or duplicate acquired-ray history')
            if not np.array_equal(selected[:warm_rays],warm[:warm_rays]):
                raise RuntimeError('warm-start mismatch')
            if len(oracle.allowed)!=budget or oracle.allowed!=set(selected.tolist()):
                raise RuntimeError('acquired-only oracle history mismatch')
            if not np.isfinite(selection_s) or selection_s<0:
                raise RuntimeError('invalid measured selection runtime')
            family_orders[policy]=selected
            for i,ray in enumerate(selected):
                orders.append(dict(object_id=object_id,policy=policy,acquired_index=i+1,
                                   ray_id=int(ray)))
            for checkpoint in checkpoints:
                reconstruction_start=time.perf_counter()
                prefix=selected[:checkpoint]
                reconstructed=mart_reconstruct(A[prefix],measured[prefix],final_epochs,
                                               relaxation=relaxation)
                reconstruction_s=time.perf_counter()-reconstruction_start
                if not np.isfinite(reconstructed).all() or (reconstructed<=0).any():
                    raise RuntimeError('non-finite/nonpositive MART reconstruction')
                rmse=float(np.sqrt(np.mean((reconstructed-truth)**2)))
                if not np.isfinite(rmse):
                    raise RuntimeError('non-finite RMSE')
                outcomes.append(dict(object_id=object_id,family=family,policy=policy,
                         acquired=checkpoint,rmse=rmse,
                         ray_order_sha256=sha_order(prefix),
                         feedback_batches=sum(int(t['feedback_active']) for t in trace
                                              if t['acquired_after']<=checkpoint)))
                times.append(dict(object_id=object_id,policy=policy,acquired=checkpoint,
                                  selection_s=selection_s,reconstruction_s=reconstruction_s,
                                  matrix_build_s=matrix_seconds,warm_order_s=warm_seconds,
                                  matrix_storage_bytes=matrix_bytes))
            print(f'{object_id} {policy:12s} {budget} unique rays, acquired-only verified, '
                  f'selection={selection_s:.2f}s',flush=True)
        if not np.array_equal(family_orders['coverage'][:48],family_orders['delayed_48'][:48]):
            raise RuntimeError('delayed policy failed to match first 48 coverage-selected rays')
    for row in outcomes:
        coverage_rmse=next(r['rmse'] for r in outcomes
             if r['object_id']==row['object_id'] and r['acquired']==row['acquired']
             and r['policy']=='coverage')
        row['gain_vs_coverage']=(coverage_rmse-row['rmse'])/max(coverage_rmse,1.e-12)
    save_csv(output_dir/'object_manifest.csv',manifest,list(manifest[0]))
    save_csv(output_dir/'acquisition_orders.csv',orders,list(orders[0]))
    save_csv(output_dir/'prefix_reconstructions.csv',outcomes,list(outcomes[0]))
    save_csv(output_dir/'timing.csv',times,list(times[0]))
    # No empirical win criterion in engineering pass status.
    passed=(len(orders)==len(families)*len(POLICIES)*budget
            and len(outcomes)==len(families)*len(POLICIES)*len(checkpoints))
    (output_dir/'engineering_status.json').write_text(json.dumps(dict(
         pass_engineering_checks=bool(passed),policies_tested=len(POLICIES),
         object_count=len(families),checks='unique ordered rays; acquired-only oracle; '
         'common warm prefix; delayed-48 prefix parity; finite positive reconstructions; '
         'nested checkpoints; geometry and data validation',
         caveat='No wall-clock or RAM feasibility threshold imposed by script; '
         'review timing.csv and available memory before Stage 2.'),indent=2)+'\n',encoding='utf-8')
    files=sorted(p for p in output_dir.iterdir() if p.is_file() and p.name!='run_manifest.sha256')
    (output_dir/'run_manifest.sha256').write_text(''.join(
        f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in files),encoding='utf-8')
    return outcomes


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,default=Path('results/experiment05b/feasibility_11_pilot'))
    p.add_argument('--size',type=int,default=12)
    p.add_argument('--angles',type=int,default=4)
    p.add_argument('--factor',type=int,default=2)
    p.add_argument('--budget',type=int,default=288)
    p.add_argument('--checkpoints',nargs='+',type=int,default=[144,288])
    p.add_argument('--warm-rays',type=int,default=36)
    p.add_argument('--batch',type=int,default=12)
    p.add_argument('--candidate-pool',type=int,default=24)
    p.add_argument('--provisional-epochs',type=int,default=4)
    p.add_argument('--final-epochs',type=int,default=16)
    p.add_argument('--relaxation',type=float,default=.25)
    p.add_argument('--families',nargs='+',choices=FAMILIES,default=list(FAMILIES))
    a=p.parse_args(argv)
    try:
        run_pilot(size=a.size,angles=a.angles,factor=a.factor,budget=a.budget,
          checkpoints=tuple(a.checkpoints),warm_rays=a.warm_rays,batch=a.batch,
          candidate_pool=a.candidate_pool,provisional_epochs=a.provisional_epochs,
          final_epochs=a.final_epochs,relaxation=a.relaxation,
          output_dir=a.output_dir,families=tuple(a.families))
    except (ValueError,RuntimeError,OSError) as exc:
        p.error(str(exc))

if __name__=='__main__':
    main()
