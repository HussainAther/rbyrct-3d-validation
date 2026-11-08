# RBYRCT-08E — Feedback-objective diagnostic (development only)

08E instruments *new* sequential acquisition decisions using the **unchanged** gradient score and 08B incremental guard (`lambda=0.25`). It does not replay unrecorded candidate pools from 08C and does **not** change the frozen 06B or 07C2 results.

## Scope

- New development object seeds: 808701–808702 (12³), 808801–808802 (32³); matched forward model only.
- Two policies: unrestricted gradient and incremental_25; 144 rays at 12³, 512 rays at 32³.
- Two candidate probes per policy/object at predeclared acquisition states: 12³ at 24/88 rays, 32³ at 64/320 rays.
- Each probe records the **actual drawn candidate IDs and gradient scores** before the acquisition decision, along with its chosen ray and geometric state.
- After the **entire acquisition history is fixed**, retrospectively compute geometric defect intersection, prior-path redundancy, and candidate-specific one-extra-ray MART RMSE changes. Ground truth, masks and unacquired candidate detector observations are used **only in that retrospective evaluation**, never in the selector.
- Full run: 8 acquisition histories × 2 probes × 16 candidates = 256 prospective candidate records and up to 272 MART reconstructions for retrospective scoring (baseline + one per candidate per probe), in addition to provisional acquisition reconstructions. Runtime not benchmarked locally.

**Interpretation:** Score-versus-one-ray RMSE correlations are exploratory associations on the sampled states; adding one ray and recomputing MART is an evaluation-only counterfactual, not evidence of real imaging effectiveness. The probe states are dependent within objects and are not independent replicates. No statistical tests or causal claims. Neither an exact replay of 08C nor a held-out study.

## Windows instructions

Extract the three files **directly into** `rbyrct-3d-05a`, without retaining a duplicate nested directory.

```powershell
python -m pytest test_experiment_08e.py -q
python -m pytest -q
git diff --check
python experiment_08e.py `
  --output-dir results/experiment08e/feedback_first
```

Inspect:

```powershell
$dir = 'results/experiment08e/feedback_first'
Get-Content "$dir/run_status.json"
Import-Csv "$dir/descriptive_summary.csv" | Format-List *
Import-Csv "$dir/candidate_probes.csv" | Select-Object -First 3 | Format-List *
```

A complete output has `run_status.json`, `protocol.json`, `candidate_probes.csv`, `acquisition_manifest.csv`, `descriptive_summary.csv`, and `sha256.json`. The script refuses overwrites. Keep these results separate from the frozen study artifacts.

### What to check

1. Are highly ranked candidates more likely to geometrically intersect defects? `score_vs_hit_corr` is descriptive only; zero/negative would suggest poor ranking alignment in these sampled states.
2. Are high-ranked rays more redundant? `score_vs_redundancy_corr` uses prior path-length coverage at candidate voxels; it is not a condition-number analysis.
3. Do high scores predict measured one-extra-ray improvement? `score_vs_one_ray_global_corr` and `score_vs_one_ray_defect_corr` describe evaluation-only retrospective gains.
4. Do the conclusions differ between 12³ and 32³, and between gradient and incremental_25 histories?

### Limitations and provenance

The experiment relies on installed repository dependencies (`experiment_04b`, `_04g`, `_04h`, `_05b_adaptive`, `_05b_gate`, `_05b_mart`, `_05b_08b`, `_06b`, `_07c_preflight`, `_08a`). Its focused tests cover pure diagnostics and source separation; they do not replace end-to-end validation on the user's Windows repository. A low or high correlation is not a demonstration of causal mechanism or algorithmic superiority.
