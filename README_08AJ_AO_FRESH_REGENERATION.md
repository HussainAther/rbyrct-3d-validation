# RBYRCT-08AJ-AO: Fresh 32-Cubed Engineering Regeneration

## Scope

Two fixed, noncohort 32-cubed engineering reconstructions
were generated in a separate local output directory using
the minimal Conda environment.

This is not a prospective or confirmatory experiment.

## Source and environment

- Documentation source revision: `a25c3336211fca04b5518b31ca73487625544471`
- Environment specification: `environment_08aj.yml`
- Runner: `experiment_08aj_an.py`
- Independent auditor: `experiment_08aj_an_audit.py`

## Job configuration

- Object: `engineering_alpha`
- Acquisition seed: `seed_a`
- Forward model: `same`
- Resolution: 32 x 32 x 32
- Ray budget: 2048
- MART epochs: 16
- Relaxation: 0.25
- Policies: `complete_view`, `information_diag`

## Fresh regeneration comparisons

| Metric | Complete view | Information diagonal |
|---|---:|---:|
| Clean measurements byte-identical | Yes | Shared regenerated catalogue |
| Noisy measurements byte-identical | Yes | Shared regenerated catalogue |
| Acquisition order byte-identical | Yes | Yes |
| Maximum reconstruction difference | 9.9920072216264089e-16 | 1.1102230246251565e-15 |
| RMSE difference | 0 | 0 |

## Provenance

- Complete-view comparison report SHA-256: `e20e8d07a08d86ebc96f7a1a1938f24939b3495da8b4ae03abbcb67d2af6ba07`
- Adaptive-policy comparison report SHA-256: `79535ac00eb74cdff26eb1a9d0d69c72485407d3a2195ebe81fbb41898d2060e`

The original and regenerated reconstruction files are
not byte-identical. Their maximum numerical differences
are below the 1e-11 reconstruction tolerance.

The complete-view and adaptive acquisition orders match
their historical counterparts byte-for-byte.

## Reproduction boundaries

These results demonstrate fresh local regeneration for two
fixed engineering policies under one object/seed/model condition.
They do not establish reproduction of the full 20-job AO set,
reproduction on another machine, or bitwise-identical
reconstruction across environments.

The numerical evidence and comparison JSON files remain local;
their published hashes alone do not make them independently
accessible or verifiable.

No prospective jobs were executed. All five scientific
approval gates remain blocked.
