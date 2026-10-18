"""04G: fixed-policy individual-ray acquisition on a validated 3D Siddon matrix.

All policies receive exactly B observed line integrals and reconstruct with the
04F CPU matrix-SIRT implementation. Selector never reads phantom measurements.
This is a deterministic, noiseless, one-phantom DEVELOPMENT benchmark: not proof
of generalization, dose savings, or genuinely measurement-adaptive acquisition.

Example:
 python experiment_04g.py --size 8 --angles 4 --budgets 64 128 --sirt-iterations 30
 python experiment_04g.py --size 16 --angles 12 --budgets 512 1024 2048 4096
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.fft import dctn
from experiment_04b import phantom_3d, system_matrix
from experiment_04f import run_sirt

TILTS = [-20.0, 0.0, 20.0]
SEED = 104729


def spread(n: int) -> np.ndarray:
    """Balanced coarse-to-fine index ordering, no repeated indices."""
    if n < 1: raise ValueError('n must be positive')
    result = [0]
    remaining = set(range(1, n))
    while remaining:
        best = max(remaining, key=lambda j: (min(abs(j-k) for k in result), -j))
        result.append(best); remaining.remove(best)
    return np.asarray(result, dtype=np.int64)


def policies(n: int, angles: int, tilts: int, seed: int) -> dict[str, np.ndarray]:
    """Every ordering covers all rays exactly once; flat order = tilt, angle, row, col."""
    rows = tilts * angles * n * n
    rng = np.random.default_rng(seed)
    rand = rng.permutation(rows)
    av = spread(angles)
    tv = spread(tilts)
    dv = spread(n)
    # Interleave views and detector positions, staying balanced across all views.
    views = [(int(t), int(a)) for a in av for t in tv]
    detectors = [(int(r), int(c)) for r in dv for c in dv]
    uniform = np.asarray([((t*angles+a)*n+r)*n+c
                          for r,c in detectors for t,a in views], dtype=np.int64)
    # Coverage-oriented: rotates the detector ordering by view, changing where
    # early measurements land while guaranteeing eventual full ray coverage.
    balanced = np.asarray([((t*angles+a)*n+detectors[(k + v*7) % (n*n)][0])*n+
                            detectors[(k + v*7) % (n*n)][1]
                            for k in range(n*n) for v,(t,a) in enumerate(views)], dtype=np.int64)
    # Conventional complete-view acquisition: equal-spaced azimuths, all detector pixels.
    whole_views = np.asarray([((t*angles+a)*n+r)*n+c
                       for t,a in views for r in range(n) for c in range(n)], dtype=np.int64)
    result = {'uniform_scalar':uniform, 'random':rand,
              'geometry_balanced':balanced, 'uniform_complete_views':whole_views}
    for key, value in result.items():
        if len(value) != rows or not np.array_equal(np.sort(value), np.arange(rows)):
            raise AssertionError(f'{key}: not a permutation')
    return result


def low_frequency_basis(n: int, side: int) -> np.ndarray:
    """Orthonormal 3D DCT basis, shape (n**3, side**3), no phantom information."""
    if not 1 <= side <= n: raise ValueError('basis side must be in [1,n]')
    basis = np.empty((n**3, side**3), dtype=np.float64)
    j = 0
    for z in range(side):
        for y in range(side):
            for x in range(side):
                freq = np.zeros((n,n,n), dtype=np.float64)
                freq[z,y,x] = 1.0
                basis[:,j] = dctn(freq, type=3, norm='ortho').ravel()
                j += 1
    return basis


def geometry_ig_order(A: sparse.csr_matrix, basis: np.ndarray,
                      max_budget: int, batch: int=16, prior_precision: float=1.0,
                      seed: int=SEED) -> np.ndarray:
    """Approximate fixed D-optimal order via batched posterior-covariance update.

    Scores are geometry-only q_i^T Cov q_i, where q=A @ DCT basis.
    The same covariance is updated using all selected rows in each batch.
    Batching makes this a heuristic approximation, not exact sequential greedy IG.
    """
    if batch < 1 or prior_precision <= 0: raise ValueError('invalid IG parameters')
    Q = np.asarray(A @ basis, dtype=np.float64)
    # Row normalize projection features to avoid preferentially scoring long rays.
    norms = np.asarray(A.sum(axis=1)).ravel()
    Q /= np.maximum(norms[:,None], 1e-12)
    # scale to a stable, dimensionless feature signal
    Q *= np.sqrt(Q.shape[1])
    nrows, dim = Q.shape
    cov = np.eye(dim) / prior_precision
    selected = np.zeros(nrows, dtype=bool)
    order = []
    for start in range(0, max_budget, batch):
        step = min(batch, max_budget-start)
        scores = np.einsum('ij,ij->i', Q @ cov, Q, optimize=True)
        scores[selected] = -np.inf
        # deterministic tie handling from original index ordering
        chosen = np.argpartition(scores, -step)[-step:]
        chosen = chosen[np.lexsort((chosen, -scores[chosen]))]
        selected[chosen] = True
        order.extend(chosen.tolist())
        C = Q[chosen]
        V = cov @ C.T
        middle = np.eye(step) + C @ V
        cov -= V @ np.linalg.solve(middle, V.T)
        cov = (cov + cov.T) * 0.5
    # The remainder is not needed for this experiment; still a valid prefix order.
    return np.asarray(order, dtype=np.int64)


def acquire(A, full_b, target, order, budget, iterations, relaxation):
    ids = order[:budget]
    sampled = A[ids].tocsr()
    observations = full_b[ids]  # ONLY acquired measurements passed to solver
    checkpoints = [iterations]
    recon, history = run_sirt(sampled, observations, target, iterations, relaxation, checkpoints)
    return recon, history[-1]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--size', type=int, default=16)
    p.add_argument('--angles', type=int, default=12)
    p.add_argument('--budgets', type=int, nargs='+', default=[512,1024,2048,4096])
    p.add_argument('--sirt-iterations', type=int, default=400)
    p.add_argument('--sirt-relaxation', type=float, default=1.0)
    p.add_argument('--ig-basis-side', type=int, default=3)
    p.add_argument('--ig-batch', type=int, default=16)
    p.add_argument('--seed', type=int, default=SEED)
    p.add_argument('--output-dir', type=Path, default=Path('results/experiment04g'))
    args = p.parse_args()
    total = len(TILTS)*args.angles*args.size**2
    if args.size < 4 or args.angles < 2 or args.sirt_iterations < 1:
        p.error('size>=4, angles>=2, iterations>=1 required')
    if not args.budgets or min(args.budgets) < 1 or max(args.budgets) > total:
        p.error(f'budgets must lie in [1, {total}]')
    if not 0 < args.sirt_relaxation <= 1: p.error('SIRT relaxation must lie in (0,1]')
    if not 1 <= args.ig_basis_side <= args.size or args.ig_batch < 1:
        p.error('invalid IG basis/batch')
    out=args.output_dir; out.mkdir(parents=True,exist_ok=True)
    t=time.perf_counter()
    A=system_matrix(args.size,args.angles,TILTS).tocsr()
    build_s=time.perf_counter()-t
    target=phantom_3d(args.size).ravel()
    full_b=A@target
    print(f'04G — 3D fixed-policy individual-ray benchmark\nvolume={args.size}^3 rays={total} nnz={A.nnz} build_s={build_s:.2f}')
    orders=policies(args.size,args.angles,len(TILTS),args.seed)
    t=time.perf_counter()
    basis=low_frequency_basis(args.size,args.ig_basis_side)
    orders['fixed_approx_information_gain']=geometry_ig_order(A,basis,max(args.budgets),args.ig_batch,args.ig_basis_side and 1.0,args.seed)
    ig_s=time.perf_counter()-t
    records=[]
    for budget in sorted(set(args.budgets)):
        for name,order in orders.items():
            assert len(np.unique(order[:budget]))==budget
            recon,result=acquire(A,full_b,target,order,budget,args.sirt_iterations,args.sirt_relaxation)
            key=hashlib.sha256(order[:budget].astype('<i8').tobytes()).hexdigest()
            record={'policy':name,'budget':budget,'rmse':result['rmse'],
                'residual_on_acquired':result['relative_projection_residual'],
                'reconstruction_s':result['elapsed_s'],
                'acquisition_hash':key,'selection_s':ig_s if name=='fixed_approx_information_gain' else 0.0}
            records.append(record)
            print(f'{name:31} rays={budget:4} RMSE={result["rmse"]:.6f} '
                  f'acquired_residual={result["relative_projection_residual"]:.5f} '
                  f'solver_s={result["elapsed_s"]:.3f}')
            np.save(out / f'{name}_{budget}_reconstruction.npy',recon.reshape((args.size,)*3))
    with (out/'metrics.csv').open('w',newline='',encoding='utf-8') as fh:
        writer=csv.DictWriter(fh,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    np.save(out/'phantom.npy',target.reshape((args.size,)*3))
    protocol={'experiment':'04G','size':args.size,'angles_per_tilt':args.angles,
        'tilts_degrees':TILTS,'rays':total,'budgets':sorted(set(args.budgets)),
        'seed':args.seed,'sirt_iterations':args.sirt_iterations,'sirt_relaxation':args.sirt_relaxation,
        'ig_basis_side':args.ig_basis_side,'ig_batch':args.ig_batch,
        'ig_selection_seconds_for_longest_prefix':ig_s,'matrix_build_seconds':build_s,
        'geometry':'04B explicit CPU Siddon sparse matrix, tilt-major/angle-major/detector row-major',
        'information_gate':'All policies are measurement-independent; full b is indexed only after ray order is frozen',
        'limitations':['Single development phantom, noiseless deterministic simulation',
           'Information gain is batched approximate covariance-based score, NOT true measurement-adaptive',
           'Uniform complete-view policy evaluated by scalar-ray prefix (possibly partial final view)',
           'Policies may have different angular/detector coverage; matched individual-ray count only',
           'Different design compute cost; no physical dose or scanner timing validation',
           'Geometry-balanced policy is a deterministic rotated detector schedule, not optimized coverage',
           'The fixed policy is derived from geometry only; no access to phantom measurements']}
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    print(f'Results saved to {out}')

if __name__=='__main__': main()
