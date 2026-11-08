# RBYRCT-08AJ protocol design memo (DRAFT — NOT LOCKED)

## Primary research contribution A

**Question.** For a fixed candidate-ray geometry and limited ray budget, does the existing geometry-based diagonal information score yield more accurate 3D MART reconstructions than an independently defined conventional sampling strategy?

The original 08M positive outcome (eight synthetic objects, +5.0042% global gain at 2048 rays) is prior evidence, **not** a member of the new test sample. 08AC/08AD corroborate numerical replay of a distinct spatial balancing intervention and are not pooled with 08M.

**Proposed target:** Computationally constrained **synthetic** parallel-ray 3D tomography with known geometry. Do not claim patient dose, scanner execution, clinical usefulness, physical CT validation, or measurement-responsive adaptation.

## Proposed 08AJ scientific experiment — MUST BE APPROVED AND SOURCE-LOCKED

- At 32³, use 24 genuinely new object seeds from three independently specified phantom families (8/family): localized defects; smooth/low-contrast heterogeneity; and multiple irregular inclusions/textures. The generators must not observe selection results.
- Provisional primary checkpoint: 2048 selected rays; secondary 1024 and 4096. Two new acquisition seeds and matched/independent forward-model conditions per object, averaged within object, not treated as independent replicates.
- Policy candidates: diagonal information (unchanged 08K), a precisely specified conventional uniform/angular-detector sampler as *primary comparator*, existing coverage and stratified-random sampler as secondary comparators. Their actual implementations, starting ray rules, and budget matching remain **to be written and verified**. Do not rename existing coverage as uniform.
- Primary endpoint: mean paired fractional whole-volume RMSE gain at 2048 rays, averaged across four model/seed conditions within object, then across 24 objects. Report object-level gains and an object-resampling uncertainty interval. Fix interval method and inference threshold before outcomes, accounting for family stratification.
- Secondary: defect/nondefect RMSE, family-specific wins/effects, sensitivity-Gini diagnostic, SSIM if spatial definition/normalization is fixed, selection timing, memory, and reconstruction time.
- Distinguish a positive-mean statistical criterion from a separate practical-effect threshold. Power/precision justification to be written **before** freezing.
- Retain all negative outcomes, failed baselines, and timeouts according to predeclared stopping rules. Do not inspect confirmatory outcomes to tune the selector.

## Supporting contribution B

Diagnose whether differences in weighted voxel sensitivity, surrogate Gaussian trace reduction, acquisition geometry diversity, and MART reconstruction iteration schedule are associated with the diagonal policy's relative performance. These are **exploratory explanations** unless causal mechanisms and distinct interventions are prespecified. Repeat 08AC's objective–reconstructor mismatch without conflating replay of archived orders with independent selector redevelopment.

## Engineering 64³ transfer gate

**08AJ-P geometry-only preflight** checks sparse operator resources, exact existing diagonal policy scheduling, deterministic order fingerprints, and sampled process memory. It intentionally has no phantom or reconstruction metrics. Proposed default: 64³, 4 azimuth angles, 3 frozen elevation tilts, 2048-ray budget, warm 64, batch 32, pool 16, seed 930011, 2 repeats. Resource gates are 2 GiB CSR and 8 GiB sampled RSS (not peak). These are screening limits, not a promise of manageable runtime.

A second separately designed **single-volume MART feasibility pilot** is mandatory before multi-object 64³ experiments. Do not automatically execute a full 64³ outcome study based on the geometry gate alone.

## Remaining lock blockers

1. Verify geometry-specific uniform and stratified-random comparator definitions and identical ray admissibility.
2. Complete 64³ geometry and MART feasibility reports.
3. Finalize phantom generator designs and object seeds without performance-based selection.
4. Choose exact interval method, family weighting, practical effect criterion, baseline-policy ordering and compute/time stopping rules.
5. Freeze complete config, test baseline determinism and disjoint object seeds, hash all required source modules, and **commit** before outcomes.

## Evidence policy

No new 08AJ outcomes have been computed. 08M and 08AC/08AD are historical, distinct protocols. Any timing on a different OS/hardware must not be compared as controlled speedup without machine-matched measurements. A geometry-only ray selection order is not equivalent to executable CT projection acquisition.
