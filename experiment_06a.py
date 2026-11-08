"""RBYRCT-06A: developmental coverage-guarded MART ray acquisition.

No offline truth or candidate measurement is accessed by selection. 06A does not
establish superiority or justify choosing eta from held-out 05B outcomes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_05b_adaptive import image_score, score_candidates
from experiment_05b_gate import AcquiredOnly
from experiment_05b_mart import mart_reconstruct


def projected_imbalance(A, candidates, counts):
    """Mean squared deviation of prospective voxel path-length totals.

    Geometry-only, global statistic. Raw units depend on voxel/ray geometry;
    compare within the SAME candidate pool using a relative tolerance.
    """
    A = A.tocsr()
    counts = np.asarray(counts, dtype=float)
    if counts.shape != (A.shape[1],) or not np.isfinite(counts).all() or (counts < 0).any():
        raise ValueError('invalid voxel coverage')
    out = np.empty(len(candidates), dtype=float)
    for i, ray in enumerate(candidates):
        lo, hi = A.indptr[int(ray)], A.indptr[int(ray)+1]
        proposed = counts.copy()
        proposed[A.indices[lo:hi]] += A.data[lo:hi]
        out[i] = float(np.var(proposed))
    return out


def choose_guarded(A, candidates, counts, viewcounts, n, features, *, eta):
    """Choose highest gradient score among geometrically admissible candidates.

    Coverage-only reference is the candidate maximizing the FROZEN coverage
    score. Let C(a) be prospective voxel-path-weight variance. Admissible rays
    satisfy C(a) <= C(reference) + eta * max(C(reference), 1e-12).
    This always admits the reference. eta=0 is a strict guard; eta=inf
    reduces exactly to the frozen gradient scorer within the same pool.
    """
    if np.isnan(eta) or eta < 0:
        raise ValueError('eta must be nonnegative')
    cand = np.asarray(candidates, dtype=np.int64)
    if len(cand) == 0 or len(np.unique(cand)) != len(cand) or (cand < 0).any() or (cand >= A.shape[0]).any():
        raise ValueError('invalid candidate pool')
    coverage_score = score_candidates(A, cand, counts, viewcounts, n, np.ones(A.shape[1]), feedback_strength=0.)
    gradient_score = score_candidates(A, cand, counts, viewcounts, n, features, feedback_strength=1.)
    if not np.isfinite(coverage_score).all() or not np.isfinite(gradient_score).all():
        raise RuntimeError('nonfinite selection scores')
    ref_positions = np.flatnonzero(np.isclose(coverage_score, max(coverage_score), rtol=1e-13, atol=1e-14))
    ref = int(min(ref_positions, key=lambda i: int(cand[i])))
    imbalance = projected_imbalance(A, cand, counts)
    cref = float(imbalance[ref])
    allowable = cref + eta * max(cref, 1e-12)
    eligible = imbalance <= allowable + 1e-14
    eligible[ref] = True
    best = max(gradient_score[eligible])
    best_positions = np.flatnonzero(eligible & np.isclose(gradient_score, best, rtol=1e-13, atol=1e-14))
    pos = int(min(best_positions, key=lambda i: int(cand[i])))
    return int(cand[pos]), dict(coverage_reference_ray=int(cand[ref]),
        reference_imbalance=cref, chosen_imbalance=float(imbalance[pos]),
        admissible_count=int(eligible.sum()), candidate_count=int(len(cand)),
        constrained=int(not eligible.all()), selected_reference=int(pos == ref))


def acquire_guarded(A, observations, n, angles, warm_order, budget, seed, *,
                    eta=.05, warm_rays=16, batch=8, candidate_pool=16,
                    provisional_epochs=4, relaxation=.25):
    """Return order, batch trace, duration; read only previously acquired y.

    The caller may pass AcquiredOnly to enforce the same invariant independently.
    New batch observations become accessible only AFTER the batch is chosen.
    """
    A = A.tocsr()
    if A.shape != (n*n*angles*len(TILTS), n**3):
        raise ValueError('geometry mismatch')
    if not (0 < warm_rays < budget <= A.shape[0] and min(batch,candidate_pool,provisional_epochs)>=1
            and np.isfinite(relaxation) and 0 < relaxation <= 1 and not np.isnan(eta) and eta >= 0):
        raise ValueError('invalid acquisition configuration')
    warm = np.asarray(warm_order[:warm_rays], dtype=np.int64)
    if (len(warm)!=warm_rays or len(np.unique(warm))!=warm_rays
            or (warm<0).any() or (warm>=A.shape[0]).any()):
        raise ValueError('invalid warm history')
    order = list(map(int,warm))
    remaining=np.ones(A.shape[0],bool); remaining[warm]=False
    counts=np.asarray(A[warm].sum(axis=0)).ravel().astype(float)
    views=np.bincount(warm//(n*n), minlength=angles*len(TILTS)).astype(int)
    rng=np.random.default_rng(seed+317)
    trace=[]
    start=time.perf_counter()
    while len(order)<budget:
        acquired=len(order)
        ids=np.asarray(order,dtype=np.int64)
        x=mart_reconstruct(A[ids], observations[ids], provisional_epochs, relaxation=relaxation)
        features=image_score(x,n)
        b=min(batch,budget-len(order))
        choices=[]
        for _ in range(b):
            available=np.flatnonzero(remaining)
            pool=rng.choice(available, size=min(candidate_pool,len(available)), replace=False)
            chosen,audit=choose_guarded(A,pool,counts,views,n,features,eta=eta)
            choices.append(audit)
            order.append(chosen);remaining[chosen]=False
            lo,hi=A.indptr[chosen],A.indptr[chosen+1]
            counts[A.indices[lo:hi]]+=A.data[lo:hi]
            views[chosen//(n*n)]+=1
        if hasattr(observations,'commit'):
            observations.commit(order[-b:])
        trace.append(dict(acquired_before=acquired,acquired_after=len(order),
            choices=b,eta=eta,mean_eligible=float(np.mean([z['admissible_count'] for z in choices])),
            fraction_guard_binding=float(np.mean([z['constrained'] for z in choices])),
            fraction_coverage_reference=float(np.mean([z['selected_reference'] for z in choices]))))
    return np.asarray(order,dtype=np.int64), trace, time.perf_counter()-start


def run_development_smoke(output_dir):
    """Tiny 4^3 manufactured-signal check, NOT evaluation or policy tuning."""
    out=Path(output_dir)
    if out.exists() and any(out.iterdir()):
        raise ValueError('refusing to overwrite existing output')
    out.mkdir(parents=True,exist_ok=True)
    n=4; angles=2; budget=48; warm_rays=12
    A=system_matrix(n,angles,TILTS).tocsr()
    rng=np.random.default_rng(606)
    truth=.1+.7*rng.random(n**3)
    observed=np.asarray(A@truth).ravel()
    warm=voxel_coverage_order(A,n,angles,len(TILTS),budget,1901,8)
    records=[]; audits=[]; orders={}
    for label,eta in [('strict',0.),('guarded',.05),('loose',float('inf'))]:
        oracle=AcquiredOnly(observed);oracle.commit(warm[:warm_rays])
        order,trace,duration=acquire_guarded(A,oracle,n,angles,warm,budget,1901,
            eta=eta,warm_rays=warm_rays,batch=6,candidate_pool=8,provisional_epochs=2)
        if len(np.unique(order))!=budget:raise RuntimeError('nonunique acquisition')
        orders[label]=order
        records.append(dict(policy=label,eta=str(eta),unique_rays=len(np.unique(order)),
            total_seconds=duration,ray_order_sha256=hashlib.sha256(order.astype('<i8').tobytes()).hexdigest(),
            final_acquired_only_pass=1))
        audits.extend(dict(policy=label,**row) for row in trace)
    with (out/'development_runs.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    with (out/'batch_audit.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(audits[0]));w.writeheader();w.writerows(audits)
    config=dict(stage='06A exploratory development smoke only',size=n,angles=angles,budget=budget,
        warm_rays=warm_rays,batch=6,candidate_pool=8,provisional_epochs=2,relaxation=.25,
        eta_values=[0,.05,'inf'],synthetic_seed=606,acquisition_seed=1901,
        heldout_objects_used=False,primary_result='No policy performance conclusion')
    (out/'protocol.json').write_text(json.dumps(config,indent=2)+'\n')
    return records


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,default=Path('results/experiment06a/development_smoke_first'))
    a=p.parse_args()
    for r in run_development_smoke(a.output_dir):print(r)


if __name__=='__main__':
    main()
