"""05B-11 Stage 2: frozen, held-out 12^3 MART acquisition study.

Full protocol: 8 new objects x 2 acquisition seeds x 2 forward models x 3 policies,
with nested ray checkpoints 144/288/576. No policy/solver tuning after pilot.
The 288-ray endpoint is primary. Purely synthetic; no CT-dose claim.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import scipy

from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_04qa import project
from experiment_05b_07 import select_delayed_order
from experiment_05b_08b import new_phantom, nonnegative_noisy_measurements
from experiment_05b_gate import AcquiredOnly
from experiment_05b_mart import mart_reconstruct
from experiment_05b_resources import validate_grid

FAMILIES = ('inclusions', 'filaments', 'laminae', 'voids')
POLICIES = ('coverage', 'gradient', 'delayed_48')
MODELS = ('same', 'independent')
SEEDS = (104729, 130363)
OBJECT_SEED_BASE = 960001
NOISE_FRACTION = .005
OFFSET = .15
STEP = .25
PRIMARY_CHECKPOINT = 288
RMSE_THRESHOLD = .10  # descriptive; checkpoint resolution only; no interpolation


def order_sha256(order):
    return hashlib.sha256(np.asarray(order, dtype='<i8').tobytes()).hexdigest()


def _write_csv(path, rows, columns=None):
    if not rows:
        raise RuntimeError(f'no rows for {path.name}')
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=columns or list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_stage2(*, size, angles, factor, budget, checkpoints, warm_rays,
                    batch, candidate_pool, provisional_epochs, final_epochs,
                    relaxation, families, seeds, models, objects_per_family,
                    object_seed_base, noise_fraction, offset, step,
                    allow_test_scale=False):
    validate_grid(size, factor)
    if not allow_test_scale and (size != 12 or angles != 4 or factor != 2 or budget != 576
        or tuple(checkpoints) != (144, 288, 576) or warm_rays != 36 or batch != 12
        or candidate_pool != 24 or provisional_epochs != 4 or final_epochs != 16
        or relaxation != .25 or tuple(families) != FAMILIES or tuple(seeds) != SEEDS
        or tuple(models) != MODELS or objects_per_family != 2
        or object_seed_base != OBJECT_SEED_BASE or noise_fraction != NOISE_FRACTION
        or offset != OFFSET or step != STEP):
        raise ValueError('Stage 2 production configuration is frozen; no tuning or overrides')
    if (angles < 2 or factor != 2 or budget > size * size * angles * len(TILTS)
        or not 2 <= warm_rays < 48 < budget or warm_rays % batch != 0
        or (48 - warm_rays) % batch != 0 or (budget-warm_rays) % batch != 0
        or not checkpoints or tuple(sorted(set(checkpoints))) != tuple(checkpoints)
        or checkpoints[-1] != budget or any(k < warm_rays or k > budget
                      or (k - warm_rays) % batch for k in checkpoints)
        or min(batch, candidate_pool, provisional_epochs, final_epochs, objects_per_family) < 1
        or not np.isfinite(relaxation) or not 0 < relaxation <= 1
        or len(set(families)) != len(families) or not families or not set(families) <= set(FAMILIES)
        or len(set(seeds)) != len(seeds) or not seeds or min(seeds) < 0
        or len(set(models)) != len(models) or not models or not set(models) <= set(MODELS)
        or object_seed_base < 0 or not np.isfinite(noise_fraction) or noise_fraction < 0
        or not np.isfinite(offset) or offset < 0 or not np.isfinite(step) or step <= 0):
        raise ValueError('invalid Stage 2 configuration')
    new_seeds = [object_seed_base + 1009 * i + j
                 for i in range(len(families)) for j in range(objects_per_family)]
    pilot_seeds = {950101, 950202}
    prior_seeds = {900001 + 1009 * i + j for i in range(4) for j in range(2)}
    if len(set(new_seeds)) != len(new_seeds) or (set(new_seeds) & (pilot_seeds | prior_seeds)):
        raise ValueError('Stage 2 objects overlap existing benchmark or pilot seeds')


def _env_data(script_path):
    try:
        p = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=script_path.parent,
                           capture_output=True, text=True, timeout=5)
        git_head = p.stdout.strip() if p.returncode == 0 else 'unavailable'
    except (OSError, subprocess.TimeoutExpired):
        git_head = 'unavailable'
    return (f'Source directory: {script_path.parent.resolve()}\nGit HEAD: {git_head}\n'
            f'Python: {sys.version}\nOS: {platform.platform()}\n'
            f'NumPy: {np.__version__}\nSciPy: {scipy.__version__}\n'
            f'CPU count: {os.cpu_count()}\n')


def run_stage2(*, output_dir, size=12, angles=4, factor=2, budget=576,
               checkpoints=(144, 288, 576), warm_rays=36, batch=12,
               candidate_pool=24, provisional_epochs=4, final_epochs=16,
               relaxation=.25, families=FAMILIES, seeds=SEEDS, models=MODELS,
               objects_per_family=2, object_seed_base=OBJECT_SEED_BASE,
               noise_fraction=NOISE_FRACTION, offset=OFFSET, step=STEP,
               allow_test_scale=False):
    validate_stage2(size=size, angles=angles, factor=factor, budget=budget,
        checkpoints=checkpoints, warm_rays=warm_rays, batch=batch,
        candidate_pool=candidate_pool, provisional_epochs=provisional_epochs,
        final_epochs=final_epochs, relaxation=relaxation, families=families,
        seeds=seeds, models=models, objects_per_family=objects_per_family,
        object_seed_base=object_seed_base, noise_fraction=noise_fraction,
        offset=offset, step=step, allow_test_scale=allow_test_scale)
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError('refusing to overwrite nonempty output directory')
    output_dir.mkdir(parents=True, exist_ok=True)
    config = dict(study='05B-11 Stage 2, frozen held-out 12^3 MART',
        grid=size, angles=angles, tilts=[float(x) for x in TILTS], factor=factor,
        ray_universe=size*size*angles*len(TILTS), budget=budget,
        checkpoints=list(checkpoints), primary_checkpoint=PRIMARY_CHECKPOINT,
        warm_rays=warm_rays, batch=batch, candidate_pool=candidate_pool,
        provisional_epochs=provisional_epochs, final_epochs=final_epochs,
        relaxation=relaxation, families=list(families), seeds=list(seeds),
        models=list(models), policies=list(POLICIES),
        object_seed_base=object_seed_base,
        object_seed_rule='base + 1009*family_index + object_index',
        objects_per_family=objects_per_family, noise_fraction=noise_fraction,
        noise_seed_rule='(object_seed*37 + model_index*100003 + 17011) mod 2^32',
        noise='additive Gaussian scaled to RMS of clean measurements, clamped to >=0',
        offset=offset, step=step,
        same_model='coarse Siddon-like matrix A @ block-mean coarse object',
        independent_model='fine-grid trilinear midpoint ray marching; offset applies only here',
        delayed_activation='48 absolute rays (not scale-adjusted)',
        primary_estimand='at 288 rays, mean of per-object mean paired relative gains over 2 seeds x 2 models',
        secondary='144/576 ray gains, per-family effects, worst object, threshold .10, runtimes',
        rmse_threshold=RMSE_THRESHOLD,
        causal_access='ray choice may depend only on acquired measurements; truth used post selection',
        independence='8 structural objects; seeds/projectors/checkpoints are repeated conditions',
        frozen_test_scale=bool(allow_test_scale))
    settings_digest=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
    config['protocol_sha256']=settings_digest
    (output_dir/'protocol.json').write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
    (output_dir/'environment.txt').write_text(_env_data(Path(__file__)),encoding='utf-8')
    setup=time.perf_counter()
    A=system_matrix(size,angles,TILTS).tocsr()
    if A.shape != (size*size*angles*len(TILTS),size**3) or not np.isfinite(A.data).all() or (A.data<0).any():
        raise RuntimeError('invalid 3D geometry')
    matrix_s=time.perf_counter()-setup
    matrix_bytes=int(A.data.nbytes+A.indices.nbytes+A.indptr.nbytes)
    warm_orders={}
    warm_timing={}
    for seed in seeds:
        start=time.perf_counter()
        warm_orders[seed]=voxel_coverage_order(A,size,angles,len(TILTS),budget,seed,candidate_pool)
        warm_timing[seed]=time.perf_counter()-start
    manifest=[]; orders=[]; rows=[]; timings=[]
    for fi,family in enumerate(families):
        for obj_index in range(objects_per_family):
            obj_seed=object_seed_base+1009*fi+obj_index
            truth,fine=new_phantom(size,factor,family,obj_seed)
            if truth.size != size**3 or (truth <= 0).any() or not np.isfinite(truth).all():
                raise RuntimeError('invalid generated phantom')
            oid=f'{family}_{obj_seed}'
            manifest.append(dict(object_id=oid,family=family,object_seed=obj_seed,
                mean_attenuation=float(truth.mean()), max_attenuation=float(truth.max()),
                coarse_target_sha256=hashlib.sha256(np.asarray(truth,dtype='<f8').tobytes()).hexdigest(),
                fine_object_sha256=hashlib.sha256(np.asarray(fine,dtype='<f8').tobytes()).hexdigest()))
            for model_index,model in enumerate(models):
                start=time.perf_counter()
                if model=='same':
                    clean=np.asarray(A@truth).ravel()
                else:
                    clean=project(fine,size,angles,TILTS,factor=factor,
                                  offset=offset,step=step,mode='linear')
                forward_s=time.perf_counter()-start
                if clean.shape!=(A.shape[0],) or not np.isfinite(clean).all() or (clean < 0).any():
                    raise RuntimeError('invalid synthetic forward measurement')
                rel_mismatch=float(np.linalg.norm(clean-A@truth)/max(np.linalg.norm(A@truth),1e-12))
                noise_seed=(obj_seed*37+model_index*100003+17011)%(2**32)
                measured=nonnegative_noisy_measurements(clean,noise_fraction,noise_seed)
                for acquisition_seed in seeds:
                    this_case=[]; case_orders={}
                    for policy in POLICIES:
                        oracle=AcquiredOnly(measured)
                        warm=warm_orders[acquisition_seed]
                        oracle.commit(warm[:warm_rays])
                        order,trace,selection_s=select_delayed_order(A,oracle,size,angles,warm,budget,
                            acquisition_seed,policy=policy,warm_rays=warm_rays,batch=batch,
                            candidate_pool=candidate_pool,provisional_epochs=provisional_epochs,
                            relaxation=relaxation)
                        order=np.asarray(order,dtype=np.int64)
                        if (len(order)!=budget or len(set(map(int,order)))!=budget
                            or not np.array_equal(order[:warm_rays],warm[:warm_rays])
                            or oracle.allowed!=set(map(int,order))):
                            raise RuntimeError('acquisition order or acquired-only validation failed')
                        case_orders[policy]=order
                        for idx,ray in enumerate(order):
                            orders.append(dict(object_id=oid,family=family,model=model,
                                acquisition_seed=acquisition_seed,policy=policy,
                                acquired_index=idx+1,ray_id=int(ray)))
                        for checkpoint in checkpoints:
                            prefix=order[:checkpoint]
                            start=time.perf_counter()
                            reconstruction=mart_reconstruct(A[prefix],measured[prefix],final_epochs,
                                                            relaxation=relaxation)
                            recon_s=time.perf_counter()-start
                            if not np.isfinite(reconstruction).all() or (reconstruction <= 0).any():
                                raise RuntimeError('nonpositive or nonfinite MART output')
                            rmse=float(np.sqrt(np.mean((reconstruction-truth)**2)))
                            if not np.isfinite(rmse):
                                raise RuntimeError('nonfinite reconstruction RMSE')
                            this_case.append(dict(object_id=oid,family=family,object_seed=obj_seed,
                                model=model,noise_fraction=noise_fraction,
                                acquisition_seed=acquisition_seed,policy=policy,
                                acquired=checkpoint,rmse=rmse,relative_forward_mismatch=rel_mismatch,
                                ray_order_sha256=order_sha256(prefix),
                                shared_with_coverage=0,
                                feedback_batches=sum(int(t['feedback_active']) for t in trace
                                                     if int(t['acquired_after'])<=checkpoint)))
                            timings.append(dict(object_id=oid,family=family,model=model,
                                acquisition_seed=acquisition_seed,policy=policy,acquired=checkpoint,
                                selection_s=float(selection_s),reconstruction_s=float(recon_s),
                                matrix_build_s=float(matrix_s),matrix_storage_bytes=matrix_bytes,
                                warm_order_s=float(warm_timing[acquisition_seed]),
                                forward_project_s=float(forward_s)))
                        print(f'{oid} {model:11s} seed={acquisition_seed} {policy:10s} '
                              f'{budget} rays; selection={selection_s:.2f}s',flush=True)
                    if not np.array_equal(case_orders['coverage'][:48],case_orders['delayed_48'][:48]):
                        raise RuntimeError('delayed policy not equal to coverage through ray 48')
                    for r in this_case:
                        baseline=next(x['rmse'] for x in this_case
                            if x['policy']=='coverage' and x['acquired']==r['acquired'])
                        r['gain_vs_coverage']=(baseline-r['rmse'])/max(baseline,1e-12)
                        r['shared_with_coverage']=len(set(map(int,case_orders[r['policy']][:r['acquired']]))
                              & set(map(int,case_orders['coverage'][:r['acquired']])))
                    rows.extend(this_case)
    _write_csv(output_dir/'object_manifest.csv',manifest)
    _write_csv(output_dir/'acquisition_orders.csv',orders)
    _write_csv(output_dir/'prefix_reconstructions.csv',rows)
    _write_csv(output_dir/'timing.csv',timings)
    matched=[r for r in rows if r['acquired']==PRIMARY_CHECKPOINT]
    if allow_test_scale and PRIMARY_CHECKPOINT not in checkpoints:
        matched=[r for r in rows if r['acquired']==checkpoints[-1]]
    _write_csv(output_dir/'matched_cases.csv',matched)
    object_summary=[]
    for oid in sorted({r['object_id'] for r in matched}):
        for policy in POLICIES:
            grp=[r for r in matched if r['object_id']==oid and r['policy']==policy]
            object_summary.append(dict(object_id=oid,family=grp[0]['family'],policy=policy,
                n_conditions=len(grp),mean_relative_gain=float(np.mean([x['gain_vs_coverage'] for x in grp])),
                min_relative_gain=float(min(x['gain_vs_coverage'] for x in grp))))
    _write_csv(output_dir/'object_level_summary.csv',object_summary)
    thresholds=[]
    for key in sorted({(r['object_id'],r['model'],r['acquisition_seed'],r['policy']) for r in rows}):
        grp=sorted((r for r in rows if (r['object_id'],r['model'],r['acquisition_seed'],r['policy'])==key),
                   key=lambda r:r['acquired'])
        first=next((r['acquired'] for r in grp if r['rmse']<=RMSE_THRESHOLD),None)
        thresholds.append(dict(object_id=key[0],model=key[1],acquisition_seed=key[2],
            policy=key[3],rmse_threshold=RMSE_THRESHOLD,
            first_observed_checkpoint=first if first is not None else '',
            crossed_by_budget=int(first is not None),
            note='checkpoint-censored; no interpolated ray savings'))
    _write_csv(output_dir/'threshold_crossings.csv',thresholds)
    result=dict(pass_engineering_checks=True,
        distinct_objects=len(manifest), acquisition_histories=len(orders)//budget,
        reconstructions=len(rows), ray_order_rows=len(orders),
        matrix_storage_bytes=matrix_bytes, matrix_build_s=matrix_s,
        primary_checkpoint=PRIMARY_CHECKPOINT,
        stop_rule='One frozen Stage 2 run; do not retune policies on outcomes.',
        caveat='No physical CT or dose validation; object level is replication unit.')
    (output_dir/'study_status.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    files=sorted(p for p in output_dir.iterdir() if p.is_file() and p.name!='run_manifest.sha256')
    (output_dir/'run_manifest.sha256').write_text(''.join(f'{_sha256(p)}  {p.name}\n' for p in files),encoding='utf-8')
    print(f'05B-11 Stage 2 complete: {len(manifest)} objects, {len(orders)//budget} histories, '
          f'{len(rows)} reconstructions; output={output_dir}',flush=True)
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,
        default=Path('results/experiment05b/stage2_11_frozen_first'))
    args=p.parse_args(argv)
    try:
        run_stage2(output_dir=args.output_dir)
    except (ValueError, RuntimeError, OSError) as exc:
        p.error(str(exc))


if __name__=='__main__':
    main()
