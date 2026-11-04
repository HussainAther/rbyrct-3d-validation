"""Acquired-only reliability-gated acquisition, MART-based 04OC port."""
from __future__ import annotations
import time
import numpy as np
from experiment_04g import TILTS
from experiment_05b_adaptive import adaptive_order, image_score, score_candidates
from experiment_05b_mart import mart_reconstruct
from experiment_05b_diagnostics import acquired_only_reliability

POLICIES=('adaptive_feedback','feedback_off_control','constant_feedback','reliability_gate')

class AcquiredOnly:
    """Fails loudly if code tries to read an unacquired measurement."""
    def __init__(self,observed):
        self.values=np.asarray(observed);self.allowed=set()
    def commit(self,ids):
        self.allowed.update(int(i) for i in ids)
    def __getitem__(self,ids):
        arr=np.asarray(ids,dtype=np.int64)
        if not all(int(i) in self.allowed for i in arr.ravel()):
            raise AssertionError('attempt to access unacquired measurement')
        return self.values[ids]


def online_order(A,observed,n,angles,warm_order,budget,seed,*,policy='reliability_gate',
                 warm_rays=128,batch=64,provisional_epochs=60,candidate_pool=64,
                 diagnostic_epochs=60,holdout_fraction=.2,threshold=2.0,
                 gate_strength=0.,constant_strength=.25,
                 diagnostic_every=256,mart_relaxation=0.15):
    """Acquired-only prospective policy; returns order, audit, selection seconds.

    Same candidate sampling, score_candidates and prefix reconstruction as 04J.
    Gate recomputes its holdout score only at a predeclared acquisition cadence.
    Previous gate strength is used between diagnostics. No truth is passed in.
    """
    if policy not in POLICIES or warm_rays<12 or budget<=warm_rays or budget>A.shape[0] or batch<1 or candidate_pool<1 or diagnostic_every<1 or threshold<=0 or not 0<holdout_fraction<.5 or not 0<=gate_strength<=1 or not 0<=constant_strength<=1:
        raise ValueError('invalid online policy parameters')
    from experiment_05b_adaptive import score_candidates as frozen_score
    rng=np.random.default_rng(seed+317)
    order=list(map(int,warm_order[:warm_rays]))
    if len(set(order))!=len(order):raise ValueError('duplicate warm rays')
    oracle=AcquiredOnly(observed);oracle.commit(order)
    remaining=np.ones(A.shape[0],bool);remaining[order]=False
    counts=np.asarray(A[order].sum(axis=0)).ravel().astype(float)
    viewcounts=np.bincount(np.asarray(order)//(n*n),minlength=angles*len(TILTS)).astype(int)
    audit=[];last_check=-diagnostic_every;strength=1.
    start=time.perf_counter()
    while len(order)<budget:
        ids=np.asarray(order,dtype=np.int64)
        if policy=='reliability_gate' and (not audit or len(order)-last_check>=diagnostic_every):
            sig = acquired_only_reliability(
                A, oracle, ids, n,
                diagnostic_epochs,
                holdout_fraction,
                seed + len(ids) * 13,
                mart_relaxation=mart_relaxation,
            )
            strength=gate_strength if sig['heldout_nrmse']>threshold else 1.
            last_check=len(order)
            audit.append(dict(acquired_before=len(order),**sig,threshold=threshold,feedback_strength_next=strength))
        elif policy=='adaptive_feedback':strength=1.
        elif policy=='feedback_off_control':strength=0.
        elif policy=='constant_feedback':strength=constant_strength
        x = mart_reconstruct(
            A[ids],
            oracle[ids],
            provisional_epochs,
            relaxation=mart_relaxation,
        )
        feat=image_score(x,n)
        count=min(batch,budget-len(order))
        for _ in range(count):
            available=np.flatnonzero(remaining)
            candidates=rng.choice(available,size=min(candidate_pool,len(available)),replace=False)
            scores=frozen_score(A,candidates,counts,viewcounts,n,feat,feedback_strength=strength)
            high=np.max(scores)
            chosen=int(np.min(candidates[np.isclose(scores,high,rtol=1e-13,atol=1e-14)]))
            order.append(chosen);remaining[chosen]=False
            lo,hi=A.indptr[chosen],A.indptr[chosen+1]
            counts[A.indices[lo:hi]]+=A.data[lo:hi]
            viewcounts[chosen//(n*n)]+=1
        oracle.commit(order[-count:])
    return np.asarray(order,dtype=np.int64),audit,time.perf_counter()-start