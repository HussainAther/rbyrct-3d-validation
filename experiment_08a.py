"""RBYRCT-08A: geometry-only development of an incremental coverage guard.

NOT a reconstruction or imaging-validation experiment. Does not read saved 07C2
outcomes, measurement data, defect masks, or use 07C2 acquisition/object seeds.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import numpy as np

from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_05b_adaptive import score_candidates

DEFAULT_STATES = {12: (24, 144, 288, 576), 32: (64, 1024, 2048, 4096)}
DEV_SEED = 808001
ANGLES = 4
POOL = 16
REPLICATES = 8
OLD_ETA = .05
NEW_LAMBDA = .25


def incremental_variance(A, candidates, counts):
    """Stable Var(c+w)-Var(c), without subtracting near-equal total variances.

    Delta = (2/N)*(c-mean(c)) dot w + (w dot w)/N - (sum(w)/N)^2.
    Sparse row w is the candidate ray's nonnegative path-length vector.
    Negative Delta is valid: a ray can improve coverage balance.
    """
    A = A.tocsr()
    ids = np.asarray(candidates, dtype=np.int64)
    c = np.asarray(counts, dtype=np.float64)
    if c.shape != (A.shape[1],) or not np.isfinite(c).all() or (c < 0).any():
        raise ValueError('invalid coverage state')
    if ids.ndim != 1 or len(ids) == 0 or len(set(ids.tolist())) != len(ids) or (ids < 0).any() or (ids >= A.shape[0]).any():
        raise ValueError('invalid candidate IDs')
    center = c - c.mean()
    nvox = len(c)
    out = np.empty(len(ids), dtype=np.float64)
    for j, idx in enumerate(ids):
        lo, hi = A.indptr[idx:idx + 2]
        vox = A.indices[lo:hi]
        w = A.data[lo:hi]
        sw = float(w.sum())
        out[j] = (2.0 * float(np.dot(center[vox], w)) + float(np.dot(w, w))) / nvox - (sw / nvox) ** 2
    if not np.isfinite(out).all():
        raise ArithmeticError('nonfinite incremental variance')
    return out


def incremental_eligibility(delta, reference_position, fraction=.25):
    """Candidate-range-normalized constraint; reference is always admissible.

    Admit i when delta_i <= delta_ref + fraction*(max(delta)-min(delta)).
    Fraction 0 admits any candidate no worse than reference, not necessarily
    only the reference; fraction 1 admits all candidates. New lambda is a
    developmental parameter, NOT proven optimal or tuned for RMSE.
    """
    d = np.asarray(delta, dtype=np.float64)
    if d.ndim != 1 or not len(d) or not np.isfinite(d).all():
        raise ValueError('invalid delta')
    if not isinstance(reference_position, (int, np.integer)) or not 0 <= reference_position < len(d):
        raise ValueError('invalid reference')
    if not math.isfinite(fraction) or not 0 <= fraction <= 1:
        raise ValueError('fraction must be in [0,1]')
    spread = float(d.max() - d.min())
    threshold = float(d[reference_position] + fraction * spread)
    tolerance = 64 * np.finfo(float).eps * max(float(np.max(np.abs(d))), 1e-12)
    eligible = d <= threshold + tolerance
    eligible[reference_position] = True
    return eligible, threshold, spread


def compare_guard(A, candidates, counts, viewcounts, n, *, old_eta=OLD_ETA, new_lambda=NEW_LAMBDA):
    """Compare eligibility on ONE identical candidate set; no observations."""
    cand = np.asarray(candidates, dtype=np.int64)
    scores = score_candidates(A, cand, counts, viewcounts, n,
                              np.ones(A.shape[1], dtype=float), feedback_strength=0.)
    high = np.max(scores)
    tied = np.flatnonzero(np.isclose(scores, high, rtol=1e-13, atol=1e-14))
    ref = int(min(tied, key=lambda j: int(cand[j])))
    delta = incremental_variance(A, cand, counts)
    # Exact same criterion as the frozen 06A guard, computed with stable
    # incremental variance; no data from validation outcomes.
    base = float(np.var(counts))
    prospective = base + delta
    creference = float(prospective[ref])
    old_threshold = creference + old_eta * max(creference, 1e-12)
    old_eligible = prospective <= old_threshold + 1e-14
    old_eligible[ref] = True
    new_eligible, new_threshold, spread = incremental_eligibility(delta, ref, new_lambda)
    return dict(reference=int(cand[ref]), old_eligible=int(old_eligible.sum()),
                new_eligible=int(new_eligible.sum()), pool_size=len(cand),
                old_binding=bool(not old_eligible.all()),
                new_binding=bool(not new_eligible.all()),
                min_delta=float(delta.min()), max_delta=float(delta.max()),
                reference_delta=float(delta[ref]), delta_range=spread,
                old_reference_variance=creference,
                old_relative_spread=float((prospective.max()-prospective.min())/max(prospective.min(),1e-12)),
                new_threshold=float(new_threshold), old_threshold=float(old_threshold))


def run(output_dir, *, states=DEFAULT_STATES, replicates=REPLICATES, pool=POOL, seed=DEV_SEED):
    """Development-only geometry diagnostic with a deterministic coverage history."""
    if seed in (104729, 130363, 707001) or seed >= 2077001 and seed <= 2132434:
        raise ValueError('seed reserved or too close to frozen validation seeds')
    if replicates < 1 or pool < 2 or not states:
        raise ValueError('invalid development configuration')
    root = Path(output_dir)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError('refusing to overwrite a nonempty output directory')
    root.mkdir(parents=True, exist_ok=True)
    rows = []
    for n, prefixes in sorted(states.items()):
        if n not in (12,32) or not prefixes or min(prefixes) < 1:
            raise ValueError('unsupported diagnostic geometry or prefix')
        A = system_matrix(n, ANGLES, TILTS).tocsr()
        if max(prefixes) >= A.shape[0]:
            raise ValueError('prefix exceeds ray geometry')
        order = voxel_coverage_order(A, n, ANGLES, len(TILTS), max(prefixes), seed + n, 16)
        rng = np.random.default_rng(seed + 100*n)
        for prefix in prefixes:
            acquired = order[:prefix]
            counts = np.asarray(A[acquired].sum(axis=0)).ravel().astype(float)
            views = np.bincount(acquired//(n*n), minlength=ANGLES*len(TILTS))
            available = np.ones(A.shape[0], dtype=bool)
            available[acquired] = False
            remaining = np.flatnonzero(available)
            for replicate in range(replicates):
                candidates = rng.choice(remaining, size=min(pool, len(remaining)), replace=False)
                diagnostic = compare_guard(A, candidates, counts, views, n)
                rows.append(dict(size=n, acquired=prefix, replicate=replicate,
                                 **diagnostic))
    cols = list(rows[0])
    with (root/'candidate_pool_diagnostics.csv').open('w', newline='', encoding='utf8') as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader(); writer.writerows(rows)
    summary = []
    for n,prefixes in sorted(states.items()):
        for prefix in prefixes:
            selected = [r for r in rows if r['size']==n and r['acquired']==prefix]
            summary.append(dict(size=n, acquired=prefix, pools=len(selected),
                  old_bindings=sum(r['old_binding'] for r in selected),
                  new_bindings=sum(r['new_binding'] for r in selected),
                  old_mean_eligible=float(np.mean([r['old_eligible'] for r in selected])),
                  new_mean_eligible=float(np.mean([r['new_eligible'] for r in selected])),
                  mean_relative_variance_spread=float(np.mean([r['old_relative_spread'] for r in selected]))))
    with (root/'summary.csv').open('w', newline='', encoding='utf8') as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0]));writer.writeheader();writer.writerows(summary)
    protocol = dict(stage='RBYRCT-08A geometry-only development; NOT reconstruction validation',
                    input='new deterministic geometry-only histories; no phantom, masks, measurement or 07C2 output files',
                    sizes=list(states),prefixes={str(k):list(v) for k,v in states.items()},
                    angles=ANGLES,seed=seed,pool=pool,replicates=replicates,
                    old_eta=OLD_ETA,new_lambda=NEW_LAMBDA,
                    new_rule='delta_i <= delta_reference + lambda*(max_delta-min_delta)',
                    no_claim='Binding does not imply better reconstruction RMSE')
    (root/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n',encoding='utf8')
    sha={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file()}
    (root/'sha256.json').write_text(json.dumps(sha,indent=2)+'\n',encoding='utf8')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=Path('results/experiment08a/geometry_first'))
    args = parser.parse_args()
    for row in run(args.output_dir):
        print(json.dumps(row,sort_keys=True))

if __name__=='__main__':
    main()
