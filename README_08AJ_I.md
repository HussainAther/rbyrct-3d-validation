# 08AJ-I — Full independent-projector and historical object-manifest engineering audit

**Status: preflight only; NOT frozen; no confirmatory outcomes.**

08AJ-I performs two tasks without reconstructing phantoms, comparing acquisition policies, computing RMSE, or editing earlier experiments:

1. Full 32³ independent-model forward projection of all 12,288 rays from one **non-validation** engineering phantom (`localized_defects`, seed `970099`), recording actual elapsed time, finite/nonnegative checks, a SHA-256 array fingerprint, and the available peak-memory measurement. It uses the unchanged `experiment_04qa.project` implementation with the fine-resolution 64³ phantom and `factor=2, step=0.5`.
2. Historical object audit against available archived `object_manifest.csv` files for 08M, 08U, 08W, 08X, 08Z, and 08AC. It checks exact seed matches and exact stored truth SHA-256 matches against the 24 proposed 08AJ-F fine/coarse objects. **No exact overlap is not proof of structural or generator independence.** The completeness check means all six named experiments had manifests, not that every historical cohort was exhaustively recovered.

## Installation

Extract these three files into your existing `rbyrct-3d-05a` folder:

- `experiment_08aj_i.py`
- `test_experiment_08aj_i.py`
- `README_08AJ_I.md`

## Run in PowerShell

Your historical results normally live in `..\rbyrct-results` relative to the code folder. Run:

```powershell
python -m pytest test_experiment_08aj_i.py -q

python experiment_08aj_i.py `
    --history "..\rbyrct-results" `
    --output-dir results\experiment08aj_i\engineering_first

Get-Content results\experiment08aj_i\engineering_first\run_status.json
Get-Content results\experiment08aj_i\engineering_first\08aj_i_report.json
```

If the results are instead archived as a ZIP, point `--history` to the ZIP file, e.g. `..\rbyrct-results.zip`.

**Important:** The output directory must not exist. The runner refuses overwriting evidence. Do not delete or replace an existing output to rerun. Use a different directory name for a deliberate repeat.

## Interpreting the report

- `ENGINEERING_AUDIT_PASS`: all six named historical studies had parseable manifests, no exact object seed or truth hash overlap was identified, and the full independent projector passed the measured time/peak-memory and numerical gates.
- `REVIEW_REQUIRED`: an archive is missing or incomplete; an exact collision exists; or memory/time/numerical acceptance was not established. Inspect report; do not assume a scientific failure.
- `lock_readiness` remains `NOT_READY` even on engineering PASS.
- Windows uses `psutil.memory_info().peak_wset` where supported; Linux uses `resource.ru_maxrss`. A missing peak metric must not be mistaken for a successful memory gate.
- The 600-second and 8-GiB limits are **engineering preflight defaults**, not yet approved study stopping rules.

## Verification scope

The local developer preflight passed 7 new tests; the combined 08AJ-B through 08AJ-I suite passed 60 tests. A single full projector run used the same 32³ geometry and provided a full-ray numerical sanity check, not reconstruction accuracy, dose, or 24-object runtime certification.

## Outstanding matters

1. Scientific review of historical generator and structural independence (distinct hashes are insufficient).
2. Approval of inferential/precision rationale, resource ceilings and practical relevance threshold.
3. Explicitly separate 64³ complete-view experiments at feasible budgets (at least 4096 rays per view).
4. Resumable 24-object runner, independent audit and signed source/protocol lock before prospective outcome generation.

**Do not freeze the protocol or run 24-object comparative reconstruction outcomes based solely on this preflight.**
