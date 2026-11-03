"""RBYRCT-05A: computational scaling feasibility benchmark.

Stage 05A-01: coarse 3D sparse-projector construction.
No adaptive policies or acquisition claims are evaluated here.
"""
from __future__ import annotations

import argparse
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy

from experiment_04b import system_matrix


def benchmark_coarse(size: int, angles: int, tilts: list[float]) -> dict:
    start = time.perf_counter()
    A = system_matrix(size, angles, tilts)
    elapsed = time.perf_counter() - start

    storage = A.data.nbytes + A.indices.nbytes + A.indptr.nbytes

    x = np.ones(A.shape[1], dtype=np.float64)
    y = A @ x

    checks = {
        "expected_shape": A.shape == (
            len(tilts) * angles * size * size,
            size**3,
        ),
        "finite_matrix": bool(np.isfinite(A.data).all()),
        "nonnegative_path_lengths": bool((A.data >= 0).all()),
        "finite_projection": bool(np.isfinite(y).all()),
    }

    return {
        "stage": "05A-01",
        "size": size,
        "angles": angles,
        "tilts_deg": tilts,
        "matrix_shape": list(A.shape),
        "nonzeros": int(A.nnz),
        "csr_storage_mib": storage / 1024**2,
        "construction_seconds": elapsed,
        "projection_min": float(y.min()),
        "projection_max": float(y.max()),
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=16)
    parser.add_argument("--angles", type=int, default=12)
    parser.add_argument(
        "--tilts", type=float, nargs="+",
        default=[-20.0, 0.0, 20.0],
    )
    parser.add_argument(
        "--output",
        default="results/experiment05a_scaling/coarse_report.json",
    )
    args = parser.parse_args()

    if args.size < 4 or args.angles < 2 or not args.tilts:
        parser.error("invalid projector configuration")

    report = {
        "experiment": "RBYRCT-05A",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "coarse": benchmark_coarse(
            args.size, args.angles, args.tilts
        ),
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    result = report["coarse"]
    print(f"RBYRCT-05A-01: {args.size}^3 coarse projector")
    print(f"Shape: {result['matrix_shape']}")
    print(f"Nonzeros: {result['nonzeros']}")
    print(f"CSR storage: {result['csr_storage_mib']:.2f} MiB")
    print(f"Construction: {result['construction_seconds']:.2f} s")
    print(f"Numerical checks passed: {result['passed']}")
    print(f"Report: {output}")

    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()


def benchmark_fine(
    size: int,
    angles: int,
    tilts: list[float],
    factor: int = 2,
) -> dict:
    """Benchmark fine-grid measurement construction at zero offset."""
    from experiment_04m import high_resolution_matrix

    start = time.perf_counter()
    A = high_resolution_matrix(
        size, angles, tilts, factor=factor, offset=0.0
    )
    elapsed = time.perf_counter() - start

    storage = A.data.nbytes + A.indices.nbytes + A.indptr.nbytes

    x = np.ones(A.shape[1], dtype=np.float64)
    y = A @ x

    checks = {
        "expected_shape": A.shape == (
            len(tilts) * angles * size * size,
            (size * factor) ** 3,
        ),
        "finite_matrix": bool(np.isfinite(A.data).all()),
        "nonnegative_path_lengths": bool((A.data >= 0).all()),
        "finite_projection": bool(np.isfinite(y).all()),
    }

    return {
        "stage": "05A-02",
        "coarse_size": size,
        "fine_size": size * factor,
        "factor": factor,
        "matrix_shape": list(A.shape),
        "nonzeros": int(A.nnz),
        "csr_storage_mib": storage / 1024**2,
        "construction_seconds": elapsed,
        "projection_min": float(y.min()),
        "projection_max": float(y.max()),
        "checks": checks,
        "passed": all(checks.values()),
    }
