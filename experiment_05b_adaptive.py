"""MART-driven acquired-only adaptive selection. Ported from 04J geometry score.

`provisional_epochs` counts MART passes. Feedback-off keeps the identical
candidate sampling and geometry, but applies zero feature strength.
"""
from __future__ import annotations
import time
import numpy as np
from experiment_04g import TILTS
from experiment_05b_mart import mart_reconstruct

def image_score(x,n):
    """Data-derived local feature magnitude, positive even in flat regions."""
    v=np.asarray(x).reshape(n,n,n)
    dz,dy,dx=np.gradient(v)
    g=np.sqrt(dx*dx+dy*dy+dz*dz)
    # Spatial uncertainty proxy: emphasize reconstructed edges, not truth.
    return 0.05+g.ravel()/max(float(np.mean(g)),1.e-8)


def score_candidates(A,candidates,counts,viewcounts,n,features,coverage_alpha=0.25,
                     feedback_strength=1.0):
    """No dependence on future measurements; geometry counts + current estimate."""
    out=[]
    for ray in candidates:
        lo,hi=A.indptr[ray],A.indptr[ray+1]
        idx=A.indices[lo:hi]; weights=A.data[lo:hi]
        view=int(ray)//(n*n)
        if not len(idx):out.append(0.);continue
        f=1.0+feedback_strength*(features[idx]-1.0)
        f=np.maximum(f,0.05)
        value=float(np.dot(weights,f/(coverage_alpha+counts[idx])))/max(float(weights.sum()),1e-12)
        out.append(value/np.sqrt(1.+viewcounts[view]))
    return np.asarray(out)


def adaptive_order(A, observations, n, angles, warm_order, budget, seed,
                   warm_rays=128, batch=64, provisional_epochs=60,
                   candidate_pool=64, feedback_strength=1.0,
                   mart_relaxation=0.15):
    """Returns selected ray IDs and trace. Only observations[acquired IDs] accessed.

    observations is a synthetic measurement oracle. It is indexed only at
    already selected IDs, after the corresponding batch is committed.
    """
    if warm_rays<1 or warm_rays>=budget or batch<1 or candidate_pool<1 or provisional_epochs<1 or feedback_strength<0:
        raise ValueError('invalid adaptive parameters')
    rng=np.random.default_rng(seed+317)
    order=list(np.asarray(warm_order[:warm_rays],dtype=np.int64))
    remaining=np.ones(A.shape[0],dtype=bool);remaining[order]=False
    counts=np.asarray(A[order].sum(axis=0)).ravel().astype(float)
    viewcounts=np.bincount(np.asarray(order)//(n*n),minlength=angles*len(TILTS)).astype(int)
    trace=[]
    elapsed=time.perf_counter()
    while len(order)<budget:
        ids=np.asarray(order,dtype=np.int64)
        # Only previously acquired measurements influence this estimate.
        x = mart_reconstruct(
            A[ids],
            observations[ids],
            provisional_epochs,
            relaxation=mart_relaxation,
        )
        features=image_score(x,n)
        target_count=min(batch,budget-len(order))
        for _ in range(target_count):
            available=np.flatnonzero(remaining)
            candidates=rng.choice(available,size=min(candidate_pool,len(available)),replace=False)
            scores=score_candidates(A,candidates,counts,viewcounts,n,features,
                                    feedback_strength=feedback_strength)
            high=np.max(scores)
            winners=candidates[np.isclose(scores,high,rtol=1e-13,atol=1e-14)]
            chosen=int(np.min(winners))
            order.append(chosen);remaining[chosen]=False
            lo,hi=A.indptr[chosen],A.indptr[chosen+1]
            counts[A.indices[lo:hi]]+=A.data[lo:hi]
            viewcounts[chosen//(n*n)]+=1
        trace.append(dict(acquired=len(order),next_batch_size=target_count,
                          provisional_epochs=provisional_epochs,
                          estimate_norm=float(np.linalg.norm(x)),
                          feature_std=float(features.std())))
    return np.asarray(order,dtype=np.int64),trace,time.perf_counter()-elapsed


