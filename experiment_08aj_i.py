"""08AJ-I engineering-only 32^3 independent-projector and history audit.

No MART, no policy ranking, no RMSE, no confirmatory validation, no freeze.
The full-projector probe uses a non-roster ENGINEERING phantom seed.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import os
import time
import zipfile
from pathlib import Path

import numpy as np
from experiment_04g import TILTS
from experiment_04qa import project
from experiment_08aj_d import FAMILIES, SEEDS
from experiment_08aj_e import full_resolution_pair, sha_array
from experiment_08aj_f import reconciled_object, hashes_of_sources
from experiment_08aj_h import PRIOR_SOURCES, statistical_rules

STAGE = '08AJ-I full independent-projector engineering and archived-object audit'
HISTORICAL = ('experiment08m', 'experiment08u', 'experiment08w',
              'experiment08x', 'experiment08z', 'experiment08ac')
ENGINEERING_SEED = 970099  # NOT one of the 24 proposed validation seeds


def digest(b):
    return hashlib.sha256(b).hexdigest()


def archive_manifests(location):
    """Read all historical manifests from directory or ZIP; no source mutation."""
    p = Path(location)
    if not p.exists():
        return [], [f'archive path does not exist: {p}']
    entries = []
    if p.is_file() and p.suffix.lower() == '.zip':
        with zipfile.ZipFile(p) as z:
            for name in sorted(z.namelist()):
                if name.endswith('/object_manifest.csv') and any('/'+k+'/' in '/'+name for k in HISTORICAL):
                    entries.append((name, z.read(name)))
    elif p.is_dir():
        for f in sorted(p.rglob('object_manifest.csv')):
            if any(k in f.parts for k in HISTORICAL):
                entries.append((str(f.relative_to(p)), f.read_bytes()))
    else:
        raise ValueError('historical results must be directory or zip file')
    return entries, []


def historical_audit(location, object_records):
    """Exact seed/hash intersection only; not a population-independence claim."""
    files, errors = archive_manifests(location)
    seeds = {str(x['object_seed']) for x in object_records}
    fine_hashes = {x['fine_truth_sha256'] for x in object_records}
    coarse_hashes = {x['coarse_truth_sha256'] for x in object_records}
    prior_seeds = set(); prior_hashes = set(); manifests = []
    for name, raw in files:
        try:
            rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
        except Exception as exc:
            errors.append(f'cannot parse {name}: {exc}')
            continue
        if not rows:
            errors.append(f'empty manifest: {name}')
            continue
        for row in rows:
            seed = row.get('object_seed') or row.get('seed')
            if seed and seed.strip(): prior_seeds.add(seed.strip())
            val = row.get('truth_sha256')
            if val and val.strip(): prior_hashes.add(val.strip().lower())
        manifests.append({'path': name, 'sha256': digest(raw), 'rows':len(rows),
                          'columns':list(rows[0].keys())})
    covered = {k: any(k in Path(m['path'].replace('\\', '/')).parts for m in manifests) for k in HISTORICAL}
    seed_overlaps = sorted(seeds & prior_seeds)
    coarse_overlaps = sorted(coarse_hashes & prior_hashes)
    fine_overlaps = sorted(fine_hashes & prior_hashes)
    return {
        'archive_input':str(location), 'manifests':manifests, 'historical_studies_covered':covered,
        'all_six_studies_have_manifest':all(covered.values()),
        'historical_unique_seeds':len(prior_seeds),'historical_unique_truth_hashes':len(prior_hashes),
        'prospective_object_count':len(object_records),
        'seed_overlaps':seed_overlaps,'coarse_truth_hash_overlaps':coarse_overlaps,
        'fine_truth_hash_overlaps':fine_overlaps,'parsing_errors':errors,
        'exact_overlap_audit_complete':bool(manifests) and all(covered.values()) and not errors,
        'generator_and_structural_independence_established':False,
        'limitations':[
            'Only archived object-manifest CSVs are checked; missing historical cohorts or files remain possible.',
            'Different seeds and SHA-256 values cannot establish generator or morphology independence.',
            'A historical and proposed phantom can be structurally similar without matching hashes.'
        ]
    }


def full_projector_engineering(n=32, family='localized_defects', seed=ENGINEERING_SEED,
                               max_seconds=600, max_peak_gib=8.0):
    """Full independent fine-grid projector using non-validation engineering phantom.

    Peak memory sourced from process high-water metric when available; no outcome comparisons.
    """
    if n != 32 or seed in {s for values in SEEDS.values() for s in values}:
        raise ValueError('full projector probe must use 32^3 and non-roster engineering seed')
    if family not in FAMILIES or max_seconds <= 0 or max_peak_gib <= 0:
        raise ValueError('invalid engineering configuration')
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        def memory():
            info = proc.memory_info()
            peak = getattr(info, 'peak_wset', None)
            source = 'psutil_peak_wset' if peak is not None else 'unavailable'
            if peak is None and os.name == 'posix':
                import resource
                # Linux ru_maxrss is KiB; macOS reports bytes.
                raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                peak = int(raw * (1024 if os.uname().sysname == 'Linux' else 1))
                source = 'resource_ru_maxrss'
            return {'rss_bytes': int(info.rss),
                    'peak_working_set_bytes': int(peak) if peak is not None else None,
                    'source':source}
    except ImportError:
        def memory():
            return {'rss_bytes':None,'peak_working_set_bytes':None,'source':'unavailable'}
    start = time.perf_counter()
    coarse, fine = full_resolution_pair(family, seed, n)
    phantom_seconds = time.perf_counter()-start
    before = memory()
    start = time.perf_counter()
    # Exact intended independent-model project() settings at 32^3.
    vals = np.asarray(project(fine,n,4,TILTS,factor=2,offset=0.0,step=0.5,mode='linear'), dtype=np.float64)
    projection_seconds = time.perf_counter()-start
    after = memory()
    expected = n*n*4*len(TILTS)
    finite = vals.shape == (expected,) and bool(np.isfinite(vals).all())
    nonnegative = finite and bool((vals >= 0).all())
    peak = after['peak_working_set_bytes']
    peak_ok = (peak is not None and peak / (1024**3) <= max_peak_gib)
    timing_ok = projection_seconds <= max_seconds
    return {
        'probe_only':True,'not_confirmatory':True,'n':n,'family':family,'engineering_seed':seed,
        'forward_model':'independent ray marching: project(fine,32,4,TILTS,factor=2,step=0.5,mode=linear)',
        'candidate_rays':expected,'projected_rays':len(vals),
        'phantom_generation_seconds':phantom_seconds, 'full_projection_seconds':projection_seconds,
        'memory_before':before,'memory_after':after,'peak_gate_measured':peak is not None,
        'peak_gate_pass':peak_ok if peak is not None else None,
        'wall_clock_gate_seconds':max_seconds,'wall_clock_gate_pass':timing_ok,
        'resource_gate_pass':bool(timing_ok and peak_ok),
        'all_finite_nonnegative':bool(finite and nonnegative),
        'projection_sha256':sha_array(vals) if finite else None,
        'no_rmse_or_policy_comparisons':True,
        'note':'A single full catalogue is a measured engineering probe, not proof of speed across all 24 phantoms.'
    }


def run(output_dir, archive_dir, *, skip_projection=False):
    out = Path(output_dir)
    if out.exists(): raise FileExistsError('refusing to overwrite earlier 08AJ-I output')
    out.mkdir(parents=True)
    status = {'stage':STAGE,'complete':False,'frozen':False,'no_confirmatory_outcomes':True}
    write(out/'run_status.json', status)
    try:
        objects = [reconciled_object(f,s) for f in FAMILIES for s in SEEDS[f]]
        history = historical_audit(archive_dir,objects)
        projector = None if skip_projection else full_projector_engineering()
        open_items = []
        if not history['exact_overlap_audit_complete']:
            open_items.append('Historical manifests missing or parsing incomplete; exact overlap audit not complete')
        if history['seed_overlaps'] or history['coarse_truth_hash_overlaps'] or history['fine_truth_hash_overlaps']:
            open_items.append('Exact historical seed or truth hash overlap: requires investigation')
        open_items.append('Structural/generator independence requires scientific review, not implied by distinct hashes')
        if projector is None:
            open_items.append('Full independent projector measurement skipped')
        elif not projector['resource_gate_pass'] or not projector['all_finite_nonnegative']:
            open_items.append('Full projector resource or validity gate not verified')
        open_items.extend([
            'Approve primary inferential design, precision rationale and time ceilings before lock',
            '64^3 complete-view requires >=4096 rays; keep as separate feasible-budget study',
            'Resumable 24-object runner, independent output audit and signed source lock pending'])
        report = {
            'stage':STAGE,'complete':True,'frozen':False,'no_confirmatory_outcomes':True,
            'historical_object_audit':history,'full_independent_projector':projector,
            'statistical_rules_status':statistical_rules()['status'],
            'source_sha256':{**hashes_of_sources(),Path(__file__).name:digest(Path(__file__).read_bytes())},
            'lock_readiness':'NOT_READY','open_items':open_items,
            'verdict':'ENGINEERING_AUDIT_PASS' if history['exact_overlap_audit_complete'] and not history['seed_overlaps'] and not history['coarse_truth_hash_overlaps'] and not history['fine_truth_hash_overlaps'] and (projector is None or (projector['resource_gate_pass'] and projector['all_finite_nonnegative'])) else 'REVIEW_REQUIRED',
        }
        write(out/'08aj_i_report.json',report)
        status.update(complete=True,verdict=report['verdict'],lock_readiness='NOT_READY',open_items=len(open_items))
        write(out/'run_status.json',status)
        (out/'manifest.sha256').write_text(''.join(digest((out/n).read_bytes())+'  '+n+'\n' for n in ('08aj_i_report.json','run_status.json')),encoding='ascii')
        print(json.dumps({'verdict':status['verdict'],'historical_manifests':len(history['manifests']),
                          'exact_overlap_audit_complete':history['exact_overlap_audit_complete'],
                          'seed_overlaps':history['seed_overlaps'],
                          'full_projector_verified':bool(projector and projector['resource_gate_pass'] and projector['all_finite_nonnegative']),
                          'lock_readiness':'NOT_READY','open_items':len(open_items)},indent=2))
        return report
    except Exception as exc:
        status.update(verdict='FAIL',error=str(exc))
        write(out/'run_status.json',status)
        raise


def write(path, value):
    path.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n',encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--history',type=Path,default=Path('../rbyrct-results'),
                   help='historical results directory OR ZIP containing object_manifest.csv files')
    p.add_argument('--skip-projection',action='store_true',help='test/development use only')
    p.add_argument('--freeze',action='store_true')
    a = p.parse_args()
    if a.freeze: raise RuntimeError('REFUSE_TO_FREEZE: open scientific and runner blockers')
    run(a.output_dir,a.history,skip_projection=a.skip_projection)

if __name__ == '__main__':
    main()
