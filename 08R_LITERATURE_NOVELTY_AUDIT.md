# RBYRCT-08R — Literature and Novelty Audit

**Working paper:** *Geometry-Based Information-Guided Ray Ordering for Sequential MART Reconstruction in Synthetic Three-Dimensional Tomography*

**Research status:** Literature scoping audit, November 4, 2026. Not an exhaustive systematic review, not a claim of priority or patent novelty.

## Executive finding

The diagonal score used by RBYRCT is an instance of a familiar trace-reduction / A-optimal design calculation **conditional on treating the current diagonal matrix as the covariance**. The mathematical form itself must not be claimed as novel. Sequential information-based selection of CT views is well-established (including 3D tomography and publications in IEEE TCI). The most defensible possible contribution is a *specific lightweight ray-wise implementation and systematic evaluation with sequential MART reconstruction*, comparing geometry-only information ordering with coverage, gradient feedback, and a geometric guard under frozen synthetic test conditions.

The frozen 08M primary result was +5.0042302724% whole-volume RMSE gain and +7.5564495063% defect-region RMSE gain versus coverage at 2,048 rays, based on eight independent synthetic objects, with 8/8 object-level wins in each endpoint. The 08N saved-output audit and 08Q replay of 384 volumes confirmed numerical consistency to maximum absolute RMSE discrepancy 4.1633e-17. These are internal user-provided experimental findings, not findings of the cited external studies. Replay shares original phantom and projector definitions and archived acquisition orders.

## 1. Mathematical classification of the score

Assume a linear observation for candidate measurement row a,

    y = a^T x + epsilon,       epsilon ~ N(0, sigma^2),

and a *current* Gaussian covariance C. After one observation, the linear-Gaussian covariance update is

    C_new = C - (C a a^T C) / (sigma^2 + a^T C a).

The trace reduction is therefore exactly

    tr(C)-tr(C_new) = (a^T C^2 a)/(sigma^2 + a^T C a).

If one sets C = D diagonal, the expression becomes the RBYRCT candidate score

    S_info(a) = (a^T D^2 a)/(sigma^2 + a^T D a).

Consequently **this score is the exact one-step A-optimal variance/trace-reduction criterion for the assumed diagonal covariance model**. It is NOT a novel information-theoretic identity. It is also NOT, in general, the exact trace reduction for the full covariance after many rows, because the posterior of a Gaussian linear inverse problem develops off-diagonal entries. If D is formed by

    D_jj = (tau^-2 + sigma^-2 sum_{i in acquired} A_ij^2)^-1,

then D is the reciprocal diagonal of a precision approximation, not the diagonal of the inverse of the full precision matrix. These differ in general. Recomputing or updating this approximation gives a greedy *surrogate*; a sequence of such scores is not in general equivalent to exact sequential Bayesian A-optimal design. Check the exact implementation and parameterization in frozen source before claiming a specific online update formula.

Avoid conflating A-optimality (trace/total variance) with D-optimality or Shannon information gain (log determinant). The label “information-guided” is an informal description of the surrogate; it does not mean that the score directly measures true mutual information or MART posterior entropy.

## 2. Directly relevant prior work

### Tier 1 — Closest CT optimal-design precedents

**Burger, Hauptmann, Helin, Hyvönen & Puska (2021), “Sequentially optimized projections in X-ray imaging,” *Inverse Problems* 37(7), 075006; DOI 10.1088/1361-6420/ac01a4.** Sequential selection of projection geometry (angle and lateral source-receiver position), Gaussian prior/noise, A- and D-optimal criteria; 2D numerical studies. This is a close conceptual antecedent to sequential, row-level geometric choice. RBYRCT must differentiate the covariance approximation, candidate selection details, MART evaluation, and 3D evidence, rather than claim first sequential A-optimal CT ray selection.

**Helin, Hyvönen & Puska (2022), “Edge-Promoting Adaptive Bayesian Experimental Design for X-ray Imaging,” *SIAM J. Sci. Comput.* 44(3), B506–B530; DOI 10.1137/21M1409330.** A/D-optimal design with approximate Gaussian posterior informed by edge-promoting priors; simulated 2D and 3D X-ray imaging. This directly rules out broad “first 3D Bayesian-designed CT acquisition” claims. Their posterior is object/data-dependent; RBYRCT information policy is geometry-only.

