# RBYRCT-08AJ-AO: Four-Job Fresh Regeneration

## Scope

Four selected 32-cubed noncohort engineering jobs were
regenerated locally and compared against historical AO evidence.

- Source checkout revision: `56736e8782c2dab688db1aecd84dfd6e088493a0`
- Environment specification SHA-256: `503948e8461d1a4e70306612bbb7abd4b82f0ec0e88a223874172642f11e0e24`
- Reconstruction difference tolerance: `1e-11`
- RMSE difference tolerance: `1e-12`

## Verified comparisons

| Job | Order byte-identical | Max reconstruction difference | RMSE difference |
|---|---|---:|---:|
| `engineering_alpha__seed_a__same__complete_view` | Yes | 9.9920072216264089e-16 | 0 |
| `engineering_alpha__seed_a__same__information_diag` | Yes | 1.1102230246251565e-15 | 0 |
| `engineering_alpha__seed_b__independent__information_diag` | Yes | 1.1102230246251565e-15 | 0 |
| `engineering_beta__seed_a__independent__information_diag` | Yes | 1.2212453270876722e-15 | 0 |

For each condition, clean and noisy measurement arrays
and the policy acquisition order were byte-identical
to the historical evidence.

## Reconstruction provenance

- `engineering_alpha__seed_a__same__complete_view`: historical reconstruction SHA-256 `41c02e0cc3285bf2d4774d5911ad3df9188aeab61ba9e97f761c0ed8d13b9340`; regenerated SHA-256 `1e086ecf8550b14e41817afff3e6e55d6c8e7e056a510032145d84439f2b53bc`; regenerated receipt SHA-256 `1703bf1072fe72d9bdc972ffddd9e35c5c43599024878ecd43475f3b3ff56928`
- `engineering_alpha__seed_a__same__information_diag`: historical reconstruction SHA-256 `d36d1a9856d3972b48c9cd5ca240b194f3c8ac27709a097c1cfec0b44fb4f243`; regenerated SHA-256 `af04fe6e38998be910bf806993a4d813621123c731d8cfe764fb319c2956b643`; regenerated receipt SHA-256 `cf9d1d53efbd9644aec22a7ddf65d6963c4b0d6e45afdc1494cbc10ab75bcf50`
- `engineering_alpha__seed_b__independent__information_diag`: historical reconstruction SHA-256 `63b56ca411096823b31f2eec6b39748288dcf9308776be90052799adf433ea2e`; regenerated SHA-256 `811e269ef9dffcc0e8c07c8ccf2727b3ae238647c9fe522aa60c614994018168`; regenerated receipt SHA-256 `43b52c661213fc2bf3f22e47e6ac8cfce434b6a107e6d29d6eb7d02b24fc9e89`
- `engineering_beta__seed_a__independent__information_diag`: historical reconstruction SHA-256 `5d60e035f6342b2e0220b5caaf3b47dab2a656c2f9b2067affd902dc0252770a`; regenerated SHA-256 `1c4120faa6dc180b1ac0a338f764c106b6fee90266517d07fe8d79ccba4f4fa7`; regenerated receipt SHA-256 `d4fe3a527dc6a7bd573bd5eb7172c7982051e9235550daf2012251c9c238f827`

## Interpretation and limits

All four comparisons satisfy the numerical tolerances.
Reconstructed arrays are not necessarily byte-identical.
The reported RMSE values agree for each historical and
regenerated pair.

The selected jobs cover both engineering objects, both
forward-model settings, two acquisition seeds, and two
policies. This is not the complete 20-job AO experiment.

These local tests do not establish independent-machine
reproduction or comparative imaging superiority.

The underlying arrays and receipts remain local.
Published hashes alone do not make that evidence accessible.

All five scientific approval gates remain blocked.
No prospective 480-job execution was authorized.
