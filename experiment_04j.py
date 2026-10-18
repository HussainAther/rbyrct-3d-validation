"""Experiment 04J: first measurement-feedback 3D scalar-ray acquisition pilot.

Uses the matched 04B Siddon matrix and frozen 04I phantoms/policies. A fixed
04H greedy warm start is followed by repeated partial SIRT and acquisition
based on gradients of the *measured-data reconstruction*. No unacquired
measurements are read by the selector. Baseline reuses frozen greedy prefix.

This is exploratory. The score is heuristic, not Bayesian information gain.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, time
from pathlib import Path
import numpy as np
from experiment_04b import system_matrix
from experiment_04g import TILTS, policies
from experiment_04h import voxel_coverage_order, coverage
from experiment_04i import heldout_phantoms, noisy_full_projection, paired_summary


def sirt_silent(A, b, iterations, initial=0.3):
    """Same row/column normalization and positivity constraint as 04F."""
    A=A.tocsr(); b=np.asarray(b, dtype=np.float64)
    row=np.asarray(A.sum(axis=1)).ravel(); col=np.asarray(A.sum(axis=0)).ravel()
    invrow=np.divide(1.,row,out=np.zeros_like(row),where=row>0)
    invcol=np.divide(1.,col,out=np.zeros_like(col),where=col>0)
    x=np.full(A.shape[1],initial,dtype=np.float64)
    for _ in range(iterations):
        x=np.maximum(x+invcol*(A.T@((b-A@x)*invrow)),0.0)
    return x


def image_score(x,n):
    """Data-derived local feature magnitude, positive even in flat regions."""
    v=np.asarray(x).reshape(n,n,n)
    dz,dy,dx=np.gradient(v)
    g=np.sqrt(dx*dx+dy*dy+dz*dz)
    # Spatial uncertainty proxy: emphasize reconstructed edges, not truth.
    return 0.05+g.ravel()/max(float(np.mean(g)),1.e-8)


def score_candidates(A,candidates,counts,viewcounts,n,features,coverage_alpha=0.25,
                     feedback_strength=1.0):
    """No dependence on future measurements; geometry counts + current estimate."""
    out=[]
    for ray in candidates:
        lo,hi=A.indptr[ray],A.indptr[ray+1]
        idx=A.indices[lo:hi]; weights=A.data[lo:hi]
        view=int(ray)//(n*n)
        if not len(idx):out.append(0.);continue
        f=1.0+feedback_strength*(features[idx]-1.0)
        f=np.maximum(f,0.05)
        value=float(np.dot(weights,f/(coverage_alpha+counts[idx])))/max(float(weights.sum()),1e-12)
        out.append(value/np.sqrt(1.+viewcounts[view]))
    return np.asarray(out)


def adaptive_order(A, observations, n, angles, warm_order, budget, seed,
                   warm_rays=128, batch=64, provisional_iterations=60,
                   candidate_pool=64, feedback_strength=1.0):
    """Returns selected ray IDs and trace. Only observations[acquired IDs] accessed.

    observations is a synthetic measurement oracle. It is indexed only at
    already selected IDs, after the corresponding batch is committed.
    """
    if warm_rays<1 or warm_rays>=budget or batch<1 or candidate_pool<1 or provisional_iterations<1 or feedback_strength<0:
        raise ValueError('invalid adaptive parameters')
    rng=np.random.default_rng(seed+317)
    order=list(np.asarray(warm_order[:warm_rays],dtype=np.int64))
    remaining=np.ones(A.shape[0],dtype=bool);remaining[order]=False
    counts=np.asarray(A[order].sum(axis=0)).ravel().astype(float)
    viewcounts=np.bincount(np.asarray(order)//(n*n),minlength=angles*len(TILTS)).astype(int)
    trace=[]
    elapsed=time.perf_counter()
    while len(order)<budget:
        ids=np.asarray(order,dtype=np.int64)
        # Only previously acquired measurements influence this estimate.
        x=sirt_silent(A[ids],observations[ids],provisional_iterations)
        features=image_score(x,n)
        target_count=min(batch,budget-len(order))
        for _ in range(target_count):
            available=np.flatnonzero(remaining)
            candidates=rng.choice(available,size=min(candidate_pool,len(available)),replace=False)
            scores=score_candidates(A,candidates,counts,viewcounts,n,features,
                                    feedback_strength=feedback_strength)
            high=np.max(scores)
            winners=candidates[np.isclose(scores,high,rtol=1e-13,atol=1e-14)]
            chosen=int(np.min(winners))
            order.append(chosen);remaining[chosen]=False
            lo,hi=A.indptr[chosen],A.indptr[chosen+1]
            counts[A.indices[lo:hi]]+=A.data[lo:hi]
            viewcounts[chosen//(n*n)]+=1
        trace.append(dict(acquired=len(order),next_batch_size=target_count,
                          provisional_iterations=provisional_iterations,
                          estimate_norm=float(np.linalg.norm(x)),
                          feature_std=float(features.std())))
    return np.asarray(order,dtype=np.int64),trace,time.perf_counter()-elapsed


def divergence(a,b,start=0):
    a=np.asarray(a)[start:];b=np.asarray(b)[start:]
    return dict(common_positions=int(np.count_nonzero(a==b)),
                same_set_fraction=float(len(set(a.tolist())&set(b.tolist()))/max(len(a),1)),
                sequence_identical=bool(np.array_equal(a,b)))


def write_csv(path,rows):
    if not rows:return
    with open(path,'w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--size',type=int,default=16)
    p.add_argument('--angles',type=int,default=12)
    p.add_argument('--budgets',nargs='+',type=int,default=[512,1024,2048])
    p.add_argument('--seeds',nargs='+',type=int,default=[104729,130363,155921])
    p.add_argument('--phantoms',nargs='+',default=['shell','cross','bands','ribbon'])
    p.add_argument('--noise-fractions',nargs='+',type=float,default=[0,0.002,0.01])
    p.add_argument('--warm-rays',type=int,default=128)
    p.add_argument('--batch',type=int,default=64)
    p.add_argument('--provisional-iterations',type=int,default=60)
    p.add_argument('--sirt-iterations',type=int,default=400)
    p.add_argument('--candidate-pool',type=int,default=64)
    p.add_argument('--feedback-strength',type=float,default=1.0)
    p.add_argument('--output-dir',type=Path,default=Path('results/experiment04j'))
    args=p.parse_args(argv)
    total=len(TILTS)*args.angles*args.size*args.size
    if (args.size<4 or args.angles<2 or not args.seeds or not args.budgets or
        args.warm_rays<1 or min(args.budgets)<=args.warm_rays or max(args.budgets)>total or
        args.batch<1 or args.candidate_pool<1 or args.provisional_iterations<1 or
        args.sirt_iterations<1 or args.feedback_strength<0 or not args.noise_fractions or
        min(args.noise_fractions)<0):p.error('invalid parameters')
    phantoms=heldout_phantoms(args.size)
    if not args.phantoms or any(q not in phantoms for q in args.phantoms):p.error('unknown phantom')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    start=time.perf_counter();A=system_matrix(args.size,args.angles,TILTS).tocsr()
    print(f'04J — genuine measurement-feedback adaptive acquisition\nvolume={args.size}^3 rays={A.shape[0]} nnz={A.nnz} matrix_s={time.perf_counter()-start:.2f}',flush=True)
    metrics=[];orders=[];divergences=[]; traces=[]; adaptive_sequences={}
    # Freeze one geometry-only max-budget schedule per seed, prior to seeing phantoms.
    for seed in args.seeds:
        begin=time.perf_counter()
        fixed=voxel_coverage_order(A,args.size,args.angles,len(TILTS),max(args.budgets),seed,args.candidate_pool)
        fixed_time=time.perf_counter()-begin
        baselines=policies(args.size,args.angles,len(TILTS),seed)
        for pname in args.phantoms:
            truth=phantoms[pname].ravel();clean=np.asarray(A@truth)
            for noise in sorted(set(args.noise_fractions)):
                noise_seed=(seed+int(hashlib.sha256(f'{pname}:{noise:.12g}'.encode()).hexdigest()[:8],16))%(2**32)
                noisy=noisy_full_projection(clean,noise,noise_seed)
                # Main adaptive sequence uses only data from the selected object.
                for budget in sorted(set(args.budgets)):
                    acquired,trace,selection_s=adaptive_order(A,noisy,args.size,args.angles,fixed,budget,seed,
                          args.warm_rays,args.batch,args.provisional_iterations,args.candidate_pool,args.feedback_strength)
                    assert len(acquired)==budget and len(np.unique(acquired))==budget
                    no_feedback,_,null_selection_s=adaptive_order(A,noisy,args.size,args.angles,fixed,budget,seed,
                          args.warm_rays,args.batch,args.provisional_iterations,args.candidate_pool,0.0)
                    adaptive_sequences[(seed,noise,budget,pname)]=acquired
                    for step in trace:
                        traces.append(dict(phantom=pname,noise_fraction=noise,seed=seed,budget=budget,**step))
                    compare={'adaptive_feedback':acquired,'feedback_off_control':no_feedback,'voxel_coverage_greedy':fixed[:budget],
                             'random':baselines['random'][:budget],
                             'geometry_balanced':baselines['geometry_balanced'][:budget]}
                    divergences.append(dict(phantom=pname,noise_fraction=noise,seed=seed,budget=budget,
                       comparator='fixed_greedy',**divergence(acquired,fixed[:budget],args.warm_rays)))
                    divergences.append(dict(phantom=pname,noise_fraction=noise,seed=seed,budget=budget,
                       comparator='feedback_off',**divergence(acquired,no_feedback,args.warm_rays)))
                    for policy,ids in compare.items():
                        t=time.perf_counter();sub=A[ids]
                        # Final evaluation uses exactly the selected data.
                        x=sirt_silent(sub,noisy[ids],args.sirt_iterations)
                        elapsed=time.perf_counter()-t
                        rmse=float(np.sqrt(np.mean((x-truth)**2)))
                        resid=float(np.linalg.norm(sub@x-noisy[ids])/max(np.linalg.norm(noisy[ids]),1.e-12))
                        metrics.append(dict(phantom=pname,seed=seed,budget=budget,noise_fraction=noise,
                                            policy=policy,rmse=rmse,acquired_residual=resid,solver_s=elapsed))
                        orders.append(dict(phantom=pname,seed=seed,budget=budget,noise_fraction=noise,
                                           policy=policy,order_hash=hashlib.sha256(ids.astype('<i8').tobytes()).hexdigest(),
                                           selection_s=selection_s if policy=='adaptive_feedback' else null_selection_s if policy=='feedback_off_control' else fixed_time if policy=='voxel_coverage_greedy' else 0,
                                           timing_note='online per budget' if policy in ('adaptive_feedback','feedback_off_control') else 'fixed full max-budget order' if policy=='voxel_coverage_greedy' else 'baseline ordering not timed',
                                           **coverage(A,ids,args.size,args.angles,len(TILTS),budget)))
                        print(f'{pname:7} seed={seed} rays={budget:4} noise={noise:.3g} {policy:22} rmse={rmse:.6f}',flush=True)
    # Explicit object-swap audit: with the same seed and noise, do different
    # measured objects lead to different *post-warm-start* ray selections?
    object_swaps=[]
    for seed in args.seeds:
        for noise in sorted(set(args.noise_fractions)):
            for budget in sorted(set(args.budgets)):
                for i,pname in enumerate(args.phantoms):
                    for other in args.phantoms[i+1:]:
                        object_swaps.append(dict(seed=seed,noise_fraction=noise,budget=budget,
                            phantom_a=pname,phantom_b=other,
                            **divergence(adaptive_sequences[(seed,noise,budget,pname)],
                                         adaptive_sequences[(seed,noise,budget,other)],args.warm_rays)))
    write_csv(args.output_dir/'object_swap.csv',object_swaps)
    write_csv(args.output_dir/'metrics.csv',metrics)
    write_csv(args.output_dir/'orders.csv',orders)
    write_csv(args.output_dir/'adaptive_trace.csv',traces)
    write_csv(args.output_dir/'divergence.csv',divergences)
    write_csv(args.output_dir/'paired_vs_random.csv',paired_summary(metrics))
    write_csv(args.output_dir/'paired_vs_feedback_off.csv',paired_summary(metrics,'feedback_off_control'))
    # include direct comparison to frozen greedy
    write_csv(args.output_dir/'paired_vs_greedy.csv',paired_summary(metrics,'voxel_coverage_greedy'))
    groups={}
    for r in metrics:groups.setdefault((r['budget'],r['noise_fraction'],r['policy']),[]).append(r['rmse'])
    write_csv(args.output_dir/'summary.csv',[dict(budget=b,noise_fraction=n,policy=p,n=len(v),mean_rmse=float(np.mean(v)))
                                            for (b,n,p),v in sorted(groups.items())])
    (args.output_dir/'protocol.json').write_text(json.dumps(dict(experiment='04J',design='exploratory closed-loop pilot',
         parameters={k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()},
         forward_operator='04B CSR Siddon',reconstructor='04F same row/column normalized SIRT',
         measurement_leakage_rule='adaptive selector indexes only observed rays; full clean/noisy array is an oracle, never passed wholesale to selector except as indexable simulation source',
         limitation=['Synthetic measurements, not a physical steerable X-ray system','Gradient scoring is heuristic, not calibrated uncertainty or information gain',
         'Adaptive selection cost includes repeated provisional SIRT, and final SIRT is restarted from uniform initialization',
         'Policies assessed on previous 04I phantom families; this is an exploratory development study, not a new independent held-out validation',
         'Object-swap audit reports data-dependence; a policy may remain unchanged for some objects, seeds and budgets',
         'Full noise oracle is generated for paired simulation but only acquired indices are read during adaptive acquisition']),indent=2),encoding='utf-8')
    print(f'Completed {len(metrics)} reconstructions; results: {args.output_dir}',flush=True)

if __name__=='__main__':main()
