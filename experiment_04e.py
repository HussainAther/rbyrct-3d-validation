"""RBYRCT Experiment 04E: diagnose ASTRA-vs-ray-length operator mismatch.

Run alongside experiment_04b.py and experiment_04c.py (ASTRA CUDA required).
Does NOT tune geometry, assert operator equivalence, or claim MART > SIRT.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np

from experiment_04b import phantom_3d, system_matrix
from experiment_04c import geometry_vectors, metrics
from experiment_04d import run_mart


def astra_project(volume, astra, proj_geom, vol_geom):
    projection_id = None
    try:
        projection_id, sinogram = astra.create_sino3d_gpu(
            np.asarray(volume, dtype=np.float32), proj_geom, vol_geom
        )
        # ASTRA layout (detector_v, view, detector_u) -> (view, detector_v, detector_u)
        return np.transpose(sinogram, (1, 0, 2)).copy().astype(np.float64)
    finally:
        if projection_id is not None:
            astra.data3d.delete(projection_id)


def comparison(A, image, astra, proj_geom, vol_geom, n, views):
    cpu = np.asarray(A @ np.asarray(image, dtype=np.float64).ravel()).reshape(views, n, n)
    gpu = astra_project(image, astra, proj_geom, vol_geom)
    if gpu.shape != cpu.shape:
        raise RuntimeError(f"Projection shape mismatch: CPU {cpu.shape}; ASTRA {gpu.shape}")
    return cpu, gpu


def write_csv(path, rows, fields):
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run(n, angles, tilts, epochs, relaxation, output_dir, impulses):
    import astra
    if not astra.use_cuda():
        raise RuntimeError('ASTRA CUDA unavailable; activate the working rbyrct-3d environment.')
    output_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    A = system_matrix(n, angles, tilts)
    matrix_seconds = time.perf_counter() - t0
    views = angles * len(tilts)
    vectors = geometry_vectors(n, angles, tilts)
    vol_geom = astra.create_vol_geom(n, n, n)
    proj_geom = astra.create_proj_geom('parallel3d_vec', n, n, vectors)
    print('Experiment 04E — forward-model mismatch diagnostics')
    print(f'volume={n}^3 rays={A.shape[0]} nnz={A.nnz} matrix_build_s={matrix_seconds:.2f}')

    # Impulse responses: asymmetric off-center positions detect flips and alignment errors.
    positions = {
        'center': (n // 2, n // 2, n // 2),
        'x_offset': (n // 2, n // 2, min(n - 2, n // 2 + max(1, n // 4))),
        'y_offset': (n // 2, max(1, n // 2 - max(1, n // 4)), n // 2),
        'z_offset': (min(n - 2, n // 2 + max(1, n // 4)), n // 2, n // 2),
        'corner_inside': (max(1, n // 4), max(1, n // 4), min(n - 2, 3 * n // 4)),
    }
    rows = []
    for name in impulses:
        if name not in positions:
            raise ValueError(f'Unknown impulse {name}; choices: {list(positions)}')
        vol = np.zeros((n, n, n), np.float32)
        loc = positions[name]
        vol[loc] = 1.0
        cpu, gpu = comparison(A, vol, astra, proj_geom, vol_geom, n, views)
        m = metrics(cpu, gpu)
        rows.append({'impulse': name, 'z': loc[0], 'y': loc[1], 'x': loc[2], **m})
        print(f"impulse={name:14} rel_L2={m['relative_l2']:.6f} max_abs={m['max_abs']:.6f}")
    write_csv(output_dir / 'impulse_metrics.csv', rows, list(rows[0]))

    # Spatially resolved discrepancy map for the full phantom.
    target = phantom_3d(n).astype(np.float64)
    cpu, gpu = comparison(A, target, astra, proj_geom, vol_geom, n, views)
    diff = gpu - cpu
    global_metrics = metrics(cpu, gpu)
    per_view = []
    for view in range(views):
        m = metrics(cpu[view], gpu[view])
        per_view.append({'view': view, 'tilt_deg': tilts[view // angles],
                         'azimuth_deg': float(180.0 * (view % angles) / angles), **m})
    write_csv(output_dir / 'per_view_metrics.csv', per_view, list(per_view[0]))
    per_pixel = []
    # RMS over views at fixed detector coordinate: maps systematic spatial mismatch.
    for v in range(n):
        for u in range(n):
            d = diff[:, v, u]
            reference = cpu[:, v, u]
            per_pixel.append({'detector_v': v, 'detector_u': u,
                              'rmse_over_views': float(np.sqrt(np.mean(d ** 2))),
                              'mean_error': float(np.mean(d)),
                              'max_abs_error': float(np.max(np.abs(d))),
                              'reference_rms': float(np.sqrt(np.mean(reference ** 2)))})
    write_csv(output_dir / 'detector_error_map.csv', per_pixel, list(per_pixel[0]))
    np.savez_compressed(output_dir / 'phantom_projection_comparison.npz', cpu=cpu, astra=gpu,
                        difference=diff)
    print(f"phantom rel_L2={global_metrics['relative_l2']:.6f} RMSE={global_metrics['rmse']:.6f}")
    for tilt_index, tilt in enumerate(tilts):
        sl = slice(tilt_index * angles, (tilt_index + 1) * angles)
        print(f"  tilt={tilt:+6.1f} deg rel_L2={metrics(cpu[sl], gpu[sl])['relative_l2']:.6f}")

    # Matched MART solver, identical matrix and target, two different observation sources.
    # This isolates observation-model mismatch while keeping MART hyperparameters frozen.
    b_cpu = cpu.reshape(-1)
    b_astra = gpu.reshape(-1)
    checkpoints = sorted(set([1, min(2, epochs), min(4, epochs), min(8, epochs), epochs]))
    print('CPU-consistent MART (CPU-generated measurements):')
    x_cpu, hist_cpu = run_mart(A, b_cpu, target, checkpoints, relaxation)
    print('Cross-model MART (ASTRA-generated measurements):')
    x_astra, hist_astra = run_mart(A, b_astra, target, checkpoints, relaxation)
    results = []
    for label, history, b in [('CPU_consistent', hist_cpu, b_cpu),
                              ('ASTRA_measurements', hist_astra, b_astra)]:
        for record in history:
            results.append({'condition': label, **record})
    write_csv(output_dir / 'mart_consistency.csv', results, list(results[0]))
    np.save(output_dir / 'phantom.npy', target)
    np.save(output_dir / 'mart_cpu_consistent.npy', x_cpu)
    np.save(output_dir / 'mart_astra_measurements.npy', x_astra)
    protocol = {
        'study': '04E projector mismatch localization and MART self-consistency',
        'astra_version': astra.__version__, 'n': n, 'angles_per_tilt': angles,
        'tilts_deg': tilts, 'num_rays': A.shape[0], 'nonzeros': A.nnz,
        'impulses': positions, 'impulses_evaluated': impulses,
        'mart_checkpoints': checkpoints, 'mart_relaxation': relaxation,
        'phantom_forward_discrepancy': global_metrics,
        'projection_order': '(view, detector_v, detector_u); flattened row-major',
        'fairness': 'Both MART conditions use identical CPU sparse A, target, initialization, update rule, and checkpoints; only input measurements differ.',
        'limitations': [
            'The ASTRA CUDA projector and exact ray-intersection matrix have different discretizations.',
            'No physical noise, measured scan, or dose claims.',
            'MART comparisons are CPU-only and cannot establish GPU performance.',
            'Impulse errors depend on voxel position and projector discretization.',
        ],
    }
    (output_dir / 'protocol.json').write_text(json.dumps(protocol, indent=2), encoding='utf-8')
    print(f'Results saved to {output_dir}')
    return protocol


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--size', type=int, default=16)
    parser.add_argument('--angles', type=int, default=12)
    parser.add_argument('--tilts', type=float, nargs='+', default=[-20.0, 0.0, 20.0])
    parser.add_argument('--epochs', type=int, default=20)
    parser.add_argument('--relaxation', type=float, default=0.15)
    parser.add_argument('--impulses', nargs='+', choices=['center', 'x_offset', 'y_offset', 'z_offset', 'corner_inside'],
                        default=['center', 'x_offset', 'y_offset', 'z_offset', 'corner_inside'])
    parser.add_argument('--output-dir', type=Path, default=Path('results/experiment04e'))
    args = parser.parse_args()
    if args.size < 6 or args.angles < 2 or not args.tilts or args.epochs < 1 or not 0 < args.relaxation <= 1:
        parser.error('Require size >=6, angles >=2, nonempty tilts, epochs >=1, 0<relaxation<=1')
    run(args.size, args.angles, args.tilts, args.epochs, args.relaxation,
        args.output_dir, args.impulses)


if __name__ == '__main__':
    main()
