# RBYRCT-08AJ-AG — Fresh-Input Row-Level Engineering Recovery

## Purpose

Connect the *fresh, noncohort engineering inputs* of 08AJ-AF to the proven row-level MART checkpoint mechanism of 08AJ-AD. **No prospective 24-object cohort data may be selected, generated, or run.** The planned 480-job roster stays locked; this stage is **not** production numerical certification.

## Package contents

- `experiment_08aj_ag.py` — fixed-engineering-input executor and append-only row checkpoint chain.
- `experiment_08aj_ag_audit.py` — independent final state, AF reference, and RMSE auditor.
- `test_experiment_08aj_ag.py` — 10 tests of small numerical fixture, interruption, corruption and locking.
- This README.

Install these four files in `C:\Users\shuss\Downloads\rbyrct-3d-05a`, retaining the existing 08AJ-AF, AD, AA, M and numerical dependency modules. The AG executor reads and verifies AF evidence but does **not** modify it.

## Windows commands

```powershell
python -m pytest test_experiment_08aj_ag.py -q

$agArgs = @(
    "--output-dir", "results\experiment08aj_ag\fresh_32_recovery_first",
    "--af-dir", "results\experiment08aj_af\fresh_engineering_32_first",
    "--aa-dir", "results\experiment08aj_aa\disabled_path_first",
    "--m-dir", "results\experiment08aj_m\contract_first"
)

python experiment_08aj_ag.py --mode init @agArgs `
    --policy information_diag --model same

python experiment_08aj_ag.py --mode run @agArgs --stop-after-rows 257

python experiment_08aj_ag.py --mode check @agArgs

python experiment_08aj_ag.py --mode run @agArgs

python experiment_08aj_ag_audit.py @agArgs
```

Expected verdicts, in order:

1. `10 passed`.
2. `AG_FRESH_RECOVERY_PREPARED`.
3. `AG_FRESH_ENGINEERING_PAUSED` with `rows_done=257`.
4. `AG_FRESH_SOURCE_AND_CHAIN_PASS`.
5. `AG_FRESH_ENGINEERING_RESUME_PASS` with `rows_done=32768` and `max_abs_error_vs_af` within tolerance.
6. `AG_INDEPENDENT_FRESH_ROW_RECOVERY_AUDIT_PASS` with no errors and near-zero numerical replay/RMSE difference.

**Only run the final audit once `run` reports `AG_FRESH_ENGINEERING_RESUME_PASS`.** Running it on a paused job correctly returns a failure because no final artifact exists.

## Key safeguards

- AF evidence is **read-only** and must be in the fixed `FRESH_ENGINEERING_ONLY` namespace with disjoint engineering seeds.
- AG uses only an already completed AF `policy__model` engineering job.
- No dynamic object family, seed, or acquisition source is accepted by AG's CLI.
- The checkpoint chain stores `cp_XXXXXXXX.npy` and linked `cp_XXXXXXXX.json` files for every 128 MART row updates, plus the interruption cursor.
- Resume checks the complete hash chain before applying any additional updates. Orphaned/missing artifacts and data corruption stop execution; no automatic repair or overwrite.
- The independent audit reconstructs from the selected CSR/measurement arrays, compares with the saved uninterrupted AF reference, regenerates the AF truth, and recomputes RMSE.
- `--wall-seconds` is a cooperative per-invocation timeout check, **not a hard OS-level timeout**; hard memory enforcement is **not implemented**.
- There is no prospective executor, unlock, or scientific freeze action.

## Scientific and engineering limitations

Local tests validate small numeric fixtures and failure-path behavior, not full-resolution AG execution. A successful Windows 32³ audit would establish one engineering reconstruction's exact recovery from a fresh-input AF reference. It would **not** establish 480-job numerical certification, resource-policy approval, or scientific sign-off. The actual prospective study remains disabled.

Preserve `results\experiment08aj_af\fresh_engineering_32_first` unchanged and do not overwrite prior 08AJ-AD, AE or AC evidence.
