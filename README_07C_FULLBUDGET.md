# RBYRCT-07C Full-Budget Engineering Preflight

This **profiling-only** add-on extends the committed `experiment_07c_preflight.py` from 1,024 to **4,096 acquired rays** for **both** adaptive policies on the same 32³ geometry. It performs no phantom accuracy comparison, defect-detection measurement, parameter search, or ground-truth feedback.

## Frozen production settings

- 32³ volume; 4 azimuths; existing 3 tilts; 12,288 candidate rays.
- 4,096 acquired rays for **coverage**, **gradient**, and **guarded_05**.
- Deterministic manufactured signal (`experiment_07b.deterministic_signal`), acquisition seed 707031.
- Coverage-order computation shared and reported separately.
- 64 common warm rays; batches of 32; candidate pool 16.
- 2 provisional and 4 final MART epochs; relaxation 0.25; guard eta 0.05.
- The selectors receive only acquired measurements through `AcquiredOnly`.

The geometry builder uses transient Python list allocations; **CSR storage bytes are not peak RAM**. `psutil` on Windows is strongly recommended for process working-set reporting. Operating-system peak working set is not the same as a line-by-line allocation profile. Run timing is machine-dependent and includes only the measured segments; no physical CT acquisition is modeled.

## Installation and run

Extract these three files into `C:\Users\shuss\Downloads\rbyrct-3d-05a` alongside existing scripts:

```powershell
python -m pytest test_experiment_07c_fullbudget.py -q
python -m pytest -q
git diff --check

python experiment_07c_fullbudget.py `
    --output-dir results/experiment07c_fullbudget/profile_4096_first
```

Outputs (new directory only): `protocol.json`, `profile.json`, `policy_timing.csv`, and `environment.json`.

```powershell
$dir = 'results/experiment07c_fullbudget/profile_4096_first'
Get-Content "$dir/profile.json"
Import-Csv "$dir/policy_timing.csv" |
    Format-Table policy, acquired, total_selection_including_common_s, final_reconstruction_s, process_peak_so_far_bytes -AutoSize
```

**Do not** use this profile to tune or select an acquisition policy based on reconstruction quality. If it completes and resource usage is acceptable, define a separate prospective 32³ accuracy validation protocol with new objects, fixed evaluation metrics, and stop rules. Do not overwrite earlier 07B/07C outputs.

### Long-running guarded path and partial output

A local 32³ / 4,096-ray engineering run completed coverage (2.12 s selection) and gradient (14.82 s selection), but the unchanged guarded selector **did not finish within a 180-second local execution limit**. This does **not** demonstrate that guarded acquisition is infeasible on your Windows machine, nor does it justify changing the method. The script now writes `policy_timing.csv`, `profile.json`, and `run_status.json` incrementally after each completed policy. If you must stop a long-running guarded profile, preserve the partial result directory; it is not a full pass. Allow the guarded run to finish if acceptable on your machine. Do not infer 4,096-ray guarded time from the shorter benchmark.
