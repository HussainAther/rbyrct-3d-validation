"""08AJ-E integration preflight ONLY. No 24-object comparisons or scientific outcomes.

Reuses existing, unchanged sparse geometry, projector, information selector, and MART.
Unresolved protocol choices are documented; this script cannot freeze or validate 08AJ.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_04qa import project
from experiment_05b_08b import nonnegative_noisy_measurements
from experiment_05b_mart import mart_reconstruct
from experiment_08k import select_information
from experiment_08aj_b import build_orders
from experiment_08aj_c_view import complete_view_order
from experiment_08aj_d import phantom, FAMILIES, SEEDS, ACQUISITION_SEEDS, MODELS, POLICIES, source_hashes

STAGE='08AJ-E integration preflight (draft, no confirmatory outcomes)'


def sha_array(a):
    a=np.asarray(a)
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def check_order(order, budget, n_rays):
    a=np.asarray(order)
    if (a.ndim!=1 or a.shape!=(budget,) or a.dtype.kind not in 'iu'
        or len(np.unique(a))!=budget or np.any(a<0) or np.any(a>=n_rays)):
        raise ValueError('invalid acquisition order: duplicate, out-of-range, wrong size or dtype')
    return a.astype(np.int64,copy=False)


def full_resolution_pair(family, seed, n, factor=2):
    """Fine truth generated at 2n and block averaged to n; shared latent object.

    This is a *draft forward-model adapter*: fine phantom uses same functional
    family and seed as coarse, so not independent phantom generation. It is
    independent forward PROJECTION arithmetic, not independent observations.
    """
    if factor!=2 or n<8:
        raise ValueError('draft forward adapter fixes factor=2 and n>=8')
    fine=phantom(family,seed,n*factor)
    coarse=fine.reshape(n,factor,n,factor,n,factor).mean(axis=(1,3,5))
    if not np.isfinite(coarse).all() or np.min(coarse)<=0:
        raise ValueError('invalid synthetic phantom')
    return coarse.ravel(), fine


def model_measurements(A, truth, fine, *, n, angles, model, noise_seed, noise_fraction=.005, offset=0.0, step=.5):
    if model not in MODELS:
        raise ValueError('invalid model')
    if A.shape[1] != n**3 or np.asarray(truth).shape!=(n**3,) or np.asarray(fine).shape!=(2*n,)*3:
        raise ValueError('model geometry/truth mismatch')
    if not (math.isfinite(noise_fraction) and noise_fraction>=0):
        raise ValueError('invalid noise')
    if model=='same':
        clean=np.asarray(A @ truth,dtype=np.float64).ravel()
    else:
        clean=np.asarray(project(fine,n,angles,TILTS,factor=2,offset=offset,step=step,mode='linear'),dtype=np.float64).ravel()
    if clean.shape!=(A.shape[0],) or not np.isfinite(clean).all() or np.any(clean<0):
        raise ValueError('nonfinite / invalid clean measurements')
    measured=nonnegative_noisy_measurements(clean,noise_fraction,noise_seed)
    if measured.shape!=clean.shape or not np.isfinite(measured).all():
        raise ValueError('invalid noisy measurements')
    return clean,measured


def acquisition_orders(A, *, n, angles, seed, budget, pool=8, warm=8, batch=8):
    if A.shape!=(n*n*angles*len(TILTS),n**3):
        raise ValueError('matrix shape is not the required ray catalogue')
    if not (0<warm<budget<=A.shape[0]):
        raise ValueError('invalid warm/budget')
    coverage=check_order(voxel_coverage_order(A,n,angles,len(TILTS),budget,seed,pool),budget,A.shape[0])
    diag,_,_=select_information(A,None,n,angles,coverage,budget,seed,warm_rays=warm,batch=batch,candidate_pool=pool)
    base=build_orders(n,angles,len(TILTS),seed)
    whole,_=complete_view_order(n,angles,tuple(TILTS),budget)
    orders={'information_diag':diag,'uniform_multiscale':base['uniform_multiscale'][:budget],
            'coverage':coverage,'stratified_random_04h':base['stratified_random_04h'][:budget],
            'complete_view':whole}
    if tuple(orders)!=POLICIES:
        raise ValueError('policy list differs from 08AJ-D draft')
    return {k:check_order(v,budget,A.shape[0]) for k,v in orders.items()}


def checked_mart(A, measurements, order, *, epochs=16, relaxation=.25):
    """Shared MART bridge; only acquired rows may reach the reconstruction kernel."""
    ids=check_order(order,len(order),A.shape[0])
    measurements=np.asarray(measurements,dtype=np.float64)
    if measurements.shape!=(A.shape[0],) or not np.isfinite(measurements).all() or np.any(measurements<0):
        raise ValueError('invalid measurements')
    if epochs<1 or not np.isfinite(relaxation) or not 0<relaxation<=1:
        raise ValueError('invalid MART configuration')
    output=np.asarray(mart_reconstruct(A[ids],measurements[ids],epochs=epochs,
                                      initial=.3,relaxation=relaxation))
    if output.shape!=(A.shape[1],) or not np.isfinite(output).all() or np.any(output<=0):
        raise ValueError('nonfinite, nonpositive or mismatched MART reconstruction')
    return output


def fixture(*, n=8, angles=4, budget=128, seed=940411):
    """Synthetic engineering smoke case only: NOT one of the 24 held-out objects."""
    if n!=8 or angles!=4 or budget!=128:
        raise ValueError('engineering fixture only accepts n=8, angles=4, budget=128')
    A=system_matrix(n,angles,TILTS).tocsr()
    orders=acquisition_orders(A,n=n,angles=angles,seed=seed,budget=budget,pool=8,warm=8,batch=8)
    assert np.array_equal(orders['information_diag'][:8],orders['coverage'][:8])
    # Engineering fixture uses seed outside held-out design; no object-level RMSE saved.
    truth,fine=full_resolution_pair('smooth_heterogeneity',970099,n)
    means={}
    for model in MODELS:
        clean,observed=model_measurements(A,truth,fine,n=n,angles=angles,model=model,
                                          noise_seed=970119,noise_fraction=.005)
        means[model]={'clean_sha256':sha_array(clean),'noisy_sha256':sha_array(observed),
                      'nonnegative_finite':bool(np.isfinite(observed).all() and np.min(observed)>=0)}
        # One MARΤ invocation is an engineering sanity check, not an accuracy comparison.
        if model=='same':
            reconstructed=checked_mart(A,observed,orders['information_diag'],epochs=2)
            means[model]['mart_two_epoch_finite_positive']=bool(np.all(reconstructed>0))
    return {'stage':STAGE,'verdict':'PREFLIGHT_PASS','complete':True,'frozen':False,
            'no_confirmatory_outcomes':True,'fixture_resolution':n,
            'fixture_object_seed':970099,'candidate_rays':A.shape[0], 'budget':budget,
            'policies':{k:{'ray_count':len(v),'order_sha256':sha_array(v)} for k,v in orders.items()},
            'models':means,'shared_warm_prefix':True,
            'unresolved':['64^3 independent projector costs not assessed',
                          'new families are not proven independent of earlier test object families',
                          'warm-start fairness across all policies not resolved',
                          'noise pairing and analysis/failure thresholds not frozen',
                          'complete-view feasibility varies with budget',
                          'full 24-object driver and external audit not implemented'],
            'notes':'2-epoch engineering-only MART sanity check; no phantom RMSE, gains or performance comparisons'}


def run(out):
    out=Path(out)
    if out.exists():
        raise FileExistsError('refusing to overwrite prior engineering results')
    out.mkdir(parents=True)
    status={'complete':False,'stage':STAGE,'no_confirmatory_outcomes':True}
    (out/'run_status.json').write_text(json.dumps(status,indent=2)+'\n')
    try:
        report=fixture()
        report['integration_source_sha256']={**source_hashes(),
            'experiment_08aj_e.py':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'experiment_04qa.py':hashlib.sha256(Path(__file__).with_name('experiment_04qa.py').read_bytes()).hexdigest()}
        (out/'integration_report.json').write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+'\n')
        status.update(complete=True,verdict='PREFLIGHT_PASS',frozen=False)
        (out/'run_status.json').write_text(json.dumps(status,indent=2)+'\n')
        (out/'manifest.sha256').write_text(''.join(hashlib.sha256((out/p).read_bytes()).hexdigest()+'  '+p+'\n' for p in ('integration_report.json','run_status.json')))
        print(json.dumps({'verdict':'PREFLIGHT_PASS','policies':len(report['policies']),
                          'models':len(report['models']),'no_confirmatory_outcomes':True,
                          'frozen':False,'unresolved':len(report['unresolved'])},indent=2))
    except Exception as exc:
        status.update(complete=False,verdict='FAIL',error=repr(exc))
        (out/'run_status.json').write_text(json.dumps(status,indent=2)+'\n')
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',required=True,type=Path)
    args=p.parse_args()
    run(args.output_dir)
