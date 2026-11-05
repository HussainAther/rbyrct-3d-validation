"""08AB: independently replay archived 08Z MART voxel reconstructions.

Read-only archived ray histories, regenerated synthetic truth/observations using
repository generators, independent sequential MART and voxel RMSE arithmetic.
No imports from experiment_08z or experiment_05b_mart; no ray reselection.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import sparse

POLICIES = ('coverage', 'information_diag', 'information_full', 'full_spatial_balanced')
CHECKPOINTS = (144, 288)
OBJECT_SEEDS = (910201, 910202, 910203, 910204)
MODELS = ('same', 'independent')
SIZE, FACTOR, ANGLES, BUDGET = 12, 2, 4, 288
MANIFEST_FILES = ('protocol.json', 'environment.json', 'acquisition_orders.csv',
                  'prefix_reconstructions.csv', 'object_manifest.csv',
                  'object_level_summary.csv', 'aggregate_summary.csv',
                  'spatial_vs_full_object.csv', 'geometry_summary.csv', 'run_status.json')


def digest_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def order_digest(order):
    return hashlib.sha256(np.asarray(order, dtype='<i8').tobytes()).hexdigest()


def read_csv(path):
    with Path(path).open('r', encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows):
    if not rows:
        raise ValueError('cannot write empty CSV')
    with Path(path).open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def replay_mart(matrix, measured, epochs=16, relaxation=0.25, initial=0.3):
    """Independent CSR sequential multiplicative MART; preserve acquired row order."""
    a = sparse.csr_matrix(matrix, dtype=np.float64)
    b = np.asarray(measured, dtype=np.float64).reshape(-1)
    if a.shape[0] != len(b) or epochs < 1 or not 0 < relaxation <= 1 or initial <= 0:
        raise ValueError('invalid MART inputs')
    if not np.isfinite(a.data).all() or np.any(a.data < 0) or not np.isfinite(b).all() or np.any(b < 0):
        raise ValueError('MART requires finite nonnegative data')
    x = np.full(a.shape[1], float(initial), dtype=np.float64)
    floor = 1e-10
    for _ in range(epochs):
        for row in range(a.shape[0]):
            lo, hi = int(a.indptr[row]), int(a.indptr[row + 1])
            if lo == hi:
                continue
            loc = a.indices[lo:hi]
            weights = a.data[lo:hi]
            largest = float(weights.max())
            if largest <= 0:
                continue
            prediction = float(weights @ x[loc])
            ratio = max(float(b[row]), floor) / max(prediction, floor)
            exponent = np.clip((relaxation / largest) * weights * math.log(max(ratio, floor)), -12, 12)
            x[loc] = np.maximum(x[loc] * np.exp(exponent), floor)
    if not np.isfinite(x).all():
        raise FloatingPointError('nonfinite voxel replay')
    return x


def voxel_rmse(estimate, truth, defect_mask):
    x = np.asarray(estimate, dtype=np.float64).reshape(-1)
    y = np.asarray(truth, dtype=np.float64).reshape(-1)
    mask = np.asarray(defect_mask, dtype=bool).reshape(-1)
    if x.shape != y.shape or x.shape != mask.shape or not 0 < mask.sum() < len(mask):
        raise ValueError('invalid replay masks or shapes')
    sq = (x - y)**2
    return {'global_rmse': float(np.sqrt(sq.mean())),
            'defect_region_rmse': float(np.sqrt(sq[mask].mean())),
            'nondefect_rmse': float(np.sqrt(sq[~mask].mean()))}


def verify_archive(archive, preflight):
    archive, preflight = Path(archive), Path(preflight)
    saved_sha = json.loads((archive / 'sha256.json').read_text(encoding='utf-8'))
    if set(saved_sha) != set(MANIFEST_FILES):
        raise RuntimeError('unexpected or incomplete SHA-256 manifest')
    for name in MANIFEST_FILES:
        if digest_file(archive / name) != saved_sha[name]:
            raise RuntimeError('08Z archive SHA mismatch: ' + name)
    status = json.loads((archive / 'run_status.json').read_text(encoding='utf-8'))
    if status.get('complete') is not True or status.get('completed_reconstructions') != 64:
        raise RuntimeError('incomplete original reconstruction archive')
    protocol = json.loads((archive / 'protocol.json').read_text(encoding='utf-8'))
    mandatory = {'size': SIZE, 'object_seeds': list(OBJECT_SEEDS),
                 'models': list(MODELS), 'policies': list(POLICIES),
                 'budget': BUDGET, 'checkpoints': list(CHECKPOINTS),
                 'final_epochs': 16, 'relaxation': 0.25, 'noise_fraction': 0.005,
                 'spatial_novelty_weight': 0.25, 'geometry_only': True}
    for key, expected in mandatory.items():
        if protocol.get(key) != expected:
            raise RuntimeError('08Z protocol changed: ' + key)
    pf = json.loads((preflight / 'preflight.json').read_text(encoding='utf-8'))
    if not (pf.get('complete') is True and pf.get('alpha_zero_equals_full') is True
            and pf.get('intervention_deterministic') is True
            and pf.get('intervention_changes_order') is True
            and all(pf.get('spatial_gini_reduced_at_checkpoints', {}).get(str(k)) is True for k in CHECKPOINTS)):
        raise RuntimeError('unapproved 08Z engineering preflight')
    if pf.get('alpha') != 0.25 or pf.get('size') != SIZE or pf.get('budget') != BUDGET:
        raise RuntimeError('08Z preflight parameter mismatch')
    return protocol, pf


def load_orders(archive, preflight_hashes, num_rays):
    groups = defaultdict(list)
    for row in read_csv(Path(archive) / 'acquisition_orders.csv'):
        if row['policy'] not in POLICIES:
            raise RuntimeError('unexpected acquisition policy')
        groups[row['policy']].append(row)
    if set(groups) != set(POLICIES):
        raise RuntimeError('missing acquisition policies')
    result = {}
    for policy, rows in groups.items():
        if len(rows) != BUDGET:
            raise RuntimeError('incorrect acquisition length: ' + policy)
        ordered = sorted((int(r['acquired_index']), int(r['ray_id']), r['order_sha256']) for r in rows)
        if [r[0] for r in ordered] != list(range(1, BUDGET + 1)):
            raise RuntimeError('noncontiguous acquired indices')
        order = np.asarray([r[1] for r in ordered], dtype=np.int64)
        if len(set(map(int, order))) != BUDGET or order.min() < 0 or order.max() >= num_rays:
            raise RuntimeError('invalid ray IDs: ' + policy)
        hash_ = order_digest(order)
        if hash_ != preflight_hashes.get(policy) or any(r[2] != hash_ for r in ordered):
            raise RuntimeError('order/preflight SHA-256 mismatch: ' + policy)
        result[policy] = order
    return result


def load_stored(archive, orders):
    stored = {}
    for row in read_csv(Path(archive) / 'prefix_reconstructions.csv'):
        key = (row['object_id'], row['model'], row['policy'], int(row['acquired']))
        if key in stored:
            raise RuntimeError('duplicate archived reconstruction: ' + str(key))
        stored[key] = row
    expected = {(f'defect_dev_{s}', m, p, k) for s in OBJECT_SEEDS
                for m in MODELS for p in POLICIES for k in CHECKPOINTS}
    if set(stored) != expected:
        raise RuntimeError('missing/extra archived reconstruction records')
    for key, row in stored.items():
        if row['order_sha256'] != order_digest(orders[key[2]][:key[3]]):
            raise RuntimeError('reconstruction prefix hash mismatch: ' + str(key))
        if int(row['object_seed']) != int(key[0].split('_')[-1]):
            raise RuntimeError('stored reconstruction object seed mismatch')
    return stored


def compare_value(a, b, tolerance):
    return math.isclose(float(a), float(b), rel_tol=tolerance, abs_tol=tolerance)


def replay(archive_dir, preflight_dir, output_dir, source_dir='.', tolerance=2e-8, save_volumes=True):
    archive, preflight, out = Path(archive_dir), Path(preflight_dir), Path(output_dir)
    if not (np.isfinite(tolerance) and 0 < tolerance <= 1e-4):
        raise ValueError('invalid tolerance')
    if out.exists():
        raise FileExistsError('refusing to overwrite prior 08AB output')
    protocol, pf = verify_archive(archive, preflight)
    source = Path(source_dir)
    sys.path.insert(0, str(source.resolve()))
    # Only synthetic target generation, evaluation mask, and forward projection are reused.
    # The production MART kernel, archived RMSE, and acquisition selectors are NOT imported.
    from experiment_04b import system_matrix
    from experiment_04g import TILTS
    from experiment_04qa import project
    from experiment_06b import defect_phantom
    from experiment_07c_preflight import defect_support
    if int(protocol['acquisition_seed']) != 910411 + SIZE:
        raise RuntimeError('acquisition seed mismatch')
    a = system_matrix(SIZE, ANGLES, TILTS).tocsr()
    orders = load_orders(archive, pf['order_sha256'], a.shape[0])
    stored = load_stored(archive, orders)
    manifest_rows = read_csv(archive / 'object_manifest.csv')
    manifest = {r['object_id']: r for r in manifest_rows}
    if len(manifest_rows) != len(OBJECT_SEEDS) or set(manifest) != {f'defect_dev_{s}' for s in OBJECT_SEEDS}:
        raise RuntimeError('invalid archived phantom manifest')
    out.mkdir(parents=True)
    start = time.perf_counter()
    checked = []
    gain_checks = []
    volumes = []
    object_rows = []
    errors = []
    run_status = out / 'run_status.json'
    run_status.write_text(json.dumps({'complete': False, 'volumes_replayed': 0}, indent=2) + '\n', encoding='utf-8')
    try:
        for seed in OBJECT_SEEDS:
            oid = f'defect_dev_{seed}'
            truth, fine, description = defect_phantom(SIZE, FACTOR, seed)
            mask, info = defect_support(SIZE, FACTOR, seed)
            digest = hashlib.sha256(np.asarray(truth, dtype='<f8').tobytes()).hexdigest()
            if digest != manifest[oid]['truth_sha256'] or info['mask_sha256'] != manifest[oid]['mask_sha256']:
                raise RuntimeError('phantom truth or mask hash mismatch: ' + oid)
            if int(info['mask_voxels']) != int(manifest[oid]['mask_voxels']):
                raise RuntimeError('defect mask count mismatch: ' + oid)
            for mi, model in enumerate(MODELS):
                if model == 'same':
                    clean = np.asarray(a @ truth, dtype=np.float64).ravel()
                else:
                    clean = np.asarray(project(fine, SIZE, ANGLES, TILTS,
                                               factor=FACTOR, offset=0.15, step=0.25,
                                               mode='linear'), dtype=np.float64).ravel()
                # Independent implementation of the original Gaussian + nonnegative clipping rule.
                noise_sigma = 0.005 * float(np.sqrt(np.mean(clean**2)))
                noise_seed = (seed * 37 + mi * 100003 + 17011) % (2**32)
                measured = np.maximum(clean + np.random.default_rng(noise_seed).normal(
                    0.0, noise_sigma, clean.shape), 0.0)
                metrics = {}
                for policy in POLICIES:
                    for k in CHECKPOINTS:
                        order = orders[policy][:k]
                        reconstructed = replay_mart(a[order], measured[order],
                                                    epochs=16, relaxation=0.25)
                        actual = voxel_rmse(reconstructed, truth, mask)
                        metrics[(policy, k)] = actual
                        archived = stored[(oid, model, policy, k)]
                        for field, value in actual.items():
                            saved = float(archived[field])
                            delta = abs(value - saved)
                            passed = compare_value(value, saved, tolerance)
                            checked.append(dict(object_id=oid, model=model, policy=policy, acquired=k,
                                                metric=field, replayed=value, archived=saved,
                                                abs_difference=delta, pass_check=passed))
                            if not passed:
                                errors.append(f'{oid}/{model}/{policy}/{k}/{field} differs by {delta:.12g}')
                        if save_volumes:
                            filename = f'{oid}_{model}_{policy}_{k}.npy'
                            path = out / filename
                            np.save(path, reconstructed, allow_pickle=False)
                            volumes.append(dict(filename=filename, sha256=digest_file(path),
                                                object_id=oid, model=model, policy=policy,
                                                acquired=k, n_voxels=reconstructed.size))
                for k in CHECKPOINTS:
                    coverage = metrics[('coverage', k)]
                    for policy in POLICIES:
                        actual = metrics[(policy, k)]
                        original = stored[(oid, model, policy, k)]
                        for metric, field in (('global_rmse', 'gain_vs_coverage'),
                                              ('defect_region_rmse', 'defect_gain_vs_coverage'),
                                              ('nondefect_rmse', 'nondefect_gain_vs_coverage')):
                            gain = (coverage[metric] - actual[metric]) / max(coverage[metric], 1e-12)
                            archived_gain = float(original[field])
                            passed = compare_value(gain, archived_gain, tolerance)
                            gain_checks.append(dict(object_id=oid, model=model, policy=policy, acquired=k,
                                                    gain_type=field, replayed=gain, archived=archived_gain,
                                                    abs_difference=abs(gain-archived_gain), pass_check=passed))
                            if not passed:
                                errors.append(f'{oid}/{model}/{policy}/{k}/{field} gain mismatch')
                print(f'08AB {oid} model={model}: {len(POLICIES)*len(CHECKPOINTS)} voxel replays', flush=True)
        write_csv(out / 'voxel_rmse_comparison.csv', checked)
        write_csv(out / 'replayed_gain_comparison.csv', gain_checks)
        if volumes:
            write_csv(out / 'volume_manifest.csv', volumes)
        # Object-balanced verification against 08Z saved object/aggregate rows.
        by_metric = {(r['object_id'], r['model'], r['policy'], r['acquired'], r['gain_type']):r['replayed']
                     for r in gain_checks}
        original_object = {(r['object_id'], int(r['acquired']), r['policy']):r
                           for r in read_csv(archive / 'object_level_summary.csv')}
        for seed in OBJECT_SEEDS:
            oid = f'defect_dev_{seed}'
            for k in CHECKPOINTS:
                for p in POLICIES:
                    global_gain = float(np.mean([by_metric[(oid,m,p,k,'gain_vs_coverage')] for m in MODELS]))
                    defect_gain = float(np.mean([by_metric[(oid,m,p,k,'defect_gain_vs_coverage')] for m in MODELS]))
                    original = original_object[(oid,k,p)]
                    passed = (compare_value(global_gain, original['mean_global_gain'], tolerance)
                              and compare_value(defect_gain, original['mean_defect_gain'], tolerance))
                    object_rows.append(dict(object_id=oid, acquired=k, policy=p,
                                            mean_global_gain=global_gain, mean_defect_gain=defect_gain,
                                            object_summary_match=passed))
                    if not passed: errors.append(f'object-level gain mismatch: {oid}/{k}/{p}')
        write_csv(out / 'object_replayed.csv', object_rows)
        archived_aggregate = {(int(r['acquired']),r['policy']):r for r in read_csv(archive / 'aggregate_summary.csv')}
        aggregate=[]
        for k in CHECKPOINTS:
            for p in POLICIES:
                z=[r for r in object_rows if r['acquired']==k and r['policy']==p]
                g=float(np.mean([r['mean_global_gain'] for r in z]))
                d=float(np.mean([r['mean_defect_gain'] for r in z]))
                gw=sum(r['mean_global_gain']>0 for r in z)
                dw=sum(r['mean_defect_gain']>0 for r in z)
                original=archived_aggregate[(k,p)]
                passed=(compare_value(g,original['mean_global_gain'],tolerance)
                        and compare_value(d,original['mean_defect_gain'],tolerance)
                        and gw==int(original['object_global_wins'])
                        and dw==int(original['object_defect_wins']))
                aggregate.append(dict(acquired=k,policy=p,n_objects=4,
                                      mean_global_gain=g,mean_defect_gain=d,
                                      object_global_wins=gw,object_defect_wins=dw,aggregate_match=passed))
                if not passed:errors.append(f'aggregate mismatch at {k}/{p}')
        write_csv(out / 'aggregate_replayed.csv', aggregate)
        matches = len(checked)==64*3 and len(gain_checks)==64*3 and not errors
        max_diff = max(r['abs_difference'] for r in checked)
        report = dict(verdict='PASS' if matches else 'FAIL', complete=matches,
                      scope='all 64 archived 08Z reconstruction records',
                      independent_objects=4,models=2,policies=4,checkpoints=list(CHECKPOINTS),
                      volumes_replayed=len(checked)//3,voxel_rmse_comparisons=len(checked),
                      fractional_gain_comparisons=len(gain_checks),
                      max_absolute_rmse_difference=max_diff, tolerance=tolerance,
                      saved_volumes=len(volumes),source_archive_sha256_files_verified=len(MANIFEST_FILES),
                      preflight_ray_orders_verified=len(POLICIES),
                      source_archive_modified=False,
                      errors=errors,
                      elapsed_seconds=time.perf_counter()-start,
                      limitations=['Independent MART update and RMSE code, but phantom, projection geometry, '
                                   'and independent forward projector reuse repository implementations.',
                                   'The replay uses archived acquisition orders; no selector is rerun.',
                                   'The 08Z archive did not retain original voxel arrays; this verifies '
                                   'recomputed voxel RMSE against stored metrics, not original voxel equality.',
                                   'Four exploratory synthetic objects; same and independent models are paired conditions.',
                                   'Not external replication, proof of broad superiority, clinical dose evidence, '
                                   'or independent physical-model validation.'])
        (out/'replay_report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        run_status.write_text(json.dumps(dict(complete=matches,verdict=report['verdict'],
                                              volumes_replayed=len(checked)//3),indent=2)+'\n',encoding='utf-8')
        (out/'sha256.json').write_text(json.dumps({p.name:digest_file(p) for p in sorted(out.iterdir()) if p.is_file()},indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report,indent=2),flush=True)
        if not matches:
            raise RuntimeError('08AB reconstructed voxel RMSE mismatch; preserve output for investigation')
        return report
    except BaseException:
        run_status.write_text(json.dumps(dict(complete=False,volumes_replayed=len(checked)//3,
                                              message='interrupted or mismatched: preserve this output directory'),indent=2)+'\n',encoding='utf-8')
        raise


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results-dir',type=Path,required=True)
    ap.add_argument('--preflight-dir',type=Path,required=True)
    ap.add_argument('--source-dir',type=Path,default=Path('.'))
    ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--tolerance',type=float,default=2e-8)
    ap.add_argument('--no-volumes',action='store_true')
    args=ap.parse_args()
    replay(args.results_dir,args.preflight_dir,args.output_dir,args.source_dir,
           tolerance=args.tolerance,save_volumes=not args.no_volumes)


if __name__=='__main__':
    main()
