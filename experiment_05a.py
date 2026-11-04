
"""RBYRCT-05A: computational scaling feasibility benchmark.

05A-01: Coarse 3D sparse-projector construction.
05A-02: Fine-grid measurement-projector construction.
05A-03: Coarse/fine uniform-volume projection consistency.
05A-04: Reduced SIRT reconstruction feasibility.

This benchmark evaluates numerical correctness and computational
feasibility. It does not establish adaptive acquisition superiority,
physical CT validation, or radiation-dose reduction.
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
DEFAULT_OUTPUT = (
    "results/experiment05a_scaling/coarse_report.json"
)


def available_ram_gib() -> float:
    """Return available physical RAM in GiB on Windows."""
    if platform.system() != "Windows":
        raise OSError(
            "This memory check currently requires Windows"
        )

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
        raise OSError(
            "Could not retrieve Windows memory status"
        )

    return status.ullAvailPhys / (1024**3)


def sparse_storage_mib(matrix) -> float:
    """Return CSR array storage in MiB, excluding process overhead."""
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
        "finite_matrix": bool(
            np.isfinite(A.data).all()
        ),
        "nonnegative_path_lengths": bool(
            (A.data >= 0).all()
        ),
        "finite_projection": bool(
            np.isfinite(y).all()
        ),
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
        "finite_matrix": bool(
            np.isfinite(A.data).all()
        ),
        "nonnegative_path_lengths": bool(
            (A.data >= 0).all()
        ),
        "finite_projection": bool(
            np.isfinite(y).all()
        ),
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
    """Compare coarse/fine ray integrals for a uniform object.

    Both operators use zero geometric offset.
    This tests a geometric invariant, not general operator
    equivalence for arbitrary objects.
    """
    coarse = system_matrix(size, angles, tilts)

    fine = high_resolution_matrix(
        size,
        angles,
        tilts,
        factor=factor,
        offset=0.0,
    )

    coarse_y = coarse @ np.ones(
        coarse.shape[1],
        dtype=np.float64,
    )

    fine_y = fine @ np.ones(
        fine.shape[1],
        dtype=np.float64,
    )

    matching_ray_counts = (
        coarse.shape[0] == fine.shape[0]
    )

    if matching_ray_counts:
        differences = np.abs(
            coarse_y - fine_y
        )

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
        "ray_count_coarse": int(
            coarse.shape[0]
        ),
        "ray_count_fine": int(
            fine.shape[0]
        ),
        "maximum_absolute_difference": max_error,
        "mean_absolute_difference": mean_error,
        "checks": checks,
        "passed": all(checks.values()),
    }


def benchmark_sirt(
    size: int = 16,
    angles: int = 12,
    tilts: list[float] | None = None,
    budget: int = 256,
    iterations: int = 40,
    seed: int = 271828,
) -> dict:
    """Benchmark reduced SIRT reconstruction on a synthetic sphere.

    Uses the same coarse projector for measurement generation
    and reconstruction. This is an inverse-crime numerical
    smoke test, not independent forward-model validation.
    """
    from experiment_04j import sirt_silent

    if tilts is None:
        tilts = list(DEFAULT_TILTS)

    if size < 4 or angles < 2 or not tilts:
        raise ValueError(
            "Invalid reconstruction geometry"
        )

    if budget < 1 or iterations < 1:
        raise ValueError(
            "Budget and iterations must be positive"
        )

    total_rays = (
        len(tilts) * angles * size**2
    )

    if budget > total_rays:
        raise ValueError(
            "Budget exceeds available rays"
        )

    start = time.perf_counter()

    A = system_matrix(
        size,
        angles,
        tilts,
    )

    matrix_seconds = (
        time.perf_counter() - start
    )

    # Construct a deterministic synthetic sphere.
    z, y, x = np.indices(
        (size, size, size)
    )

    center = (size - 1) / 2.0
    radius = size / 4.0

    truth = (
        (x - center) ** 2
        + (y - center) ** 2
        + (z - center) ** 2
        <= radius**2
    ).astype(np.float64).ravel()

    # Generate noiseless measurements with the coarse operator.
    measurements = A @ truth

    # Select a reproducible random subset of rays.
    rng = np.random.default_rng(seed)

    selected = np.sort(
        rng.choice(
            A.shape[0],
            size=budget,
            replace=False,
        )
    )

    selected_A = A[selected].tocsr()
    selected_b = measurements[selected]

    # Measure initial data residual.
    initial = np.full(
        size**3,
        0.3,
        dtype=np.float64,
    )

    initial_residual = float(
        np.linalg.norm(
            selected_A @ initial - selected_b
        )
    )

    # Reuse the validated 04J SIRT implementation.
    start = time.perf_counter()

    reconstruction = sirt_silent(
        selected_A,
        selected_b,
        iterations=iterations,
        initial=0.3,
    )

    reconstruction_seconds = (
        time.perf_counter() - start
    )

    predicted = selected_A @ reconstruction

    final_residual = float(
        np.linalg.norm(
            predicted - selected_b
        )
    )

    rmse = float(
        np.sqrt(
            np.mean(
                (reconstruction - truth) ** 2
            )
        )
    )

    checks = {
        "finite_reconstruction": bool(
            np.isfinite(reconstruction).all()
        ),
        "nonnegative_reconstruction": bool(
            (reconstruction >= 0).all()
        ),
        "finite_residuals": bool(
            np.isfinite(
                [initial_residual, final_residual, rmse]
            ).all()
        ),
        "residual_improved": bool(
            final_residual < initial_residual
        ),
    }

    return {
        "stage": "05A-04",
        "size": size,
        "angles": angles,
        "tilts_deg": tilts,
        "budget": budget,
        "iterations": iterations,
        "seed": seed,
        "matrix_shape": list(
            selected_A.shape
        ),
        "matrix_construction_seconds": matrix_seconds,
        "selected_matrix_storage_mib": sparse_storage_mib(
            selected_A
        ),
        "reconstruction_seconds": reconstruction_seconds,
        "reconstruction_milliseconds": (
            reconstruction_seconds * 1000
        ),
        "initial_residual": initial_residual,
        "final_residual": final_residual,
        "rmse": rmse,
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "RBYRCT-05A: 3D projector and "
            "reconstruction scaling feasibility benchmark."
        )
    )

    parser.add_argument(
        "--size",
        type=int,
        default=16,
    )

    parser.add_argument(
        "--angles",
        type=int,
        default=12,
    )

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
        help="Benchmark fine-grid projector construction.",
    )

    parser.add_argument(
        "--check-uniform",
        action="store_true",
        help="Compare coarse/fine uniform-volume projections.",
    )

    parser.add_argument(
        "--include-sirt",
        action="store_true",
        help="Run reduced SIRT reconstruction benchmark.",
    )

    parser.add_argument(
        "--sirt-budget",
        type=int,
        default=256,
        help="Number of selected rays for SIRT.",
    )

    parser.add_argument(
        "--sirt-iterations",
        type=int,
        default=40,
        help="Number of SIRT iterations.",
    )

    parser.add_argument(
        "--sirt-seed",
        type=int,
        default=271828,
        help="Random seed for SIRT ray selection.",
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
        help="Minimum available RAM in GiB for larger runs.",
    )

    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
    )

    args = parser.parse_args()

    # --------------------------------------------------
    # Configuration validation
    # --------------------------------------------------

    if args.size < 4:
        parser.error(
            "--size must be at least 4"
        )

    if args.angles < 2:
        parser.error(
            "--angles must be at least 2"
        )

    if not args.tilts or not all(
        math.isfinite(t) for t in args.tilts
    ):
        parser.error(
            "--tilts must contain finite values"
        )

    if args.factor < 2:
        parser.error(
            "--factor must be at least 2"
        )

    if args.size > 32:
        parser.error(
            "05A currently supports grid sizes up to 32"
        )

    if args.size > 16 and not args.allow_large:
        parser.error(
            "Use --allow-large for grid sizes above 16"
        )

    if (
        not math.isfinite(args.min_free_ram)
        or args.min_free_ram <= 0
    ):
        parser.error(
            "--min-free-ram must be finite and positive"
        )

    if args.sirt_budget < 1:
        parser.error(
            "--sirt-budget must be positive"
        )

    if args.sirt_iterations < 1:
        parser.error(
            "--sirt-iterations must be positive"
        )

    total_rays = (
        len(args.tilts)
        * args.angles
        * args.size**2
    )

    if (
        args.include_sirt
        and args.sirt_budget > total_rays
    ):
        parser.error(
            "--sirt-budget exceeds available rays"
        )

    if (
        args.include_fine or args.check_uniform
    ) and args.size * args.factor > 64:
        parser.error(
            "Fine-grid dimensions above 64 "
            "are outside 05A scope"
        )

    # --------------------------------------------------
    # Memory admission check
    # --------------------------------------------------

    try:
        free_ram = available_ram_gib()
    except OSError as exc:
        if args.size > 16:
            parser.error(str(exc))
        free_ram = None

    if args.size > 16:
        if free_ram is None:
            parser.error(
                "Available RAM could not be determined"
            )

        if free_ram < args.min_free_ram:
            parser.error(
                f"Only {free_ram:.2f} GiB RAM available; "
                f"{args.min_free_ram:.2f} GiB required."
            )

    # --------------------------------------------------
    # Report metadata
    # --------------------------------------------------

    report = {
        "experiment": "RBYRCT-05A",
        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),
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
            "include_sirt": args.include_sirt,
            "sirt_budget": args.sirt_budget,
            "sirt_iterations": args.sirt_iterations,
            "sirt_seed": args.sirt_seed,
            "allow_large": args.allow_large,
            "min_free_ram_gib": args.min_free_ram,
        },
        "available_ram_before_gib": free_ram,
    }

    print(
        f"RBYRCT-05A: {args.size}^3 coarse grid"
    )

    # --------------------------------------------------
    # Stage 05A-01: coarse projector
    # --------------------------------------------------

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

    # --------------------------------------------------
    # Stage 05A-02: fine projector
    # --------------------------------------------------

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

    # --------------------------------------------------
    # Stage 05A-03: uniform-volume consistency
    # --------------------------------------------------

    if args.check_uniform:
        report["uniform_agreement"] = (
            benchmark_uniform_agreement(
                args.size,
                args.angles,
                args.tilts,
                factor=args.factor,
            )
        )

        uniform = report["uniform_agreement"]

        print(
            "Uniform agreement: "
            f"max error="
            f"{uniform['maximum_absolute_difference']}, "
            f"passed={uniform['passed']}"
        )

    # --------------------------------------------------
    # Stage 05A-04: reduced SIRT reconstruction
    # --------------------------------------------------

    if args.include_sirt:
        report["sirt"] = benchmark_sirt(
            size=args.size,
            angles=args.angles,
            tilts=args.tilts,
            budget=args.sirt_budget,
            iterations=args.sirt_iterations,
            seed=args.sirt_seed,
        )

        sirt = report["sirt"]

        print(
            f"SIRT: rays={sirt['budget']}, "
            f"iterations={sirt['iterations']}, "
            f"time={sirt['reconstruction_milliseconds']:.3f} ms, "
            f"RMSE={sirt['rmse']:.6f}, "
            f"residual={sirt['final_residual']:.6f}, "
            f"passed={sirt['passed']}"
        )

    # --------------------------------------------------
    # Overall validation
    # --------------------------------------------------

    stages = ["coarse"]

    if args.include_fine:
        stages.append("fine")

    if args.check_uniform:
        stages.append("uniform_agreement")

    if args.include_sirt:
        stages.append("sirt")

    report["numerical_checks_passed"] = all(
        report[stage]["passed"]
        for stage in stages
    )

    report["limitations"] = [
        "Synthetic parallel-ray geometry only.",
        "No adaptive acquisition policy evaluated.",
        "SIRT uses a same-operator inverse-crime smoke test.",
        "Uniform-volume agreement does not establish "
        "general operator equivalence.",
        "CSR storage excludes temporary allocations "
        "and other process memory.",
        "Available-RAM screening does not guarantee "
        "a safe peak-memory bound.",
        "Stages reconstruct matrices independently; "
        "construction times are not end-to-end optimized.",
        "Physical CT performance, radiation dose, and "
        "clinical usefulness are not evaluated.",
    ]

    # --------------------------------------------------
    # Save reproducible JSON report
    # --------------------------------------------------

    output = Path(args.output)
    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_text(
        json.dumps(
            report,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    print(
        "All numerical checks passed: "
        f"{report['numerical_checks_passed']}"
    )
    print(f"Report: {output}")

    if not report["numerical_checks_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
