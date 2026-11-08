"""RBYRCT-08D: READ-ONLY acquisition-path and defect-intersection diagnostic.

Never uses evaluation masks for acquisition. Does not rerun MART or select rays.
Input: COMPLETE 08C archived results; outputs are written to a separate folder.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

POLICIES = ('coverage', 'gradient', 'incremental_25')
METRICS = ('global_rmse', 'defect_region_rmse', 'nondefect_rmse')


def read_csv(path):
    with path.open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows):
    if not rows:
        raise ValueError('cannot write empty result table')
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sha_ids(ids):
    return hashlib.sha256(np.asarray(ids, dtype='<i8').tobytes()).hexdigest()


def verify_archive(root):
    status = json.loads((root / 'run_status.json').read_text(encoding='utf-8'))
    if status.get('complete') is not True:
        raise ValueError('08C experiment is not marked complete')
    manifest = json.loads((root / 'sha256.json').read_text(encoding='utf-8'))
    if not manifest:
        raise ValueError('empty 08C hash manifest')
    for name, expected in manifest.items():
        if Path(name).name != name:
            raise ValueError('unsafe filename in manifest')
        data = (root / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f'08C hash mismatch: {name}')
    return status, len(manifest)


def geometry_for(n, object_seed, *, factor):
    # Delayed imports keep pure numerical diagnostics independently testable.
    from experiment_04b import system_matrix
    from experiment_04g import TILTS
    from experiment_07c_preflight import defect_support
    A = system_matrix(n, 4, TILTS).tocsr()
    mask, info = defect_support(n, factor, object_seed)
    return A, np.asarray(mask, dtype=bool).ravel(), info


def path_statistics(A, ids, mask):
    """Diagnostics for a fixed acquisition prefix; mask is evaluation-only."""
    ids = np.asarray(ids, dtype=np.int64)
    if ids.ndim != 1 or len(ids) == 0 or len(np.unique(ids)) != len(ids):
        raise ValueError('empty or duplicate ray prefix')
    if ids.min() < 0 or ids.max() >= A.shape[0]:
        raise ValueError('ray index outside geometry')
    if len(mask) != A.shape[1] or not np.any(mask) or np.all(mask):
        raise ValueError('invalid defect support')
    sub = A[ids]
    # Ray lengths passing through evaluation-defined defect voxels.
    defect_lengths = np.asarray(sub @ mask.astype(float)).ravel()
    all_lengths = np.asarray(sub.sum(axis=1)).ravel()
    if (all_lengths <= 0).any():
        raise ValueError('empty ray in saved order')
    hits = defect_lengths > 1e-12
    coverage = np.asarray(sub.sum(axis=0)).ravel()
    mean = float(np.mean(coverage))
    local = coverage[mask]
    return dict(
        n_rays=int(len(ids)),
        defect_hit_fraction=float(np.mean(hits)),
        defect_hit_count=int(np.sum(hits)),
        defect_path_length=float(np.sum(defect_lengths)),
        defect_path_fraction=float(np.sum(defect_lengths) / np.sum(all_lengths)),
        spatial_coverage_cv=float(np.std(coverage) / max(mean, 1e-15)),
        spatial_coverage_variance=float(np.var(coverage)),
        defect_voxel_coverage_fraction=float(np.mean(local > 1e-12)),
        mean_defect_coverage=float(np.mean(local)),
        mean_nondefect_coverage=float(np.mean(coverage[~mask])),
    )


def check_orders(orders, recon_rows, protocol, n_rays_by_size):
    # Acquisition-index continuity and uniqueness are crucial: an apparent
    # intersection deficit might otherwise be a truncated or malformed order.
    indexed = defaultdict(list)
    for row in orders:
        key = (int(row['size']), row['object_id'], row['model'], row['policy'])
        indexed[key].append((int(row['acquired_index']), int(row['ray_id'])))
    finished = {}
    for key, pairs in indexed.items():
        pairs.sort()
        idx = [i for i, _ in pairs]
        ids = [r for _, r in pairs]
        budget = int(protocol['configs'][str(key[0])]['budget'])
        if idx != list(range(1, budget + 1)) or len(set(ids)) != budget:
            raise ValueError(f'noncontinuous or duplicate order: {key}')
        if min(ids) < 0 or max(ids) >= n_rays_by_size[key[0]]:
            raise ValueError(f'ray ID outside system matrix: {key}')
        finished[key] = np.asarray(ids, dtype=np.int64)
    if len(finished) != len(recon_rows) // 2:
        # More generally, a dataset may have different checkpoint counts.
        checkpoints = {int(n): len(c['checkpoints']) for n, c in protocol['configs'].items()}
        if sum(checkpoints[k[0]] for k in finished) != len(recon_rows):
            raise ValueError('inconsistent acquisition/reconstruction row counts')
    seen = set()
    for row in recon_rows:
        key = (int(row['size']), row['object_id'], row['model'], row['policy'])
        k = int(row['acquired'])
        if (key, k) in seen or key not in finished:
            raise ValueError('duplicate or missing reconstruction record')
        seen.add((key, k))
        if k not in protocol['configs'][str(key[0])]['checkpoints']:
            raise ValueError('unexpected checkpoint')
        if sha_ids(finished[key][:k]) != row['order_sha256']:
            raise ValueError(f'08C checkpoint ray fingerprint mismatch: {key}, {k}')
    if sum(len(protocol['configs'][str(k[0])]['checkpoints']) for k in finished) != len(seen):
        raise ValueError('missing checkpoint reconstruction')
    return finished


def summarize_pairs(path_rows):
    """Paired within object/model/checkpoint; descriptive correlations only."""
    grouped = defaultdict(dict)
    for r in path_rows:
        key = (r['size'], r['object_id'], r['model'], r['acquired'])
        grouped[key][r['policy']] = r
    pairs = []
    for (n, obj, model, k), variants in sorted(grouped.items()):
        if set(variants) != set(POLICIES):
            raise ValueError('missing policy in paired diagnostic')
        baseline = variants['coverage']
        gradient = variants['gradient']
        for policy in ('gradient', 'incremental_25'):
            r = variants[policy]
            pair = dict(size=n, object_id=obj, model=model, acquired=k, policy=policy)
            for metric in ('defect_hit_fraction', 'defect_path_fraction', 'spatial_coverage_cv',
                           'defect_voxel_coverage_fraction', 'mean_defect_coverage'):
                pair['delta_' + metric] = r[metric] - baseline[metric]
            pair['gain_global_vs_coverage'] = r['gain_vs_coverage']
            pair['gain_defect_vs_coverage'] = r['defect_gain_vs_coverage']
            pair['gain_defect_vs_gradient'] = (gradient['defect_region_rmse'] - r['defect_region_rmse']) / max(gradient['defect_region_rmse'], 1e-12)
            pairs.append(pair)
    return pairs


def descriptive_correlations(pairs):
    """Object-balanced aggregation before correlations; no inferential p-values."""
    buckets = defaultdict(list)
    for r in pairs:
        buckets[(r['size'], r['acquired'], r['policy'], r['object_id'])].append(r)
    object_means = []
    for (n, k, pol, obj), rows in sorted(buckets.items()):
        object_means.append(dict(size=n, acquired=k, policy=pol, object_id=obj,
            delta_defect_hit_fraction=float(np.mean([r['delta_defect_hit_fraction'] for r in rows])),
            delta_defect_path_fraction=float(np.mean([r['delta_defect_path_fraction'] for r in rows])),
            delta_spatial_coverage_cv=float(np.mean([r['delta_spatial_coverage_cv'] for r in rows])),
            mean_defect_gain=float(np.mean([r['gain_defect_vs_coverage'] for r in rows]))))
    sets = defaultdict(list)
    for row in object_means:
        sets[(row['size'], row['acquired'], row['policy'])].append(row)
    summaries = []
    for (n,k,pol), rows in sorted(sets.items()):
        entry = dict(size=n,acquired=k,policy=pol,n_objects=len(rows),
            mean_delta_defect_hit_fraction=float(np.mean([r['delta_defect_hit_fraction'] for r in rows])),
            mean_delta_defect_path_fraction=float(np.mean([r['delta_defect_path_fraction'] for r in rows])),
            mean_delta_spatial_coverage_cv=float(np.mean([r['delta_spatial_coverage_cv'] for r in rows])),
            mean_defect_gain=float(np.mean([r['mean_defect_gain'] for r in rows])))
        for feature in ('delta_defect_hit_fraction','delta_defect_path_fraction','delta_spatial_coverage_cv'):
            x = [r[feature] for r in rows]
            y = [r['mean_defect_gain'] for r in rows]
            if len(rows) >= 3 and np.std(x) > 1e-12 and np.std(y) > 1e-12:
                rho = float(spearmanr(x,y).statistic)
            else:
                rho = float('nan')
            entry['descriptive_spearman_' + feature] = rho
        summaries.append(entry)
    return object_means, summaries


def run(results_dir, output_dir):
    root = Path(results_dir).resolve()
    dest = Path(output_dir).resolve()
    if root == dest or root in dest.parents or dest in root.parents:
        raise ValueError('08D report must be outside the source tree')
    if dest.exists() and any(dest.iterdir()):
        raise FileExistsError('refusing to overwrite an existing audit')
    status, n_hashes = verify_archive(root)
    protocol = json.loads((root/'protocol.json').read_text(encoding='utf-8'))
    if protocol.get('stage', '').split(' ')[0] != '08C':
        raise ValueError('not an 08C data set')
    rows = read_csv(root/'prefix_reconstructions.csv')
    orders = read_csv(root/'acquisition_orders.csv')
    objects = read_csv(root/'object_manifest.csv')
    if len(rows) != status['completed_reconstructions']:
        raise ValueError('08C status/reconstruction count mismatch')
    sizes = [int(s) for s in protocol['sizes']]
    matrices = {}
    masks = {}
    meta = {}
    for n in sizes:
        for obj in objects:
            if int(obj['size']) != n:
                continue
            oid = obj['object_id']
            A, mask, info = geometry_for(n, int(obj['object_seed']), factor=int(protocol['factor']))
            if info['mask_sha256'] != obj['mask_sha256'] or int(info['mask_voxels']) != int(obj['mask_voxels']):
                raise ValueError(f'defect mask mismatch for {oid}')
            if n in matrices and matrices[n].shape != A.shape:
                raise ValueError('inconsistent geometry')
            matrices[n] = A
            if (n, oid) in masks:
                raise ValueError('duplicate object manifest entry')
            masks[(n, oid)] = mask
            meta[(n, oid)] = info
    for n in sizes:
        if n not in matrices:
            raise ValueError(f'missing object/geometry for size {n}')
    indexed = check_orders(orders, rows, protocol, {n:A.shape[0] for n,A in matrices.items()})
    dest.mkdir(parents=True, exist_ok=True)
    path_rows=[]
    for row in rows:
        n=int(row['size']); oid=row['object_id']; k=int(row['acquired'])
        key=(n,oid,row['model'],row['policy'])
        mask=masks[(n,oid)]
        ids=indexed[key][:k]
        s=path_statistics(matrices[n], ids, mask)
        cov=indexed[(n,oid,row['model'],'coverage')][:k]
        grad=indexed[(n,oid,row['model'],'gradient')][:k]
        s.update(size=n,object_id=oid,model=row['model'],policy=row['policy'],acquired=k,
                 overlap_with_coverage=int(len(set(ids)&set(cov))),
                 jaccard_with_coverage=float(len(set(ids)&set(cov))/len(set(ids)|set(cov))),
                 overlap_with_gradient=int(len(set(ids)&set(grad))),
                 jaccard_with_gradient=float(len(set(ids)&set(grad))/len(set(ids)|set(grad))),
                 global_rmse=float(row['global_rmse']),defect_region_rmse=float(row['defect_region_rmse']),
                 gain_vs_coverage=float(row['gain_vs_coverage']),
                 defect_gain_vs_coverage=float(row['defect_gain_vs_coverage']))
        if int(row['shared_with_coverage'])!=s['overlap_with_coverage']:
            raise ValueError('saved shared_with_coverage does not match raw ray IDs')
        path_rows.append(s)
    pairs=summarize_pairs(path_rows)
    object_means, summaries=descriptive_correlations(pairs)
    write_csv(dest/'path_metrics.csv', path_rows)
    write_csv(dest/'paired_differences.csv', pairs)
    write_csv(dest/'object_level_differences.csv', object_means)
    write_csv(dest/'descriptive_summary.csv', summaries)
    report=dict(verdict='PASS',scope='read-only post-hoc path diagnostics on exploratory 08C',
        original_data_unchanged=True,archive_hashes_verified=n_hashes,
        acquired_orders_verified=len(indexed),checkpoint_rows_verified=len(rows),
        mask_regenerations_verified=len(masks),
        limitations=['No causal attribution; sampled rays and errors respond to the same acquisition policy',
          'Evaluation-only defect masks were regenerated after acquisition, not supplied to the selector',
          'Only object is a replication unit; correlations are descriptive and p-values intentionally omitted',
          'Ray intersection is geometric, not a simulated detector signal or clinical detection criterion',
          'No MART reconstruction was repeated and no acquisition history was changed'])
    (dest/'audit_report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    print('\n--- object-balanced path contrasts ---')
    for s in summaries:
        print(f"{s['size']}^3 {s['acquired']:4} {s['policy']:15} "
              f"delta_hit={s['mean_delta_defect_hit_fraction']:+.4f} "
              f"delta_defect_path={s['mean_delta_defect_path_fraction']:+.4f} "
              f"defect_gain={100*s['mean_defect_gain']:+.2f}%")
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results-dir',type=Path,default=Path('../rbyrct-results/experiment08c/exploratory_first'))
    p.add_argument('--output-dir',type=Path,default=Path('../rbyrct-results/experiment08d/path_diagnostic_first'))
    args=p.parse_args()
    run(args.results_dir,args.output_dir)

if __name__=='__main__':
    main()
