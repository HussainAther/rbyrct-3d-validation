
import astra
import numpy as np

# ============================================================
# RBYRCT Experiment 04A
# GPU-Accelerated 3D CT Reconstruction and Convergence Test
#
# Hardware: NVIDIA RTX 4070 Laptop GPU
# Backend: ASTRA SIRT3D_CUDA
# ============================================================

# 1. Configuration
N = 32
NUM_ANGLES = 64
CHECKPOINTS = [25, 50, 100, 200, 400]

angles = np.linspace(
    0, np.pi, NUM_ANGLES, endpoint=False
)

# 2. Construct synthetic 3D ellipsoidal phantom
z, y, x = np.mgrid[
    -1:1:complex(N),
    -1:1:complex(N),
    -1:1:complex(N)
]

phantom = (
    (x / 0.6)**2 +
    (y / 0.5)**2 +
    (z / 0.7)**2 < 1
).astype(np.float32)

# 3. Define ASTRA volume and projection geometries
vol_geom = astra.create_vol_geom(N, N, N)

# Corrected detector spacing:
# ASTRA's default volume spans N units along each axis.
proj_geom = astra.create_proj_geom(
    "parallel3d",
    1.0,  # detector row spacing
    1.0,  # detector column spacing
    N,    # detector rows
    N,    # detector columns
    angles
)

proj_id = None
rec_id = None
alg_id = None

try:
    # 4. Forward projection
    proj_id, projections = astra.create_sino3d_gpu(
        phantom,
        proj_geom,
        vol_geom
    )

    print("=" * 60)
    print("RBYRCT EXPERIMENT 04A — 3D RECONSTRUCTION")
    print("=" * 60)

    print("ASTRA version:", astra.__version__)
    print("CUDA available:", astra.use_cuda())
    print("Phantom shape:", phantom.shape)
    print("Projection shape:", projections.shape)

    assert projections.shape == (N, NUM_ANGLES, N)
    assert np.isfinite(projections).all()

    # 5. Create reconstruction volume
    rec_id = astra.data3d.create(
        "-vol",
        vol_geom,
        0.0
    )

    # 6. Configure CUDA-based 3D SIRT
    cfg = astra.astra_dict("SIRT3D_CUDA")
    cfg["ProjectionDataId"] = proj_id
    cfg["ReconstructionDataId"] = rec_id

    alg_id = astra.algorithm.create(cfg)

    # 7. Convergence experiment
    print("\nConvergence results")
    print("-" * 60)
    print(f"{'Iterations':>12} {'RMSE':>14} {'MAE':>14}")
    print("-" * 60)

    previous_iterations = 0
    results = []

    for total_iterations in CHECKPOINTS:
        additional_iterations = (
            total_iterations - previous_iterations
        )

        astra.algorithm.run(
            alg_id,
            additional_iterations
        )

        reconstruction = astra.data3d.get(rec_id)

        # Calculate in float64 for numerical stability
        error = (
            reconstruction.astype(np.float64) -
            phantom.astype(np.float64)
        )

        rmse = float(
            np.sqrt(np.mean(error**2))
        )

        mae = float(
            np.mean(np.abs(error))
        )

        assert np.isfinite(reconstruction).all()
        assert np.isfinite(rmse)
        assert np.isfinite(mae)

        print(
            f"{total_iterations:>12d} "
            f"{rmse:>14.6f} "
            f"{mae:>14.6f}"
        )

        results.append({
            "iterations": total_iterations,
            "rmse": rmse,
            "mae": mae
        })

        previous_iterations = total_iterations

    # 8. Final diagnostics
    print("-" * 60)
    print("Reconstruction shape:", reconstruction.shape)
    print("Finite reconstruction:", np.isfinite(reconstruction).all())

    initial_rmse = results[0]["rmse"]
    final_rmse = results[-1]["rmse"]

    improvement_pct = (
        100.0 * (initial_rmse - final_rmse) / initial_rmse
        if initial_rmse > 0
        else 0.0
    )

    print(
        f"RMSE improvement (25 -> 400 iterations): "
        f"{improvement_pct:.2f}%"
    )

    print("Experiment 04A convergence test completed.")

finally:
    # 9. Clean up ASTRA GPU resources
    if alg_id is not None:
        astra.algorithm.delete(alg_id)

    if rec_id is not None:
        astra.data3d.delete(rec_id)

    if proj_id is not None:
        astra.data3d.delete(proj_id)
