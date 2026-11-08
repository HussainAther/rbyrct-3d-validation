# RBYRCT-08Q — Source-locked voxel-level MART replay

## Objective

Independently reconstruct the *frozen 08M acquisition orders*, regenerate 08M measurements from the locked synthetic phantom / forward-projector definitions, and calculate numerical errors **directly from newly generated voxel arrays** rather than the archived RMSE columns. The new MART kernel and RMSE calculator are defined inside `replay_08q.py`; the original `mart_reconstruct` and `error_metrics` are **not** used by the replay.

**Claim boundary:** this is a second implementation of MART on the **same synthetic modeling assumptions**, using the frozen phantom and projection generators. It is not an independent CT simulation, an external validation, or an independent physical measurement. The acquisition selectors are not rerun: 08M's recorded ray sequences are replayed exactly.

## Extract into the source repository root

Extract the three root-level files `replay_08q.py`, `test_replay_08q.py`, and `README_08Q.md` into `C:\Users\shuss\Downloads\rbyrct-3d-05a`. Do not extract into an additional directory.

## Step 1 — Check code and tests

```powershell
python -m pytest test_replay_08q.py -q
python -m pytest -q
git diff --check
```

## Step 2 — Replay the predeclared primary endpoint

The primary run reconstructs **64** volumes: 8 objects × 2 forward models × 2 acquisition seeds × 2 policies (`coverage` and `information_diag`) at **2,048** acquired rays. It saves the new `float64` voxel arrays as `.npy` files and compares every replay RMSE against archived 08M records. An absolute/relative comparison tolerance of `2e-8` is a strict numerical consistency check; it is not a statistical threshold and was not chosen using the held-out outcomes.

```powershell
python replay_08q.py `
    --results-dir ..\rbyrct-results\experiment08m\frozen_first `
    --protocol-lock protocol_08m_frozen.json `
    --source-dir . `
    --output-dir ..\rbyrct-results\experiment08q\primary_replay_first `
    --scope primary
```

The process may take substantially longer than the 08M acquisition-selection preflight. The 64 MART reconstructions do full 16-epoch row-by-row updates. Do not interrupt simply because no progress appears between printed conditions. For a failure or interruption, **preserve the partial output**, inspect the error, and do not overwrite the same directory.

Inspect:

```powershell
$dir = '..\rbyrct-results\experiment08q\primary_replay_first'
Get-Content "$dir\run_status.json"
Get-Content "$dir\replay_report.json"
Import-Csv "$dir\aggregate_replayed.csv" | Format-List *
Import-Csv "$dir\voxel_rmse_comparison.csv" |
    Where-Object { $_.pass_check -ne 'True' } | Format-Table
```

A `PASS` should reproduce the archived primary object-balanced global gain `0.0500423027241302`, defect-region gain `0.0755644950628323`, and 8/8 positive object means on each endpoint. The program **never writes** into the 08M archive or changes the protocol lock. It verifies the 10 archived file digests and 15 frozen source hashes before computing.

## Step 3 — Optional full study replay

After a successful primary replay, execute all four policies and three checkpoints (384 volumes). Use a **new output directory**:

```powershell
python replay_08q.py `
    --results-dir ..\rbyrct-results\experiment08m\frozen_first `
    --protocol-lock protocol_08m_frozen.json `
    --source-dir . `
    --output-dir ..\rbyrct-results\experiment08q\all_replay_first `
    --scope all
```

The larger replay is computationally expensive; preserving `.npy` volumes may use approximately 96 MiB uncompressed, plus CSV/JSON manifests. It compares each of the 384 replay volumes across three RMSE measures and recomputes the information-policy object-level outcome for every checkpoint. A later audit can independently inspect saved arrays and hashes.

## Artifacts

- `voxel_rmse_comparison.csv`: 3 independent voxel-derived RMSE checks per reconstructed volume.
- `paired_gains.csv`: replayed paired policy-vs-coverage fractional gains.
- `object_level_replayed.csv` and `aggregate_replayed.csv`: information-policy gains using **eight** independent phantoms as statistical units.
- `*.npy`: newly saved full-precision reconstruction vectors, not present in 08M.
- `volume_manifest.csv`: hashes for those reconstruction arrays.
- `replay_report.json`: PASS/FAIL, primary endpoint, max absolute RMSE difference, source/archival provenance, limitations.
- `run_status.json` and `sha256.json`: completion status and saved result checksums.

## Method limits

The frozen geometry and high-resolution forward-model generators still come from the original source modules, so this is not independent forward-projector implementation. The random number generator is NumPy's seeded generator under your current environment; cross-version differences can cause reproducibility failures. Failures should be reported, not fixed by retuning or retroactively modifying 08M. We compare the full voxel-derived errors and paired primary endpoint; we do not automatically infer clinical dose reduction, statistical significance, or broad generalization.
