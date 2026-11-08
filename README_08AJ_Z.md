# RBYRCT-08AJ-Z — Engineering resource/failure controls and RMSE audit

**Safety/status:** Source lock and scientific approval are still absent. The 480-job prospective M roster remains `execution_allowed: false`. This script **cannot** execute the 24 prospective objects. Only fixed, noncohort engineering phantom seed `970099`, family `smooth_heterogeneity` is permitted through the existing Q/R numerical pipeline. No prospective reconstruction gains or rankings are computed.

## Package contents

Copy these four files into the repository root (alongside existing 08AJ-M/Q/R modules):

- `experiment_08aj_z.py`: proposed resource/failure gate, actual engineering job runner, numerical diagnostic receipts.
- `experiment_08aj_z_audit.py`: independently validates source links, numerical replay, immutable receipt hashes, and recalculates each job's RMSE against the fixed noncohort truth.
- `test_experiment_08aj_z.py`: eight automated tests.
- `README_08AJ_Z.md`: this guide.

## Proposed, NOT approved resource/failure limits

| Rule | Engineering proposal |
|---|---|
| Per-job numerical runtime | 600 seconds |
| Total runtime per run invocation | 7,200 seconds |
| Process peak resident/working set | 8 GiB, when available from psutil/resource |
| Corrupted/missing/out-of-lock input | Refuse execution/reuse |
| Nonfinite or nonpositive reconstruction | Abort and retain failure evidence |
| Incomplete or duplicated prospective records | Reject; no imputation |
| Failed job | Preserve failure receipt; no automatic retry |
| Outcome-based stopping/tuning | Forbidden |

**Limitations:** these are provisional engineering gates, not an approved study policy. The total wall-clock gate is checked **between** jobs; it is not an OS-enforced kill timeout. Process peak measurement may include prior work in the process. Execution interruptions caused by external termination may leave Q staging, which the independent auditor flags for review; Z records failures it catches. The gate does not measure total disk usage, aggregate 480-job runtime, or validate production execution. The resource ceilings require review/sign-off before the scientific freeze.

## Windows PowerShell commands

Run from the existing `rbyrct-3d-05a` directory, with the previously verified **08AJ-M** directory intact.

```powershell
python -m pytest test_experiment_08aj_z.py -q

python experiment_08aj_z.py `
  --output-dir results\experiment08aj_z\engineering_8_first `
  --m-dir results\experiment08aj_m\contract_first `
  --mode prepare --n 8

python experiment_08aj_z.py `
  --output-dir results\experiment08aj_z\engineering_8_first `
  --m-dir results\experiment08aj_m\contract_first `
  --mode check

python experiment_08aj_z.py `
  --output-dir results\experiment08aj_z\engineering_8_first `
  --m-dir results\experiment08aj_m\contract_first `
  --mode run

python experiment_08aj_z_audit.py `
  --output-dir results\experiment08aj_z\engineering_8_first `
  --m-dir results\experiment08aj_m\contract_first `
  --require-complete
```

Expected verdicts: `Z_ENGINEERING_GATE_PREPARED`, `Z_SOURCE_AND_GATE_MATCH`, `Z_ENGINEERING_EXECUTION_PASS`, `Z_INDEPENDENT_ENGINEERING_AUDIT_PASS`. The final audit should report **10 engineering jobs**, **no errors**, and `production_480_job_certified: false`. Run `--mode run` again to test verified reuse, **not `prepare`**.

### Optional full-resolution numerical compatibility

This executes one noncohort 32³, 2,048-ray, 16-epoch engineering job. The independent numerical replay is computationally expensive and was **not completed under the local execution limit**; its completion on Windows must be judged from the actual audit output, not assumed.

```powershell
python experiment_08aj_z.py `
  --output-dir results\experiment08aj_z\engineering_32_first `
  --m-dir results\experiment08aj_m\contract_first `
  --mode prepare --n 32

python experiment_08aj_z.py `
  --output-dir results\experiment08aj_z\engineering_32_first `
  --m-dir results\experiment08aj_m\contract_first `
  --mode run --policy coverage --model independent

python experiment_08aj_z_audit.py `
  --output-dir results\experiment08aj_z\engineering_32_first `
  --m-dir results\experiment08aj_m\contract_first
```

Do not overwrite evidence folders; use new names for another run.

## What remains unclosed

- **G1/G2:** scientific approval of fixed synthetic benchmark framing, phantom morphology limitations, and conditional inferential method.
- **G3:** these quantitative resource/failure rules are *implemented as proposals* but not yet approved or certified for full-scale 480-job operation.
- **G4:** production 480-job numerical executor and independent outcome audit are **not yet implemented or certified**. Z explicitly reuses fixed engineering-only Q/R code and does not claim production certification.
- **G5:** scientific signatures, source/environment lock, and permission to generate confirmatory outcomes are still pending.

**This is an engineering policy integration and audit stage, not a protocol freeze.**
