# RBYRCT 08AJ-AD — row-checkpoint recovery for engineering AB jobs

This patch works **only** on a previously completed and independently audited 08AJ-AB engineering job. It reads its saved, SHA256-verified CSR geometry, measurements and reference reconstruction. It does not read any of the 24 prospective phantoms, and cannot dispatch 480 production jobs. The AB shadow object seed remains 970099.

Files: `experiment_08aj_ad.py`, `experiment_08aj_ad_audit.py`, `test_experiment_08aj_ad.py`, this README. Copy them to the same directory as your existing AA, M, AB and E scripts, without changing prior evidence.

## Run automated tests

```powershell
python -m pytest test_experiment_08aj_ad.py -q
```

## Reproduce an interrupted 32^3, 16-epoch engineering MART job

The AB source below is your already-audited `information_diag__same` 32^3 job. The new AD directory MUST NOT already exist; these operations leave AB evidence unchanged.

```powershell
$adArgs = @(
    '--output-dir', 'results\experiment08aj_ad\engineering_32_resume_first',
    '--ab-dir', 'results\experiment08aj_ab\engineering_32_first',
    '--aa-dir', 'results\experiment08aj_aa\disabled_path_first',
    '--m-dir', 'results\experiment08aj_m\contract_first'
)

python experiment_08aj_ad.py --mode init @adArgs --policy information_diag --model same
python experiment_08aj_ad.py --mode run @adArgs --stop-after-rows 257
python experiment_08aj_ad.py --mode check @adArgs
python experiment_08aj_ad.py --mode run @adArgs
python experiment_08aj_ad_audit.py @adArgs
```

Expected stage results: `AD_ENGINEERING_RECOVERY_PREPARED`, `AD_ENGINEERING_INTERRUPTED_AT_CHECKPOINT`, `AD_SOURCE_AND_CHECKPOINT_CHAIN_PASS`, `AD_ENGINEERING_RESUME_PASS`, and `AD_INDEPENDENT_ROW_RECOVERY_AUDIT_PASS`.

The full-resolution AB reference was computed without interruption. AD resumes the same MART recurrence after an intentional row-257 stop. It must obtain a final array within `1e-11` maximum absolute difference from the AB reference, and the independent auditor checks the full recurrence plus RMSE equality. These are numerical reproducibility checks, *not* policy-improvement results.

## Safeguards and limitations

* AD runs only against an existing audited AB engineering job, with the same fixed seed and geometry. It cannot select a prospective object ID.
* Every checkpoint stores the complete current voxel vector and a SHA256-linked, append-only receipt keyed to the AB job. Before any resume it validates the entire chain and all previous arrays. Missing/modified/orphan files cause failure, never silent restart.
* A user-specified `--stop-after-rows` is a controlled simulation of interruption. Each 128 rows (and at a simulated stop) produces an immutable checkpoint. A real ungraceful kill between checkpoints loses up to 127 computed rows, and an incomplete final write is *not* silently repaired.
* The `--wall-seconds` cap (default 600, maximum accepted 7200) is checked inside the row loop, **not** an OS-enforced timeout. It is per invocation and does not account for independent AB replay during source validation. Peak RSS is not hard limited.
* This is not full 480-job numerical certification. Source freeze, resource-policy approval, scientific sign-off, and confirmatory execution authorization remain blocked.
* To test clean uninterrupted vs resumed AD runs, use a **different** AD output directory and omit `--stop-after-rows`; never edit the evidence directories. Both AD runs must match the independently audited AB reference.
* If the AD process crashes during a checkpoint write and leaves orphan data, preserve the directory as failure evidence. Do not delete/repair it silently; investigate and create a new explicitly labeled engineering attempt.