**Wang, Lucka & van Leeuwen (2024), “Sequential Experimental Design for X-Ray CT Using Deep Reinforcement Learning,” *IEEE Trans. Computational Imaging* 10, 953–968; DOI 10.1109/TCI.2024.3414273.** Sequential angular selection cast as Bayesian/partially observable decision problem, evaluated in 2D simulated CT. Distinguish trained, measurement-responsive angle selection from deterministic geometric row ordering. Especially important because this appeared in the target journal.

### Tier 2 — Other acquisition-selection and reconstruction precedents

**“Adaptive projection selection for computed tomography” (2013), *IEEE Trans. Image Processing* 22(12), 5085–5095; DOI 10.1109/TIP.2013.2280185.** Uses spectral richness or added information to adapt projection angles; phantom/real-image simulation evidence. Supports the conclusion that information-based adaptive projection selection predates RBYRCT. Verify full author list from publisher before final bibliography.

**Barkan, Weill, Averbuch & Dekel (2013), “Adaptive Compressed Tomography Sensing,” *CVPR*, 2195–2202.** Selective line projections and reconstruction iteration; claimed image-quality advantages over nonadaptive limited-angle strategies. Important ray-wise/line-wise conceptual precedent, though not the same diagonal A-optimal criterion.

**“Task-Adaptive Angle Selection for Computed Tomography-Based Defect Detection” (2024), open-access article, PubMed Central PMC11433431.** Sequential OED and reinforcement learning oriented toward a defect-detection task. Different utility and angle-level selection; important task-driven counterexample to broad “new defect-aware CT acquisition” framing. Confirm authors and DOI before final reference list.

**“Selecting projection views based on error equidistribution for computed tomography” (2025), DOI 10.1177/08953996241289267.** Computationally economical nonuniform projection view selection based on projection errors; reported simulated and real-data comparisons. Closer to reconstruction-feedback selection than geometry-only RBYRCT. Verify full bibliographic details before citation.

**Wang et al. (2026), “Deep Reinforcement Learning for Optimizing Angle Selection and Dose Allocation in CT Reconstruction,” preprint arXiv:2604.20939 and subsequent online journal presentation.** Joint angle/dose decision and photon-statistical modeling. A reminder not to claim demonstrated radiation-dose reductions from a fixed ray-count synthetic MART study.

**Karimi & McGuire (2026), “View optimization in Computed Tomography,” arXiv:2611.03322 (posted November 2, 2026).** Very recent object-aware view-selection score using forward-model matrix decomposition and estimated object gradient; simulations at 5/15 views. Include as recent preprint context, without implying peer review or equivalence to ray-wise diagonal trace reduction.

## 3. Comparative matrix summary

- **Selection unit:** RBYRCT chooses individual candidate rays; much CT literature chooses projection angle/view, sometimes source-receiver pair. Barkan 2013 and Burger 2021 make an unqualified “first ray-wise selection” claim unsafe.
- **Uses measured intensities:** RBYRCT information selector: no; 2022 edge-promoting and 2024 learned adaptive variants can use acquired-data-dependent beliefs, so they may be more adaptive in the strict sense.
- **Objective:** RBYRCT diagonal A-optimal surrogate; Burger/Helin use Bayesian A/D-optimal design; RL papers use learned/task objectives; projection-error methods use error estimates.
- **Reconstructor:** RBYRCT fixed MART; related studies use other reconstruction families. This is a real implementation distinction, not automatic novelty by itself.
- **Evidence:** 08M frozen eight-object 32^3 synthetic dataset + 08N and 08Q verification; not yet external geometry, real CT, photon statistics, or head-to-head comparisons with established A-optimal alternatives.

## 4. Suggested contribution framing

Candidate contributions, appropriately conditional:

