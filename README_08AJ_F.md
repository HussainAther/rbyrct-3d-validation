# 08AJ-F: phantom reconciliation and lock-readiness draft

**Status: DRAFT. No study protocol frozen, no comparative reconstructions run.**

The existing `08AJ-D` manifest hashes `phantom(family, seed, 32)`, whereas `08AJ-E` builds a fine phantom at 64³ and block-averages it to 32³. These are not generally identical. The proposed authoritative truth is the 64³ fine phantom and **exact 2×2×2 block-averaged** 32³ truth; the 08AJ-D roster of 24 object seeds and families is retained, but the truth hashes are versioned afresh.

This package adds `experiment_08aj_f.py` and `test_experiment_08aj_f.py`. Neither edits the 08AJ-D or 08AJ-E implementations, and the old `results/experiment08aj_d/design_draft_first` is preserved. Do not replace an existing result folder.

## Windows PowerShell commands

```powershell
python -m pytest test_experiment_08aj_f.py -q
python experiment_08aj_f.py `
    --output-dir results\experiment08aj_f\reconciled_draft_first
Get-Content results\experiment08aj_f\reconciled_draft_first\run_status.json
```

Expected verdict: `RECONCILIATION_PASS`, **frozen=false**, 24 objects, no outcome data. The proposed design report is `08aj_f_reconciled_design_draft.json` and a SHA-256 manifest is produced for the saved report and status.

## Explicit remaining review gates

1. Audit overlap with all historical phantom families and object seeds; internal uniqueness alone is not historical independence.
2. Resolve policy-specific warm-start fairness; a common individual-ray warm prefix is **not** automatically compatible with complete-view orders.
3. Fix the paired noise-generation rule, by object/seed/model, independent of policy identity.
4. Lock statistical CI assumptions, practical effect threshold, stopping/failure rules and budgets, after review.
5. Assess the fine forward-model adapter at 32³ across all three families; 64³ projector costs need separate feasibility work.
6. Keep the complete-view comparator secondary and only in budgets divisible by n².
7. Implement a resumable 24-object scientific runner, independent auditor, and signed source/protocol lock; do not run its outcomes before freeze.

No `--freeze` operation is permitted. No RMSE, policy gain, or hypothesis test is computed here.
