"""Experiment 04D: shared-data 3D MART vs CUDA SIRT reconstruction benchmark.

Both reconstruct from the SAME ASTRA-generated line-integral measurements and
3D acquisition geometry. The projectors remain numerically different (~3% on
prior phantom test); comparisons are descriptive and not solver superiority
proof. MART runs on CPU, SIRT on GPU. No ray dose or acquisition advantage claim.

Dependencies: experiment_04b.py, experiment_04c.py, numpy, scipy, ASTRA CUDA.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import time

import astra
import numpy as np
from experiment_04b import phantom_3d, system_matrix
from experiment_04c import geometry_vectors


def diagnostics(x, target, b, A):
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    target = target.reshape(-1)
    b = b.reshape(-1)
    pred = A @ x
    return {
        'rmse': float(np.sqrt(np.mean((x - target) ** 2))),
        'mae': float(np.mean(np.abs(x - target))),
        'reference_residual': float(np.linalg.norm(pred - b) / max(np.linalg.norm(b), 1e-12)),
        'min_value': float(np.min(x)),
        'max_value': float(np.max(x)),
    }


def run_mart(A, b, target, checkpoints, relaxation):
    """Sequential multiplicative MART, same update as Experiment 04B."""
    if (b < 0).any():
        raise ValueError('Negative projection observations cannot be used by MART.')
    tiny = 1e-10
    x = np.full(A.shape[1], 0.3, dtype=np.float64)
    row_max = np.maximum(np.asarray(A.max(axis=1).toarray()).ravel(), tiny)
    results = []
    t0 = time.perf_counter()
    epoch = 0
    for stop in checkpoints:
        while epoch < stop:
            for i in range(A.shape[0]):
                a, z = A.indptr[i], A.indptr[i + 1]
                ids, weights = A.indices[a:z], A.data[a:z]
                if not len(ids):
                    continue
                prediction = float(np.dot(weights, x[ids]))
                ratio = max(float(b[i]), tiny) / max(prediction, tiny)
                exponent = relaxation * weights / row_max[i]
                change = np.clip(exponent * np.log(max(ratio, tiny)), -12, 12)
                x[ids] = np.maximum(x[ids] * np.exp(change), tiny)
            epoch += 1
        record = {'method': 'MART_CPU', 'step': epoch, 'step_unit': 'epoch',
                  'elapsed_s': time.perf_counter() - t0,
                  **diagnostics(x, target, b, A)}
        results.append(record)
        print(f"MART epoch={epoch:3d} rmse={record['rmse']:.6f} "
              f"cpu_residual={record['reference_residual']:.6f} time={record['elapsed_s']:.2f}s")
    return x.reshape(target.shape), results


def run_sirt(proj_id, proj_geom, vol_geom, A, b, target, checkpoints):
    """SIRT3D_CUDA receives exactly the shared ASTRA measurement object."""
    rec_id = alg_id = None
    try:
        rec_id = astra.data3d.create('-vol', vol_geom, 0.0)
        cfg = astra.astra_dict('SIRT3D_CUDA')
        cfg['ProjectionDataId'] = proj_id
        cfg['ReconstructionDataId'] = rec_id
        # Constrain SIRT to the same nonnegative domain as MART.
        cfg['option'] = {'MinConstraint': 0.0}
        alg_id = astra.algorithm.create(cfg)
        results = []
        steps = 0
        t0 = time.perf_counter()
        for stop in checkpoints:
            astra.algorithm.run(alg_id, stop - steps)
            steps = stop
            elapsed = time.perf_counter() - t0
            x = astra.data3d.get(rec_id)
            record = {'method': 'SIRT3D_CUDA', 'step': steps, 'step_unit': 'iteration',
                      'elapsed_s': elapsed, **diagnostics(x, target, b, A)}
            results.append(record)
            print(f"SIRT iter={steps:3d} rmse={record['rmse']:.6f} "
                  f"cpu_residual={record['reference_residual']:.6f} time={record['elapsed_s']:.2f}s")
        return x.astype(np.float64), results
    finally:
        if alg_id is not None:
            astra.algorithm.delete(alg_id)
        if rec_id is not None:
            astra.data3d.delete(rec_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--size', type=int, default=16)
    parser.add_argument('--angles', type=int, default=12)
    parser.add_argument('--tilts', nargs='+', type=float, default=[-20, 0, 20])
    parser.add_argument('--mart-epochs', nargs='+', type=int, default=[1, 2, 4, 8, 12, 20])
    parser.add_argument('--sirt-iterations', nargs='+', type=int, default=[10, 25, 50, 100, 200, 400])
    parser.add_argument('--relaxation', type=float, default=0.15)
    parser.add_argument('--output-dir', type=Path, default=Path('results/experiment04d'))
    args = parser.parse_args()
    if not astra.use_cuda():
        parser.error('ASTRA CUDA unavailable; activate rbyrct-3d GPU environment')
    for name, values in [('mart-epochs', args.mart_epochs), ('sirt-iterations', args.sirt_iterations)]:
        if not values or any(v < 1 for v in values) or values != sorted(set(values)):
            parser.error(f'{name} must be positive, unique, ascending values')
    if args.size < 4 or args.angles < 2 or not args.tilts or not 0 < args.relaxation <= 1:
        parser.error('Invalid size, angles, tilts, or MART relaxation')

    args.output_dir.mkdir(parents=True, exist_ok=True)
    target = phantom_3d(args.size).astype(np.float64)
    vol_geom = astra.create_vol_geom(args.size, args.size, args.size)
    vectors = geometry_vectors(args.size, args.angles, args.tilts)
    proj_geom = astra.create_proj_geom('parallel3d_vec', args.size, args.size, vectors)
    t0 = time.perf_counter()
    A = system_matrix(args.size, args.angles, args.tilts)
    build_s = time.perf_counter() - t0
    proj_id = None
    try:
        proj_id, sino = astra.create_sino3d_gpu(target.astype(np.float32), proj_geom, vol_geom)
        expected_shape = (args.size, args.angles * len(args.tilts), args.size)
        if sino.shape != expected_shape:
            raise RuntimeError(f'ASTRA shape {sino.shape}, expected {expected_shape}')
        # Convert ASTRA [detector_row, view, detector_col] to reference
        # ray-major [view, detector_row, detector_col].
        b = np.transpose(sino, (1, 0, 2)).reshape(-1).astype(np.float64)
        if not np.isfinite(b).all() or (b < 0).any():
            raise RuntimeError('Invalid ASTRA projections (nonfinite or negative).')
        b_cpu = A @ target.ravel()
        discrepancy = float(np.linalg.norm(b_cpu - b) / max(np.linalg.norm(b), 1e-12))
        print('Experiment 04D — matched input measurements, CPU MART vs GPU SIRT')
        print(f'volume={args.size}^3 rays={A.shape[0]} nnz={A.nnz} matrix_build_s={build_s:.2f}')
        print(f'ASTRA-vs-CPU forward discrepancy relative_L2={discrepancy:.6f}')
        if discrepancy > 0.05:
            print('WARNING: Cross-projector difference exceeds previous 5% diagnostic threshold.')
        print('NOTE: MART and SIRT iterations are NOT computationally equivalent.')
        # Shared ASTRA measurement is supplied to both solvers.
        xm, mh = run_mart(A, b, target, args.mart_epochs, args.relaxation)
        xs, sh = run_sirt(proj_id, proj_geom, vol_geom, A, b, target, args.sirt_iterations)
        # All reconstruction residuals in CSV are evaluated with the same CPU
        # forward model; separate ASTRA reconstruction residuals are not claimed.
        rows = mh + sh
        with (args.output_dir / 'convergence.csv').open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        np.save(args.output_dir / 'phantom.npy', target)
        np.save(args.output_dir / 'shared_astra_sinogram.npy', sino)
        np.save(args.output_dir / 'mart_reconstruction.npy', xm)
        np.save(args.output_dir / 'sirt_reconstruction.npy', xs)
        protocol = {
            'study': '04D shared ASTRA line integrals, CPU MART versus GPU SIRT',
            'astra_version': astra.__version__,
            'size': args.size, 'angles_per_tilt': args.angles, 'tilts_deg': args.tilts,
            'num_rays': int(A.shape[0]), 'nonzeros': int(A.nnz),
            'mart_relaxation': args.relaxation,
            'mart_epochs': args.mart_epochs, 'sirt_iterations': args.sirt_iterations,
            'forward_discrepancy_relative_l2': discrepancy, 'matrix_build_s': build_s,
            'measurements': 'ASTRA CUDA parallel3d_vec forward projections reused by both solvers',
            'metric_operator': 'CPU ray-length system matrix for both methods',
            'timing': 'solver cumulative wall time, excludes projector, matrix build and file IO; CPU vs GPU',
            'caveats': ['Different CPU/GPU forward discretizations',
                        'Not a matched-compute comparison or clinical benchmark',
                        'SIRT per-iteration and MART per-epoch costs differ',
                        'No evidence of dose or adaptive acquisition advantage'],
        }
        (args.output_dir / 'protocol.json').write_text(json.dumps(protocol, indent=2), encoding='utf-8')
        print(f'Saved comparison to {args.output_dir}')
    finally:
        if proj_id is not None:
            astra.data3d.delete(proj_id)


if __name__ == '__main__':
    main()
