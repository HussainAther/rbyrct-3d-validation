# RBYRCT-08AJ-AO: 32-Cubed Engineering Evidence

## Scope

This document records non-confirmatory engineering evidence
from the RBYRCT-08AJ-AO 32-cubed qualification.

The prospective 480-job scientific experiment remains disabled.
No scientific signoff, source freeze, or production authorization
is implied by this documentation.

## Configuration

- Resolution: 32 x 32 x 32 voxels
- Ray budget: 2,048 per job
- MART epochs: 16
- Row updates per job: 32,768
- Reconstruction relaxation: 0.25
- Engineering objects: engineering_alpha, engineering_beta
- Acquisition seeds: seed_a, seed_b
- Forward models: same, independent
- Policies: information_diag, uniform_multiscale, coverage,
  stratified_random_04h, complete_view
- Completed engineering jobs: 20
- Prepared measurement catalogues: 8

## Provenance

- AO plan SHA-256: `631f434b56037010936f617d0bf8b1159e1061c78ed8e5fafc72076054bbe521`
- Saved independent audit SHA-256: `1bb70efcf49287bd2dfa2ed4f577fbb3dc89818014deda713af279b7a6a857a9`
- Local provenance inventory SHA-256: `0f47c724b9207f16b3e2d2cf2d0c4a81c749091d9a6162933d1face6fb8bebe9`

The local provenance inventory contains the individual
measurement-receipt and reconstruction hashes. The inventory
and large numerical evidence files are not included in this README.
Hashes cannot be independently verified without access to
the corresponding evidence files.

## Saved independent numerical audit

- Verdict: `AN_INDEPENDENT_MULTI_SEED_AUDIT_PASS`
- Jobs audited: 20
- Groups audited: 8
- Maximum reported replay error: 0
- Maximum reported RMSE difference: 0

Acceptance tolerances:

- Maximum absolute reconstruction replay difference: 1e-11
- Maximum absolute RMSE difference: 1e-12

The independent AN auditor numerically replays the saved
reconstructions. The AP qualification module only reconciles
reported audits and provenance relationships.

## Completed engineering jobs

| Job ID | Saved RMSE |
|---|---:|
| `engineering_alpha__seed_a__same__complete_view` | 0.0861258046976 |
| `engineering_alpha__seed_a__same__coverage` | 0.141556848605 |
| `engineering_alpha__seed_a__same__information_diag` | 0.135398411819 |
| `engineering_alpha__seed_a__same__stratified_random_04h` | 0.149171148531 |
| `engineering_alpha__seed_a__same__uniform_multiscale` | 0.164649274673 |
| `engineering_alpha__seed_b__independent__complete_view` | 0.0861048362106 |
| `engineering_alpha__seed_b__independent__coverage` | 0.144104130163 |
| `engineering_alpha__seed_b__independent__information_diag` | 0.134619795502 |
| `engineering_alpha__seed_b__independent__stratified_random_04h` | 0.148286035862 |
| `engineering_alpha__seed_b__independent__uniform_multiscale` | 0.164751283827 |
| `engineering_beta__seed_a__independent__complete_view` | 0.0836459543312 |
| `engineering_beta__seed_a__independent__coverage` | 0.134469194956 |
| `engineering_beta__seed_a__independent__information_diag` | 0.128753559786 |
| `engineering_beta__seed_a__independent__stratified_random_04h` | 0.142076468826 |
| `engineering_beta__seed_a__independent__uniform_multiscale` | 0.156389572153 |
| `engineering_beta__seed_b__same__complete_view` | 0.083685894374 |
| `engineering_beta__seed_b__same__coverage` | 0.136838112298 |
| `engineering_beta__seed_b__same__information_diag` | 0.128287096961 |
| `engineering_beta__seed_b__same__stratified_random_04h` | 0.141018698456 |
| `engineering_beta__seed_b__same__uniform_multiscale` | 0.156472576409 |

## Reproduction

Install the documented environment using
`environment_08aj.yml`, then make the original
AA, M, and AO evidence directories available.

From the repository root:

```powershell
$args08 = @(
    "--output-dir", "results/experiment08aj_an/engineering_32_ao_first",
    "--aa-dir", "results/experiment08aj_aa/disabled_path_first",
    "--m-dir", "results/experiment08aj_m/contract_first"
)
python experiment_08aj_an_audit.py @args08
```

This command audits and replays existing engineering evidence.
It does not regenerate the original evidence from scratch.
The saved evidence may depend on historical source hashes;
source compatibility must be established before attempting
regeneration under another revision.

## Limitations

- This is an engineering qualification, not a confirmatory study.
- Twenty of the forty possible 32-cubed engineering jobs completed.
- Eight measurement catalogues were prepared; only four
  object/acquisition/model combinations have completed five-policy sets.
- Engineering RMSE values do not establish policy superiority.
- The local evidence files are required for independent re-audit.
- All five scientific approval gates remain blocked.
- Zero prospective jobs were authorized or executed.
