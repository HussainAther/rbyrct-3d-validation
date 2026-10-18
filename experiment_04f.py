"""Experiment 04F: same-operator 3D MART versus matrix-based SIRT.

Both methods use the *identical* sparse Siddon ray-length matrix from 04B,
the *identical* synthetic target and measurements, and the same positive
initial image. This is a controlled solver comparison, NOT a CUDA benchmark.

Usage:
    python experiment_04f.py --size 8 --angles 4 --mart-epochs 2 --sirt-iterations 4 --output-dir results/experiment04f_smoke
    python experiment_04f.py --output-dir results/experiment04f
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np
from scipy import sparse

from experiment_04b import phantom_3d, system_matrix

TILTS = [-20.0, 0.0, 20.0]
EPS = 1e-10


def metrics(A: sparse.csr_matrix, x: np.ndarray, b: np.ndarray,
            target: np.ndarray) -> tuple[float, float]:
    rmse = float(np.sqrt(np.mean((x - target) ** 2)))
    relative_residual = float(np.linalg.norm(A @ x - b) / max(np.linalg.norm(b), EPS))
    if not np.isfinite(rmse) or not np.isfinite(relative_residual):
        raise FloatingPointError('Non-finite reconstruction metric')
    return rmse, relative_residual


def run_mart(A: sparse.csr_matrix, b: np.ndarray, target: np.ndarray,
             epochs: int, relaxation: float, checkpoints: list[int]):
    """Exactly the 04B MART exponent/update, with cumulative wall-clock timing."""
    if np.any(b < -EPS):
        raise ValueError('MART requires nonnegative measurements')
    if not (0 < relaxation <= 1):
        raise ValueError('MART relaxation must be in (0, 1]')
    x = np.full(A.shape[1], 0.3, dtype=np.float64)
    history = []
    clock = time.perf_counter()
    checkpoints_set = set(checkpoints)
    for epoch in range(1, epochs + 1):
        for ray in range(A.shape[0]):
            start, end = A.indptr[ray], A.indptr[ray + 1]
            ids, weights = A.indices[start:end], A.data[start:end]
            if len(ids) == 0:
                continue
            prediction = float(np.dot(weights, x[ids]))
            ratio = max(float(b[ray]), EPS) / max(prediction, EPS)
            exponent = relaxation * weights / np.max(weights)
            change = np.clip(exponent * np.log(max(ratio, EPS)), -12, 12)
            x[ids] = np.maximum(x[ids] * np.exp(change), EPS)
        if epoch in checkpoints_set:
            elapsed = time.perf_counter() - clock
            rmse, residual = metrics(A, x, b, target)
            history.append(dict(solver='MART', step=epoch, step_unit='epoch',
                                rmse=rmse, relative_projection_residual=residual,
                                elapsed_s=elapsed))
            print(f'MART epoch={epoch:3d} rmse={rmse:.6f} residual={residual:.6f} time={elapsed:.2f}s')
    return x, history


def run_sirt(A: sparse.csr_matrix, b: np.ndarray, target: np.ndarray,
             iterations: int, relaxation: float, checkpoints: list[int]):
    """Row/column-normalized simultaneous SIRT for the identical matrix.

    x <- max(0, x + lambda * C^-1 A^T R^-1 (b - Ax))
    R_ii = sum_j A_ij; C_jj = sum_i A_ij.
    Empty rows and unobserved voxels are guarded against division by zero.
    """
    if not (0 < relaxation <= 1):
        raise ValueError('SIRT relaxation must be in (0, 1]')
    A = A.tocsr()
    row_sum = np.asarray(A.sum(axis=1)).ravel()
    col_sum = np.asarray(A.sum(axis=0)).ravel()
    inv_row = np.divide(1.0, row_sum, out=np.zeros_like(row_sum), where=row_sum > 0)
    inv_col = np.divide(1.0, col_sum, out=np.zeros_like(col_sum), where=col_sum > 0)
    x = np.full(A.shape[1], 0.3, dtype=np.float64)
    history = []
    clock = time.perf_counter()
    checkpoints_set = set(checkpoints)
    for step in range(1, iterations + 1):
        correction = A.T @ ((b - A @ x) * inv_row)
        x = np.maximum(x + relaxation * correction * inv_col, 0.0)
        if step in checkpoints_set:
            elapsed = time.perf_counter() - clock
            rmse, residual = metrics(A, x, b, target)
            history.append(dict(solver='SIRT', step=step, step_unit='iteration',
                                rmse=rmse, relative_projection_residual=residual,
                                elapsed_s=elapsed))
            print(f'SIRT iter={step:3d} rmse={rmse:.6f} residual={residual:.6f} time={elapsed:.2f}s')
    return x, history


def checkpoints_to(maximum: int, canonical: list[int]) -> list[int]:
    return sorted(set([value for value in canonical if value <= maximum] + [maximum]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--size', type=int, default=16)
    parser.add_argument('--angles', type=int, default=12)
    parser.add_argument('--mart-epochs', type=int, default=20)
    parser.add_argument('--mart-relaxation', type=float, default=0.15)
    parser.add_argument('--sirt-iterations', type=int, default=400)
    parser.add_argument('--sirt-relaxation', type=float, default=1.0)
    parser.add_argument('--output-dir', type=Path, default=Path('results/experiment04f'))
    args = parser.parse_args()
    if args.size < 4 or args.angles < 2 or args.mart_epochs < 1 or args.sirt_iterations < 1:
        parser.error('size>=4, angles>=2 and positive iteration counts required')
    if not (0 < args.mart_relaxation <= 1 and 0 < args.sirt_relaxation <= 1):
        parser.error('Relaxations must belong to (0, 1]')

    args.output_dir.mkdir(parents=True, exist_ok=True)
    target = phantom_3d(args.size).reshape(-1)
    build_start = time.perf_counter()
    A = system_matrix(args.size, args.angles, TILTS).tocsr()
    build_seconds = time.perf_counter() - build_start
    assert A.shape == (3 * args.angles * args.size * args.size, args.size ** 3)
    assert np.all(A.data > 0) and np.isfinite(A.data).all()
    b = A @ target  # Exactly the same measurements for both solvers
    assert np.all(b >= -EPS) and np.isfinite(b).all()

    rng = np.random.default_rng(104729)
    p = rng.normal(size=A.shape[1]); q = rng.normal(size=A.shape[0])
    lhs, rhs = float(np.dot(A @ p, q)), float(np.dot(p, A.T @ q))
    adjoint_error = abs(lhs-rhs) / max(abs(lhs), abs(rhs), EPS)
    assert adjoint_error < 1e-10

    print('Experiment 04F — same sparse operator and measurements, CPU MART vs CPU SIRT')
    print(f'volume={args.size}^3 rays={A.shape[0]} nnz={A.nnz} matrix_build_s={build_seconds:.2f}')
    print(f'relative_adjoint_error={adjoint_error:.3e}')
    print('NOTE: MART epochs and SIRT iterations are not equivalent computational work.')
    mart_steps = checkpoints_to(args.mart_epochs, [1, 2, 4, 8, 12, 20, 40])
    sirt_steps = checkpoints_to(args.sirt_iterations, [1, 2, 4, 8, 12, 20, 50, 100, 200, 400])
    mart_x, mh = run_mart(A, b, target, args.mart_epochs, args.mart_relaxation, mart_steps)
    sirt_x, sh = run_sirt(A, b, target, args.sirt_iterations, args.sirt_relaxation, sirt_steps)

    records = mh + sh
    with (args.output_dir / 'convergence.csv').open('w', encoding='utf-8', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=list(records[0]))
        writer.writeheader(); writer.writerows(records)
    np.save(args.output_dir / 'phantom.npy', target.reshape((args.size,) * 3))
    np.save(args.output_dir / 'mart_reconstruction.npy', mart_x.reshape((args.size,) * 3))
    np.save(args.output_dir / 'sirt_reconstruction.npy', sirt_x.reshape((args.size,) * 3))
    np.save(args.output_dir / 'measurements.npy', b)
    protocol = {
        'experiment': '04F', 'volume_side': args.size, 'angles_per_tilt': args.angles,
        'tilts_degrees': TILTS, 'rays': int(A.shape[0]), 'nonzeros': int(A.nnz),
        'forward_model': 'identical explicit CPU Siddon path-length matrix A, imported from 04B',
        'measurements': 'noiseless A @ same phantom, for both methods',
        'initialization': 'both solvers start at x=0.3 everywhere',
        'mart_rule': 'sequential multiplicative, exponent=lambda * a_ij/max(a_i)',
        'mart_epochs': args.mart_epochs, 'mart_relaxation': args.mart_relaxation,
        'sirt_rule': 'simultaneous row- and column-sum-normalized additive update; positivity clipping',
        'sirt_iterations': args.sirt_iterations, 'sirt_relaxation': args.sirt_relaxation,
        'adjoint_error': adjoint_error,
        'matrix_build_seconds_excluded_from_solver_times': build_seconds,
        'limitations': ['CPU vs CPU; not ASTRA CUDA SIRT or GPU MART',
                        'Noisy measurements, adaptive acquisition, or physical dose not tested',
                        'Epoch and iteration counts are not workload-equivalent',
                        'MART and SIRT use different natural relaxation scales and update rules',
                        'One hand-designed phantom; no generalization claim']
    }
    (args.output_dir / 'protocol.json').write_text(json.dumps(protocol, indent=2), encoding='utf-8')
    print(f'Saved 04F results to {args.output_dir}')


if __name__ == '__main__':
    main()
