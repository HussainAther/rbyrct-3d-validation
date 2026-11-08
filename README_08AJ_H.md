# RBYRCT-08AJ-H — Full-scale engineering and lock-readiness draft

This is a **no-outcome preflight**, not a frozen validation or a publication result.
It reuses `experiment_08aj_b.py` through `experiment_08aj_g.py` and the existing geometry/projector. No production algorithm, prior preflight, or original protocol file is changed.

## Installation

Place the three files from this ZIP at the top level of `rbyrct-3d-05a`, alongside the 08AJ-B–G files.
Activate the existing `(rbyrct-3d)` environment.

## Commands (PowerShell)

```powershell
python -m pytest test_experiment_08aj_h.py -q

python experiment_08aj_h.py `
    --output-dir results\experiment08aj_h\lock_readiness_first

Get-Content results\experiment08aj_h\lock_readiness_first\run_status.json
Get-Content results\experiment08aj_h\lock_readiness_first\lock_readiness_report.json
```

Use a *new output directory* if rerunning: the script refuses overwrites to preserve evidence. Do not run `--freeze`; this is deliberately rejected.

## Checks

- Full `32^3` geometry, 12,288 candidate rays, 2,048 selected rays, both acquisition seeds (940411, 940829). Confirms 64-ray warm prefix across the four individual-ray policies, and exactly two complete-view acquisitions. Records acquisition-order SHA-256 fingerprints and execution times.
- A limited historical literal-seed scan of named 08M/08U/08W/08X/08Z/08AC source modules. **No detected literal overlap does not establish structural, generator-level, or exhaustive independence.**
- A **16-ray** sample of the independent ray-marching forward projector on a registered fine-resolution phantom. This times the bounded sample only; it is **not** a full 12,288-ray projector assessment, nor a 64^3 feasibility certificate. Pass `--probe-rays 1..64` if needed.
- Explicit draft primary endpoint, paired unit of analysis, family-stratified bootstrap proposal, missing-record handling, and proposed resource gates. These rules remain under scientific review and are not frozen.
- A no-overwrite results directory, machine-readable JSON, source SHA-256 hashes, and output manifest.

## Expected outcomes

`LOCK_READINESS_PREFLIGHT_PASS` means this preflight executed successfully. `lock_readiness` must remain `NOT_READY`, `frozen` remains false, and `no_confirmatory_outcomes` remains true.

## Known open items

1. Historical phantom structural/generator independence is not exhaustively established.
2. Complete full-catalogue, all-family independent-forward-model costs and assumptions still need evaluation.
3. Formal precision/power rationale, practical relevance and wall-clock ceilings need approval.
4. `64^3` complete-view sampling at 2,048 rays is impossible; test only at compatible budgets.
5. Full resumable 24-object validation runner, independent audit, signed protocol lock and explicit scientific approval are outstanding.

**Do not launch 24-object confirmatory reconstruction runs until these are resolved and the protocol is formally frozen.**
