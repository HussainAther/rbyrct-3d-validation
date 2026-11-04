"""Acquired-only MART reliability diagnostics (04O protocol, MART engine)."""
from __future__ import annotations
import numpy as np
from experiment_05b_mart import mart_reconstruct
from experiment_05b_adaptive import image_score

def acquired_only_reliability(A, observed, ids, n, epochs=60, holdout_fraction=.2, seed=42):
    """All accesses to observed are restricted to ids. No ground truth argument."""
    ids=np.asarray(ids,dtype=np.int64)
    if len(ids)<12 or len(np.unique(ids))!=len(ids) or not 0<holdout_fraction<.5:
        raise ValueError('invalid acquired prefix or holdout')
    rng=np.random.default_rng(seed)
    perm=rng.permutation(len(ids))
    n_hold=max(2,min(len(ids)-4,int(round(len(ids)*holdout_fraction))))
    hold=ids[perm[:n_hold]];train=ids[perm[n_hold:]]
    btrain=np.asarray(observed[train]); bhold=np.asarray(observed[hold])
    model=mart_reconstruct(A[train],btrain,epochs)
    pred=np.asarray(A[hold]@model)
    # Divide by RMS observed amplitude, not by potentially tiny residual norms.
    normalizer=max(float(np.sqrt(np.mean(bhold*bhold))),1.e-12)
    heldout_nrmse=float(np.sqrt(np.mean((pred-bhold)**2))/normalizer)
    # Disjoint training subsets: reproducible stability proxy; both are observed.
    left=train[::2];right=train[1::2]
    f1=image_score(mart_reconstruct(A[left],observed[left],epochs),n)
    f2=image_score(mart_reconstruct(A[right],observed[right],epochs),n)
    d1=f1-f1.mean();d2=f2-f2.mean();denom=np.linalg.norm(d1)*np.linalg.norm(d2)
    stability=float(np.dot(d1,d2)/denom) if denom>1.e-12 else 0.
    return dict(heldout_nrmse=heldout_nrmse,feature_split_correlation=stability,
                feature_instability=1.-stability,n_train=len(train),n_holdout=len(hold))


