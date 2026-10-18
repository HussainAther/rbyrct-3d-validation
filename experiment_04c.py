"""Experiment 04C-1: cross-validate CPU ray-length matrix vs ASTRA CUDA 3D.

Requires experiment_04b.py in the same folder, ASTRA with CUDA, NumPy, SciPy.
This is a forward-operator comparison, NOT a MART-vs-SIRT performance test.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import time

import numpy as np
import astra
from experiment_04b import phantom_3d, system_matrix


def geometry_vectors(n: int, angles: int, tilts_deg: list[float]) -> np.ndarray:
    """Match the ray origins/directions from experiment_04b.system_matrix.

    ASTRA parallel3d_vec: (ray_xyz, detector_center_xyz, detector_u_xyz,
    detector_v_xyz). Detector pixel spacing is 1 world unit, with pixel
    centers at (index + 0.5 - N/2) times their detector basis vectors.
    """
    vectors = []
    for tilt in tilts_deg:
        elev = np.deg2rad(tilt)
        for theta in np.linspace(0, np.pi, angles, endpoint=False):
            u = np.array([np.cos(theta), np.sin(theta), 0.0])
            ray = np.array([-np.sin(theta) * np.cos(elev),
                            np.cos(theta) * np.cos(elev), np.sin(elev)])
            v = np.cross(u, ray)
            vectors.append(np.concatenate([ray, np.zeros(3), u, v]))
    return np.asarray(vectors, dtype=np.float64)


def metrics(reference: np.ndarray, actual: np.ndarray) -> dict:
    diff = actual.astype(np.float64) - reference.astype(np.float64)
    denom = max(float(np.linalg.norm(reference)), 1e-12)
    return {
        "relative_l2": float(np.linalg.norm(diff) / denom),
        "rmse": float(np.sqrt(np.mean(diff ** 2))),
        "max_abs": float(np.max(np.abs(diff))),
        "mean_reference": float(np.mean(reference)),
        "mean_astra": float(np.mean(actual)),
    }


def run(n: int, angles: int, tilts: list[float], output_dir: Path, tolerance: float):
    if n < 4 or angles < 2 or not tilts:
        raise ValueError("Require size >= 4, angles >= 2, at least one tilt")
    if not astra.use_cuda():
        raise RuntimeError("ASTRA CUDA unavailable. Activate the GPU-enabled Conda environment.")
    output_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    matrix = system_matrix(n, angles, tilts)
    print(f"CPU ray-length matrix: shape={matrix.shape}, nnz={matrix.nnz}, build_s={time.perf_counter()-t0:.2f}")
    vectors = geometry_vectors(n, angles, tilts)
    assert vectors.shape == (angles * len(tilts), 12)
    vol_geom = astra.create_vol_geom(n, n, n)
    proj_geom = astra.create_proj_geom("parallel3d_vec", n, n, vectors)

    centers = np.arange(n) + 0.5 - n / 2
    zz, yy, xx = np.meshgrid(centers, centers, centers, indexing="ij")
    # Asymmetric images reveal axis reversals, flips and detector-order errors.
    test_volumes = {
        "ones": np.ones((n, n, n), dtype=np.float32),
        "asymmetric_gradient": (0.5 + 0.012 * xx + 0.018 * yy + 0.023 * zz).astype(np.float32),
        "phantom": phantom_3d(n).astype(np.float32),
    }
    results = []
    for name, volume in test_volumes.items():
        projection_id = None
        try:
            projection_id, astra_projection = astra.create_sino3d_gpu(volume, proj_geom, vol_geom)
            expected_shape = (n, angles * len(tilts), n)
            if astra_projection.shape != expected_shape:
                raise AssertionError(f"ASTRA output shape {astra_projection.shape} != {expected_shape}")
            # CPU row order is (view, detector_v, detector_u), while ASTRA
            # array storage is (detector_v, view, detector_u).
            gpu_by_ray = np.transpose(astra_projection, (1, 0, 2)).reshape(-1)
            cpu_by_ray = np.asarray(matrix @ volume.astype(np.float64).ravel())
            record = {"volume": name, **metrics(cpu_by_ray, gpu_by_ray)}
            results.append(record)
            print(f"{name:>20} rel_L2={record['relative_l2']:.6g} "
                  f"RMSE={record['rmse']:.6g} max_abs={record['max_abs']:.6g}")
            if name == "phantom":
                np.save(output_dir / "cpu_projections.npy", cpu_by_ray.reshape(-1, n, n))
                np.save(output_dir / "astra_projections.npy", np.transpose(astra_projection, (1, 0, 2)))
        finally:
            if projection_id is not None:
                astra.data3d.delete(projection_id)
    with (output_dir / "metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    protocol = {"size": n, "angles_per_tilt": angles, "tilts_deg": tilts,
                "n_rays": int(matrix.shape[0]), "astra_version": astra.__version__,
                "metric": "relative L2 norm of flattened ASTRA minus CPU line integrals",
                "tolerance": tolerance,
                "status": "match" if all(r["relative_l2"] <= tolerance for r in results) else "mismatch"}
    (output_dir / "protocol.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    print(f"Cross-projector agreement: {protocol['status']} (tolerance={tolerance:g})")
    print(f"Results saved to {output_dir}")
    if protocol["status"] != "match":
        print("WARNING: Geometry mismatch; DO NOT proceed to comparative SIRT/MART claims.")
        print("Next: inspect axis conventions, vector orientations, and projector discretization.")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=16)
    parser.add_argument("--angles", type=int, default=12)
    parser.add_argument("--tilts", type=float, nargs="+", default=[-20.0, 0.0, 20.0])
    parser.add_argument("--tolerance", type=float, default=0.05,
                        help="Diagnostic threshold, not a theoretical precision guarantee")
    parser.add_argument("--output-dir", type=Path, default=Path("results/experiment04c"))
    args = parser.parse_args()
    run(args.size, args.angles, args.tilts, args.output_dir, args.tolerance)


if __name__ == "__main__":
    main()
