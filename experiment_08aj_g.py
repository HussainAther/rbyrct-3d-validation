"""08AJ-G draft acquisition fairness/noise pairing preflight, no outcome comparisons.

Preserves 08AJ-D/F source and does NOT freeze any prospective protocol.
The individual-ray policies share a 64-ray coverage prefix at 32^3;
complete-view acquisition never uses a partial-view prefix.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_08k import select_information
from experiment_08aj_b import build_orders
from experiment_08aj_c_view import complete_view_order
from experiment_08aj_d import ACQUISITION_SEEDS, MODELS, POLICIES, SEEDS
from experiment_08aj_e import check_order, full_resolution_pair, model_measurements, sha_array
from experiment_08aj_f import hashes_of_sources

STAGE='08AJ-G draft acquisition fairness and paired noise preflight'
INDIVIDUAL=('information_diag','uniform_multiscale','coverage','stratified_random_04h')
NOISE_FRACTION=0.005
WARM=64
POOL=16
BATCH=32


def measurement_seed(family:str, object_seed:int, acquisition_seed:int, model:str)->int:
    """Stable seed per paired condition, independent of acquisition policy.

    This is a proposed 08AJ-G draft rule, not a frozen protocol constant.
    """
    if family not in SEEDS or object_seed not in SEEDS[family]:
        raise ValueError('unregistered phantom object')
    if acquisition_seed not in ACQUISITION_SEEDS or model not in MODELS:
        raise ValueError('unregistered paired condition')
    payload=f'08AJ-G-noise-v1|{family}|{object_seed}|{acquisition_seed}|{model}'
    return int.from_bytes(hashlib.sha256(payload.encode('ascii')).digest()[:8], 'little')


def add_shared_prefix(prefix, raw_order, budget, nrows):
    """Prefill individual-ray baseline, preserving original relative order thereafter."""
    if not (0 < len(prefix) < budget <= nrows):
        raise ValueError('invalid prefix/budget')
    prefix=check_order(prefix,len(prefix),nrows)
    remaining=check_order(raw_order,len(raw_order),nrows)
    # Filtering the original order, not moving the warm-prefix rays twice.
    mask=~np.isin(remaining,prefix)
    return check_order(np.concatenate([prefix,remaining[mask]])[:budget],budget,nrows)


def fair_orders(A, *, n, angles, seed, budget, warm=WARM, pool=POOL, batch=BATCH):
    """Build draft 32^3-style comparable individual-ray histories.

    The complete-view arm is unmodified and explicitly exempt from shared prefix.
    """
    nrows=n*n*angles*len(TILTS)
    if A.shape != (nrows,n**3) or not (0<warm<budget<=nrows):
        raise ValueError('invalid geometry/warm/budget')
    if budget%(n*n):
        raise ValueError('complete-view requires budget divisible by n^2')
    coverage=check_order(voxel_coverage_order(A,n,angles,len(TILTS),budget,seed,pool),budget,nrows)
    prefix=coverage[:warm].copy()
    diag,_,_=select_information(A,None,n,angles,coverage,budget,seed,
                                warm_rays=warm,batch=batch,candidate_pool=pool)
    raw=build_orders(n,angles,len(TILTS),seed)
    whole,_=complete_view_order(n,angles,tuple(TILTS),budget)
    orders={
        'information_diag':check_order(diag,budget,nrows),
        'uniform_multiscale':add_shared_prefix(prefix,raw['uniform_multiscale'],budget,nrows),
        'coverage':coverage,
        'stratified_random_04h':add_shared_prefix(prefix,raw['stratified_random_04h'],budget,nrows),
        'complete_view':check_order(whole,budget,nrows),
    }
    if tuple(orders)!=POLICIES or not all(np.array_equal(orders[k][:warm],prefix) for k in INDIVIDUAL):
        raise AssertionError('individual-ray warm history mismatch')
    # Whole views must be complete, no partial prefix injected.
    whole_view_ids=np.unique(orders['complete_view']//(n*n))
    for view_id in whole_view_ids:
        ids=orders['complete_view'][orders['complete_view']//(n*n)==view_id]
        if len(ids)!=n*n or set(ids.tolist())!=set((view_id*n*n+np.arange(n*n)).tolist()):
            raise AssertionError('complete-view invariant violated')
    return orders, prefix


def paired_catalogue(A, truth, fine, *, family, object_seed, acquisition_seed, model, n, angles):
    """Compute a single full candidate catalogue for each object/seed/model.

    All policies index the very same noisy catalogue; no policy-specific RNG.
    """
    seed=measurement_seed(family,object_seed,acquisition_seed,model)
    clean,noisy=model_measurements(A,truth,fine,n=n,angles=angles,model=model,
                                    noise_seed=seed,noise_fraction=NOISE_FRACTION)
    if clean.shape!=(A.shape[0],) or noisy.shape!=clean.shape or not np.isfinite(noisy).all() or np.any(noisy<0):
        raise ValueError('invalid paired measurement catalogue')
    return {'seed':seed,'clean':clean,'noisy':noisy}


def sampled_noisy_values(catalogue, order):
    """Only values at acquired rows; validates one shared full catalogue."""
    noisy=np.asarray(catalogue['noisy'],dtype=np.float64)
    if noisy.ndim!=1 or not np.isfinite(noisy).all() or (noisy<0).any():
        raise ValueError('invalid noise catalogue')
    ids=check_order(order,len(order),len(noisy))
    return noisy[ids]


def fixture():
    # Engineering-only seed, deliberately absent from the 24-object roster.
    n,angles,budget,warm=8,4,128,8
    A=system_matrix(n,angles,TILTS).tocsr()
    orders,prefix=fair_orders(A,n=n,angles=angles,seed=940411,budget=budget,
                              warm=warm,pool=8,batch=8)
    truth,fine=full_resolution_pair('smooth_heterogeneity',970099,n)
    # Registered object seed needed for the draft seed scheme, but fixture
    # measurements are still explicitly engineering-only and no RMSE is computed.
    # Use the registered seed solely for noise-key validation, never as phantom truth.
    obj_seed=SEEDS['smooth_heterogeneity'][0]
    records={}
    for model in MODELS:
        catalogue=paired_catalogue(A,truth,fine,family='smooth_heterogeneity',
                       object_seed=obj_seed,acquisition_seed=940411,model=model,n=n,angles=angles)
        values={k:sampled_noisy_values(catalogue,v) for k,v in orders.items()}
        # Verify equality at shared ray IDs, including between different policies.
        for i,k in enumerate(orders):
            for other in list(orders)[i+1:]:
                shared=np.intersect1d(orders[k],orders[other]);
                km=dict(zip(orders[k].tolist(),values[k].tolist()))
                om=dict(zip(orders[other].tolist(),values[other].tolist()))
                if any(km[r]!=om[r] for r in shared.tolist()):
                    raise AssertionError('policy-dependent noise realization')
        records[model]={'noise_seed':catalogue['seed'],
                        'full_clean_sha256':sha_array(catalogue['clean']),
                        'full_noisy_sha256':sha_array(catalogue['noisy']),
                        'finite_nonnegative':True}
    return {
        'stage':STAGE,'verdict':'FAIRNESS_PREFLIGHT_PASS','complete':True,
        'frozen':False,'no_confirmatory_outcomes':True,'fixture_n':8,
        'fixture_object_seed':970099,'fixture_noise_key_object_seed':obj_seed,
        'common_prefix_length_fixture':warm,'proposed_main_warm':WARM,
        'individual_ray_policies':list(INDIVIDUAL),
        'complete_view_exempt_from_prefix':True,
        'complete_view_ids':np.unique(orders['complete_view']//(n*n)).tolist(),
        'order_sha256':{p:sha_array(v) for p,v in orders.items()},
        'prefix_sha256':sha_array(prefix),
        'paired_models':records,
        'noise_rule':'SHA256 canonical object/seed/model key, first 8 bytes little endian; one full noisy catalogue shared across policies',
        'engineering_only_no_accuracy_metrics':True,
        'open_items':[
            'Verify all 24 families against earlier synthetic cohorts and check historical overlap',
            'Review shared warm prefix at full 32^3 before committing protocol; changing original uniform/stratified orders must be documented',
            'Review inferential thresholds, bootstrap, failure and resource ceilings',
            'Test independent-model full-scale cost and numerical agreement with intended assumptions',
            'Implement resumable 24-object runner, independent audit, git/source lock',
            '64^3 complete-view comparisons require 4096+ rays; validate separately',
        ],
    }


def run(output_dir):
    root=Path(output_dir)
    if root.exists():
        raise FileExistsError('refusing to overwrite prior preflight results')
    root.mkdir(parents=True)
    status={'stage':STAGE,'complete':False,'frozen':False,'no_confirmatory_outcomes':True}
    (root/'run_status.json').write_text(json.dumps(status,indent=2)+'\n')
    try:
        result=fixture()
        result['source_sha256']={**hashes_of_sources(),
               Path(__file__).name:hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        (root/'fairness_report.json').write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n')
        status.update(complete=True,verdict='FAIRNESS_PREFLIGHT_PASS')
        (root/'run_status.json').write_text(json.dumps(status,indent=2,sort_keys=True)+'\n')
        names=('fairness_report.json','run_status.json')
        (root/'manifest.sha256').write_text(''.join(hashlib.sha256((root/f).read_bytes()).hexdigest()+'  '+f+'\n' for f in names))
        print(json.dumps({'verdict':status['verdict'],'policies':len(result['order_sha256']),
                         'forward_models':len(result['paired_models']),
                         'shared_prefix_for_individual_policies':True,
                         'complete_view_prefix_exempt':True,'frozen':False,
                         'no_confirmatory_outcomes':True,'open_items':len(result['open_items'])},indent=2))
        return result
    except Exception as exc:
        status.update(complete=False,verdict='FAIL',error=repr(exc))
        (root/'run_status.json').write_text(json.dumps(status,indent=2)+'\n')
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--freeze',action='store_true')
    a=p.parse_args()
    if a.freeze:
        p.error('08AJ-G is engineering-only and cannot freeze the prospective protocol')
    run(a.output_dir)
