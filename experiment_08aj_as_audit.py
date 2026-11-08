"""08AJ-AS: read-only second-pass receipt, identity, and input-file audit.

Recomputes actual on-disk SHA-256 values and calls AN regeneration/chain validation.
Does NOT independently replay MART; use AN/AR auditor for numerical outputs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import experiment_08aj_as as contract
import experiment_08aj_ar as ar
import experiment_08aj_an as an


def audit(output_dir, ar_dir, aa_dir, m_dir):
    errors = []
    job_id = None
    try:
        root = contract._safe_directory(output_dir)
        if {p.name for p in root.iterdir()} != {'contract_validation.json', 'run_status.json'}:
            raise ValueError('unexpected/missing AS evidence files')
        record_path = root/'contract_validation.json'
        status_path = root/'run_status.json'
        raw = record_path.read_bytes()
        record = json.loads(raw)
        status = json.loads(status_path.read_bytes())
        if raw != contract.canonical(record) or status_path.read_bytes() != contract.canonical(status):
            raise ValueError('noncanonical AS evidence')
        job_id = record.get('job_id')
        expected_status = {'schema': contract.SCHEMA,
                           'verdict': 'AS_ENGINEERING_INPUT_CONTRACT_VALIDATED',
                           'receipt_sha256': contract.digest(raw), 'job_id': job_id,
                           'production_execution_allowed': False, 'no_confirmatory_outcomes': True}
        if status != expected_status:
            raise ValueError('AS status or receipt hash mismatch')
        # Independently check the physical files and exact identities, rather than
        # trusting the embedded digest list. Then repeat the AN regeneration check.
        _, job = ar.lookup(ar_dir, aa_dir, m_dir, job_id)
        if record.get('identity') != job or record.get('group_id') != job['group_id']:
            raise ValueError('manifest identity differs from validation receipt')
        engine = Path(ar_dir)/'engine'
        group = engine/'groups'/an.group_name(job['object_id'], job['acquisition_id'], job['model'])
        work = engine/'jobs'/an.job_name(job['object_id'], job['acquisition_id'], job['model'], job['policy'])
        artifacts = {
            'ar_manifest.json': Path(ar_dir)/'ar_manifest.json',
            'engine/plan.json': engine/'plan.json',
            'group/receipt.json': group/'receipt.json',
            'group/clean.npy': group/'clean.npy',
            'group/noisy.npy': group/'noisy.npy',
            'job/source.json': work/'source.json',
            'job/order.npy': work/'order.npy',
        }
        observed_hashes = {key: contract.sha(path) for key, path in artifacts.items()}
        if observed_hashes != record.get('artifact_sha256'):
            raise ValueError('input artifact digest mismatch')
        current = contract.validated_binding(ar_dir, aa_dir, m_dir, job_id)
        if current != record:
            raise ValueError('source, environment or object contract drift')
    except Exception as exc:
        errors.append(type(exc).__name__ + ': ' + str(exc))
    return {'verdict': 'AS_INDEPENDENT_CONTRACT_AUDIT_PASS' if not errors else 'AS_CONTRACT_AUDIT_FAIL',
            'pass': not errors, 'job_id': job_id, 'errors': errors,
            'production_jobs_executed': 0, 'production_execution_allowed': False,
            'production_480_job_certified': False, 'no_confirmatory_outcomes': True}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for field in ('output-dir', 'ar-dir', 'aa-dir', 'm-dir'):
        ap.add_argument('--'+field, required=True, type=Path)
    args = ap.parse_args()
    result = audit(args.output_dir, args.ar_dir, args.aa_dir, args.m_dir)
    print(json.dumps(result, indent=2))
    if not result['pass']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
