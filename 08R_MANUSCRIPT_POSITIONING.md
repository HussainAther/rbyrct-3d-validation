# RBYRCT-08R — Manuscript positioning text

## Recommended title

Geometry-Based Information-Guided Ray Ordering for Sequential MART Reconstruction in Synthetic Three-Dimensional Tomography

## Proposed abstract (working, not submission ready)

Sequential acquisition in tomographic imaging requires deciding which measurements to collect under a limited measurement budget. Although reconstruction-feedback heuristics can prioritize rays associated with current image structure, such choices do not necessarily improve reconstruction quality. We study a geometry-based ray-ordering policy that ranks candidate projection rows by a diagonal surrogate of one-step A-optimal covariance trace reduction and evaluates the resulting acquisition sequence using the multiplicative algebraic reconstruction technique (MART). The score is derived from a standard linear-Gaussian rank-one covariance update under an explicitly approximate diagonal covariance model; it is not a calibrated MART posterior or a new information-theoretic criterion. We compare the policy with coverage-based ordering, reconstruction-gradient selection, and a scale-aware incremental geometric guard in three-dimensional synthetic tomography. In a prospectively frozen 32^3 validation on eight independent synthetic phantoms, averaging matched and independent forward-model conditions and two acquisition seeds within each object, the information-guided policy improved whole-volume root-mean-square error by 5.00% relative to coverage ordering at the prespecified 2,048-ray checkpoint, with positive object-level mean gains for all eight phantoms. The corresponding defect-region improvement was 7.56%. A saved-output audit and an independently implemented MART kernel replay reproduced all 384 recorded reconstructions' RMSE values to floating-point precision. The findings support the numerical utility of this fixed geometry-based ordering under the investigated synthetic protocol, without establishing optimality, generalization to physical CT, or radiation-dose benefit.

## Proposed contribution statement

We do not introduce a new Bayesian A-optimal objective. We investigate an efficient diagonal approximation to the familiar covariance trace-reduction criterion in individual-ray ordering for three-dimensional MART, and document budget-specific reconstruction behavior against geometric and feedback-based selectors in a pre-registered synthetic validation with independently replayed numerical results.

## Related work bridge

Bayesian optimal experimental design has previously been applied to sequential CT geometry selection using A- and D-optimal criteria (Burger et al., 2021), and to edge-promoting, approximately Gaussian CT reconstruction with two- and three-dimensional demonstrations (Helin et al., 2022). Sequential CT angle selection has also been modeled as a learned decision problem (Wang et al., 2024). Our approach is narrower: it constructs a deterministic, geometry-only order of individual projection rows using a diagonal approximation to a standard A-optimal trace-reduction score and evaluates its interaction with MART reconstruction. The empirical comparison focuses on reconstruction error under frozen synthetic conditions rather than optimality of an inferred posterior or measurement-adaptive behavior.

## Reviewer concerns to preempt

1. Score formula and A-optimality are established theory; state this openly.
2. Diagonal covariance approximation may discard correlations and change greedy rankings.
3. 08M objects share one phantom family; independent objects != independent geometries.
4. Source and projector shared in replay, acquisition orders reused: partial independence.
5. No genuine head-to-head OED comparator yet; avoid state-of-the-art language.
6. No physical dose model or real acquisition; do not equate ray counts with dose.
7. Clarify sensor/gantry feasibility of ray-wise ordering.
