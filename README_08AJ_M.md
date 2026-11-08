# RBYRCT-08AJ-M — Execution-disabled 480-job contract and independent engineering evidence audit

**Status: DRAFT. NO CONFIRMATORY EXECUTION. NO SCIENTIFIC FREEZE.**

This stage prepares a full 480-job *contract/roster*, not the live 480-job MART execution engine. The module cannot execute 24-object study jobs; `execute`, `commit`, `unlock`, and `freeze` always fail. This is intentional until scientific sign-off and independent end-to-end 16-epoch production audits are complete.

The job roster is 24 prospective objects × 2 acquisition seeds × 2 forward-model conditions × 5 acquisition policies = **480** uniquely identified conditions. All have 32^3 / 2048 rays / 16 MART epochs / 0.25 relaxation written as intended production settings, **not executed**. The draft contract also records a future per-job checkpoint/artifact schema, paired-noise rule, complete-view exception, proposed primary inference, and unresolved approval gates.

The 08AJ-M engineering evidence link *does not rerun reconstructions*. It reruns the existing independent 08AJ-L audit on the two 32^3 **2-epoch** noncohort engineering reconstructions, records SHA-256 hashes for their artifacts and L protocol, and refuses to overwrite an already committed link with different evidence. This does **not** certify 16-epoch numerical results or an operational production runner.

## Install

Extract these four new files into `C:\Users\shuss\Downloads\rbyrct-3d-05a` (alongside the installed 08AJ-D–L scripts):

- `experiment_08aj_m.py`
- `experiment_08aj_m_audit.py`
- `test_experiment_08aj_m.py`
- `README_08AJ_M.md`

Keep earlier `results\experiment08aj_l\draft_first` unchanged. Preserve all prior evidence.

## Windows PowerShell commands

```powershell
python -m pytest test_experiment_08aj_m.py -q

python experiment_08aj_m.py `
  --output-dir results\experiment08aj_m\contract_first `
  --mode prepare

python experiment_08aj_m.py `
  --output-dir results\experiment08aj_m\contract_first `
  --mode check

python experiment_08aj_m.py `
  --output-dir results\experiment08aj_m\contract_first `
  --mode attach-engineering `
  --l-dir results\experiment08aj_l\draft_first

python experiment_08aj_m_audit.py `
  --output-dir results\experiment08aj_m\contract_first `
  --l-dir results\experiment08aj_l\draft_first `
  --require-link
```

Expected verdicts: `M_CONTRACT_PREPARED`, `M_CONTRACT_SOURCE_MATCH`, `M_ENGINEERING_ATTACHMENT_PASS`, `M_INDEPENDENT_CONTRACT_AUDIT_PASS`. Tests should show **10 passed**.

The first three commands require a complete installed repository. `attach-engineering` requires your previously completed 08AJ-L run. The independent M auditor validates roster cardinality and order, unique identifiers, execution-disable flags, source file hashes, canonical JSON, exact 08AJ-L evidence file hashes, and reruns L's independent 2-epoch numerical replay. It fails closed on missing or modified evidence.

Do not retry `prepare` in the same output directory; it intentionally refuses to overwrite historical evidence. Repeated `check`, `attach-engineering` (unchanged input), and `audit` should be safe. If the M or L source files change after `prepare`, source checks will reject the old manifest; create a new versioned directory only after investigating why.

## Remaining requirements before scientific execution

1. Expert generator/morphological independence review; exact historical seed/hash nonoverlap is not conclusive.
2. Statistical precision/power rationale, bootstrap/design approval, and practical relevance interpretation.
3. Total runtime and memory ceilings, failure handling and retry rules approved.
4. A **real** 480-job numerical executor and independently validated per-job 16-epoch MART auditor. 08AJ-M only specifies the artifact/checkpoint interface and links 2-epoch engineering evidence.
5. Git source lock, explicit reviewers/approval identities, versioned frozen protocol and separate authorization gate.

The infeasible 64^3 / 2048-ray complete-view comparison remains out of scope of the primary 32^3 study.

No RMSE, phantom-accuracy comparisons, policy performance rankings, prospective reconstructions, or confirmatory estimates are produced by 08AJ-M.
