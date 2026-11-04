"""05B-02: MART convergence and ray-order sensitivity.

Uses the restored 05B MART kernel. Synthetic same-operator feasibility
study only; does not evaluate adaptive acquisition.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np

from experiment_04b import system_matrix
from experiment_05b_mart import mart_reconstruct


EPOCHS = (2, 4, 8, 16, 32)
RELAXATIONS = (0.05, 0.10, 0.15, 0.25)
SEEDS = (271828, 314159, 161803)
ORDERS = ("sorted", "reversed")


def run(size: int = 8, budget: int = 128) -> list[dict]:
    if not 4 <= size <= 8:
        raise ValueError("Initial convergence sweep requires size 4..8")

    angles = 12
    tilts = [-20.0, 0.0, 20.0]
    total_rays = len(tilts) * angles * size**2

    if not 1 <= budget <= total_rays:
        raise ValueError("Invalid ray budget")

    print(f"Building {size}^3 coarse projector...", flush=True)
    A = system_matrix(size, angles, tilts)

    z, y, x = np.indices((size, size, size))
    center = (size - 1) / 2.0

    truth = (
        (x - center)**2
        + (y - center)**2
        + (z - center)**2
        <= (size / 4.0)**2
    ).astype(np.float64).ravel()

    rows = []

    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        selected = np.sort(
            rng.choice(A.shape[0], size=budget, replace=False)
        )

        sub = A[selected].tocsr()
        b = sub @ truth

        initial = np.full(sub.shape[1], 0.3)
        baseline = float(np.linalg.norm(sub @ initial - b))

        for order_name in ORDERS:
            if order_name == "sorted":
                order = np.arange(budget)
            else:
                order = np.arange(budget - 1, -1, -1)

            for relaxation in RELAXATIONS:
                for epochs in EPOCHS:
                    start = time.perf_counter()

                    estimate = mart_reconstruct(
                        sub,
                        b,
                        epochs=epochs,
                        initial=0.3,
                        relaxation=relaxation,
                        ray_order=order,
                    )

                    elapsed = time.perf_counter() - start

                    residual = float(np.linalg.norm(sub @ estimate - b))
                    rmse = float(
                        np.sqrt(np.mean((estimate - truth)**2))
                    )

                    finite = bool(
                        np.isfinite(estimate).all()
                        and np.isfinite([rmse, residual]).all()
                    )

                    row = {
                        "size": size,
                        "budget": budget,
                        "seed": seed,
                        "order": order_name,
                        "relaxation": relaxation,
                        "epochs": epochs,
                        "rmse": rmse,
                        "residual": residual,
                        "relative_residual": (
                            residual / max(float(np.linalg.norm(b)), 1e-10)
                        ),
                        "initial_residual": baseline,
                        "seconds": elapsed,
                        "finite": finite,
                        "nonnegative": bool((estimate >= 0).all()),
                        "residual_improved": bool(residual < baseline),
                    }

                    rows.append(row)

                    print(
                        f"seed={seed} order={order_name:8s} "
                        f"lambda={relaxation:.2f} epochs={epochs:2d} "
                        f"RMSE={rmse:.6f} residual={residual:.6f}",
                        flush=True,
                    )

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=8)
    parser.add_argument("--budget", type=int, default=128)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/experiment05b/convergence"),
    )
    args = parser.parse_args()

    rows = run(size=args.size, budget=args.budget)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = args.output_dir / "convergence.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "experiment": "RBYRCT-05B-02",
        "size": args.size,
        "budget": args.budget,
        "configurations": len(rows),
        "all_finite": all(r["finite"] for r in rows),
        "all_nonnegative": all(r["nonnegative"] for r in rows),
        "all_residuals_improved": all(
            r["residual_improved"] for r in rows
        ),
        "best_rmse": min(rows, key=lambda r: r["rmse"]),
        "best_residual": min(rows, key=lambda r: r["residual"]),
        "limitations": [
            "Same-operator noiseless synthetic measurements.",
            "Single sphere phantom, not representative of all imaging cases.",
            "Fixed random ray subsets; no adaptive acquisition evaluated.",
            "Order variations test sorted versus reversed rows only.",
            "Best configurations are exploratory and may overfit this setup.",
            "Timing is not a controlled performance benchmark.",
        ],
    }

    json_path = args.output_dir / "summary.json"
    json_path.write_text(
        json.dumps(summary, indent=2, allow_nan=False),
        encoding="utf-8",
    )

    print("\n=== 05B-02 SUMMARY ===")
    print("Configurations:", len(rows))
    print("All finite:", summary["all_finite"])
    print("All nonnegative:", summary["all_nonnegative"])
    print("All residuals improved:", summary["all_residuals_improved"])
    print("Best RMSE:", summary["best_rmse"])
    print("Best measurement residual:", summary["best_residual"])
    print("CSV:", csv_path)
    print("JSON:", json_path)

    if not summary["all_finite"] or not summary["all_nonnegative"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
