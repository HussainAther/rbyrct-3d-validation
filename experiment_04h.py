"""Experiment 04H: Diagnose 04G coverage and test frozen, geometry-only alternatives.

This is an exploratory DEVELOPMENT benchmark. All policies are frozen before
reading any phantom measurements; evaluates multiple deterministic synthetic
phantoms and random seeds under a shared 04B matrix / 04F SIRT solver.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, time
from pathlib import Path
import numpy as np
from experiment_04b import phantom_3d, system_matrix
from experiment_04f import run_sirt
from experiment_04g import TILTS, policies, low_frequency_basis, geometry_ig_order


def phantom_family(n: int) -> dict[str, np.ndarray]:
    zz, yy, xx = np.meshgrid(*([(np.arange(n)+0.5-n/2)/(n/2)]*3), indexing='ij')
    ell = lambda x0,y0,z0,a,b,c: ((xx-x0)/a)**2 + ((yy-y0)/b)**2 + ((zz-z0)/c)**2 <= 1
    base=phantom_3d(n)
    shifted=(0.025 + 0.7*ell(0.16,-0.11,0.08,0.60,0.55,0.63)
             +0.40*ell(-0.18,0.22,-0.20,0.17,0.19,0.18)).astype(np.float64)
    multitarget=(0.025+0.48*ell(0,0,0,0.78,0.71,0.75)
                +0.6*ell(.30,.15,.10,.14,.16,.17)
                +0.40*ell(-.30,-.19,-.19,.17,.14,.14)
                -0.20*ell(.01,-.27,.24,.15,.14,.13)).astype(np.float64)
    layers=(0.025+0.58*ell(0,0,0,.75,.65,.78)
            +0.16*((np.abs(zz-.1)<.12)&ell(0,0,0,.75,.65,.78))
            +0.22*ell(.23,-.23,.14,.17,.11,.22)).astype(np.float64)
    return {'original':base, 'shifted':shifted, 'multitarget':multitarget, 'layers':layers}


def stratified_order(n: int, angles: int, tilts: int, seed: int) -> np.ndarray:
    """Round-robin across views; shuffle detector locations separately in each view."""
    rng=np.random.default_rng(seed)
    nviews=angles*tilts
    views=rng.permutation(nviews)
    perms=np.stack([rng.permutation(n*n) for _ in range(nviews)])
    ids=np.empty(nviews*n*n,dtype=np.int64)
    for k in range(n*n):
        ids[k*nviews:(k+1)*nviews]=views*(n*n)+perms[views,k]
    return ids


def voxel_coverage_order(A, n:int, angles:int, tilts:int, budget:int,
                         seed:int, candidate_pool:int=64, alpha:float=0.25) -> np.ndarray:
    """Greedy ray paths that cover under-observed voxels; geometry only.

    Stochastic candidate subpool is reproducible, avoids an O(rays^2) search.
    Per-ray score is path-length-weighted inverse accumulated voxel coverage,
    with a view-count diversity factor. Not exact info gain or feedback.
    """
    if not 1 <= budget <= A.shape[0] or candidate_pool < 1 or alpha <= 0:
        raise ValueError('invalid coverage parameters')
    rng=np.random.default_rng(seed)
    remaining=np.arange(A.shape[0],dtype=np.int64)
    counts=np.zeros(A.shape[1],dtype=np.float64)
    viewcounts=np.zeros(tilts*angles,dtype=np.int64)
    row_sums=np.asarray(A.sum(axis=1)).ravel()
    out=np.empty(budget,dtype=np.int64)
    for step in range(budget):
        sampleidx=rng.choice(len(remaining),size=min(candidate_pool,len(remaining)),replace=False)
        candidates=remaining[sampleidx]
        scored=[]
        for ray in candidates:
            lo,hi=A.indptr[ray],A.indptr[ray+1]
            vox=A.indices[lo:hi]; weights=A.data[lo:hi]
            view=int(ray)//(n*n)
            value=(float(np.dot(weights,1/(alpha+counts[vox])))/max(row_sums[ray],1e-12)
                   if len(vox) else 0.) / np.sqrt(1.0+viewcounts[view])
            scored.append(value)
        max_score=max(scored)
        tied=[int(ray) for ray,score in zip(candidates,scored) if np.isclose(score,max_score,rtol=1e-13,atol=1e-14)]
        chosen=min(tied)
        out[step]=chosen
        lo,hi=A.indptr[chosen],A.indptr[chosen+1]
        counts[A.indices[lo:hi]]+=A.data[lo:hi]
        viewcounts[chosen//(n*n)]+=1
        remaining=remaining[remaining!=chosen]
    return out


def coverage(A, order:np.ndarray, n:int, angles:int, tilts:int, budget:int)->dict:
    ids=order[:budget]
    nviews=angles*tilts
    view_ids=ids//(n*n)
    counts=np.bincount(view_ids,minlength=nviews)
    tilt_counts=np.bincount(view_ids//angles,minlength=tilts)
    det=ids%(n*n)
    det_counts=np.bincount(det,minlength=n*n)
    selected=A[ids]
    vox=np.asarray(selected.getnnz(axis=0)).ravel()
    vcover=np.asarray(selected.sum(axis=0)).ravel()
    return {'views_hit':int(np.count_nonzero(counts)),
            'min_rays_per_view':int(counts.min()), 'max_rays_per_view':int(counts.max()),
            'view_count_cv':float(counts.std()/max(counts.mean(),1e-12)),
            'tilt_counts':json.dumps(tilt_counts.tolist()),
            'unique_detector_cells':int(np.count_nonzero(det_counts)),
            'detector_count_cv':float(det_counts.std()/max(det_counts.mean(),1e-12)),
            'covered_voxels':int(np.count_nonzero(vox)),
            'zero_coverage_voxels':int(np.count_nonzero(vox==0)),
            'voxel_pathlength_cv':float(vcover.std()/max(vcover.mean(),1e-12)),
            'ray_length_mean':float(np.asarray(selected.sum(axis=1)).mean())}


def write_csv(path, rows):
    if not rows:return
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--size',type=int,default=16)
    p.add_argument('--angles',type=int,default=12)
    p.add_argument('--budgets',type=int,nargs='+',default=[512,1024,2048,4096])
    p.add_argument('--sirt-iterations',type=int,default=400)
    p.add_argument('--seeds',type=int,nargs='+',default=[104729,130363,155921])
    p.add_argument('--phantoms',nargs='+',default=['original','shifted','multitarget','layers'])
    p.add_argument('--ig-basis-side',type=int,default=3)
    p.add_argument('--ig-batch',type=int,default=16)
    p.add_argument('--candidate-pool',type=int,default=64)
    p.add_argument('--output-dir',type=Path,default=Path('results/experiment04h'))
    args=p.parse_args()
    total=len(TILTS)*args.angles*args.size**2
    if args.size<4 or args.angles<2 or args.sirt_iterations<1 or min(args.budgets)<1 or max(args.budgets)>total or not args.seeds or args.candidate_pool<1 or not 1<=args.ig_basis_side<=args.size:
        p.error('invalid experiment configuration')
    phantoms=phantom_family(args.size)
    if any(name not in phantoms for name in args.phantoms):p.error(f'phantoms must be among {list(phantoms)}')
    out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    t=time.perf_counter();A=system_matrix(args.size,args.angles,TILTS).tocsr()
    print(f'04H — 3D geometry-only acquisition diagnostics\nvolume={args.size}^3 rays={A.shape[0]} nnz={A.nnz} build_s={time.perf_counter()-t:.2f}')
    t=time.perf_counter()
    basis=low_frequency_basis(args.size,args.ig_basis_side)
    ig=geometry_ig_order(A,basis,max(args.budgets),args.ig_batch)
    ig_s=time.perf_counter()-t
    coverage_records=[]; metrics=[]; order_records=[]
    for seed in args.seeds:
        originals=policies(args.size,args.angles,len(TILTS),seed)
        originals['fixed_approx_information_gain']=ig
        originals['stratified_random']=stratified_order(args.size,args.angles,len(TILTS),seed)
        t=time.perf_counter()
        originals['voxel_coverage_greedy']=voxel_coverage_order(A,args.size,args.angles,len(TILTS),max(args.budgets),seed,args.candidate_pool)
        greedy_s=time.perf_counter()-t
        for budget in sorted(set(args.budgets)):
            for policy,order in originals.items():
                ids=order[:budget]
                if len(set(ids.tolist()))!=budget or min(ids)<0 or max(ids)>=total:raise AssertionError('duplicate/invalid ray')
                order_hash=hashlib.sha256(ids.astype('<i8').tobytes()).hexdigest()
                d=dict(seed=seed,budget=budget,policy=policy,order_hash=order_hash)
                coverage_records.append({**d,**coverage(A,order,args.size,args.angles,len(TILTS),budget)})
                order_records.append({**d,'selection_s':ig_s if policy=='fixed_approx_information_gain' else greedy_s if policy=='voxel_coverage_greedy' else 0.0})
                subset=A[ids].tocsr()
                for pname in args.phantoms:
                    target=phantoms[pname].ravel()
                    # Acquire ONLY the selected projection rows. No other target measurements are passed to the solver.
                    b=subset@target
                    _,h=run_sirt(subset,b,target,args.sirt_iterations,1.0,[args.sirt_iterations])
                    r=h[-1]
                    metrics.append({**d,'phantom':pname,'rmse':r['rmse'],
                        'acquired_residual':r['relative_projection_residual'],
                        'solver_s':r['elapsed_s']})
                    print(f'{pname:12} seed={seed} rays={budget:4} {policy:31} RMSE={r["rmse"]:.6f}')
    write_csv(out/'metrics.csv',metrics)
    write_csv(out/'coverage.csv',coverage_records)
    write_csv(out/'orders.csv',order_records)
    groups={}
    for r in metrics:
        key=(r['budget'],r['policy'])
        groups.setdefault(key,[]).append(r['rmse'])
    summaries=[{'budget':b,'policy':policy,'n':len(v),'mean_rmse':float(np.mean(v)),'median_rmse':float(np.median(v))}
               for (b,policy),v in sorted(groups.items())]
    write_csv(out/'summary.csv',summaries)
    (out/'protocol.json').write_text(json.dumps({'experiment':'04H','size':args.size,'angles':args.angles,
       'tilts':TILTS,'budgets':sorted(set(args.budgets)),'seeds':args.seeds,'phantoms':args.phantoms,
       'sirt_iterations':args.sirt_iterations,'candidate_pool':args.candidate_pool,
       'ig_basis_side':args.ig_basis_side,'ig_batch':args.ig_batch,
       'limitations':['All synthetic development phantoms; no independent external validation',
       'No measurement-adaptive acquisition, no photon noise, no dose claim',
       'IG policy unchanged from 04G; greedy policy exploratory and geometry-only',
       'Repeated seeds for deterministic policies are not independent replicates',
       'Greedy selection overhead measured once and amortized over budgets and phantoms',
       'Solver results use exact same sparse CPU system matrix as 04F']},indent=2),encoding='utf-8')
    print(f'Completed {len(metrics)} reconstructions; results: {out}')
if __name__=='__main__':main()
