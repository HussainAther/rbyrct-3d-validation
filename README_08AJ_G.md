# RBYRCT 08AJ-G — acquisition fairness and deterministic noise pairing (DRAFT)

**Status:** Engineering preflight only. Not a prospective lock. Do not use these results to claim comparative reconstruction performance.

## Files

- `experiment_08aj_g.py` — draft fairness/noise implementation and output-producing engineering fixture
- `test_experiment_08aj_g.py` — invariant checks and fixture tests
- `README_08AJ_G.md` — this document

Requires 08AJ-B through 08AJ-F and the unchanged upstream RBYRCT modules. Copy files into the same source directory as those modules.

## Windows PowerShell commands

```powershell
python -m pytest test_experiment_08aj_g.py -q

python experiment_08aj_g.py `
    --output-dir results\experiment08aj_g\fairness_first

Get-Content results\experiment08aj_g\fairness_first\run_status.json
Get-Content results\experiment08aj_g\fairness_first\fairness_report.json
```

Expected local smoke status: `FAIRNESS_PREFLIGHT_PASS`, `frozen: false`, `no_confirmatory_outcomes: true`.

## Proposed rules (subject to formal protocol review)

1. At the 32^3 primary configuration, the four *individual-ray* policies (`information_diag`, `coverage`, `uniform_multiscale`, and `stratified_random_04h`) start with the same first **64 rays** from the source coverage order, with matching acquisition seed. The diagonal selector continues with its existing algorithm. Coverage is unchanged. The two baseline raw permutations are filtered to remove shared-prefix rays and then appended in their original relative order. Thus these are **new prefixed policy variants** and must not be misrepresented as their historical unprefixed forms.
2. `complete_view` selects entire detector grids (`n*n` rays per view) using the existing 08AJ-C angular-spacing selector. **No shared 64-ray prefix is added** because that would violate the complete-view constraint. This arm is a secondary comparison with different acquisition admissibility constraints.
3. Each `(family, object seed, acquisition seed, forward-model condition)` determines one noise RNG seed by the first eight SHA-256 digest bytes of the exact ASCII key `08AJ-G-noise-v1|family|object_seed|acquisition_seed|model`, interpreted little-endian. The matched and independent conditions are distinct, but within each condition **all policies consume the same full candidate measurement catalogue**.
4. Noise is generated once over all candidate rays with the existing `nonnegative_noisy_measurements(..., fraction=0.005, seed=...)`, and policy-specific data are indexed from it. Overlapping selected ray IDs therefore carry identical observed values. This is a computational pairing choice, not a physical independent acquisition experiment.
5. The miniature 8^3 fixture uses a synthetic object seed **outside** the prospective 24-object roster. Its registered key seed is used **only to test the proposed noise-seed mapping**. No phantom RMSE, gains, whole-volume reconstruction, or 24-object outcomes are computed.

## Remaining issues before lock

- Audit the three phantom families against previously used source definitions and object rosters.
- Evaluate the proposed shared-prefix variants on the intended full 32^3 geometry before freezing. Do not inspect validation RMSE while selecting policy parameters.
- Freeze noise definition and the precise statistical CI/failure/resource rules.
- Validate full-size independent projector cost.
- Implement resumable runner, independent saved-output audit, source-lock checks, and repository commit.
- Design 64^3 complete-view comparisons at a budget divisible by 4096, separately from the 2048-ray pilot.

The preflight refuses to overwrite its output directory. Keep this report and the earlier 08AJ-F reconciliation draft unchanged. Do **not** invoke `--freeze`; the option is intentionally rejected.
