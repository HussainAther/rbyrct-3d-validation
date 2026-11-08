"""RBYRCT-08V: read-only geometric acquisition-pattern diagnostics of 08U.

No new ray selections, phantoms, measurements, or reconstructions. The archived
08U ray orders are treated as fixed observations; the geometric analysis is
retrospective, exploratory and does not establish why an ordering helped MART.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy import sparse

POLICIES = ('coverage', 'information_diag', 'information_full')
CHECKPOINTS = (144, 288)
SIZE = 12
ANGLES = 4
TILTS = 3
EXPECTED_BUDGET = 288


def sha_order(order):
    return hashlib.sha256(np.asarray(order, dtype='<i8').tobytes()).hexdigest()


def load_csv(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    if not rows:
        raise ValueError('cannot write empty table')
    with Path(path).open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def normalized_entropy(counts):
    a = np.asarray(counts, dtype=float).ravel()
    if a.size <= 1:
        return 1.0
    total = float(a.sum())
    if total <= 0:
        return 0.0
    probabilities = a[a > 0] / total
    return float(-np.sum(probabilities * np.log(probabilities)) / np.log(a.size))


def gini(values):
    x = np.asarray(values, dtype=float).ravel()
    if len(x) == 0 or np.any(x < 0) or np.any(~np.isfinite(x)):
        raise ValueError('invalid gini sample')
    total = float(x.sum())
    if total == 0:
        return 0.0
    x = np.sort(x)
    n = len(x)
    return float((2 * np.dot(np.arange(1, n+1, dtype=float), x)) / (n * total) - (n + 1) / n)


def ray_order_from_csv(path, expected_policies=POLICIES, budget=EXPECTED_BUDGET, nrays=None):
    """Strictly validate one-based acquired_index and complete unambiguous orders."""
    rows = load_csv(path)
    orders = {}
    for r in rows:
        policy = r['policy']
        if policy not in expected_policies:
            raise ValueError(f'unexpected policy {policy}')
        orders.setdefault(policy, []).append(r)
    if set(orders) != set(expected_policies):
        raise ValueError('missing policy history')
    result = {}
    for policy, data in orders.items():
        data = sorted(data, key=lambda r: int(r['acquired_index']))
        indices = [int(r['acquired_index']) for r in data]
        if indices != list(range(1, budget + 1)):
            raise ValueError(f'noncontiguous or duplicate acquisition indices: {policy}')
        rays = np.array([int(r['ray_id']) for r in data], dtype=np.int64)
        if len(set(map(int, rays))) != budget:
            raise ValueError(f'duplicate ray IDs: {policy}')
        if np.any(rays < 0) or (nrays is not None and np.any(rays >= nrays)):
            raise ValueError(f'out of range ray IDs: {policy}')
        hashes = {r.get('order_sha256', '') for r in data}
        if len(hashes) != 1 or sha_order(rays) != next(iter(hashes)):
            raise ValueError(f'ray history fingerprint mismatch: {policy}')
        result[policy] = rays
    return result


def validate_archive_hashes(archive):
    manifest = archive / 'sha256.json'
    if not manifest.is_file():
        raise FileNotFoundError('08U sha256.json not found; cannot verify archive')
    digests = json.loads(manifest.read_text(encoding='utf-8'))
    if not isinstance(digests, dict) or not digests:
        raise ValueError('invalid SHA-256 manifest')
    for name, expected in digests.items():
        if Path(name).name != name:
            raise ValueError('unsafe manifest path')
        path = archive / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f'archive hash mismatch: {name}')
    return len(digests)


def sampled_pair_cosine(A, rays, *, max_pairs=512, seed=23081):
    """Mean positive cosine of sampled distinct ray-path pairs (not detector view diversity)."""
    rays = np.asarray(rays, dtype=int)
    if len(rays) < 2:
        return 0.0
    B = A[rays].tocsr()
    norms = np.sqrt(np.asarray(B.multiply(B).sum(axis=1)).ravel())
    rng = np.random.default_rng(seed)
    sample_size = min(int(max_pairs), len(rays) * (len(rays) - 1) // 2)
    if sample_size == len(rays) * (len(rays) - 1) // 2:
        left, right = np.triu_indices(len(rays), k=1)
    else:
        left = rng.integers(0, len(rays), size=sample_size)
        right = rng.integers(0, len(rays)-1, size=sample_size)
        right += right >= left
    cosines = []
    for i, j in zip(left, right):
        dot = float(B[int(i)].multiply(B[int(j)]).sum())
        den = float(norms[i] * norms[j])
        cosines.append(dot / den if den else 0.)
    return float(np.mean(cosines))


def geometry_metrics(A, rays, *, size=SIZE, angles=ANGLES, ntilts=TILTS, max_pairs=512):
    """Compute geometry alone, with no phantom truth and no evaluation masks."""
    A = A.tocsr()
    rays = np.asarray(rays, dtype=np.int64)
    if rays.ndim != 1 or not len(rays) or len(set(map(int, rays))) != len(rays):
        raise ValueError('ray order must be unique and nonempty')
    expected_rows = size*size*angles*ntilts
    if A.shape != (expected_rows, size**3) or np.any(rays < 0) or np.any(rays >= expected_rows):
        raise ValueError('geometry mismatch')
    B = A[rays].tocsr()
    nonzero = B.copy()
    nonzero.data[:] = 1.
    visits = np.asarray(nonzero.sum(axis=0)).ravel()
    lengths = np.asarray(B.sum(axis=0)).ravel()
    # Row order per experiment_04b.system_matrix: tilt, azimuth, detector row, col.
    view = rays // (size*size)
    detector = rays % (size*size)
    view_hist = np.bincount(view, minlength=angles*ntilts)
    detector_hist = np.bincount(detector, minlength=size*size)
    ray_lengths = np.asarray(B.sum(axis=1)).ravel()
    return dict(
        acquired=len(rays),
        visited_voxel_fraction=float(np.mean(visits>0)),
        voxel_visit_mean=float(visits.mean()),
        voxel_visit_cv=float(visits.std()/visits.mean()) if visits.mean() else 0.,
        voxel_visit_gini=gini(visits),
        voxel_visit_entropy=normalized_entropy(visits),
        cumulative_pathlength_cv=float(lengths.std()/lengths.mean()) if lengths.mean() else 0.,
        view_bins_visited=int(np.sum(view_hist>0)),
        view_entropy=normalized_entropy(view_hist),
        view_max_share=float(np.max(view_hist)/len(rays)),
        detector_bins_visited=int(np.sum(detector_hist>0)),
        detector_entropy=normalized_entropy(detector_hist),
        detector_max_share=float(np.max(detector_hist)/len(rays)),
        mean_ray_pathlength=float(ray_lengths.mean()),
        sampled_ray_cosine=sampled_pair_cosine(A, rays, max_pairs=max_pairs),
    )


def load_reconstruction_summary(path):
    rows = load_csv(path)
    lookup = {}
    for r in rows:
        key = (r['policy'], int(r['acquired']))
        if key in lookup:
            raise ValueError('duplicate aggregate record')
        lookup[key] = r
    if set(lookup) != {(p,k) for p in POLICIES for k in CHECKPOINTS}:
        raise ValueError('incomplete aggregate table')
    for r in lookup.values():
        if int(r['n_objects']) != 3:
            raise ValueError('08U expected three independent objects')
    return lookup


def check_prefix_hashes(rows, orders):
    """Check archived reconstruction rows refer to the same acquisition prefixes."""
    seen = set()
    complete = set()
    for r in rows:
        key = (r['policy'], int(r['acquired']))
        record = (r['object_id'], r['model'], key[0], key[1])
        if record in complete:
            raise ValueError('duplicate archived reconstruction condition')
        complete.add(record)
        if key[0] not in orders or key[1] not in CHECKPOINTS:
            raise ValueError('unrecognized reconstruction condition')
        if sha_order(orders[key[0]][:key[1]]) != r['order_sha256']:
            raise ValueError(f'08U reconstruction order fingerprint mismatch: {key}')
        seen.add(key)
    if seen != {(p,k) for p in POLICIES for k in CHECKPOINTS}:
        raise ValueError('missing reconstruction condition')
    if len(complete) != 36 or len({r[0] for r in complete}) != 3 or len({r[1] for r in complete}) != 2:
        raise ValueError('incomplete archived reconstruction conditions')


def run(results_dir, output_dir, *, max_pairs=512):
    archive = Path(results_dir)
    output = Path(output_dir)
    if output.exists():
        raise FileExistsError(f'refusing to overwrite existing output: {output}')
    status_path = archive/'run_status.json'
    if not status_path.exists():
        raise FileNotFoundError('08U run status missing')
    status = json.loads(status_path.read_text(encoding='utf-8'))
    if not status.get('complete') or status.get('completed_reconstructions') != 36:
        raise RuntimeError('08U reconstruction archive incomplete')
    hashes_verified = validate_archive_hashes(archive)
    from experiment_04b import system_matrix
    from experiment_04g import TILTS as SOURCE_TILTS
    if len(SOURCE_TILTS) != TILTS:
        raise ValueError('unexpected number of tilts')
    A = system_matrix(SIZE, ANGLES, SOURCE_TILTS).tocsr()
    orders = ray_order_from_csv(archive/'acquisition_orders.csv',nrays=A.shape[0])
    check_prefix_hashes(load_csv(archive/'prefix_reconstructions.csv'), orders)
    aggregate = load_reconstruction_summary(archive/'aggregate_summary.csv')
    geometric = []
    combined = []
    for k in CHECKPOINTS:
        for p in POLICIES:
            m = geometry_metrics(A, orders[p][:k], max_pairs=max_pairs)
            reference = orders['coverage'][:k]
            diag = orders['information_diag'][:k]
            m.update(policy=p,
                     shared_ray_fraction_with_coverage=float(len(set(orders[p][:k]) & set(reference))/k),
                     shared_ray_fraction_with_diagonal=float(len(set(orders[p][:k]) & set(diag))/k),
                     prefix_sha256=sha_order(orders[p][:k]))
            # Stable column order: put policy and budget at front.
            m = {'policy':m.pop('policy'), 'acquired':m.pop('acquired'), **m}
            geometric.append(m)
            r = aggregate[(p,k)]
            combined.append({**m,
                'n_objects':int(r['n_objects']),
                'mean_global_gain_vs_coverage':float(r['mean_global_gain']),
                'mean_defect_gain_vs_coverage':float(r['mean_defect_gain']),
                'object_global_wins':int(r['object_global_wins']),
                'object_defect_wins':int(r['object_defect_wins'])})
    output.mkdir(parents=True)
    write_csv(output/'geometry_by_policy_checkpoint.csv', geometric)
    write_csv(output/'geometry_with_exploratory_rmse.csv', combined)
    summaries = []
    for k in CHECKPOINTS:
        d = next(x for x in combined if x['acquired']==k and x['policy']=='information_diag')
        f = next(x for x in combined if x['acquired']==k and x['policy']=='information_full')
        summaries.append(dict(acquired=k,
            diagonal_minus_full_visited_voxel_fraction=d['visited_voxel_fraction']-f['visited_voxel_fraction'],
            diagonal_minus_full_voxel_visit_cv=d['voxel_visit_cv']-f['voxel_visit_cv'],
            diagonal_minus_full_voxel_visit_gini=d['voxel_visit_gini']-f['voxel_visit_gini'],
            diagonal_minus_full_view_entropy=d['view_entropy']-f['view_entropy'],
            diagonal_minus_full_detector_entropy=d['detector_entropy']-f['detector_entropy'],
            diagonal_minus_full_sampled_ray_cosine=d['sampled_ray_cosine']-f['sampled_ray_cosine'],
            diagonal_minus_full_mean_global_gain=d['mean_global_gain_vs_coverage']-f['mean_global_gain_vs_coverage'],
            diagonal_minus_full_mean_defect_gain=d['mean_defect_gain_vs_coverage']-f['mean_defect_gain_vs_coverage']))
    write_csv(output/'diagonal_minus_full_summary.csv', summaries)
    result = dict(complete=True,scope='retrospective 08U geometric path diagnostics',
        policies=list(POLICIES),checkpoints=list(CHECKPOINTS),geometric_rows=len(geometric),
        source_archive_files_sha256_verified=hashes_verified,
        source_archive_modified=False, archived_reconstructions_untouched=True,
        ray_histories_verified=len(orders), reconstruction_rows_checked=36,
        metric_definitions={
            'voxel_visits':'number of selected ray paths with positive sparse-matrix weight at each voxel',
            'voxel_visit_cv':'coefficient of variation over all voxels including zero-visited voxels; smaller is more uniform',
            'voxel_visit_gini':'inequality of voxel visit counts; smaller is more uniform',
            'view_entropy':'normalized entropy over tilt-by-azimuth view bins; larger is more balanced',
            'detector_entropy':'normalized entropy over detector row-column positions, pooling views',
            'sampled_ray_cosine':'mean cosine between up to 512 deterministically sampled distinct sparse ray vectors',
            'shared_ray_fraction':'prefix set intersection divided by prefix budget'},
        limitations=[
            'Descriptive only; three independent phantom objects in 08U and the same fixed ray order reused across them.',
            'Geometric descriptors are not independent statistical observations or dose estimates.',
            'No new MART runs, no new phantom truth, and no defect support used by the geometric calculations.',
            'Geometric association cannot establish that a metric caused the reconstruction differences.',
            'Sampled cosine is a fixed-seed Monte Carlo diagnostic, not all-pairs redundancy.',
            'Full-covariance Gaussian A-optimality is not MART optimality.'])
    (output/'run_status.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (output/'sha256.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(output.iterdir()) if p.is_file()}, indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results-dir',required=True,help='Archived 08U reconstruction_third directory')
    p.add_argument('--output-dir',required=True,help='New, separate diagnostic directory')
    p.add_argument('--sample-pairs',type=int,default=512)
    args=p.parse_args()
    if args.sample_pairs<1:
        p.error('--sample-pairs must be positive')
    run(args.results_dir,args.output_dir,max_pairs=args.sample_pairs)


if __name__=='__main__':
    main()
