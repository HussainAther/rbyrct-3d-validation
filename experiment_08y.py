"""RBYRCT-08Y: retrospective voxel-wise geometry and information-surrogate audit.

Read-only analysis of 08U/08W/08X. No phantom, measured detector values,
reconstruction volumes, defect masks, re-selection, or fresh MART runs are used.
The precision proxy is diagonal linear-Gaussian geometry, NOT a MART posterior.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import sparse

SIZE = 12
ANGLES = 4
TILTS = 3
BUDGET = 288
CHECKPOINTS = (144, 288)
STUDIES = {
    '08U': (('coverage', 'information_diag', 'information_full'), 36, 3),
    '08W': (('coverage', 'information_diag', 'information_full', 'full_detector_diverse'), 64, 4),
    '08X': (('coverage', 'information_diag', 'information_full', 'full_detector_diverse', 'detector_only'), 80, 4),
}
# Use the frozen Gaussian surrogate hyperparameters, not new tuned values.
# The command-line runner imports them from the existing 08U module.


def load_csv(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as handle:
        return list(csv.DictReader(handle))


def write_csv(path, records):
    if not records:
        raise ValueError('empty table')
    with Path(path).open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def sha_order(values):
    return hashlib.sha256(np.asarray(values, dtype='<i8').tobytes()).hexdigest()


def verified_manifest(root):
    data = json.loads((root / 'sha256.json').read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not data:
        raise ValueError('empty or malformed source SHA-256 manifest')
    for name, digest in data.items():
        if not name or Path(name).name != name:
            raise ValueError(f'unsafe SHA-256 manifest entry: {name}')
        target = root / name
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError(f'archive file hash mismatch: {name}')
    return len(data)


def load_orders(root, policies, number_of_rays):
    records = load_csv(root/'acquisition_orders.csv')
    by_policy = {}
    for r in records:
        by_policy.setdefault(r['policy'], []).append(r)
    if set(by_policy) != set(policies):
        raise ValueError('missing or unexpected policies')
    orders = {}
    for policy in policies:
        rows = sorted(by_policy[policy], key=lambda x: int(x['acquired_index']))
        if [int(r['acquired_index']) for r in rows] != list(range(1, BUDGET + 1)):
            raise ValueError(f'noncontiguous acquisition indices for {policy}')
        ids = np.asarray([int(r['ray_id']) for r in rows], dtype=np.int64)
        if len(np.unique(ids)) != BUDGET or (ids < 0).any() or (ids >= number_of_rays).any():
            raise ValueError(f'invalid ray order for {policy}')
        hashes = {r['order_sha256'] for r in rows}
        if len(hashes) != 1 or sha_order(ids) not in hashes:
            raise ValueError(f'full acquisition fingerprint mismatch for {policy}')
        orders[policy] = ids
    return orders


def validate_reconstruction_records(root, orders, policies, nrecords, nobjects):
    records = load_csv(root/'prefix_reconstructions.csv')
    if len(records) != nrecords:
        raise ValueError('incorrect number of archived reconstruction rows')
    seen = set()
    objects = set()
    models = set()
    for r in records:
        policy = r['policy']
        prefix = int(r['acquired'])
        model = r['model']
        obj = r['object_id']
        key = (obj, model, policy, prefix)
        if key in seen or policy not in policies or prefix not in CHECKPOINTS:
            raise ValueError('duplicate or invalid reconstruction condition')
        seen.add(key)
        objects.add(obj)
        models.add(model)
        if sha_order(orders[policy][:prefix]) != r['order_sha256']:
            raise ValueError(f'reconstruction prefix fingerprint mismatch: {key}')
    if len(objects) != nobjects or models != {'same', 'independent'}:
        raise ValueError('unexpected number of objects or forward model conditions')
    expected = {(obj, model, p, k) for obj in objects for model in models for p in policies for k in CHECKPOINTS}
    if seen != expected:
        raise ValueError('incomplete reconstruction cross product')
    summary = load_csv(root/'aggregate_summary.csv')
    lookup = {}
    for row in summary:
        key = (row['policy'], int(row['acquired']))
        if key in lookup or key[0] not in policies or key[1] not in CHECKPOINTS or int(row['n_objects']) != nobjects:
            raise ValueError('invalid aggregate summary')
        lookup[key] = row
    if set(lookup) != {(p, k) for p in policies for k in CHECKPOINTS}:
        raise ValueError('incomplete aggregate summary')
    return lookup, len(records)


def gini(values):
    x = np.asarray(values, dtype=float).ravel()
    if not len(x) or not np.all(np.isfinite(x)) or np.any(x < 0):
        raise ValueError('invalid gini input')
    total = float(x.sum())
    if total <= 0:
        return 0.0
    x = np.sort(x)
    n = len(x)
    return float(2.0*np.dot(np.arange(1, n+1), x)/(n*total) - (n+1)/n)


def entropy(values):
    x = np.asarray(values, dtype=float).ravel()
    if not len(x) or np.any(x < 0) or not np.all(np.isfinite(x)):
        raise ValueError('invalid entropy input')
    if len(x) == 1:
        return 1.0
    total = float(x.sum())
    if total <= 0:
        return 0.0
    p = x[x > 0]/total
    return float(-np.dot(p, np.log(p))/np.log(len(x)))


def center_indices(size):
    """Prespecified central half-side cube (not object/defect mask)."""
    coords = np.indices((size, size, size)).reshape(3, -1)
    low = size//4
    high = size-low
    return np.all((coords >= low) & (coords < high), axis=0)


def surrogate_fields(A, rays, *, prior_variance, observation_variance):
    """Diagonal precision and sensitivity from row geometry ONLY.

    precision_j = prior_variance^-1 + observation_variance^-1 * sum_i A_ij^2
    variance_j = 1/precision_j
    Weighted path sensitivity = sum_i |A_ij| (nonnegative ray geometry here).
    This diagonal precision inverse is NOT diag of the full posterior covariance.
    """
    A = sparse.csr_matrix(A)
    ids = np.asarray(rays, dtype=np.int64)
    if ids.ndim != 1 or not len(ids) or len(np.unique(ids)) != len(ids) or np.any(ids < 0) or np.any(ids >= A.shape[0]):
        raise ValueError('invalid distinct ray IDs')
    if prior_variance <= 0 or observation_variance <= 0:
        raise ValueError('Gaussian hyperparameters must be positive')
    B = A[ids].tocsr()
    visits_matrix = B.copy()
    visits_matrix.data = np.ones_like(visits_matrix.data)
    visits = np.asarray(visits_matrix.sum(axis=0)).ravel().astype(np.float64)
    weighted_sensitivity = np.asarray(abs(B).sum(axis=0)).ravel()
    squared_sensitivity = np.asarray(B.multiply(B).sum(axis=0)).ravel()
    precision = 1.0/prior_variance + squared_sensitivity/observation_variance
    variance = 1.0/precision
    reduction = 1.0 - variance/prior_variance
    return {'visits':visits, 'weighted_sensitivity':weighted_sensitivity,
            'squared_sensitivity':squared_sensitivity, 'precision':precision,
            'variance':variance, 'relative_variance_reduction':reduction}


def metrics(A, rays, *, size=SIZE, prior_variance, observation_variance):
    if A.shape != (size*size*ANGLES*TILTS, size**3):
        raise ValueError('geometry dimensions do not match frozen 12^3 protocol')
    fields = surrogate_fields(A, rays, prior_variance=prior_variance, observation_variance=observation_variance)
    mask = center_indices(size)
    visits = fields['visits']
    weighted = fields['weighted_sensitivity']
    sq = fields['squared_sensitivity']
    variance = fields['variance']
    reduction = fields['relative_variance_reduction']
    return {
        'visited_voxel_fraction': float(np.mean(visits > 0)),
        'visitation_cv': float(visits.std()/visits.mean()) if visits.mean() else 0.,
        'visitation_gini': gini(visits),
        'weighted_sensitivity_mean': float(weighted.mean()),
        'weighted_sensitivity_cv': float(weighted.std()/weighted.mean()) if weighted.mean() else 0.,
        'weighted_sensitivity_gini':gini(weighted),
        'squared_sensitivity_mean':float(sq.mean()),
        'squared_sensitivity_gini':gini(sq),
        'diagonal_variance_mean':float(variance.mean()),
        'diagonal_variance_p90':float(np.quantile(variance, .90)),
        'diagonal_variance_max':float(variance.max()),
        'diagonal_precision_gini':gini(fields['precision']),
        'relative_variance_reduction_mean':float(reduction.mean()),
        'relative_variance_reduction_p10':float(np.quantile(reduction, .10)),
        'relative_variance_reduction_gini':gini(reduction),
        'central_cube_visited_fraction':float(np.mean(visits[mask]>0)),
        'outer_region_visited_fraction':float(np.mean(visits[~mask]>0)),
        'central_cube_weighted_sensitivity_mean':float(weighted[mask].mean()),
        'outer_region_weighted_sensitivity_mean':float(weighted[~mask].mean()),
        'central_cube_relative_variance_reduction_mean':float(reduction[mask].mean()),
        'outer_region_relative_variance_reduction_mean':float(reduction[~mask].mean()),
        'mean_row_nnz':float(A[np.asarray(rays,dtype=int)].getnnz(axis=1).mean()),
        'mean_row_squared_norm':float(A[np.asarray(rays,dtype=int)].multiply(A[np.asarray(rays,dtype=int)]).sum(axis=1).mean()),
    }


def perform(archives, output_dir, *, prior_variance, observation_variance):
    out = Path(output_dir)
    if out.exists():
        raise FileExistsError(f'refusing to overwrite: {out}')
    from experiment_04b import system_matrix
    from experiment_04g import TILTS as SOURCE_TILTS
    if len(SOURCE_TILTS) != TILTS:
        raise ValueError('tilt count differs from frozen protocol')
    A = system_matrix(SIZE, ANGLES, SOURCE_TILTS).tocsr()
    if A.shape != (SIZE*SIZE*ANGLES*TILTS, SIZE**3):
        raise ValueError('system matrix geometry mismatch')
    rows=[]
    comparisons=[]
    voxel_arrays={}
    filecounts={}
    checked_records={}
    for study in ('08U','08W','08X'):
        root=Path(archives[study])
        policies, nrecords, nobjects=STUDIES[study]
        status=json.loads((root/'run_status.json').read_text(encoding='utf-8'))
        if not status.get('complete') or int(status.get('completed_reconstructions', -1)) != nrecords:
            raise ValueError(f'incomplete {study} archive')
        filecounts[study] = verified_manifest(root)
        orders = load_orders(root, policies, A.shape[0])
        aggregate, checked_records[study] = validate_reconstruction_records(root, orders, policies, nrecords, nobjects)
        for prefix in CHECKPOINTS:
            for policy in policies:
                x=metrics(A, orders[policy][:prefix],size=SIZE,
                          prior_variance=prior_variance,observation_variance=observation_variance)
                raw=surrogate_fields(A,orders[policy][:prefix],prior_variance=prior_variance,observation_variance=observation_variance)
                for field in ('visits','weighted_sensitivity','squared_sensitivity','precision','variance','relative_variance_reduction'):
                    voxel_arrays[f'{study}__{policy}__{prefix}__{field}']=raw[field].reshape((SIZE,SIZE,SIZE)).astype(np.float64)
                agg=aggregate[(policy,prefix)]
                rows.append({'study':study,'policy':policy,'acquired':prefix,'n_objects':nobjects,
                             'mean_global_gain_vs_coverage':float(agg['mean_global_gain']),
                             'mean_defect_gain_vs_coverage':float(agg['mean_defect_gain']),
                             'object_global_wins':int(agg['object_global_wins']),
                             'object_defect_wins':int(agg['object_defect_wins']),
                             'prefix_sha256':sha_order(orders[policy][:prefix]), **x})
            diag=next(row for row in rows if row['study']==study and row['policy']=='information_diag' and row['acquired']==prefix)
            for reference_policy in [p for p in policies if p!='information_diag']:
                ref=next(row for row in rows if row['study']==study and row['policy']==reference_policy and row['acquired']==prefix)
                comparisons.append({
                    'study':study,'acquired':prefix,'comparison':'diagonal_minus_'+reference_policy,
                    'delta_global_gain':diag['mean_global_gain_vs_coverage']-ref['mean_global_gain_vs_coverage'],
                    'delta_defect_gain':diag['mean_defect_gain_vs_coverage']-ref['mean_defect_gain_vs_coverage'],
                    'delta_visited_fraction':diag['visited_voxel_fraction']-ref['visited_voxel_fraction'],
                    'delta_weighted_sensitivity_gini':diag['weighted_sensitivity_gini']-ref['weighted_sensitivity_gini'],
                    'delta_diagonal_variance_mean':diag['diagonal_variance_mean']-ref['diagonal_variance_mean'],
                    'delta_relative_variance_reduction_mean':diag['relative_variance_reduction_mean']-ref['relative_variance_reduction_mean'],
                    'delta_central_cube_variance_reduction':diag['central_cube_relative_variance_reduction_mean']-ref['central_cube_relative_variance_reduction_mean'],
                    'delta_outer_region_variance_reduction':diag['outer_region_relative_variance_reduction_mean']-ref['outer_region_relative_variance_reduction_mean'],
                })
    out.mkdir(parents=True)
    write_csv(out/'voxel_information_by_policy_checkpoint.csv',rows)
    write_csv(out/'diagonal_vs_alternatives.csv',comparisons)
    np.savez_compressed(out/'voxel_surrogate_fields.npz',**voxel_arrays)
    status={'complete':True,'scope':'retrospective, read-only geometry and diagonal-Gaussian surrogate',
            'studies':['08U','08W','08X'], 'checkpoints':list(CHECKPOINTS),
            'rows':len(rows), 'comparisons':len(comparisons), 'saved_voxel_fields':len(voxel_arrays),
            'archived_sha256_files_verified':filecounts,
            'archived_reconstruction_rows_checked':checked_records,
            'archived_files_modified':False,
            'prior_variance':prior_variance,'observation_variance':observation_variance,
            'definitions':{
                'weighted_sensitivity':'sum of absolute system-matrix ray coefficients across selected rows',
                'squared_sensitivity':'sum of squared ray coefficients across selected rows',
                'diagonal_precision':'prior_variance^-1 + squared_sensitivity / observation_variance',
                'diagonal_variance':'reciprocal of diagonal_precision (precision-diagonal surrogate, not true posterior diagonal)',
                'relative_variance_reduction':'1 - diagonal_variance / prior_variance',
                'central_cube':'central half-side cube, defined geometrically with no object or defect support',
                'comparison_deltas':'diagonal minus named alternative; archived RMSE gains repeated descriptively'},
            'limitations':[
                'No new ray selection, detector measurements, phantoms, or MART reconstruction.',
                'Precision-diagonal inversion is not the diagonal of the full Gaussian posterior, and is not a MART uncertainty measure.',
                'Same fixed ray history is used for every object within each archive; geometry rows are not independent samples.',
                'Different studies have different acquisition seeds and phantoms: do not pool object-level outcomes across archives.',
                'Descriptive geometry-outcome juxtaposition cannot establish a causal mechanism.',
                'No defect masks or ground-truth values enter the geometry metrics.'
            ]}
    (out/'run_status.json').write_text(json.dumps(status,indent=2)+'\n',encoding='utf-8')
    sha={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()}
    (out/'sha256.json').write_text(json.dumps(sha,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(status,indent=2))
    return status


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--08u-dir',required=True)
    parser.add_argument('--08w-dir',required=True)
    parser.add_argument('--08x-dir',required=True)
    parser.add_argument('--output-dir',required=True)
    args=parser.parse_args()
    from experiment_08u import PRIOR_VARIANCE, OBSERVATION_VARIANCE
    perform({'08U':args.__dict__['08u_dir'],'08W':args.__dict__['08w_dir'],
             '08X':args.__dict__['08x_dir']},args.output_dir,
            prior_variance=PRIOR_VARIANCE,observation_variance=OBSERVATION_VARIANCE)

if __name__=='__main__':
    main()
