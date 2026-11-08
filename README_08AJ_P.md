# RBYRCT-08AJ-P — Engineering-only feasibility preflight

This package reuses **unchanged** `experiment_08m0.run` and `experiment_08k.select_information` from the existing RBYRCT repository. The new wrapper profiles only sparse geometry construction, common coverage ordering, and two repeated diagonal-information schedules. It reads **no object truth, defect masks, detector intensities or MART reconstruction results**. It is not a validation study or a locked experiment.

## Installation

Copy `experiment_08aj_p.py` and `test_experiment_08aj_p.py` to your `rbyrct-3d-05a` repository root. Do **not** replace the historical 08M/08AC implementation or edit any archived experiment. Existing `experiment_08m0.py`, `experiment_08k.py`, `experiment_08j.py`, and geometry modules are required.

## Commands in PowerShell

```powershell
python -m pytest test_experiment_08aj_p.py -q
python experiment_08aj_p.py --smoke --output-dir results/experiment08aj_p/smoke_first
python experiment_08aj_p.py --output-dir results/experiment08aj_p/geometry64_first
Get-Content results/experiment08aj_p/geometry64_first/08aj_p_assessment.json
```

**Important:** the pytest test already runs a smoke preflight in an isolated temporary directory; the separate smoke CLI is optional. The full `64^3` default generates a 64³ sparse parallel-beam operator with 4 azimuth angles, 3 elevation tilts (49,152 candidate rays), a 2,048-ray geometry-only acquisition schedule, two repeated selection runs, and no reconstruction. Values are feasibility proposals, **not** locked scientific sample settings. Preserve all outputs. `--output-dir` must not already exist.

Resource gates default to 2 GiB CSR storage and 8 GiB sampled RSS. These gates are engineering screening thresholds and may be configured *before* the run for available hardware. Current RSS samples **do not estimate peak memory**. The wrapper measures no MART reconstruction time; geometry feasibility does not establish full 64³ feasibility.

If the full preflight completes, report `csr_gib`, `observed_rss_gib_not_peak`, timing fields in `profile.json`, and `deterministic`. If it fails, preserve its partial output and the console log and do not silently change the sampling methodology.

### Next after this preflight

1. Audit a safe single-volume 64³ MART reconstruction using a **separate**, explicitly engineering-only synthetic pilot and record peak memory. Do not treat it as evidence of diagonal superiority.
2. Design/test exact uniform-angular and stratified randomized baselines with fixed admissible ray geometry. Run geometry-invariant tests before object experiments.
3. Set and freeze the full 08AJ scientific protocol, including the primary comparator, object seeds, phantom populations, effect-size criterion, uncertainty method, reconstruction schedule and publication reporting rules.
4. Do not execute confirmatory outcome comparisons before protocol/source fingerprints are committed.
