"""08AC: protocol-locked fresh 32^3 spatial-sensitivity intervention evaluation.

The 08Z full-covariance spatial penalty is unchanged (alpha=0.25).
This is a prospective synthetic study of new objects, not a clinical claim.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import importlib.util
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
from experiment_08u import select_full, order_sha256
from experiment_08z import select_full_spatial, sensitivity_gini

SIZE = 32
ANGLES = 4
FACTOR = 2
POLICIES = ('coverage', 'information_diag', 'information_full', 'full_spatial_balanced')
MODELS = ('same', 'independent')
OBJECT_SEEDS = (920201, 920202, 920203, 920204, 920205, 920206)
ACQUISITION_SEEDS = (920411, 920829)
BUDGET = 1024
CHECKPOINTS = (512, 1024)
PRIMARY_CHECKPOINT = 1024
PRIMARY_POLICY = 'full_spatial_balanced'
REFERENCE_POLICY = 'information_full'
WARM = 64
BATCH = 32
POOL = 16
ALPHA = .25
EPOCHS = 16
RELAXATION = .25
NOISE_FRACTION = .005
OFFSET = .15
STEP = .25
LOCK_SCHEMA = 'RBYRCT-08AC-PROTOCOL-v1'
SOURCE_MODULES = ('experiment_08ac','experiment_08z','experiment_08u','experiment_08k',
                  'experiment_04b','experiment_04g','experiment_04h','experiment_04qa',
                  'experiment_05b_08b','experiment_05b_mart','experiment_06b',
                  'experiment_07c_preflight')


def write_csv(path, rows):
    if not rows:
        raise ValueError('no output rows')
    with Path(path).open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_fingerprints():
    result = {}
    for name in SOURCE_MODULES:
        spec = importlib.util.find_spec(name)
        if spec is None or not spec.origin or not Path(spec.origin).is_file():
            raise FileNotFoundError('required module absent: ' + name)
        result[name] = file_sha256(spec.origin)
    return result


def protocol():
    return dict(schema=LOCK_SCHEMA, classification='new synthetic 32-cubed prospectively locked study',
        size=SIZE, object_seeds=list(OBJECT_SEEDS), acquisition_seeds=list(ACQUISITION_SEEDS),
        models=list(MODELS), policies=list(POLICIES), budget=BUDGET,
        checkpoints=list(CHECKPOINTS), primary_checkpoint=PRIMARY_CHECKPOINT,
        primary_policy=PRIMARY_POLICY, primary_reference=REFERENCE_POLICY,
        primary_metric='mean over 6 independent objects of paired whole-volume fractional RMSE gain',
        conditions='average matched/independent models and two acquisition seeds WITHIN object',
        warm=WARM, batch=BATCH, pool=POOL, spatial_alpha=ALPHA,
        spatial_definition='08Z negative ray-path-weighted cumulative absolute voxel sensitivity',
        score_normalization='independent per-pool min-max',
        epochs=EPOCHS, relaxation=RELAXATION, factor=FACTOR, angles=ANGLES,
        noise_fraction=NOISE_FRACTION, offset=OFFSET, step=STEP,
        source_sha256=source_fingerprints(),
        rules=['Never tune alpha or change selector after outcomes',
               'Report all endpoints, including negative results and object-level wins',
               'No clinical or radiation-dose conclusions',
               'Do not modify the frozen 08M protocol or archive'])


def freeze(path):
    p = Path(path)
    if p.exists():
        raise FileExistsError('refuse to overwrite existing lock')
    p.write_text(json.dumps(protocol(), indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print('Protocol lock created:', p)


def check_lock(path):
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError('freeze and commit the protocol before execution')
    saved = json.loads(p.read_text(encoding='utf-8'))
    actual = protocol()
    if saved != actual:
        diffs = [key for key in sorted(set(saved) | set(actual)) if saved.get(key) != actual.get(key)]
        raise RuntimeError('protocol/source lock changed: ' + ', '.join(diffs))
    return saved


def validate_orders(orders, coverage):
    for policy in POLICIES:
        order = np.asarray(orders[policy], dtype=np.int64)
        if (len(order) != BUDGET or len(set(order.tolist())) != BUDGET
                or not np.array_equal(order[:WARM], coverage[:WARM])):
            raise RuntimeError('invalid ray order: ' + policy)


def choose_orders(A, seed):
    from experiment_04g import TILTS
    from experiment_04h import voxel_coverage_order
    from experiment_08k import select_information
    coverage = np.asarray(voxel_coverage_order(A, SIZE, ANGLES, len(TILTS), BUDGET,
                                               seed + SIZE, POOL), dtype=np.int64)
    d, _, dt = select_information(A, None, SIZE, ANGLES, coverage, BUDGET,
                                  seed + SIZE, warm_rays=WARM, batch=BATCH, candidate_pool=POOL)
    f, ft = select_full(A, None, coverage, BUDGET, seed + SIZE,
                        warm_rays=WARM, batch=BATCH, candidate_pool=POOL)
    s, st = select_full_spatial(A, None, coverage, BUDGET, seed + SIZE,
                 size=SIZE, alpha=ALPHA, warm_rays=WARM, batch=BATCH, candidate_pool=POOL)
    orders = dict(coverage=coverage, information_diag=d, information_full=f,
                  full_spatial_balanced=s)
    validate_orders(orders, coverage)
    times = dict(coverage=0., information_diag=dt, information_full=ft,
                 full_spatial_balanced=st)
    return orders, times


def geometry():
    from experiment_04b import system_matrix
    from experiment_04g import TILTS
    A = system_matrix(SIZE, ANGLES, TILTS).tocsr()
    if A.shape != (SIZE * SIZE * ANGLES * len(TILTS), SIZE ** 3):
        raise ValueError('unexpected 32-cubed system matrix shape')
    return A


def preflight(output_dir, lock_path):
    check_lock(lock_path)
    out = Path(output_dir)
    if out.exists():
        raise FileExistsError('preflight output exists; preserve it')
    A = geometry()
    orders_by_seed, all_times, metric_rows, order_rows = {}, {}, [], []
    for seed in ACQUISITION_SEEDS:
        orders, times = choose_orders(A, seed)
        orders_by_seed[str(seed)] = {p: order_sha256(orders[p]) for p in POLICIES}
        all_times[str(seed)] = times
        for p in POLICIES:
            for k in CHECKPOINTS:
                metric_rows.append(dict(acquisition_seed=seed, policy=p, acquired=k,
                   weighted_sensitivity_gini=sensitivity_gini(A, orders[p][:k])))
            for i, ray in enumerate(orders[p]):
                order_rows.append(dict(acquisition_seed=seed, policy=p, acquired_index=i + 1,
                                       ray_id=int(ray), order_sha256=order_sha256(orders[p])))
        print('08AC preflight acquisition seed:', seed, flush=True)
    out.mkdir(parents=True)
    write_csv(out / 'acquisition_orders.csv', order_rows)
    write_csv(out / 'geometry_preflight.csv', metric_rows)
    orders_file_sha256 = file_sha256(out / 'acquisition_orders.csv')
    reduction = {}
    for seed in ACQUISITION_SEEDS:
        for k in CHECKPOINTS:
            by = {r['policy']: r['weighted_sensitivity_gini'] for r in metric_rows
                  if r['acquisition_seed'] == seed and r['acquired'] == k}
            reduction[f'{seed}/{k}'] = bool(by['full_spatial_balanced'] < by['information_full'])
    report = dict(complete=True, engineering_only=True, size=SIZE, budget=BUDGET,
        primary_checkpoint=PRIMARY_CHECKPOINT, alpha=ALPHA, geometry_only=True,
        no_object_truth_accessed=True, acquisition_orders_file_sha256=orders_file_sha256,
        order_sha256=orders_by_seed,
        selector_seconds=all_times, sensitivity_gini_reduced=reduction,
        important='Gini is an OBSERVATION, not a success gate; negative results must be retained.')
    (out / 'preflight.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


def object_summary(rows):
    result = []
    for obj in sorted({r['object_id'] for r in rows}):
        for k in CHECKPOINTS:
            for p in POLICIES:
                sub = [r for r in rows if (r['object_id'], r['acquired'], r['policy']) == (obj, k, p)]
                expected = len(MODELS) * len(ACQUISITION_SEEDS)
                if len(sub) != expected or len({(r['model'], r['acquisition_seed']) for r in sub}) != expected:
                    raise RuntimeError('missing or duplicate paired condition')
                result.append(dict(object_id=obj, acquired=k, policy=p, n_conditions=expected,
                    mean_global_gain=float(np.mean([r['gain_vs_coverage'] for r in sub])),
                    mean_defect_gain=float(np.mean([r['defect_gain_vs_coverage'] for r in sub])),
                    mean_nondefect_gain=float(np.mean([r['nondefect_gain_vs_coverage'] for r in sub])),
                    mean_global_rmse=float(np.mean([r['global_rmse'] for r in sub]))))
    return result


def aggregate(objects):
    summary = []
    for k in CHECKPOINTS:
        for p in POLICIES:
            selected = [r for r in objects if r['acquired'] == k and r['policy'] == p]
            if len(selected) != len(OBJECT_SEEDS):
                raise RuntimeError('object count mismatch')
            summary.append(dict(size=SIZE, acquired=k, policy=p, n_objects=len(selected),
                mean_global_gain=float(np.mean([r['mean_global_gain'] for r in selected])),
                mean_defect_gain=float(np.mean([r['mean_defect_gain'] for r in selected])),
                object_global_wins=sum(r['mean_global_gain'] > 0 for r in selected),
                object_defect_wins=sum(r['mean_defect_gain'] > 0 for r in selected)))
    return summary


def run(output_dir, lock_path, preflight_dir):
    locked = check_lock(lock_path)
    pf_path = Path(preflight_dir) / 'preflight.json'
    if not pf_path.is_file():
        raise FileNotFoundError('missing successful 08AC preflight')
    pf = json.loads(pf_path.read_text(encoding='utf-8'))
    if not (pf.get('complete') and pf.get('geometry_only') and pf.get('size') == SIZE
            and pf.get('budget') == BUDGET and pf.get('alpha') == ALPHA):
        raise ValueError('preflight protocol mismatch')
    out = Path(output_dir)
    if out.exists():
        raise FileExistsError('refuse to overwrite run output')
    A = geometry()
    order_file = Path(preflight_dir) / 'acquisition_orders.csv'
    if file_sha256(order_file) != pf.get('acquisition_orders_file_sha256'):
        raise RuntimeError('saved preflight ray-order file modified')
    with order_file.open(newline='', encoding='utf-8') as fh:
        order_rows = list(csv.DictReader(fh))
    orders = {}
    for seed in ACQUISITION_SEEDS:
        orders[seed] = {}
        for p in POLICIES:
            selected = sorted((r for r in order_rows if int(r['acquisition_seed']) == seed
                    and r['policy'] == p), key=lambda r: int(r['acquired_index']))
            if len(selected) != BUDGET or [int(r['acquired_index']) for r in selected] != list(range(1, BUDGET + 1)):
                raise RuntimeError('invalid saved order records')
            ids = np.asarray([int(r['ray_id']) for r in selected], dtype=np.int64)
            if (order_sha256(ids) != pf['order_sha256'][str(seed)][p]
                    or any(r['order_sha256'] != order_sha256(ids) for r in selected)):
                raise RuntimeError('preflight acquisition fingerprint mismatch')
            orders[seed][p] = ids
        validate_orders(orders[seed], orders[seed]['coverage'])
    from experiment_04g import TILTS
    from experiment_04qa import project
    from experiment_05b_08b import nonnegative_noisy_measurements
    from experiment_05b_mart import mart_reconstruct
    from experiment_06b import defect_phantom
    from experiment_07c_preflight import defect_support, error_metrics
    out.mkdir(parents=True)
    (out / 'protocol.json').write_text(json.dumps(locked, indent=2) + '\n', encoding='utf-8')
    (out / 'environment.json').write_text(json.dumps(dict(python=sys.version,
        platform=platform.platform(), numpy=np.__version__), indent=2) + '\n', encoding='utf-8')
    write_csv(out / 'acquisition_orders.csv', order_rows)
    records, manifest = [], []
    expected = len(OBJECT_SEEDS) * len(ACQUISITION_SEEDS) * len(MODELS) * len(POLICIES) * len(CHECKPOINTS)
    def status(done=False):
        (out / 'run_status.json').write_text(json.dumps(dict(complete=done,
           completed_reconstructions=len(records), expected_reconstructions=expected), indent=2) + '\n', encoding='utf-8')
    status()
    try:
        for obj_seed in OBJECT_SEEDS:
            truth, fine, desc = defect_phantom(SIZE, FACTOR, obj_seed)
            mask, maskinfo = defect_support(SIZE, FACTOR, obj_seed)
            obj_id = f'defect_validation_08ac_{obj_seed}'
            manifest.append(dict(object_id=obj_id, object_seed=obj_seed, n_defects=desc['n_defects'],
                mask_voxels=maskinfo['mask_voxels'], mask_sha256=maskinfo['mask_sha256'],
                truth_sha256=hashlib.sha256(np.asarray(truth, dtype='<f8').tobytes()).hexdigest()))
            for acq_i, acq_seed in enumerate(ACQUISITION_SEEDS):
                for mi, model in enumerate(MODELS):
                    if model == 'same':
                        clean = np.asarray(A @ truth).ravel()
                    else:
                        clean = np.asarray(project(fine, SIZE, ANGLES, TILTS, factor=FACTOR,
                                         offset=OFFSET, step=STEP, mode='linear')).ravel()
                    noise_seed = (obj_seed * 37 + mi * 100003 + 17011 + acq_i * 133337) % (2**32)
                    measured = nonnegative_noisy_measurements(clean, NOISE_FRACTION, noise_seed)
                    batch_rows = []
                    for p in POLICIES:
                        order = orders[acq_seed][p]
                        for k in CHECKPOINTS:
                            start = time.perf_counter()
                            reconstructed = mart_reconstruct(A[order[:k]], measured[order[:k]],
                                                             EPOCHS, relaxation=RELAXATION)
                            metrics = error_metrics(reconstructed, truth, mask)
                            batch_rows.append(dict(object_id=obj_id, object_seed=obj_seed,
                                acquisition_seed=acq_seed, model=model, policy=p, acquired=k,
                                **metrics, gain_vs_coverage=0., defect_gain_vs_coverage=0.,
                                nondefect_gain_vs_coverage=0., order_sha256=order_sha256(order[:k]),
                                reconstruction_seconds=time.perf_counter() - start))
                        print(f'08AC object={obj_seed} seed={acq_seed} model={model} policy={p}', flush=True)
                    for row in batch_rows:
                        reference = next(r for r in batch_rows if r['policy'] == 'coverage' and
                                         r['acquired'] == row['acquired'])
                        for metric, gain in (('global_rmse', 'gain_vs_coverage'),
                                             ('defect_region_rmse', 'defect_gain_vs_coverage'),
                                             ('nondefect_rmse', 'nondefect_gain_vs_coverage')):
                            row[gain] = (reference[metric] - row[metric]) / max(reference[metric], 1e-12)
                    records.extend(batch_rows)
                    status()
    except BaseException:
        status(False)
        raise
    write_csv(out / 'prefix_reconstructions.csv', records)
    write_csv(out / 'object_manifest.csv', manifest)
    objects = object_summary(records)
    write_csv(out / 'object_level_summary.csv', objects)
    write_csv(out / 'aggregate_summary.csv', aggregate(objects))
    primary = []
    for obj in sorted({r['object_id'] for r in objects}):
        selected = {r['policy']: r for r in objects if r['object_id'] == obj and
                    r['acquired'] == PRIMARY_CHECKPOINT}
        full = selected[REFERENCE_POLICY]
        spatial = selected[PRIMARY_POLICY]
        primary.append(dict(object_id=obj, acquired=PRIMARY_CHECKPOINT,
            spatial_minus_full_global_gain=spatial['mean_global_gain'] - full['mean_global_gain'],
            spatial_minus_full_global_rmse=spatial['mean_global_rmse'] - full['mean_global_rmse'],
            spatial_better_global=int(spatial['mean_global_rmse'] < full['mean_global_rmse']),
            spatial_global_gain_vs_coverage=spatial['mean_global_gain'],
            full_global_gain_vs_coverage=full['mean_global_gain']))
    write_csv(out / 'primary_object_comparison.csv', primary)
    status(True)
    (out / 'sha256.json').write_text(json.dumps({p.name: file_sha256(p) for p in sorted(out.iterdir()) if p.is_file()},
                                              indent=2) + '\n', encoding='utf-8')
    print(json.dumps(json.loads((out / 'run_status.json').read_text(encoding='utf-8')), indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    action = ap.add_mutually_exclusive_group(required=True)
    action.add_argument('--freeze-protocol', action='store_true')
    action.add_argument('--preflight', action='store_true')
    action.add_argument('--run', action='store_true')
    ap.add_argument('--lock-path', default='protocol_08ac_frozen.json')
    ap.add_argument('--preflight-dir')
    ap.add_argument('--output-dir')
    args = ap.parse_args()
    if args.freeze_protocol:
        freeze(args.lock_path)
    elif args.preflight:
        if not args.output_dir: ap.error('--preflight requires --output-dir')
        preflight(args.output_dir, args.lock_path)
    else:
        if not args.output_dir or not args.preflight_dir:
            ap.error('--run requires --output-dir and --preflight-dir')
        run(args.output_dir, args.lock_path, args.preflight_dir)


if __name__ == '__main__':
    main()
