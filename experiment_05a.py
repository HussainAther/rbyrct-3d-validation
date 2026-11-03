
"""RBYRCT-05A: computational scaling feasibility benchmark.

05A-01: coarse 3D sparse-projector construction.
05A-02: fine-grid measurement projector construction.
05A-03: coarse/fine uniform-volume projection consistency.

This benchmark evaluates numerical correctness and computational feasibility.
It does not evaluate adaptive acquisition superiority or physical CT dose.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import math
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy

from experiment_04b import system_matrix
from experiment_04m import high_resolution_matrix


DEFAULT_TILTS = [-20.0, 0.0, 20.0]
DEFAULT_OUTPUT = "results/experiment05a_scaling/coarse_report.json"


def available_ram_gib() -> float:
    """Return available physical RAM in GiB on Windows."""
    if platform.system() != "Windows":
        raise OSError("This memory check currently requires Windows")

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)

    success = ctypes.windll.kernel32.GlobalMemoryStatusEx(
        ctypes.byref(status)
    )

    if not success:
        raise OSError("Could not retrieve Windows memory status")

    return status.ullAvailPhys / (1024**3)


def sparse_storage_mib(matrix) -> float:
    """Return CSR array storage in MiB (not total process memory)."""
    return (
        matrix.data.nbytes
        + matrix.indices.nbytes
        + matrix.indptr.nbytes
    ) / (1024**2)


def benchmark_coarse(
    size: int,
    angles: int,
    tilts: list[float],
) -> dict:
    """Benchmark coarse reconstruction-projector construction."""
    start = time.perf_counter()
    A = system_matrix(size, angles, tilts)
    elapsed = time.perf_counter() - start

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
        "csr_storage_mib": sparse_storage_mib(A),
        "construction_seconds": elapsed,
        "projection_min": float(y.min()),
        "projection_max": float(y.max()),
        "checks": checks,
        "passed": all(checks.values()),
    }


def benchmark_fine(
    size: int,
    angles: int,
    tilts: list[float],
    factor: int = 2,
) -> dict:
    """Benchmark fine-grid measurement construction at zero offset."""
    start = time.perf_counter()
    A = high_resolution_matrix(
        size,
        angles,
        tilts,
        factor=factor,
        offset=0.0,
    )
    elapsed = time.perf_counter() - start

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
        "csr_storage_mib": sparse_storage_mib(A),
        "construction_seconds": elapsed,
        "projection_min": float(y.min()),
        "projection_max": float(y.max()),
        "checks": checks,
        "passed": all(checks.values()),
    }


def benchmark_uniform_agreement(
    size: int,
    angles: int,
    tilts: list[float],
    factor: int = 2,
) -> dict:
    """Check matching coarse/fine ray integrals for a uniform object.

    Both operators use zero geometric offset. This checks a basic
    geometric invariant, not agreement for arbitrary objects.
    """
    coarse = system_matrix(size, angles, tilts)
    fine = high_resolution_matrix(
        size,
        angles,
        tilts,
        factor=factor,
        offset=0.0,
    )

    coarse_y = coarse @ np.ones(coarse.shape[1], dtype=np.float64)
    fine_y = fine @ np.ones(fine.shape[1], dtype=np.float64)

    matching_ray_counts = coarse.shape[0] == fine.shape[0]

    if matching_ray_counts:
        differences = np.abs(coarse_y - fine_y)
        max_error = float(differences.max())
        mean_error = float(differences.mean())
        agreement = bool(
            np.allclose(
                coarse_y,
                fine_y,
                rtol=1e-10,
                atol=1e-10,
            )
        )
    else:
        max_error = None
        mean_error = None
        agreement = False

    checks = {
        "matching_ray_counts": matching_ray_counts,
        "uniform_projection_agreement": agreement,
    }

    return {
        "stage": "05A-03",
        "size": size,
        "factor": factor,
        "ray_count_coarse": int(coarse.shape[0]),
        "ray_count_fine": int(fine.shape[0]),
        "maximum_absolute_difference": max_error,
        "mean_absolute_difference": mean_error,
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RBYRCT-05A: 3D projector scaling feasibility benchmark."
    )

    parser.add_argument("--size", type=int, default=16)
    parser.add_argument("--angles", type=int, default=12)

    parser.add_argument(
        "--tilts",
        type=float,
        nargs="+",
        default=DEFAULT_TILTS,
    )

    parser.add_argument(
        "--factor",
        type=int,
        default=2,
        help="Fine-grid resolution multiplier.",
    )

    parser.add_argument(
        "--include-fine",
        action="store_true",
        help="Include fine-grid projector construction.",
    )

    parser.add_argument(
        "--check-uniform",
        action="store_true",
        help="Check coarse/fine agreement for a uniform volume.",
    )

    parser.add_argument(
        "--allow-large",
        action="store_true",
        help="Explicitly authorize grid sizes 17 through 32.",
    )

    parser.add_argument(
        "--min-free-ram",
        type=float,
        default=4.0,
        help="Minimum free physical RAM in GiB for larger runs.",
    )

    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
    )

    args = parser.parse_args()

    # Configuration validation
    if args.size < 4:
        parser.error("--size must be at least 4")

    if args.angles < 2:
        parser.error("--angles must be at least 2")

    if not args.tilts or not all(math.isfinite(t) for t in args.tilts):
        parser.error("--tilts must contain finite values")

    if args.factor < 2:
        parser.error("--factor must be at least 2")

    if args.size > 32:
        parser.error("05A currently supports grid sizes up to 32")

    if args.size > 16 and not args.allow_large:
        parser.error("Use --allow-large for grid sizes above 16")

    if not math.isfinite(args.min_free_ram) or args.min_free_ram <= 0:
        parser.error("--min-free-ram must be finite and positive")

    if args.size > 16:
        try:
            free_ram = available_ram_gib()
        except OSError as exc:
            parser.error(str(exc))

        if free_ram < args.min_free_ram:
            parser.error(
                f"Only {free_ram:.2f} GiB RAM available; "
                f"{args.min_free_ram:.2f} GiB required."
            )
    else:
        try:
            free_ram = available_ram_gib()
        except OSError:
            free_ram = None

    # Safeguard against unusually large fine grids at a small coarse size.
    if (args.include_fine or args.check_uniform) and args.size * args.factor > 64:
        parser.error("Fine-grid dimensions above 64 are outside 05A scope")

    report = {
        "experiment": "RBYRCT-05A",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "configuration": {
            "size": args.size,
            "angles": args.angles,
            "tilts_deg": args.tilts,
            "factor": args.factor,
            "include_fine": args.include_fine,
            "check_uniform": args.check_uniform,
            "allow_large": args.allow_large,
            "min_free_ram_gib": args.min_free_ram,
        },
        "available_ram_before_gib": free_ram,
    }

    print(f"RBYRCT-05A: {args.size}^3 coarse grid")

    # Stage 05A-01
    report["coarse"] = benchmark_coarse(
        args.size,
        args.angles,
        args.tilts,
    )

    coarse = report["coarse"]
    print(
        f"Coarse: shape={coarse['matrix_shape']}, "
        f"nnz={coarse['nonzeros']}, "
        f"storage={coarse['csr_storage_mib']:.2f} MiB, "
        f"time={coarse['construction_seconds']:.2f} s"
    )

    # Stage 05A-02
    if args.include_fine:
        report["fine"] = benchmark_fine(
            args.size,
            args.angles,
            args.tilts,
            factor=args.factor,
        )

        fine = report["fine"]
        print(
            f"Fine: shape={fine['matrix_shape']}, "
            f"nnz={fine['nonzeros']}, "
            f"storage={fine['csr_storage_mib']:.2f} MiB, "
            f"time={fine['construction_seconds']:.2f} s"
        )

    # Stage 05A-03
    if args.check_uniform:
        report["uniform_agreement"] = benchmark_uniform_agreement(
            args.size,
            args.angles,
            args.tilts,
            factor=args.factor,
        )

        uniform = report["uniform_agreement"]
        print(
            "Uniform agreement: "
            f"max error={uniform['maximum_absolute_difference']}, "
            f"passed={uniform['passed']}"
        )

    stages = ["coarse"]

    if args.include_fine:
        stages.append("fine")

    if args.check_uniform:
        stages.append("uniform_agreement")

    report["numerical_checks_passed"] = all(
        report[stage]["passed"] for stage in stages
    )

    report["limitations"] = [
        "Synthetic parallel-ray geometry only.",
        "No adaptive acquisition policy evaluated.",
        "Uniform-volume agreement does not prove general operator equivalence.",
        "CSR storage excludes temporary allocations and other process memory.",
        "Available-RAM screening is not a guaranteed peak-memory bound.",
    ]

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print(f"All numerical checks passed: {report['numerical_checks_passed']}")
    print(f"Report: {output}")

    if not report["numerical_checks_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
