# RBYRCT-08AJ-U | Scientific blocker evidence (OUTCOME-FREE)

**Status:** SCIENTIFIC_REVIEW_EVIDENCE_PREPARED. NOT FROZEN. The prospective 24-object cohort is **not reconstructed**, evaluated or compared by acquisition policy.

## Scope

- Recompute deterministic structural summaries of the **proposed** 24 coarse 32³ phantoms using the authoritative 08AJ-F 64³-to-32³ block-averaged truth generator. Checking their morphology before a confirmatory lock is a protocol review action, not a reconstruction-outcome analysis.
- Recompute eight historical **06B generator** objects using the seed roster from 08M (`820101+7919*i`, `i=0..7`). This is a *reference subset*, not an exhaustive historical cohort audit. Both groups are synthetic; this does not establish external validity.
- Summaries include mean attenuation, spread, quantiles, edge/gradient RMS, bright/dark fractions and range. These are **descriptive** and not diagnostic proof of independence.
- Simulation uses **hypothetical Gaussian object-level gain** distributions, 8 objects per family and seeded family-stratified percentile bootstrap. It never samples empirical RMSE or generates any prospective acquisitions, reconstructions, or policy comparisons.

## Scientific interpretation

08AJ shares a high-level idea of synthetic hosts and seeded defects with 06B but differs in its hard-boundary spherical host and specific textures/inclusions, whereas 06B uses a tapered ellipsoidal host and rotated Gaussian defects. The three 08AJ families share a spherical host; describe them as **three synthetic stress-test families**, not three independent imaging populations.

The candidate bootstrap assumes within-family object exchangeability, with 24 object-level observations and four paired conditions nested within each object. The simulation explicitly does **not** establish power, nominal coverage across real gain distributions, or practical relevance. Treat the previously proposed 2% gain as a discussion threshold until approved. Lower CI >0 assesses directional evidence, not necessarily practical benefit.

## Windows PowerShell

Extract the three `.py` / `.md` files to the established `rbyrct-3d-05a` project folder. `experiment_08aj_u.py` imports existing project modules, including `experiment_06b.py`, `experiment_08aj_d.py`, `experiment_08aj_e.py`, and `experiment_08aj_f.py`.

```powershell
python -m pytest test_experiment_08aj_u.py -q

python experiment_08aj_u.py `
    --output-dir results\experiment08aj_u\scientific_review_first

Get-Content results\experiment08aj_u\scientific_review_first\run_status.json
```

Full report: `results\experiment08aj_u\scientific_review_first\scientific_review_evidence.json`.

Do not run `init` or any reconstruction command for the proposed 24-object study. This script refuses to overwrite any prior output directory.

## Remaining approvals and limitations

1. Reviewer assessment of generator/feature relevance, possible resemblance to older cohorts, and scope of conclusions. Exact hash non-overlap is not morphology independence.
2. Scientific/statistical sign-off on inference after sensitivity/calibration work (e.g. non-Gaussian distributions, family effects, BCa or studentized intervals), the 24-object precision target, and a practical-effect interpretation.
3. Calibrated engineering resource/failure rules.
4. Validated 480-job production executor and independent RMSE/outcome auditor.
5. Immutable source lock, approvals, and separate execution authorization.

**Output is review evidence only. It does not clear 08AJ-T’s freeze gate.**
