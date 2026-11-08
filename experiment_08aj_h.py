"""08AJ-H no-outcome lock-readiness engineering audit (DRAFT, cannot freeze).

Checks full-size 32^3 acquisition fairness, source-level prior-seed overlap,
optional bounded independent forward-ray cost, and explicit statistical rules.
Does not reconstruct any phantom or compute an RMSE/gain.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import time
from pathlib import Path
import numpy as np
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04qa import rays, march_ray
from experiment_08aj_d import SEEDS, FAMILIES, ACQUISITION_SEEDS, MODELS, CHECKPOINTS
from experiment_08aj_e import full_resolution_pair, sha_array
from experiment_08aj_g import fair_orders, INDIVIDUAL, WARM, measurement_seed
from experiment_08aj_f import hashes_of_sources

STAGE='08AJ-H 32-cubed lock-readiness engineering preflight'
PRIOR_SOURCES=('experiment_08m.py','experiment_08u.py','experiment_08w.py',
               'experiment_08x.py','experiment_08z.py','experiment_08ac.py')


def historical_seed_review(directory:Path):
    """Check literal numbers in named historical source files, NOT object independence."""
    current={s for seeds in SEEDS.values() for s in seeds}
    records=[]; found=set(); missing=[]
    for name in PRIOR_SOURCES:
        path=directory/name
        if not path.is_file():
            missing.append(name);continue
        text=path.read_text(encoding='utf8')
        literals={int(v) for v in re.findall(r'(?<![\w.])\d{6,9}(?![\w.])',text)}
        overlap=sorted(literals&current)
        found.update(overlap)
        records.append({'file':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                        'matching_seed_literals':overlap})
    return {'review_scope':'six named historical source files, lexical integer-literal scan only',
            'files_reviewed':records,'missing_files':missing,
            'seed_literal_overlaps':sorted(found),
            'no_seed_literal_overlap_in_reviewed_files':not found,
            'structural_and_generator_independence_established':False,
            'exhaustive_historical_overlap_excluded':False}


def statistical_rules():
    """Explicit DRAFT decisions, cannot be interpreted as approved frozen design."""
    return {
      'status':'DRAFT_PENDING_REVIEW',
      'primary':'32^3; 2048 rays; information_diag versus uniform_multiscale; whole-volume MART RMSE',
      'phantom_unit':'24 synthetic objects, 8 per each of three families',
      'paired_conditions':'2 acquisition seeds x 2 model conditions per object; one deterministic noisy catalogue per condition',
      'gain_formula':'per condition 1 - rmse_information_diag / rmse_uniform_multiscale; average 4 within object; average 24 objects',
      'bootstrap':'20000 seeded (941007) family-stratified object resamples; percentile 95% CI',
      'directional_success':'primary lower 95% CI bound > 0; positive average gain alone is insufficient',
      'practical_effect_target':'2% mean paired gain is a suggested engineering benchmark, NOT a confirmatory gate until reviewed',
      'secondary':'coverage, stratified_random_04h, complete_view, defect RMSE, geometry sensitivity, 1024/4096 budgets; exploratory',
      'missingness':'abort primary analysis for any missing/duplicate/unmatched condition, invalid data, or failed source lock; no imputation',
      'numerical_failure':'abort and preserve failed artifact; reject nonfinite/negative measurement values and nonfinite/negative MART voxels',
      'time_memory_limits':'proposed engineering gates: process peak <=8 GiB; wall-clock ceilings not yet hardware-calibrated',
      'independent_forward_model':'shared latent phantom, separate ray-marching forward projector; not independent objects',
      'stopping':'no outcome-based early stopping or tuning; computational failures documented before rerun',
      'review_blockers':['power/precision rationale','practical relevance threshold approval',
                         'wall-clock ceilings','source lock and independent audit','scientific sign-off']
    }


def full_geometry_check(n:int=32,budget:int=2048,seeds=ACQUISITION_SEEDS):
    if n!=32 or budget!=2048:
        raise ValueError('08AJ-H full geometry is fixed to 32^3 and 2048 rays')
    t=time.perf_counter()
    A=system_matrix(n,4,TILTS).tocsr()
    build_s=time.perf_counter()-t
    results=[]
    for seed in seeds:
        t=time.perf_counter()
        orders,prefix=fair_orders(A,n=n,angles=4,seed=seed,budget=budget,warm=WARM,pool=16,batch=32)
        seconds=time.perf_counter()-t
        assert all(np.array_equal(orders[p][:WARM],prefix) for p in INDIVIDUAL)
        assert len(np.unique(orders['complete_view']//(n*n)))==2
        assert len(np.unique(orders['complete_view']))==budget
        results.append({'acquisition_seed':seed,'time_seconds':seconds,
                        'prefix_sha256':sha_array(prefix),
                        'order_sha256':{p:sha_array(x) for p,x in orders.items()},
                        'whole_view_ids':np.unique(orders['complete_view']//(n*n)).tolist(),
                        'all_four_individual_prefix_equal':True,'complete_view_has_two_full_views':True})
    return {'size':n,'candidate_rays':A.shape[0],'budget':budget,'matrix_build_seconds':build_s,
            'matrix_csr_bytes':int(A.data.nbytes+A.indices.nbytes+A.indptr.nbytes),
            'warm_prefix':WARM,'acquisition_seeds':results,'all_geometry_checks_pass':True}


def independent_ray_probe(n=32,count=16,seed=940101):
    """Bounded 32^3 independent-projector ray sample, no full catalogue, no MART."""
    if n!=32 or count<1 or count>64:
        raise ValueError('probe limited to 1..64 rays at 32^3')
    fine=full_resolution_pair('localized_defects',seed,n)[1]
    # Select deterministically spaced rays across full candidate list.
    total=n*n*4*len(TILTS)
    ids=np.linspace(0,total-1,count,dtype=int)
    selected=set(ids.tolist())
    t=time.perf_counter(); measurements=[]
    for idx,(o,d) in enumerate(rays(n,4,TILTS)):
        if idx in selected:
            measurements.append(march_ray(fine,np.asarray(o)*2,d,1.0,'linear')/2)
    elapsed=time.perf_counter()-t
    vals=np.asarray(measurements)
    if vals.shape!=(count,) or not np.isfinite(vals).all() or np.any(vals<0):
        raise AssertionError('invalid independent ray probe')
    return {'measured_probe_only':True,'n':n,'ray_count':count,'total_catalogue_rays':total,
            'elapsed_seconds':elapsed,'all_values_finite_nonnegative':True,
            'probe_sha256':sha_array(vals),
            'full_catalogue_runtime_measured':False,
            'note':'Includes iteration through ray descriptors; this is NOT a full-projector resource certification.'}


def run(output_dir, *, probe_rays=16, skip_geometry=False, skip_probe=False):
    root=Path(output_dir)
    if root.exists():
        raise FileExistsError('refusing to overwrite previous 08AJ-H preflight')
    root.mkdir(parents=True)
    status={'stage':STAGE,'complete':False,'frozen':False,'no_confirmatory_outcomes':True}
    (root/'run_status.json').write_text(json.dumps(status,indent=2)+'\n')
    try:
        history=historical_seed_review(Path(__file__).resolve().parent)
        noise_keys={f:{str(s):{model:measurement_seed(f,s,ACQUISITION_SEEDS[0],model)
                    for model in MODELS} for s in SEEDS[f]} for f in FAMILIES}
        report={'stage':STAGE,'complete':True,'frozen':False,'no_confirmatory_outcomes':True,
                'phantom_count':24,'family_counts':{f:len(SEEDS[f]) for f in FAMILIES},
                'historical_seed_review':history,'noise_key_uniqueness':len({v for fam in noise_keys.values() for rec in fam.values() for v in rec.values()})==48,
                'noise_pairing':'same object/seed/model maps to one noise seed, independent of policy',
                'statistical_rules':statistical_rules(),
                'geometry':None if skip_geometry else full_geometry_check(),
                'independent_ray_probe':None if skip_probe else independent_ray_probe(count=probe_rays),
                'source_sha256':{**hashes_of_sources(),Path(__file__).name:hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
                'lock_readiness':'NOT_READY',
                'open_items':['Historical seed-literal scan is not an exhaustive phantom-structure independence audit',
                              '32^3 full independent-model catalogue and all-family verification not yet established',
                              'Inference and resource ceilings require review and sign-off',
                              'Complete-view 64^3 2048-ray budget remains infeasible',
                              'Full resumable validation runner, independent audit and signed source lock pending']}
        if history['seed_literal_overlaps']:
            report['open_items'].append('Literal historical seed overlap detected; investigate before locking')
        (root/'lock_readiness_report.json').write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+'\n')
        status.update(complete=True,verdict='LOCK_READINESS_PREFLIGHT_PASS',lock_readiness='NOT_READY',open_items=len(report['open_items']))
        (root/'run_status.json').write_text(json.dumps(status,indent=2,sort_keys=True)+'\n')
        (root/'manifest.sha256').write_text(''.join(hashlib.sha256((root/f).read_bytes()).hexdigest()+f'  {f}\n' for f in ('lock_readiness_report.json','run_status.json')))
        print(json.dumps({'verdict':status['verdict'],'frozen':False,'no_confirmatory_outcomes':True,
                          'geometry_checked':report['geometry'] is not None,
                          'independent_ray_probe_checked':report['independent_ray_probe'] is not None,
                          'historical_literal_overlaps':history['seed_literal_overlaps'],
                          'open_items':len(report['open_items'])},indent=2))
        return report
    except Exception as e:
        status.update(verdict='FAIL',error=str(e))
        (root/'run_status.json').write_text(json.dumps(status,indent=2)+'\n')
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--probe-rays',type=int,default=16)
    p.add_argument('--skip-geometry',action='store_true',help='unit-test only')
    p.add_argument('--skip-probe',action='store_true',help='unit-test only')
    p.add_argument('--freeze',action='store_true')
    args=p.parse_args()
    if args.freeze:
        raise RuntimeError('REFUSE_TO_FREEZE: protocol scientific and runner blockers remain')
    run(args.output_dir,probe_rays=args.probe_rays,skip_geometry=args.skip_geometry,skip_probe=args.skip_probe)

if __name__=='__main__':
    main()
