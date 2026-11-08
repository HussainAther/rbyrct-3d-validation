# RBYRCT-08AJ-AO: Independent Audit Comparison

## Scope

Comparison of two independent numerical replay audits
of the same 20 saved, non-confirmatory 32-cubed
engineering reconstructions.

## Audit identities

- Historical audit SHA-256: `1bb70efcf49287bd2dfa2ed4f577fbb3dc89818014deda713af279b7a6a857a9`
- New audit SHA-256: `ea6d5088ed5d11e25367660c4031effea5855e3beccc356a4826e8a99e5cb859`
- New audit Git revision: `f9d30fe15061784e8d6fc4318bdba3d5ef61c3d1`
- New audit start (UTC): `2026-11-08T03:41:35.429159+00:00`

## Results

- Engineering jobs compared: 20
- Measurement groups: 8
- Both independent audits passed
- Changed numerical replay values: 20
- Maximum new replay discrepancy: 1.7763568394002505e-15
- Maximum RMSE recomputation difference: 0
- Replay acceptance tolerance: 1e-11
- RMSE acceptance tolerance: 1e-12

## Per-job numerical comparison

| Job | Historical replay error | New replay error |
|---|---:|---:|
| `engineering_alpha__seed_a__same__complete_view` | 0 | 9.9920072216264089e-16 |
| `engineering_alpha__seed_a__same__coverage` | 0 | 1.7763568394002505e-15 |
| `engineering_alpha__seed_a__same__information_diag` | 0 | 1.1102230246251565e-15 |
| `engineering_alpha__seed_a__same__stratified_random_04h` | 0 | 1.5543122344752192e-15 |
| `engineering_alpha__seed_a__same__uniform_multiscale` | 0 | 1.5543122344752192e-15 |
| `engineering_alpha__seed_b__independent__complete_view` | 0 | 8.8817841970012523e-16 |
| `engineering_alpha__seed_b__independent__coverage` | 0 | 1.5543122344752192e-15 |
| `engineering_alpha__seed_b__independent__information_diag` | 0 | 1.1102230246251565e-15 |
| `engineering_alpha__seed_b__independent__stratified_random_04h` | 0 | 1.5543122344752192e-15 |
| `engineering_alpha__seed_b__independent__uniform_multiscale` | 0 | 1.7763568394002505e-15 |
| `engineering_beta__seed_a__independent__complete_view` | 0 | 8.8817841970012523e-16 |
| `engineering_beta__seed_a__independent__coverage` | 0 | 1.2212453270876722e-15 |
| `engineering_beta__seed_a__independent__information_diag` | 0 | 1.2212453270876722e-15 |
| `engineering_beta__seed_a__independent__stratified_random_04h` | 0 | 1.1102230246251565e-15 |
| `engineering_beta__seed_a__independent__uniform_multiscale` | 0 | 1.1102230246251565e-15 |
| `engineering_beta__seed_b__same__complete_view` | 0 | 8.8817841970012523e-16 |
| `engineering_beta__seed_b__same__coverage` | 0 | 1.3322676295501878e-15 |
| `engineering_beta__seed_b__same__information_diag` | 0 | 1.2212453270876722e-15 |
| `engineering_beta__seed_b__same__stratified_random_04h` | 0 | 1.3322676295501878e-15 |
| `engineering_beta__seed_b__same__uniform_multiscale` | 0 | 1.7763568394002505e-15 |

## Interpretation

All observed differences are within the independent
auditor's specified numerical tolerances.

The difference between zero and machine-precision
nonzero replay errors does not establish a scientific
performance difference.

The reports audit previously saved engineering evidence.
They do not establish full regeneration from scratch
in an independent environment.

The underlying numerical results and full audit JSON
remain local and are identified here by SHA-256 hashes.

The prospective 480-job experiment remains disabled.
All five scientific approval gates remain blocked.
