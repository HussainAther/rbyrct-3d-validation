"""08AJ-AS: execution-disabled engineering input-to-job contract receipts.

Reads an existing AR/AN noncohort engineering fixture; never creates catalogues,
reconstruction jobs, or prospective objects. A prepared AR job is required.
No production/unlock/freeze modes, arbitrary objects, or input-loader hooks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
from pathlib import Path

import numpy as np
import scipy

import experiment_08aj_ar as ar
import experiment_08aj_an as an

SCHEMA = 'RBYRCT-08AJ-AS-engineering-contract-validation-v1'
SOURCES = ('experiment_08aj_as.py', 'experiment_08aj_as_audit.py')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('missing or unsafe input file: ' + str(path))
    return digest(path.read_bytes())


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')


def sources():
    root = Path(__file__).resolve().parent
    return {name: sha(root/name) for name in SOURCES}


def environment():
    return {'python': '.'.join(map(str, sys.version_info[:3])),
            'implementation': platform.python_implementation(),
            'numpy': np.__version__, 'scipy': scipy.__version__}


def _safe_directory(path):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise ValueError('missing or unsafe directory: '+str(path))
    return path


def validated_binding(ar_dir, aa_dir, m_dir, job_id):
    """Validate existing engineering inputs; does not prepare or execute anything."""
    root = _safe_directory(ar_dir)
    manifest, job = ar.lookup(root, aa_dir, m_dir, job_id)
    if job.get('execution_scope') != 'ENGINEERING_ONLY' or job.get('production_execution_allowed') is not False:
        raise ValueError('not an execution-disabled noncohort engineering job')
    if job_id not in {r['job_id'] for r in ar.fixed_roster()}:
        raise ValueError('job not in internal engineering allowlist')
    engine = root/'engine'
    _safe_directory(engine)
    obj, acq, model, policy = (job[k] for k in ('object_id', 'acquisition_id', 'model', 'policy'))
    group = engine/'groups'/an.group_name(obj, acq, model)
    work = engine/'jobs'/an.job_name(obj, acq, model, policy)
    _safe_directory(group)
    _safe_directory(work)
    # AN independently regenerates truth, noisy measurements, acquisition orders,
    # and verifies the entire checkpoint chain. It does not run MART here.
    specification, job_dir, _, _, truth, rows_done, _, _ = an.verify_job(
        engine, aa_dir, m_dir, obj, acq, model, policy)
    group_receipt = an.read(group/'receipt.json')
    if specification['job_id'] != job_id or specification['truth_sha256'] != group_receipt['truth_sha256']:
        raise ValueError('cross-object or cross-group provenance mismatch')
    if specification['group_receipt_sha256'] != sha(group/'receipt.json'):
        raise ValueError('job/group receipt hash mismatch')
    if group_receipt['object_seed'] != job['object_seed'] or group_receipt['noise_seed'] != job['noise_seed']:
        raise ValueError('object/noise seed mismatch')
    if job['family'] != an.OBJECTS[obj]['family'] or job['acquisition_seed'] != an.ACQUISITIONS[acq]:
        raise ValueError('engineering manifest identity mismatch')
    if int(specification['n']) != manifest['n'] or int(specification['budget']) != manifest['ray_budget']:
        raise ValueError('resolution or ray budget mismatch')
    if int(specification['epochs']) != manifest['mart_epochs'] or float(specification['relaxation']) != manifest['relaxation']:
        raise ValueError('MART parameter mismatch')
    if specification['production_execution_allowed'] is not False or manifest['production_execution_allowed'] is not False:
        raise ValueError('production authorization drift')
    expected_truth = hashlib.sha256(np.asarray(truth, dtype='<f8').tobytes()).hexdigest()
    if expected_truth != group_receipt['truth_sha256']:
        raise ValueError('regenerated truth mismatch')
    selected = {
        'ar_manifest.json': sha(root/'ar_manifest.json'),
        'engine/plan.json': sha(engine/'plan.json'),
        'group/receipt.json': sha(group/'receipt.json'),
        'group/clean.npy': sha(group/'clean.npy'),
        'group/noisy.npy': sha(group/'noisy.npy'),
        'job/source.json': sha(job_dir/'source.json'),
        'job/order.npy': sha(job_dir/'order.npy'),
    }
    checkpoint_dir = _safe_directory(job_dir/'checkpoints')
    checkpoint_hashes = {}
    for cp in sorted(checkpoint_dir.iterdir()):
        _safe_directory(cp)
        if not cp.name.startswith('cp_') or set(x.name for x in cp.iterdir()) != {'state.npy', 'receipt.json'}:
            raise ValueError('unexpected checkpoint structure')
        checkpoint_hashes[cp.name] = {'state.npy': sha(cp/'state.npy'),
                                      'receipt.json': sha(cp/'receipt.json')}
    if (job_dir/'final').exists():
        raise ValueError('AS qualification requires an unexecuted prepared job')
    if rows_done != 0 or checkpoint_hashes:
        raise ValueError('AS qualification requires no reconstruction checkpoints')
    return {'schema': SCHEMA, 'job_id': job_id, 'identity': job,
            'group_id': job['group_id'], 'n': specification['n'],
            'budget': specification['budget'], 'epochs': specification['epochs'],
            'relaxation': specification['relaxation'],
            'truth_sha256': group_receipt['truth_sha256'],
            'noise_seed': group_receipt['noise_seed'],
            'source_sha256': sources(), 'environment': environment(),
            'environment_sha256': digest(canonical(environment())),
            'artifact_sha256': selected, 'checkpoint_sha256': checkpoint_hashes,
            'rows_done_on_validation': rows_done,
            'namespace': 'NONCOHORT_ENGINEERING_ONLY',
            'scientific_signoff': False, 'resource_policy_approved': False,
            'production_480_job_certified': False, 'production_execution_allowed': False,
            'frozen': False, 'no_confirmatory_outcomes': True,
            'does_not_run_reconstruction': True,
            'not_a_production_authorization': True}


def prepare(output_dir, ar_dir, aa_dir, m_dir, job_id):
    output = Path(output_dir)
    if output.exists():
        raise FileExistsError('AS output exists; refusing overwrite')
    record = validated_binding(ar_dir, aa_dir, m_dir, job_id)
    output.mkdir(parents=True)
    data = canonical(record)
    target = output/'contract_validation.json'
    with target.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    status = {'schema': SCHEMA, 'verdict': 'AS_ENGINEERING_INPUT_CONTRACT_VALIDATED',
              'receipt_sha256': digest(data), 'job_id': job_id,
              'production_execution_allowed': False, 'no_confirmatory_outcomes': True}
    with (output/'run_status.json').open('xb') as stream:
        stream.write(canonical(status))
        stream.flush()
        os.fsync(stream.fileno())
    return status


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode', required=True, choices=('prepare', 'audit', 'production-run', 'unlock', 'freeze'))
    for field in ('output-dir', 'ar-dir', 'aa-dir', 'm-dir'):
        ap.add_argument('--'+field, required=True, type=Path)
    ap.add_argument('--job-id')
    args = ap.parse_args(argv)
    if args.mode in ('production-run', 'unlock', 'freeze'):
        ap.error('PROSPECTIVE_EXECUTION_DISABLED')
    if args.mode == 'prepare':
        if not args.job_id:
            ap.error('--job-id required')
        result = prepare(args.output_dir, args.ar_dir, args.aa_dir, args.m_dir, args.job_id)
    else:
        from experiment_08aj_as_audit import audit
        result = audit(args.output_dir, args.ar_dir, args.aa_dir, args.m_dir)
    print(json.dumps(result, indent=2))
    if result.get('pass') is False:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
