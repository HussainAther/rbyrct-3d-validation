"""Experiment 04B: reference ray-sequential MART on a small 3D volume.

This is a CPU reference solver, not an ASTRA CUDA reconstruction. The phantom
measurements are synthesized from the very same sparse ray model. It validates
MART implementation mechanics, not CT dose or cross-projector agreement.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import time

import numpy as np
from scipy import sparse


def phantom_3d(n: int) -> np.ndarray:
    zz, yy, xx = np.meshgrid(
        (np.arange(n) + 0.5 - n / 2) / (n / 2),
        (np.arange(n) + 0.5 - n / 2) / (n / 2),
        (np.arange(n) + 0.5 - n / 2) / (n / 2), indexing="ij"
    )
    body = (xx / 0.72) ** 2 + (yy / 0.64) ** 2 + (zz / 0.78) ** 2 <= 1
    lesion = ((xx - 0.21) / 0.17) ** 2 + ((yy + 0.14) / 0.14) ** 2 + ((zz - 0.12) / 0.19) ** 2 <= 1
    core = ((xx + 0.25) / 0.20) ** 2 + ((yy - 0.14) / 0.14) ** 2 + ((zz + 0.16) / 0.24) ** 2 <= 1
    return (0.025 + 0.65 * body + 0.5 * lesion - 0.28 * core).astype(np.float64)


def trace_ray(origin: np.ndarray, direction: np.ndarray, n: int):
    """Exact segment lengths through axis-aligned unit cubes in [-n/2,n/2]^3.

    Return voxel indices in NumPy (z,y,x) flattening order and path lengths.
    """
    low, high = -n / 2, n / 2
    entry, leave = -np.inf, np.inf
    for axis in range(3):
        if abs(direction[axis]) < 1e-12:
            if not low <= origin[axis] <= high:
                return [], []
            continue
        a = (low - origin[axis]) / direction[axis]
        b = (high - origin[axis]) / direction[axis]
        entry = max(entry, min(a, b))
        leave = min(leave, max(a, b))
    if leave <= entry:
        return [], []
    ts = [entry, leave]
    for axis in range(3):
        if abs(direction[axis]) > 1e-12:
            boundaries = np.arange(1, n, dtype=float) - n / 2
            crossings = (boundaries - origin[axis]) / direction[axis]
            ts.extend(crossings[(crossings > entry) & (crossings < leave)])
    ts = np.unique(np.asarray(ts))
    indices, lengths = [], []
    for left, right in zip(ts[:-1], ts[1:]):
        if right - left <= 1e-11:
            continue
        xyz = origin + (0.5 * (left + right)) * direction
        ijk = np.floor(xyz + n / 2).astype(int)
        if np.all((ijk >= 0) & (ijk < n)):
            ix, iy, iz = map(int, ijk)
            indices.append((iz * n + iy) * n + ix)
            lengths.append(float(right - left))
    return indices, lengths


def system_matrix(n: int, angles: int, tilts_deg: list[float]) -> sparse.csr_matrix:
    """Construct physical 3D parallel rays at azimuths and elevation tilts."""
    rows, cols, values = [], [], []
    ray = 0
    detector_coords = np.arange(n, dtype=float) + 0.5 - n / 2
    for tilt_deg in tilts_deg:
        elevation = np.deg2rad(tilt_deg)
        for theta in np.linspace(0, np.pi, angles, endpoint=False):
            # x,y,z vectors are orthonormal, with nonzero z component when tilted.
            u = np.array([np.cos(theta), np.sin(theta), 0.0])
            direction = np.array([-np.sin(theta) * np.cos(elevation),
                                  np.cos(theta) * np.cos(elevation), np.sin(elevation)])
            v = np.cross(u, direction)
            for dv in detector_coords:
                for du in detector_coords:
                    origin = du * u + dv * v
                    ids, lens = trace_ray(origin, direction, n)
                    rows.extend([ray] * len(ids))
                    cols.extend(ids)
                    values.extend(lens)
                    ray += 1
    return sparse.coo_matrix((values, (rows, cols)),
                             shape=(ray, n ** 3), dtype=np.float64).tocsr()


def mart(A: sparse.csr_matrix, measured: np.ndarray, reference: np.ndarray,
         epochs: int, relaxation: float, checkpoint_interval: int) -> tuple[np.ndarray, list[dict]]:
    """Sequential MART with positive initialization and per-ray path normalization.

    x_j <- x_j * (b_i / max(a_i @ x, eps)) ** (lambda*a_ij/max_j(a_ij))
    """
    if np.any(measured < 0):
        raise ValueError("MART requires nonnegative line-integral observations")
    x = np.full(A.shape[1], 0.3, dtype=np.float64)
    tiny = 1e-10
    history = []
    for epoch in range(1, epochs + 1):
        for ray in range(A.shape[0]):
            start, end = A.indptr[ray], A.indptr[ray + 1]
            ids, weights = A.indices[start:end], A.data[start:end]
            if not len(ids):
                continue
            prediction = float(np.dot(weights, x[ids]))
            if measured[ray] <= tiny:
                # A zero ray should push traversed positive attenuation toward zero.
                ratio = tiny / max(prediction, tiny)
            else:
                ratio = measured[ray] / max(prediction, tiny)
            exponent = relaxation * weights / np.max(weights)
            log_update = np.clip(exponent * np.log(max(ratio, tiny)), -12, 12)
            x[ids] = np.maximum(x[ids] * np.exp(log_update), tiny)
        if epoch == 1 or epoch % checkpoint_interval == 0 or epoch == epochs:
            residual = A @ x - measured
            rmse = float(np.sqrt(np.mean((x - reference) ** 2)))
            relative_residual = float(np.linalg.norm(residual) / max(np.linalg.norm(measured), tiny))
            history.append({"epoch": epoch, "rmse": rmse, "relative_projection_residual": relative_residual})
            print(f"epoch={epoch:3d}  RMSE={rmse:.6f}  relative_projection_residual={relative_residual:.6f}")
    return x, history


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=16)
    parser.add_argument("--angles", type=int, default=12)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--relaxation", type=float, default=0.15)
    parser.add_argument("--checkpoint-interval", type=int, default=2)
    parser.add_argument("--output-dir", type=Path, default=Path("results/experiment04b"))
    args = parser.parse_args()
    if args.size < 4 or args.angles < 2 or args.epochs < 1:
        parser.error("size >= 4, angles >= 2, epochs >= 1 are required")
    if not (0 < args.relaxation <= 1) or args.checkpoint_interval < 1:
        parser.error("0 < relaxation <= 1 and checkpoint-interval >= 1 are required")
    tilts = [-20.0, 0.0, 20.0]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reference = phantom_3d(args.size).ravel()
    print("Experiment 04B — CPU reference 3D ray-by-ray MART")
    print(f"volume={args.size}^3 angles={args.angles} tilts={tilts}")
    t0 = time.perf_counter()
    A = system_matrix(args.size, args.angles, tilts)
    print(f"rays={A.shape[0]} nonzero_ray_voxel_weights={A.nnz} build_s={time.perf_counter()-t0:.2f}")
    assert A.nnz > 0 and np.isfinite(A.data).all() and np.all(A.data > 0)
    # Test the implemented linear operator and its exact sparse adjoint.
    rng = np.random.default_rng(104729)
    v = rng.normal(size=A.shape[1])
    w = rng.normal(size=A.shape[0])
    lhs, rhs = float(np.dot(A @ v, w)), float(np.dot(v, A.T @ w))
    adjoint_error = abs(lhs-rhs) / max(abs(lhs), abs(rhs), 1e-12)
    print(f"relative_adjoint_error={adjoint_error:.3e}")
    assert adjoint_error < 1e-10
    measured = A @ reference  # exact, noiseless synthetic measurements
    reconstruction, history = mart(A, measured, reference, args.epochs,
                                   args.relaxation, args.checkpoint_interval)
    np.save(args.output_dir / "phantom.npy", reference.reshape((args.size,)*3))
    np.save(args.output_dir / "reconstruction.npy", reconstruction.reshape((args.size,)*3))
    with (args.output_dir / "convergence.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(history[0]))
        writer.writeheader()
        writer.writerows(history)
    print(f"Saved results to {args.output_dir}")
    print("Note: this reference test does not establish ASTRA-to-MART geometry equivalence or GPU speed.")


if __name__ == "__main__":
    main()
