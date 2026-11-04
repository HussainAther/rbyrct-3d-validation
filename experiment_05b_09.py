"""05B-09: freeze 08B acquisition rays and audit MART reconstruction convergence.

Only the original 08B frozen selection protocol chooses rays. Each selected
ray set is then held identical across the final-MART parameter grid. Optional
08B source verification compares the anchor reconstruction against saved 08B
results and rejects incompatible protocols. No online policy is modified.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_04qa import project
from experiment_05b_08b import (FAMILIES, POLICIES, new_phantom,
                               nonnegative_noisy_measurements, run_matched_case)
from experiment_05b_mart import mart_reconstruct
from experiment_05b_resources import validate_grid


def write_csv(path, rows):
    if not rows:
        raise ValueError('no output rows')
    with path.open('w', newline='', encoding='utf8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def ray_digest(ids):
    return hashlib.sha256(np.asarray(ids, dtype='<i8').tobytes()).hexdigest()


def load_source(source_dir, args):
    if source_dir is None:
        return None
    protocol_path = source_dir / 'protocol.json'
    cases_path = source_dir / 'matched_cases.csv'
    if not protocol_path.is_file() or not cases_path.is_file():
        raise ValueError('missing source 08B protocol or matched_cases.csv')
    protocol = json.loads(protocol_path.read_text(encoding='utf8'))
    params = protocol['parameters']
    checked = ('size', 'angles', 'factor', 'families', 'objects_per_family',
               'object_seed_base', 'seeds', 'models', 'noise_fractions',
               'offset', 'step', 'budget', 'warm_rays', 'batch',
               'candidate_pool', 'provisional_epochs', 'mart_epochs',
               'mart_relaxation', 'feature_cap')
    for key in checked:
        actual = getattr(args, key)
        expected = params[key]
        if isinstance(actual, list):
            matches = actual == expected
        elif isinstance(actual, (int, float)):
            matches = actual == expected
        else:
            matches = str(actual) == str(expected)
        if not matches:
            raise ValueError(f'08B source parameter mismatch: {key}: {expected} vs {actual}')
    with cases_path.open(newline='', encoding='utf8') as f:
        rows = list(csv.DictReader(f))
    index = {}
    for r in rows:
        k = (r['object_id'], r['model'], float(r['noise_fraction']),
             int(r['acquisition_seed']), r['policy'])
        if k in index:
            raise ValueError('duplicate 08B source case')
        index[k] = float(r['rmse'])
    return index


def analyze_fixed_orders(A, observed, truth, orders, grid, *, anchor=(16, .25)):
    """Pure offline endpoint evaluation; orders are frozen, never recomputed."""
    results=[]
    if set(orders) != set(POLICIES):
        raise ValueError('policy ray sets incomplete')
    for policy in POLICIES:
        ids = np.asarray(orders[policy], dtype=np.int64)
        if (ids.ndim != 1 or len(set(ids.tolist())) != len(ids) or
                (ids < 0).any() or (ids >= A.shape[0]).any()):
            raise ValueError('invalid frozen ray set')
        sub = A[ids]
        b = np.asarray(observed)[ids]
        sha = ray_digest(ids)
        for epochs, relaxation in grid:
            x = mart_reconstruct(sub, b, epochs, relaxation=relaxation)
            rmse = float(np.sqrt(np.mean((x-truth)**2)))
            residual = float(np.linalg.norm(sub@x-b)/max(np.linalg.norm(b),1.e-12))
            results.append(dict(policy=policy, rays=len(ids), ray_order_sha256=sha,
                                epochs=epochs, relaxation=relaxation,
                                rmse=rmse, acquired_relative_residual=residual))
    by_params=defaultdict(dict)
    for r in results:
        k=(r['epochs'],r['relaxation'])
        by_params[k][r['policy']]=r['rmse']
    for r in results:
        coverage=by_params[(r['epochs'],r['relaxation'])]['coverage']
        r['gain_vs_coverage']=(coverage-r['rmse'])/max(coverage,1.e-12)
    return results


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--size',type=int,default=8)
    p.add_argument('--angles',type=int,default=4)
    p.add_argument('--factor',type=int,default=2)
    p.add_argument('--families',nargs='+',choices=FAMILIES,default=list(FAMILIES))
    p.add_argument('--objects-per-family',type=int,default=2)
    p.add_argument('--object-seed-base',type=int,default=900001)
    p.add_argument('--seeds',nargs='+',type=int,default=[104729,130363])
    p.add_argument('--models',nargs='+',choices=['same','independent'],default=['same','independent'])
    p.add_argument('--noise-fractions',nargs='+',type=float,default=[0.,.005])
    p.add_argument('--offset',type=float,default=.15)
    p.add_argument('--step',type=float,default=.25)
    p.add_argument('--budget',type=int,default=128)
    p.add_argument('--warm-rays',type=int,default=16)
    p.add_argument('--batch',type=int,default=8)
    p.add_argument('--candidate-pool',type=int,default=16)
    p.add_argument('--provisional-epochs',type=int,default=4)
    p.add_argument('--mart-epochs',type=int,default=16)
    p.add_argument('--mart-relaxation',type=float,default=.25)
    p.add_argument('--feature-cap',type=float,default=3.)
    p.add_argument('--final-epochs',nargs='+',type=int,default=[8,16,32,64])
    p.add_argument('--final-relaxations',nargs='+',type=float,default=[.15,.25])
    p.add_argument('--source-dir',type=Path,default=Path('results/experiment05b/robustness_08b_frozen_first'))
    p.add_argument('--output-dir',type=Path,default=Path('results/experiment05b/frozen_rays_09_first'))
    p.add_argument('--allow-large',action='store_true')
    a=p.parse_args(argv)
    try:
        validate_grid(a.size,a.factor,a.allow_large)
        if (a.angles < 2 or a.objects_per_family < 1 or not a.seeds
            or not a.models or not a.noise_fractions or not a.families
            or a.object_seed_base < 0 or min(a.seeds) < 0
            or any(not np.isfinite(v) or v<0 for v in a.noise_fractions)
            or not np.isfinite(a.offset) or a.offset<0
            or not np.isfinite(a.step) or not 0<a.step<=1
            or min(a.batch,a.candidate_pool,a.provisional_epochs,a.mart_epochs) < 1
            or not np.isfinite(a.mart_relaxation) or not 0<a.mart_relaxation<=1
            or not np.isfinite(a.feature_cap) or a.feature_cap < 1
            or not 2<=a.warm_rays<48<a.budget<=a.size*a.size*a.angles*len(TILTS)
            or (48-a.warm_rays)%a.batch
            or not a.final_epochs or min(a.final_epochs)<1
            or not a.final_relaxations
            or any(not np.isfinite(v) or not 0<v<=1 for v in a.final_relaxations)
            or len(set(a.final_epochs))!=len(a.final_epochs)
            or len(set(a.final_relaxations))!=len(a.final_relaxations)):
            raise ValueError('invalid 05B-09 configuration')
        if (a.mart_epochs,a.mart_relaxation) not in {(e,r) for e in a.final_epochs for r in a.final_relaxations}:
            raise ValueError('the original 08B anchor (mart_epochs, mart_relaxation) must be in the final grid')
        if a.output_dir.exists() and any(a.output_dir.iterdir()):
            raise ValueError('output directory must be new or empty')
        source=load_source(a.source_dir,a)
    except (ValueError,OSError,KeyError) as exc:
        p.error(str(exc))
    A=system_matrix(a.size,a.angles,TILTS).tocsr()
    warm={seed:voxel_coverage_order(A,a.size,a.angles,len(TILTS),a.budget,seed,a.candidate_pool) for seed in a.seeds}
    grid=[(e,r) for e in a.final_epochs for r in a.final_relaxations]
    records=[]; fingerprints=[]; validated=0
    for family_index,family in enumerate(a.families):
        for instance in range(a.objects_per_family):
            object_seed=a.object_seed_base+1009*family_index+instance
            truth,fine=new_phantom(a.size,a.factor,family,object_seed)
            object_id=f'{family}_{object_seed}'
            for model_index,model in enumerate(a.models):
                clean=np.asarray(A@truth).ravel() if model=='same' else project(
                    fine,a.size,a.angles,TILTS,factor=a.factor,offset=a.offset,step=a.step,mode='linear')
                for noise_index,noise in enumerate(a.noise_fractions):
                    noise_seed=(object_seed*37+model_index*100003+noise_index*17011)%(2**32)
                    observed=nonnegative_noisy_measurements(clean,noise,noise_seed)
                    for seed in a.seeds:
                        # Reproduce selected ray sets exactly under the original frozen acquisition settings.
                        original,orders=run_matched_case(
                            A, observed,truth,warm[seed],n=a.size,angles=a.angles,budget=a.budget,
                            acquisition_seed=seed,warm_rays=a.warm_rays,batch=a.batch,
                            candidate_pool=a.candidate_pool,provisional_epochs=a.provisional_epochs,
                            mart_epochs=a.mart_epochs,relaxation=a.mart_relaxation,
                            feature_cap=a.feature_cap)
                        original_by_policy={r['policy']:r['rmse'] for r in original}
                        for policy in POLICIES:
                            if source is not None:
                                key=(object_id,model,float(noise),seed,policy)
                                if key not in source or not np.isclose(original_by_policy[policy],source[key],atol=1e-11,rtol=1e-10):
                                    raise AssertionError(f'08B anchor does not reproduce: {key}')
                                validated += 1
                            fingerprints.append(dict(object_id=object_id,model=model,noise_fraction=noise,
                                                     seed=seed,policy=policy,rays=len(orders[policy]),
                                                     ray_order_sha256=ray_digest(orders[policy])))
                        analyzed=analyze_fixed_orders(A,observed,truth,orders,grid)
                        for r in analyzed:
                            if (r['epochs'],r['relaxation'])==(a.mart_epochs,a.mart_relaxation):
                                if not np.isclose(r['rmse'],original_by_policy[r['policy']],rtol=1e-10,atol=1e-11):
                                    raise AssertionError('frozen ray-set anchor mismatch')
                            records.append(dict(object_id=object_id,family=family,object_seed=object_seed,
                                                model=model,noise_fraction=noise,acquisition_seed=seed,**r))
                        print(f'{object_id} model={model} noise={noise:g} seed={seed}: '
                              f'{len(analyzed)} frozen reconstructions, 08B anchors verified',flush=True)
    a.output_dir.mkdir(parents=True,exist_ok=True)
    write_csv(a.output_dir/'frozen_reconstructions.csv',records)
    write_csv(a.output_dir/'ray_fingerprints.csv',fingerprints)
    aggregates=[]
    for policy in POLICIES:
        for e,r in grid:
            sub=[x for x in records if x['policy']==policy and x['epochs']==e and x['relaxation']==r]
            by_object=defaultdict(list)
            for x in sub:
                by_object[x['object_id']].append(x['gain_vs_coverage'])
            vals=np.array([np.mean(v) for v in by_object.values()])
            aggregates.append(dict(policy=policy,epochs=e,relaxation=r,n_objects=len(vals),
                                   mean_object_gain=float(np.mean(vals)),
                                   worst_object_gain=float(np.min(vals)),
                                   objects_with_positive_mean_gain=int(np.count_nonzero(vals>0))))
    write_csv(a.output_dir/'object_level_summary.csv',aggregates)
    protocol=dict(study='05B-09 offline frozen-ray-set MART convergence audit',
                  parameters={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},
                  source_verified_records=validated,
                  anchor_epochs=a.mart_epochs,anchor_relaxation=a.mart_relaxation,
                  limitations=['All acquisition orders frozen under 08B policy; only final reconstruction varies',
                               'New final reconstructions are NOT a retuned adaptive acquisition policy',
                               'Results are repeated measurements on eight synthetic objects',
                               'Training projection residual is not ground-truth reconstruction accuracy',
                               'One fixed order per policy; MART sequential order may affect convergence',
                               'Grid endpoint improvements do not certify full convergence',
                               'No physical dose, scanner or clinical claims'])
    (a.output_dir/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf8')
    print(f'05B-09 complete: {len(records)} reconstructions, {validated} 08B anchors verified; output={a.output_dir}')
    return records


if __name__=='__main__':
    main()
