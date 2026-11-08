"""MART reconstruction kernel for RBYRCT-05B.

Uses the 04B/04F multiplicative per-ray update and positive initialization.
No ground truth, unacquired measurements, or SIRT are involved.
"""
from __future__ import annotations
import numpy as np
from scipy import sparse


def mart_reconstruct(A: sparse.spmatrix, measured: np.ndarray, epochs: int,
                     initial: float = 0.3, relaxation: float = 0.15,
                     ray_order: np.ndarray | None = None) -> np.ndarray:
    """Sequential MART, matching the per-row 04B update (including log clipping).

    `epochs` means complete passes through acquired rows, NOT SIRT iterations.
    The original row order is preserved unless `ray_order` is provided.
    """
    A = sparse.csr_matrix(A)
    b = np.asarray(measured, dtype=np.float64).reshape(-1)
    if A.shape[0] != b.size:
        raise ValueError("Observation/matrix row mismatch")
    if epochs < 1 or not (0 < relaxation <= 1):
        raise ValueError("epochs >= 1 and 0 < relaxation <= 1 required")
    if not (np.isfinite(initial) and initial > 0):
        raise ValueError("MART requires positive finite initialization")
    if (not np.isfinite(b).all() or (b < 0).any()
            or not np.isfinite(A.data).all() or (A.data < 0).any()):
        raise ValueError("MART requires nonnegative finite measurements/weights")
    order = (np.arange(A.shape[0], dtype=np.int64) if ray_order is None
             else np.asarray(ray_order, dtype=np.int64))
    if (len(order) != A.shape[0] or len(np.unique(order)) != len(order)
            or (order < 0).any() or (order >= A.shape[0]).any()):
        raise ValueError("ray_order must be a permutation of all acquired rows")
    x = np.full(A.shape[1], float(initial), dtype=np.float64)
    tiny = 1e-10
    for _ in range(epochs):
        for ray in order:
            lo, hi = A.indptr[ray], A.indptr[ray + 1]
            ids, weights = A.indices[lo:hi], A.data[lo:hi]
            if not len(ids):
                continue
            top = float(weights.max())
            if top <= 0:
                continue
            prediction = float(np.dot(weights, x[ids]))
            ratio = max(float(b[ray]), tiny) / max(prediction, tiny)
            exponent = relaxation * weights / top
            change = np.clip(exponent * np.log(max(ratio, tiny)), -12, 12)
            x[ids] = np.maximum(x[ids] * np.exp(change), tiny)
    return x