1. **Engineering / method:** A low-cost, geometry-only greedy diagonal trace-reduction surrogate for ordering available single-ray measurements in a 3D synthetic tomography operator, intended to be compatible with MART. Avoid claiming the mathematical score is invented here.
2. **Evaluation:** Paired, budget-specific comparison against coverage ordering, reconstruction-gradient feedback, and a scale-aware guard under a prespecified 32^3 synthetic protocol (8 objects; repeated forward-model and acquisition-seed conditions). Report the prespecified whole-volume endpoint and secondary defect endpoint.
3. **Reproducibility:** Frozen protocol/source hashes, saved acquisition orders, 08N file-level consistency audit, and 08Q independent MART kernel/voxel-level replay; clearly state remaining shared assumptions.
4. **Mechanism / caution:** A geometry-only information score can beat measurement-responsive heuristics in this particular reconstruction regime; this does not imply general dominance, patient/object adaptivity, or Bayesian posterior calibration.

Strong caution: The current comparisons are all in-house baselines. A reviewer can reasonably ask for comparisons against a full or low-rank A-optimal design, a simpler diagonal variance-only score, uniform-angle/stratified designs, and at least one alternate CT geometry or phantom family. Computational cost should report preprocessing as well as selector time. Ray count is not equivalent to photon dose, and ray-wise trajectories may impose gantry or detector operational constraints.

## 5. Recommended experiments before strong submission claims

**Priority A — mathematical/implementation ablation:** compare S_info to (i) simple a^T D a, (ii) exact/low-rank A-optimal selection on reduced 12^3 cases, and (iii) a geometric coverage score, with matched pools and budgets. Keep new tests separate from frozen 08M.

**Priority B — external-protocol validation:** different phantom-generation family, angle/ray geometry, randomization, noise statistics, and reconstruction tuning; do not retune the method on validation objects.

**Priority C — practical constraints:** batch and acquisition hardware feasibility; clarify counting of rays versus projections, views, scanner motion and dose.

**Priority D — full bibliography:** read full texts (not just abstracts) of Burger 2021, Helin 2022 and Wang 2024 and independently check claims about computational complexity, rank updates, candidate domain and evaluation geometry. Do not assert first-of-kind status before this step.

## 6. Manuscript language to adopt or avoid

**Use:** “We employ a diagonal surrogate for the one-step A-optimal trace reduction to construct a deterministic geometry-based ray order and evaluate it with MART reconstruction.”

**Use:** “Under a prospectively specified 32^3 synthetic protocol, the information-guided policy achieved 5.00% object-balanced whole-volume RMSE improvement over a coverage baseline at 2,048 acquired rays; 8/8 objects showed positive object-mean gains. Saved-data verification and a separate MART replay reproduced the recorded numerical outcomes.”

**Avoid:** “We introduce a new Bayesian information-gain formula”; “first adaptive CT ray selection”; “the policy learns defect locations”; “optimized radiation dose”; “MART posterior uncertainty is reduced by 5%”; “superior to state of the art”; “validated in real CT.”

## 7. Source URLs and confidence

1. Burger et al. 2021 — https://doi.org/10.1088/1361-6420/ac01a4 (journal and institutional records; high confidence in abstract-level comparison)
2. Helin et al. 2022 — https://doi.org/10.1137/21M1409330 (publisher and university record; high)
3. Wang et al. 2024 — https://doi.org/10.1109/TCI.2024.3414273 (university record and full-text hosted by CWI; high)
4. Adaptive projection selection 2013 — https://doi.org/10.1109/TIP.2013.2280185 (PubMed/university record; medium-high)
5. Barkan et al. 2013 — https://openaccess.thecvf.com/content_cvpr_2013/html/Barkan_Adaptive_Compressed_Tomography_2013_CVPR_paper.html (primary conference page; high)
6. Task-Adaptive Angle Selection 2024 — https://pmc.ncbi.nlm.nih.gov/articles/PMC11433431/ (full text; high thematic relevance, bibliographic verification pending)
7. Error equidistribution 2025 — https://pubmed.ncbi.nlm.nih.gov/39973765/ (PubMed; medium-high)
8. Wang et al. 2026 — https://arxiv.org/abs/2604.20939 (preprint; current status may change)
9. Karimi & McGuire 2026 — https://arxiv.org/abs/2611.03322 (preprint posted Nov 2, 2026; preliminary)

**Audit boundary:** The sources above were located and reviewed at abstract/metadata level, with some full-text availability. This is a targeted audit, not a comprehensive article-by-article derivation comparison. Literature novelty conclusions are provisional pending close full-text analysis of the nearest works.
