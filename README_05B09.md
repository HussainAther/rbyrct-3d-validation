# RBYRCT-05B-09: Frozen-ray-set MART convergence audit

**Purpose:** Test whether 05B-08B differences between reconstruction-informed acquisition and coverage-only persist when the *selected ray IDs are held fixed* but the **final** MART epochs and relaxation are varied.

- Reconstructs the original 08B acquisition orders using exactly the original parameters and seeds. **08B did not save ray IDs**, so the study regenerates them deterministically, and checks that every baseline `(16 epochs, 0.25 relaxation)` RMSE matches `08B/matched_cases.csv` at high numerical precision. If the old baseline doesn't match, the run fails.
- Uses only acquired observations to select rays. The full synthetic observation vector and truth are used only to evaluate frozen reconstruction outputs after selection.
- Saves SHA256 fingerprints of the *ordered* ray IDs for each policy and case, so reconstruction alternatives are provably matched to the same ray sequence.
- Uses final reconstruction grid of 8,16,32,64 epochs and 0.15,0.25 relaxation by default; acquisition itself remains fixed at 08B's provisional 4 epochs and relaxation 0.25.
- Keeps the original source results untouched and saves new CSVs under a new output folder.

## Installation / tests

Copy `experiment_05b_09.py`, `test_experiment_05b_09.py`, `README_05B09.md` to the root of the **same** Windows worktree; don't retain a nested duplicate test folder.

```powershell
python -m pytest test_experiment_05b_09.py -q
python -m pytest -q
git diff --check
```

## Frozen 08B audit

```powershell
python experiment_05b_09.py `
    --source-dir results/experiment05b/robustness_08b_frozen_first `
    --final-epochs 8 16 32 64 `
    --final-relaxations 0.15 0.25 `
    --output-dir results/experiment05b/frozen_rays_09_first
```

**Outputs:** `frozen_reconstructions.csv` (RMSE, observed-ray residual, matched policy/solver config); `ray_fingerprints.csv`; `object_level_summary.csv` (object-aggregated gains); `protocol.json`. The anchor reference must match for all 256 original policy-case records; the audit will produce 2,048 final reconstruction rows (64 case conditions x 4 policies x 8 solver settings).

**Interpretation:** A worse RMSE at 16 epochs could be due to insufficient reconstruction, but improvement with epochs does not imply mathematical convergence. If a policy's ranking changes under the same final solver settings, that supports solver-sensitivity of comparative conclusions. This *does not* establish whether the policy chooses intrinsically good rays. Acquired-ray relative residual is a diagnostic, not substitute for object RMSE. Repeated noise/model/seed conditions for each object are dependent, not 64 independent objects.
