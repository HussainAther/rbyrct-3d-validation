"""04S matched-prefix policy-switch pilot, extending 04R (synthetic 04P model).

Reads 04R selected_rays.csv. For each 896-ray shared prefix, continue both
feedback strengths (1 and 0), using EXACTLY the 04J scoring and candidate RNG.
No frozen experiment source files are modified. Truth is used offline only.

Example:
 python experiment_04s.py --source-dir results/experiment04r_pilot \
   --output-dir results/experiment04s_pilot
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np
import scipy

from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_04i import noisy_full_projection
from experiment_04j import adaptive_order, image_score, score_candidates, sirt_silent
from experiment_04m import high_resolution_matrix
from experiment_04p import object_pair


def save_rows(path, rows):
    if not rows:
        raise ValueError(f'No rows: {path}')
    with path.open('w', newline='', encoding='utf8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sha_order(ids):
    return hashlib.sha256(np.asarray(ids, dtype='<i8').tobytes()).hexdigest()


def read_reference(path, phantom, representation, seed, budget):
    orders = {'adaptive_feedback': [], 'feedback_off_control': []}
    with path.open(newline='', encoding='utf8') as f:
        for r in csv.DictReader(f):
            if (r['phantom'] == phantom and r['representation'] == representation
                    and int(r['seed']) == seed and int(r['budget']) == budget):
                if r['policy'] in orders:
                    orders[r['policy']].append((int(r['acquisition_position']), int(r['ray_index'])))
    out = {}
    for name, values in orders.items():
        values.sort()
        if [p for p, _ in values] != list(range(1, budget + 1)):
            raise ValueError(f'04R ray order missing positions: {representation} {name}')
        out[name] = np.asarray([i for _, i in values], dtype=np.int64)
    return out


def continue_after_prefix(A, observed, n, angles, prefix, seed, budget, strength, warm_rays, batch, candidate_pool, provisional_iterations):
    """04J-equivalent replay and continuation; candidate RNG advanced over prefix.

    A shared acquisition history is held fixed; RNG candidate draw calls are
    replayed by removing the already-selected rays after each historical draw.
    The source policy's replay is checked against its 04R trajectory downstream.
    """
    prefix = np.asarray(prefix, dtype=np.int64)
    if len(prefix) < warm_rays or (len(prefix)-warm_rays) % batch:
        raise ValueError('Switch prefix must end at a full 04J batch boundary')
    if len(set(map(int, prefix))) != len(prefix):
        raise ValueError('Duplicate rays in prefix')
    remaining = np.ones(A.shape[0], dtype=bool)
    remaining[prefix[:warm_rays]] = False
    rng = np.random.default_rng(seed + 317)

    # Replay random candidate draws for the historical prefix WITHOUT altering it.
    # The candidate pool is sampled before the selected ray is committed in 04J.
    for chosen in prefix[warm_rays:]:
        available = np.flatnonzero(remaining)
        candidates = rng.choice(available, size=min(candidate_pool, len(available)), replace=False)
        if int(chosen) not in candidates:
            raise AssertionError('Saved prefix is incompatible with 04J candidate RNG')
        remaining[int(chosen)] = False

    order = list(map(int, prefix))
    counts = np.asarray(A[order].sum(axis=0)).ravel().astype(float)
    viewcounts = np.bincount(np.asarray(order)//(n*n), minlength=angles*len(TILTS)).astype(int)

    while len(order) < budget:
        ids = np.asarray(order, dtype=np.int64)
        # Observations are indexed ONLY for previously acquired rays.
        x = sirt_silent(A[ids], observed[ids], provisional_iterations)
        features = image_score(x, n)
        count = min(batch, budget-len(order))
        for _ in range(count):
            available = np.flatnonzero(remaining)
            candidates = rng.choice(available, size=min(candidate_pool, len(available)), replace=False)
            scores = score_candidates(A, candidates, counts, viewcounts, n, features, feedback_strength=strength)
            high = np.max(scores)
            chosen = int(np.min(candidates[np.isclose(scores, high, rtol=1e-13, atol=1e-14)]))
            order.append(chosen)
            remaining[chosen] = False
            lo, hi = A.indptr[chosen], A.indptr[chosen+1]
            counts[A.indices[lo:hi]] += A.data[lo:hi]
            viewcounts[chosen//(n*n)] += 1
    return np.asarray(order, dtype=np.int64)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-dir', type=Path, default=Path('results/experiment04r_pilot'))
    p.add_argument('--output-dir', type=Path, default=Path('results/experiment04s_pilot'))
    p.add_argument('--phantom', default='defects', choices=['branches','layers','pores','defects'])
    p.add_argument('--size', type=int, default=16)
    p.add_argument('--angles', type=int, default=12)
    p.add_argument('--factor', type=int, default=2)
    p.add_argument('--offset', type=float, default=0.0)
    p.add_argument('--seed', type=int, default=271828)
    p.add_argument('--budget', type=int, default=2048)
    p.add_argument('--switch-at', type=int, default=896)
    p.add_argument('--warm-rays', type=int, default=128)
    p.add_argument('--batch', type=int, default=64)
    p.add_argument('--candidate-pool', type=int, default=64)
    p.add_argument('--provisional-iterations', type=int, default=60)
    p.add_argument('--sirt-iterations', type=int, default=400)
    a = p.parse_args()
    if a.output_dir.exists() and any(a.output_dir.iterdir()):
        p.error(f'Output directory is not empty: {a.output_dir}; use a fresh directory')
    if not (0 < a.warm_rays < a.switch_at < a.budget <= a.size*a.size*a.angles*len(TILTS)):
        p.error('Invalid warm/switch/budget arrangement')
    if (a.switch_at-a.warm_rays) % a.batch:
        p.error('--switch-at must be a 04J batch boundary: warm + multiple of batch')
    if min(a.size,a.angles,a.factor,a.batch,a.candidate_pool,a.provisional_iterations,a.sirt_iterations) <= 0 or a.factor < 2 or a.offset < 0:
        p.error('Invalid geometry or iteration settings')
    source = a.source_dir/'selected_rays.csv'
    if not source.is_file():
        p.error(f'Missing 04R selected-ray file: {source}')
    proto_path = a.source_dir/'protocol.json'
    if not proto_path.is_file():
        p.error(f'Missing 04R protocol: {proto_path}')
    source_proto = json.loads(proto_path.read_text(encoding='utf8'))['arguments']
    # Guard against silently matching 04R histories to a different geometry or protocol.
    for k in ('phantom','size','angles','factor','offset','seed','budget','warm_rays','batch','candidate_pool','provisional_iterations','sirt_iterations'):
        orig, new = source_proto[k], getattr(a,k)
        if k == 'offset':
            matches = float(orig) == float(new)
        elif isinstance(new,int):
            matches = int(orig) == new
        else:
            matches = str(orig) == str(new)
        if not matches:
            p.error(f'04R protocol mismatch for {k}: source={orig}, requested={new}')

    A = system_matrix(a.size, a.angles, TILTS).tocsr()
    M = high_resolution_matrix(a.size, a.angles, TILTS, a.factor, a.offset)
    warm = voxel_coverage_order(A, a.size, a.angles, len(TILTS), a.budget, a.seed, a.candidate_pool)
    checkpoints = sorted(set([a.switch_at, a.budget] + list(range(a.switch_at+256, a.budget, 256))))
    selection_rows, checkpoint_rows, compare_rows = [], [], []
    for representation in ('replicated', 'subvoxel'):
        truth, fine = object_pair(a.phantom, a.size, a.factor)[representation]
        clean = np.asarray(M@fine).ravel()
        noise_seed = (a.seed+int(hashlib.sha256(f'{a.phantom}:{0.:.12g}'.encode()).hexdigest()[:8], 16))%(2**32)
        obs = noisy_full_projection(clean, 0., noise_seed)
        references = read_reference(source, a.phantom, representation, a.seed, a.budget)
        for name, reference in references.items():
            if len(set(map(int, reference))) != a.budget or np.any(reference<0) or np.any(reference>=A.shape[0]):
                raise AssertionError(f'Invalid 04R reference: {representation}/{name}')
            if not np.array_equal(reference[:a.warm_rays], warm[:a.warm_rays]):
                raise AssertionError(f'Warm rays disagree: {representation}/{name}')
            strength = 1. if name == 'adaptive_feedback' else 0.
            # Independent frozen-selector reproducibility test on this Mac.
            fresh, _, _ = adaptive_order(A, obs, a.size, a.angles, warm, a.budget,
                                          a.seed, a.warm_rays, a.batch,
                                          a.provisional_iterations, a.candidate_pool, strength)
            if not np.array_equal(fresh, reference):
                raise AssertionError(f'Frozen 04J does not reproduce saved 04R reference: {representation}/{name}')

        arms = {}
        for source_name, source_label in (('adaptive_feedback','adaptive_prefix'),('feedback_off_control','off_prefix')):
            prefix = references[source_name][:a.switch_at]
            for continuation_label, strength in (('adaptive',1.),('off',0.)):
                arm = source_label+'__'+continuation_label
                order = continue_after_prefix(A, obs, a.size, a.angles, prefix, a.seed,
                                              a.budget, strength, a.warm_rays, a.batch,
                                              a.candidate_pool, a.provisional_iterations)
                assert np.array_equal(order[:a.switch_at], prefix)
                if len(set(map(int,order)))!=a.budget:
                    raise AssertionError(f'Duplicate selection: {arm}')
                if ((source_name=='adaptive_feedback' and continuation_label=='adaptive') or
                    (source_name=='feedback_off_control' and continuation_label=='off')):
                    if not np.array_equal(order, references[source_name]):
                        raise AssertionError(f'Identical-policy replay failed: {representation}/{arm}; RNG/state mismatch')
                arms[arm]=order
                for pos, ray in enumerate(order):
                    selection_rows.append(dict(representation=representation,arm=arm,
                                               source_prefix=source_label,continuation=continuation_label,
                                               acquisition_position=pos+1,ray_index=int(ray),
                                               after_switch=int(pos>=a.switch_at),
                                               view_index=int(ray)//(a.size*a.size)))
                for k in checkpoints:
                    ids=order[:k]
                    x=sirt_silent(A[ids],obs[ids],a.sirt_iterations)
                    rmse=float(np.sqrt(np.mean((np.asarray(x).ravel()-np.asarray(truth).ravel())**2)))
                    checkpoint_rows.append(dict(representation=representation,arm=arm,
                                                source_prefix=source_label,continuation=continuation_label,
                                                acquired=k,rmse=rmse,prefix_sha256=sha_order(ids)))
                    print(f'{representation:10s} {arm:27s} rays={k:4d} RMSE={rmse:.6f}', flush=True)

        for source_label in ('adaptive_prefix','off_prefix'):
            adaptive_arm=source_label+'__adaptive'
            off_arm=source_label+'__off'
            for k in checkpoints:
                ra=next(r['rmse'] for r in checkpoint_rows if r['representation']==representation and r['arm']==adaptive_arm and r['acquired']==k)
                ro=next(r['rmse'] for r in checkpoint_rows if r['representation']==representation and r['arm']==off_arm and r['acquired']==k)
                ia,io=arms[adaptive_arm][:k],arms[off_arm][:k]
                overlap=len(set(map(int,ia))&set(map(int,io)))
                compare_rows.append(dict(representation=representation,source_prefix=source_label,
                                         acquired=k,rmse_adaptive=ra,rmse_off=ro,
                                         relative_gain_adaptive=(ro-ra)/max(ro,1e-12),
                                         common_rays=overlap,set_divergence=1-overlap/k))
            end=[r for r in compare_rows if r['representation']==representation and r['source_prefix']==source_label and r['acquired']==a.budget][0]
            print(f'ENDPOINT {representation}, {source_label}: continuation-adaptive relative gain {end["relative_gain_adaptive"]*100:+.3f}%')

    a.output_dir.mkdir(parents=True,exist_ok=True)
    save_rows(a.output_dir/'selected_rays_04s.csv',selection_rows)
    save_rows(a.output_dir/'reconstruction_checkpoints_04s.csv',checkpoint_rows)
    save_rows(a.output_dir/'matched_prefix_comparisons.csv',compare_rows)
    protocol = dict(experiment='04S matched-prefix policy-switch pilot',
        hypothesis='For a common acquired history, the feedback strength used after the switch changes later selections and endpoint RMSE.',
        arguments={k:(str(v) if isinstance(v,Path) else v) for k,v in vars(a).items()},
        checkpoints=checkpoints,source_protocol=source_proto,
        same_policy_replay_verified=True,
        rng_rule='Replay 04J random candidate draws against the recorded acquired prefix, then continue with preserved RNG stream; no future measurements used to choose rays.',
        inference='Within-simulation controlled continuation-policy contrast; exploratory single seed/family; not population-level or clinical causality.',
        offline_ground_truth='Only reconstruction RMSE evaluation after selection, never online selector.',
        python=sys.version,platform=platform.platform(),numpy=np.__version__,scipy=scipy.__version__)
    (a.output_dir/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf8')
    print(f'04S complete: {a.output_dir}')

if __name__=='__main__':
    main()
