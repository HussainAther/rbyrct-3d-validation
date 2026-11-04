"""05B-08B frozen-policy, new-object robustness evaluation for MART RBYRCT.

Experimental policies and numerical settings are frozen from 05B-07. Ground
truth and future-ray measurements are OFFLINE only. This is synthetic numerical
validation, not an independent clinical study or a guarantee of generalization.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_04qa import project
from experiment_05b_07 import select_delayed_order
from experiment_05b_gate import AcquiredOnly
from experiment_05b_mart import mart_reconstruct
from experiment_05b_resources import validate_grid

POLICIES = ('coverage', 'gradient', 'capped_gradient', 'delayed_48')
FAMILIES = ('inclusions', 'filaments', 'laminae', 'voids')


def new_phantom(n: int, factor: int, family: str, object_seed: int):
    """Create a parameterized positive fine-grid object, distinct from 04P shapes.

    Returns (coarse block-averaged truth, fine volume). Independent object_seed
    changes geometry rather than merely changing acquisition randomness.
    """
    if n < 4 or factor < 2 or family not in FAMILIES:
        raise ValueError('invalid phantom definition')
    rng = np.random.default_rng(object_seed)
    m = n * factor
    q = (np.arange(m, dtype=float) + .5 - m/2) / (m/2)
    z, y, x = np.meshgrid(q, q, q, indexing='ij')
    image = np.full((m, m, m), .035, dtype=float)
    if family == 'inclusions':
        for _ in range(5):
            center = rng.uniform(-.58, .58, size=3)
            width = rng.uniform(.10, .27, size=3)
            d = ((x-center[0])/width[0])**2 + ((y-center[1])/width[1])**2 + ((z-center[2])/width[2])**2
            image += rng.uniform(.15, .45) * np.exp(-1.6*d)
    elif family == 'filaments':
        for _ in range(3):
            a, b = rng.uniform(-.32, .32, size=2)
            slope = rng.uniform(-.55, .55, size=2)
            width = rng.uniform(.075, .17)
            radius = (x-a-slope[0]*z-.10*np.sin(3*y))**2 + (y-b-slope[1]*z)**2
            image += rng.uniform(.25, .62) * np.exp(-radius/(width**2)) * (np.abs(z)<.85)
    elif family == 'laminae':
        normal = rng.normal(size=3)
        normal /= np.linalg.norm(normal)
        for offset in rng.uniform(-.53, .53, size=3):
            d = normal[0]*x + normal[1]*y + normal[2]*z - offset + .07*np.sin(3*x+2*y)
            image += rng.uniform(.18, .38) * np.exp(-(d/.095)**2)
        image *= (x*x/0.95**2+y*y/0.91**2+z*z/0.9**2<1)
        image += .035
    else:
        center = rng.uniform(-.1, .1, size=3)
        radii = rng.uniform(.55, .84, size=3)
        host = ((x-center[0])/radii[0])**2 + ((y-center[1])/radii[1])**2 + ((z-center[2])/radii[2])**2 < 1
        image += .6 * host
        for _ in range(5):
            pos = rng.uniform(-.53, .53, size=3)
            r = rng.uniform(.11, .23)
            image -= .57 * (((x-pos[0])**2+(y-pos[1])**2+(z-pos[2])**2)<r*r) * host
    image = np.maximum(image, .005)
    # Coarse target is the fine object's mean attenuation per voxel.
    coarse = image.reshape(n,factor,n,factor,n,factor).mean(axis=(1,3,5))
    return coarse.ravel(), image


def nonnegative_noisy_measurements(clean, fraction, seed):
    """Gaussian perturbation followed by zero clipping for nonnegative MART.

    The clipping convention is fixed and recorded; this is not Poisson CT noise.
    """
    clean = np.asarray(clean, dtype=float)
    if not np.isfinite(clean).all() or np.min(clean) < 0 or not np.isfinite(fraction) or fraction < 0:
        raise ValueError('invalid noise inputs')
    sigma = fraction * float(np.sqrt(np.mean(clean**2)))
    return np.maximum(clean + np.random.default_rng(seed).normal(0., sigma, clean.shape), 0.)


def run_matched_case(A, measurements, truth, warm, *, n, angles, budget,
                     acquisition_seed, warm_rays=16, batch=8, candidate_pool=16,
                     provisional_epochs=4, mart_epochs=16, relaxation=.25,
                     feature_cap=3.):
    """Four policies on identical measurement noise, geometry and warm prefix."""
    results = []
    orders = {}
    for policy in POLICIES:
        oracle = AcquiredOnly(measurements)
        oracle.commit(warm[:warm_rays])
        order, trace, selection_s = select_delayed_order(
            A, oracle, n, angles, warm, budget, acquisition_seed, policy=policy,
            warm_rays=warm_rays, batch=batch, candidate_pool=candidate_pool,
            provisional_epochs=provisional_epochs, relaxation=relaxation,
            feature_cap=feature_cap)
        assert len(order) == budget and len(np.unique(order)) == budget
        orders[policy] = order
        # All held-out/future observations and truth are read only AFTER order finalized.
        reconstruction = mart_reconstruct(A[order], measurements[order], mart_epochs,
                                          relaxation=relaxation)
        rmse = float(np.sqrt(np.mean((reconstruction-truth)**2)))
        results.append(dict(policy=policy, rmse=rmse, selection_s=selection_s,
                            feedback_batches=sum(int(t['feedback_active']) for t in trace)))
    coverage = next(r['rmse'] for r in results if r['policy'] == 'coverage')
    for r in results:
        r['gain_vs_coverage'] = (coverage-r['rmse']) / max(coverage,1.e-12)
        r['shared_rays_with_coverage'] = len(set(orders[r['policy']]) & set(orders['coverage']))
    return results, orders


def write_csv(path, rows):
    if not rows:
        return
    with path.open('w', encoding='utf8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def digest(settings):
    return hashlib.sha256(json.dumps(settings,sort_keys=True).encode('utf8')).hexdigest()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--size', type=int, default=8)
    p.add_argument('--angles', type=int, default=4)
    p.add_argument('--factor', type=int, default=2)
    p.add_argument('--families', nargs='+', choices=FAMILIES, default=list(FAMILIES))
    p.add_argument('--objects-per-family', type=int, default=2)
    p.add_argument('--object-seed-base', type=int, default=900001)
    p.add_argument('--seeds', nargs='+', type=int, default=[104729,130363])
    p.add_argument('--models', nargs='+', choices=['same','independent'], default=['same','independent'])
    p.add_argument('--noise-fractions', nargs='+', type=float, default=[0., .005])
    p.add_argument('--offset', type=float, default=.15)
    p.add_argument('--step', type=float, default=.25)
    p.add_argument('--budget', type=int, default=128)
    p.add_argument('--warm-rays', type=int, default=16)
    p.add_argument('--batch', type=int, default=8)
    p.add_argument('--candidate-pool', type=int, default=16)
    p.add_argument('--provisional-epochs', type=int, default=4)
    p.add_argument('--mart-epochs', type=int, default=16)
    p.add_argument('--mart-relaxation', type=float, default=.25)
    p.add_argument('--feature-cap', type=float, default=3.)
    p.add_argument('--output-dir', type=Path, default=Path('results/experiment05b/robustness_08b'))
    p.add_argument('--allow-large', action='store_true')
    a = p.parse_args(argv)
    try:
        validate_grid(a.size, a.factor, a.allow_large)
    except (ValueError,OSError) as exc:
        p.error(str(exc))
    if (a.angles < 2 or a.objects_per_family < 1 or not a.seeds or len(set(a.seeds))!=len(a.seeds)
        or len(set(a.families))!=len(a.families) or len(set(a.models))!=len(a.models)
        or len(set(a.noise_fractions))!=len(a.noise_fractions)
        or a.object_seed_base < 0 or min(a.seeds) < 0 or not a.noise_fractions
        or any(not np.isfinite(v) or v < 0 for v in a.noise_fractions)
        or not np.isfinite(a.offset) or a.offset < 0
        or not np.isfinite(a.step) or not 0 < a.step <= 1
        or min(a.batch,a.candidate_pool,a.provisional_epochs,a.mart_epochs) < 1
        or not np.isfinite(a.mart_relaxation) or not 0 < a.mart_relaxation <= 1
        or not np.isfinite(a.feature_cap) or a.feature_cap < 1
        or not 2 <= a.warm_rays < 48 < a.budget <= a.size*a.size*a.angles*len(TILTS)
        or (48-a.warm_rays) % a.batch != 0):
        p.error('invalid frozen 05B-08B protocol')
    if a.output_dir.exists() and any(a.output_dir.iterdir()):
        p.error('output directory must be new or empty')
    # Save the frozen setup BEFORE results are generated.
    config = {k:(str(v) if isinstance(v,Path) else v) for k,v in vars(a).items()}
    plan = dict(study='05B-08B frozen exploratory robustness study',parameters=config,
                policies=list(POLICIES),independent_phantom_seed_rule='object_seed_base + 1009*family_index + instance',
                acquisition_seed_role='acquisition RNG only',
                noise_seed_rule='object_seed*37 + model_index*100003 + noise_index*17011 (mod 2^32)',
                noise='additive Gaussian sigma=fraction*RMS(clean); clamp negative values to zero for MART',
                mismatch='04Q-A trilinear fine-grid ray marching with detector offset; same=coarse A @ coarse truth',
                primary_outcome='paired final-budget relative RMSE gain vs coverage, averaged by object before any across-object summary',
                limitations=['New parameterized synthetic objects, not independent CT patient data',
                             'One numerical model with a separate trilinear-forward-model mismatch condition',
                             '4 model/noise conditions on each object are repeated measures, not independent objects',
                             'Previous exploratory analyses influenced policy choice and 48-ray switch; validation of that choice is limited to these newly seeded objects',
                             'Statistical uncertainty must cluster by object, not by ray/checkpoint/condition',
                             'No physical dose or clinical performance inference'])
    plan['protocol_sha256'] = digest(plan)
    a.output_dir.mkdir(parents=True,exist_ok=True)
    (a.output_dir/'protocol.json').write_text(json.dumps(plan,indent=2),encoding='utf8')
    A=system_matrix(a.size,a.angles,TILTS).tocsr()
    warm_orders={seed:voxel_coverage_order(A,a.size,a.angles,len(TILTS),a.budget,
                                           seed,a.candidate_pool) for seed in a.seeds}
    rows=[]; object_meta=[]
    for family_index,family in enumerate(a.families):
        for instance in range(a.objects_per_family):
            obj_seed=a.object_seed_base+1009*family_index+instance
            truth,fine=new_phantom(a.size,a.factor,family,obj_seed)
            object_id=f'{family}_{obj_seed}'
            object_meta.append(dict(object_id=object_id,family=family,object_seed=obj_seed,
                                    mean_attenuation=float(np.mean(truth)),max_attenuation=float(np.max(truth))))
            for model_index,model in enumerate(a.models):
                if model=='same':
                    clean=np.asarray(A@truth).ravel()
                else:
                    clean=project(fine,a.size,a.angles,TILTS,factor=a.factor,
                                  offset=a.offset,step=a.step,mode='linear')
                rel_mismatch=float(np.linalg.norm(clean - A@truth)/max(np.linalg.norm(A@truth),1.e-12))
                for noise_index,fraction in enumerate(a.noise_fractions):
                    noise_seed=(obj_seed*37+model_index*100003+noise_index*17011)%(2**32)
                    observed=nonnegative_noisy_measurements(clean,fraction,noise_seed)
                    for seed in a.seeds:
                        results,_=run_matched_case(A,observed,truth,warm_orders[seed],
                            n=a.size,angles=a.angles,budget=a.budget,acquisition_seed=seed,
                            warm_rays=a.warm_rays,batch=a.batch,candidate_pool=a.candidate_pool,
                            provisional_epochs=a.provisional_epochs,mart_epochs=a.mart_epochs,
                            relaxation=a.mart_relaxation,feature_cap=a.feature_cap)
                        for outcome in results:
                            row=dict(object_id=object_id,family=family,object_seed=obj_seed,
                                     acquisition_seed=seed,model=model,noise_fraction=fraction,
                                     offset=(a.offset if model=='independent' else 0.),
                                     relative_forward_mismatch=rel_mismatch,
                                     budget=a.budget,relaxation=a.mart_relaxation,**outcome)
                            rows.append(row)
                            print(f"{object_id} {model:11s} noise={fraction:g} seed={seed} {outcome['policy']:15s} "
                                  f"RMSE={outcome['rmse']:.6f} gain={outcome['gain_vs_coverage']:+.2%}",flush=True)
    write_csv(a.output_dir/'matched_cases.csv',rows)
    write_csv(a.output_dir/'object_manifest.csv',object_meta)
    # Object-level descriptive aggregates. Do not pool repeated conditions as independent observations.
    aggregated=[]
    for family in a.families:
        for model in a.models:
            for fraction in a.noise_fractions:
                for policy in POLICIES:
                    subset=[r for r in rows if r['family']==family and r['model']==model
                            and r['noise_fraction']==fraction and r['policy']==policy]
                    grouped={}
                    for r in subset:grouped.setdefault(r['object_id'],[]).append(r['gain_vs_coverage'])
                    by_object=np.array([np.mean(v) for v in grouped.values()],dtype=float)
                    aggregated.append(dict(family=family,model=model,noise_fraction=fraction,
                        policy=policy,n_objects=len(by_object),n_acquisition_runs=len(subset),
                        mean_object_gain=float(by_object.mean()),median_object_gain=float(np.median(by_object)),
                        worst_object_gain=float(by_object.min()),objects_with_positive_mean_gain=int((by_object>0).sum())))
    write_csv(a.output_dir/'object_level_summary.csv',aggregated)
    print(f'05B-08B complete: {len(rows)} paired policy records; {len(object_meta)} unique objects; output={a.output_dir}',flush=True)
    return rows


if __name__ == '__main__':
    main()
