"""04I: held-out phantom / Gaussian projection noise robustness of frozen 04H policies.

Requires experiment_04b.py, experiment_04f.py, experiment_04g.py,
experiment_04h.py beside this script. All reported methods are geometry-only.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import time
from pathlib import Path
import numpy as np
from experiment_04b import system_matrix
from experiment_04f import run_sirt
from experiment_04g import TILTS, policies
from experiment_04h import stratified_order, voxel_coverage_order, coverage


def heldout_phantoms(n: int) -> dict[str, np.ndarray]:
    """New analytical shapes, not the 04H ellipsoid-based test families."""
    z, y, x = np.meshgrid(*([(np.arange(n) + .5 - n/2) / (n/2)] * 3), indexing='ij')
    rxy = np.sqrt((x + .045)**2 + (y - .035)**2)
    r3 = np.sqrt(x*x+y*y+z*z)
    # Annular shell with an off-axis tunnel and a small bright inclusion.
    shell = .025 + .58 * ((r3 > .40) & (r3 < .79)) * (rxy > .18)
    shell += .31 * (((x-.32)**2+(y+.20)**2+(z-.16)**2) < .11**2)
    # Non-ellipsoidal cross of rods with a spatial density gradient.
    bars = ((abs(x) < .17) & (abs(y) < .17) & (abs(z) < .79)) | ((abs(y+.12)<.13)&(abs(z-.15)<.14)&(abs(x)<.73))
    cross = .025 + bars * (.28 + .35 * (z+1)/2)
    # Alternating smooth density bands and localized off-axis lesions.
    slab = (abs(z) < .70) & (abs(x) < .70) & (abs(y) < .65)
    bands = .025 + slab*(.18 + .29*(np.sin(8*x+3*z)**2))
    bands += .38*((x+.31)**2+(y-.25)**2+(z+.11)**2 < .13**2)
    # Non-axis-aligned tubular ribbon.
    tube_dist = np.sqrt((y-.30*np.sin(3*z))**2+(x-.30*np.cos(2.4*z))**2)
    ribbon = .025 + .65*((tube_dist<.17)&(abs(z)<.77)) + .16*((abs(y+x*.6)<.11)&(abs(z)<.5)&(abs(x)<.55))
    return {key: np.asarray(val, dtype=np.float64) for key, val in
            {'shell':shell, 'cross':cross, 'bands':bands, 'ribbon':ribbon}.items()}


def noisy_full_projection(clean: np.ndarray, level: float, seed: int) -> np.ndarray:
    """Additive Gaussian noise; sigma = level * RMS(clean full-projection data).

    Noise is generated over all candidate rays for paired comparisons but the
    reconstructor receives only selected indices. No clipping of negative values:
    the chosen SIRT solver supports signed Gaussian perturbations.
    """
    if level < 0: raise ValueError('noise level must be nonnegative')
    rms = float(np.sqrt(np.mean(clean**2)))
    return clean + level * rms * np.random.default_rng(seed).standard_normal(clean.shape)


def paired_summary(records: list[dict], comparator: str = 'random') -> list[dict]:
    from collections import defaultdict
    by_case = defaultdict(dict)
    for r in records:
        by_case[(r['phantom'], r['seed'], r['budget'], r['noise_fraction'])][r['policy']] = float(r['rmse'])
    groups = defaultdict(list)
    for key, methods in by_case.items():
        if comparator not in methods: continue
        for name, rmse in methods.items():
            if name == comparator: continue
            baseline=methods[comparator]
            groups[(key[2],key[3],name)].append((baseline-rmse)/max(baseline,1e-12))
    return [dict(budget=b, noise_fraction=noise, policy=name, versus=comparator,
                 n=len(values), wins=sum(v>0 for v in values),
                 mean_relative_rmse_gain=float(np.mean(values)),
                 median_relative_rmse_gain=float(np.median(values)),
                 min_relative_rmse_gain=float(np.min(values)))
            for (b,noise,name),values in sorted(groups.items())]


def write_csv(path: Path, records: list[dict]):
    if not records: return
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--size',type=int,default=16)
    p.add_argument('--angles',type=int,default=12)
    p.add_argument('--budgets',nargs='+',type=int,default=[512,1024,2048,4096])
    p.add_argument('--noise-fractions',nargs='+',type=float,default=[0.0,0.002,0.01])
    p.add_argument('--sirt-iterations',type=int,default=400)
    p.add_argument('--seeds',nargs='+',type=int,default=[104729,130363,155921])
    p.add_argument('--phantoms',nargs='+',default=['shell','cross','bands','ribbon'])
    p.add_argument('--candidate-pool',type=int,default=64)
    p.add_argument('--output-dir',type=Path,default=Path('results/experiment04i'))
    args=p.parse_args(argv)
    total=len(TILTS)*args.angles*args.size*args.size
    if (args.size<4 or args.angles<2 or args.sirt_iterations<1 or not args.budgets
        or min(args.budgets)<1 or max(args.budgets)>total or not args.seeds or not args.noise_fractions
        or min(args.noise_fractions)<0 or args.candidate_pool<1): p.error('invalid configuration')
    phantoms=heldout_phantoms(args.size)
    if not args.phantoms or any(q not in phantoms for q in args.phantoms):p.error('unknown phantom')
    out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    t=time.perf_counter();A=system_matrix(args.size,args.angles,TILTS).tocsr()
    print(f'04I — held-out geometry-only acquisition robustness\nvolume={args.size}^3 rays={total} nnz={A.nnz} matrix_s={time.perf_counter()-t:.2f}')
    metrics=[]; order_rows=[]; coverage_rows=[]
    for seed in args.seeds:
        fixed=policies(args.size,args.angles,len(TILTS),seed)
        # Freeze named rules and parameters from 04H; no tuning using held-out phantoms.
        selected={'random':fixed['random'],
                  'geometry_balanced':fixed['geometry_balanced'],
                  'stratified_random':stratified_order(args.size,args.angles,len(TILTS),seed)}
        t=time.perf_counter()
        selected['voxel_coverage_greedy']=voxel_coverage_order(A,args.size,args.angles,len(TILTS),max(args.budgets),seed,args.candidate_pool)
        greedy_s=time.perf_counter()-t
        for budget in sorted(set(args.budgets)):
            for policy, order in selected.items():
                ids=order[:budget]
                if len(np.unique(ids))!=budget: raise AssertionError('repeated ray selected')
                meta={'seed':seed,'budget':budget,'policy':policy,
                      'order_hash':hashlib.sha256(ids.astype('<i8').tobytes()).hexdigest()}
                order_rows.append({**meta,'selection_s':greedy_s if policy=='voxel_coverage_greedy' else 0.0,
                                  'selection_time_scope':'full_max_budget_order' if policy=='voxel_coverage_greedy' else 'unmeasured_baseline'})
                coverage_rows.append({**meta,**coverage(A,order,args.size,args.angles,len(TILTS),budget)})
                sub=A[ids].tocsr()
                for pname in args.phantoms:
                    truth=phantoms[pname].ravel()
                    clean=np.asarray(A@truth)
                    for noise in sorted(set(args.noise_fractions)):
                        # Stable, independent Gaussian realization per phantom, seed, noise.
                        # Same realization shared by all acquisition policies.
                        noise_seed=(seed+int(hashlib.sha256(f'{pname}:{noise:.12g}'.encode()).hexdigest()[:8],16))%(2**32)
                        observations=noisy_full_projection(clean,noise,noise_seed)[ids]
                        _,h=run_sirt(sub,observations,truth,args.sirt_iterations,1.0,[args.sirt_iterations])
                        result=h[-1]
                        metrics.append({**meta,'phantom':pname,'noise_fraction':noise,
                           'noise_sigma':float(noise*np.sqrt(np.mean(clean**2))),
                           'rmse':result['rmse'], 'acquired_residual':result['relative_projection_residual'],
                           'solver_s':result['elapsed_s']})
                        print(f'{pname:7} seed={seed} budget={budget:4} noise={noise:.3g} {policy:22} rmse={result["rmse"]:.6f}')
    write_csv(out/'metrics.csv',metrics)
    write_csv(out/'orders.csv',order_rows)
    write_csv(out/'coverage.csv',coverage_rows)
    group={}
    for r in metrics:
        key=(r['budget'],r['noise_fraction'],r['policy'])
        group.setdefault(key,[]).append(r['rmse'])
    write_csv(out/'summary.csv',[
        {'budget':b,'noise_fraction':noise,'policy':policy,'n':len(vals),
         'mean_rmse':float(np.mean(vals)),'median_rmse':float(np.median(vals))}
        for (b,noise,policy),vals in sorted(group.items())])
    write_csv(out/'paired_vs_random.csv',paired_summary(metrics))
    (out/'protocol.json').write_text(json.dumps({'experiment':'04I','stage':'held-out validation',
         'volume_size':args.size,'angles':args.angles,'tilts':TILTS,'budgets':sorted(set(args.budgets)),
         'noise_fractions':sorted(set(args.noise_fractions)),
         'noise_definition':'independent Gaussian per full ray, sigma=fraction*RMS(clean full candidate sinogram)',
         'phantoms':args.phantoms,'seeds':args.seeds,'sirt_iterations':args.sirt_iterations,
         'candidate_pool':args.candidate_pool,'policies':['random','geometry_balanced','stratified_random','voxel_coverage_greedy'],
         'limitations':['Analytical held-out phantoms, no external datasets or physical dose model',
         'Synthetic Gaussian projection noise, not photon-counting Poisson noise',
         'Seed repeats for geometry_balanced do not constitute independent observations',
         'Each new phantom is a handcrafted synthetic structure',
         'Geometry-only rules; no measurement-dependent adaptive acquisition',
         'Selection overhead is not included in SIRT solver runtime',
         'The selection time for greedy is for full max-budget order and must not be read as per-budget selection time']},indent=2),encoding='utf-8')
    print(f'Completed {len(metrics)} reconstructions; results: {out}')

if __name__=='__main__': main()
