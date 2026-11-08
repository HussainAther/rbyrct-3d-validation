"""08AJ-P: geometry-only 64^3 diagonal-information engineering preflight.

This is NOT a frozen scientific validation. It never creates phantoms,
measurements, reconstructions, error metrics, or comparative outcomes.
Reuse the unchanged 08M0 engineering run and 08K selector.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import platform
from pathlib import Path

from experiment_08m0 import run as run_08m0

DEFAULTS = dict(size=64, angles=4, budget=2048, warm_rays=64,
                batch=32, pool=16, seed=930011, repeats=2)
MODULES = ('experiment_08aj_p.py', 'experiment_08m0.py', 'experiment_08k.py',
           'experiment_08j.py', 'experiment_04b.py', 'experiment_04g.py',
           'experiment_04h.py')


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(output_dir, *, smoke=False, max_csr_gib=2.0, max_rss_gib=8.0):
    """Run the engineering preflight, preserve all output, and assess gates.

    A runtime failure leaves 08M0's partial status in output_dir.
    Gate failures are flagged, NEVER silently edited or discarded.
    """
    if max_csr_gib <= 0 or max_rss_gib <= 0:
        raise ValueError('positive resource limits required')
    root = Path(output_dir)
    if root.exists():
        raise FileExistsError('output directory already exists; do not overwrite evidence')
    if smoke:
        cfg = dict(size=8, angles=2, budget=64, warm_rays=8,
                   batch=8, pool=4, seed=930011, repeats=2)
    else:
        cfg = DEFAULTS.copy()
    profile = run_08m0(root, **cfg, allow_test_scale=True)
    csr_gib = profile['csr_storage_bytes'] / (1024 ** 3)
    # RSS is a current-process value, NOT necessarily peak usage.
    rss_values = [m.get('rss_bytes') for m in
                  (profile['memory_after_matrix'], profile['memory_final'])]
    rss_values = [v for v in rss_values if v is not None]
    observed_rss_gib = max(rss_values) / (1024 ** 3) if rss_values else None
    status = {
        'stage': '08AJ-P engineering-only geometry preflight',
        'smoke': bool(smoke), 'complete': True,
        'no_phantoms_or_reconstruction': True,
        'size': cfg['size'], 'voxel_count': cfg['size'] ** 3,
        'ray_catalogue_size': cfg['size'] ** 2 * cfg['angles'] * 3,
        'budget': cfg['budget'],
        'csr_gib': csr_gib, 'observed_rss_gib_not_peak': observed_rss_gib,
        'max_csr_gib': max_csr_gib, 'max_rss_gib': max_rss_gib,
        'csr_gate_pass': csr_gib <= max_csr_gib,
        'rss_gate_pass': None if observed_rss_gib is None else observed_rss_gib <= max_rss_gib,
        'deterministic': profile['repeat_full_order_identical'],
        'engineering_feasible_under_observed_gates': bool(
            csr_gib <= max_csr_gib and observed_rss_gib is not None and
            observed_rss_gib <= max_rss_gib and profile['repeat_full_order_identical']),
        'reconstruction_feasibility_not_tested': True,
        'note': 'RSS samples do not measure peak use; a separate MART timing/memory pilot is required.',
        'python_platform': platform.platform(),
        'source_sha256': {name: file_sha(Path(__file__).parent / name)
                          for name in MODULES},
    }
    (root / '08aj_p_assessment.json').write_text(
        json.dumps(status, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    (root / '08aj_p_assessment.sha256').write_text(
        file_sha(root / '08aj_p_assessment.json') + '  08aj_p_assessment.json\n',
        encoding='utf-8')
    return status


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', required=True)
    p.add_argument('--smoke', action='store_true', help='8^3 engineering smoke; never scientific evidence')
    p.add_argument('--max-csr-gib', type=float, default=2.0)
    p.add_argument('--max-rss-gib', type=float, default=8.0)
    a = p.parse_args()
    print(json.dumps(run(a.output_dir, smoke=a.smoke,
                         max_csr_gib=a.max_csr_gib,
                         max_rss_gib=a.max_rss_gib), indent=2))

if __name__ == '__main__':
    main()
