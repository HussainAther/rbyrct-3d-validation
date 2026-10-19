"""04O-C prospective reliability-gated ray acquisition pilot.

Frozen 04J selection score/candidate RNG; online strength only changes by
an acquired-only holdout diagnostic. Thresholds are preregistered CLI options,
not tuned on this experiment's truth. Synthetic-only exploratory pilot.
"""
from __future__ import annotations
import argparse,csv,json,time
from pathlib import Path
import numpy as np
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_04i import noisy_full_projection
from experiment_04j import adaptive_order, sirt_silent, image_score, score_candidates, divergence
from experiment_04k import noise_seed_for
from experiment_04m import high_resolution_matrix
from experiment_04n import object_pair
from experiment_04o import acquired_only_reliability

POLICIES=('adaptive_feedback','feedback_off_control','constant_feedback','reliability_gate')

class AcquiredOnly:
    """Fails loudly if code tries to read an unacquired measurement."""
    def __init__(self,observed):
        self.values=np.asarray(observed);self.allowed=set()
    def commit(self,ids):
        self.allowed.update(int(i) for i in ids)
    def __getitem__(self,ids):
        arr=np.asarray(ids,dtype=np.int64)
        if not all(int(i) in self.allowed for i in arr.ravel()):
            raise AssertionError('attempt to access unacquired measurement')
        return self.values[ids]


def online_order(A,observed,n,angles,warm_order,budget,seed,*,policy='reliability_gate',
                 warm_rays=128,batch=64,provisional_iterations=60,candidate_pool=64,
                 diagnostic_iterations=60,holdout_fraction=.2,threshold=2.0,
                 gate_strength=0.,constant_strength=.25,diagnostic_every=256):
    """Acquired-only prospective policy; returns order, audit, selection seconds.

    Same candidate sampling, score_candidates and prefix reconstruction as 04J.
    Gate recomputes its holdout score only at a predeclared acquisition cadence.
    Previous gate strength is used between diagnostics. No truth is passed in.
    """
    if policy not in POLICIES or warm_rays<12 or budget<=warm_rays or budget>A.shape[0] or batch<1 or candidate_pool<1 or diagnostic_every<1 or threshold<=0 or not 0<holdout_fraction<.5 or not 0<=gate_strength<=1 or not 0<=constant_strength<=1:
        raise ValueError('invalid online policy parameters')
    from experiment_04j import score_candidates as frozen_score
    rng=np.random.default_rng(seed+317)
    order=list(map(int,warm_order[:warm_rays]))
    if len(set(order))!=len(order):raise ValueError('duplicate warm rays')
    oracle=AcquiredOnly(observed);oracle.commit(order)
    remaining=np.ones(A.shape[0],bool);remaining[order]=False
    counts=np.asarray(A[order].sum(axis=0)).ravel().astype(float)
    viewcounts=np.bincount(np.asarray(order)//(n*n),minlength=angles*len(TILTS)).astype(int)
    audit=[];last_check=-diagnostic_every;strength=1.
    start=time.perf_counter()
    while len(order)<budget:
        ids=np.asarray(order,dtype=np.int64)
        if policy=='reliability_gate' and (not audit or len(order)-last_check>=diagnostic_every):
            sig=acquired_only_reliability(A,oracle,ids,n,diagnostic_iterations,holdout_fraction,seed+len(ids)*13)
            strength=gate_strength if sig['heldout_nrmse']>threshold else 1.
            last_check=len(order)
            audit.append(dict(acquired_before=len(order),**sig,threshold=threshold,feedback_strength_next=strength))
        elif policy=='adaptive_feedback':strength=1.
        elif policy=='feedback_off_control':strength=0.
        elif policy=='constant_feedback':strength=constant_strength
        x=sirt_silent(A[ids],oracle[ids],provisional_iterations)
        feat=image_score(x,n)
        count=min(batch,budget-len(order))
        for _ in range(count):
            available=np.flatnonzero(remaining)
            candidates=rng.choice(available,size=min(candidate_pool,len(available)),replace=False)
            scores=frozen_score(A,candidates,counts,viewcounts,n,feat,feedback_strength=strength)
            high=np.max(scores)
            chosen=int(np.min(candidates[np.isclose(scores,high,rtol=1e-13,atol=1e-14)]))
            order.append(chosen);remaining[chosen]=False
            lo,hi=A.indptr[chosen],A.indptr[chosen+1]
            counts[A.indices[lo:hi]]+=A.data[lo:hi]
            viewcounts[chosen//(n*n)]+=1
        oracle.commit(order[-count:])
    return np.asarray(order,dtype=np.int64),audit,time.perf_counter()-start


def save(path,rows):
    if not rows:return
    with Path(path).open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def paired_table(metrics):
    cases={}
    for row in metrics:
        key=tuple(row[k] for k in ('object_type','offset','phantom','seed','budget','noise_fraction'))
        cases.setdefault(key,{})[row['policy']]=row['rmse']
    out=[]
    for key,group in sorted(cases.items()):
        if set(group)!=set(POLICIES):raise ValueError('missing policy in case')
        for candidate in ('adaptive_feedback','constant_feedback','reliability_gate'):
            off=group['feedback_off_control'];v=group[candidate]
            out.append(dict(**dict(zip(('object_type','offset','phantom','seed','budget','noise_fraction'),key)),
                policy=candidate,rmse=v,feedback_off_rmse=off,relative_gain=(off-v)/max(off,1e-12),win=int(v<off)))
    return out


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--size',type=int,default=16);p.add_argument('--angles',type=int,default=12);p.add_argument('--factor',type=int,default=2)
    p.add_argument('--object-types',nargs='+',choices=['replicated','subvoxel'],default=['replicated','subvoxel'])
    p.add_argument('--offsets',nargs='+',type=float,default=[0.,.15])
    p.add_argument('--phantoms',nargs='+',choices=['torus','slats','beads','wedges'],default=['torus','slats','beads','wedges'])
    p.add_argument('--seeds',nargs='+',type=int,default=[104729]);p.add_argument('--budgets',nargs='+',type=int,default=[512,1024,2048])
    p.add_argument('--noise-fractions',nargs='+',type=float,default=[0.])
    p.add_argument('--warm-rays',type=int,default=128);p.add_argument('--batch',type=int,default=64)
    p.add_argument('--provisional-iterations',type=int,default=60);p.add_argument('--diagnostic-iterations',type=int,default=60)
    p.add_argument('--sirt-iterations',type=int,default=400);p.add_argument('--candidate-pool',type=int,default=64)
    p.add_argument('--threshold',type=float,default=2.0,help='Predeclared diagnostic held-out NRMSE gate threshold; NOT validated')
    p.add_argument('--gate-strength',type=float,default=0.0,help='Feedback strength on high error')
    p.add_argument('--constant-strength',type=float,default=.25)
    p.add_argument('--diagnostic-every',type=int,default=256)
    p.add_argument('--holdout-fraction',type=float,default=.2)
    p.add_argument('--output-dir',type=Path,default=Path('results/experiment04oc'))
    a=p.parse_args(argv)
    total=len(TILTS)*a.angles*a.size*a.size
    if a.size<4 or a.angles<2 or a.factor<2 or not a.offsets or min(a.offsets)<0 or not a.budgets or min(a.budgets)<=a.warm_rays or max(a.budgets)>total or not a.seeds or not a.phantoms or not a.noise_fractions or min(a.noise_fractions)<0 or a.provisional_iterations<1 or a.sirt_iterations<1 or a.diagnostic_iterations<1 or a.candidate_pool<1 or a.batch<1 or a.warm_rays<12 or not 0<a.holdout_fraction<.5 or a.diagnostic_every<1 or a.threshold<=0 or not 0<=a.gate_strength<=1 or not 0<=a.constant_strength<=1:p.error('invalid parameters')
    a.output_dir.mkdir(parents=True,exist_ok=True)
    A=system_matrix(a.size,a.angles,TILTS).tocsr()
    ops={offset:high_resolution_matrix(a.size,a.angles,TILTS,a.factor,offset) for offset in sorted(set(a.offsets))}
    objects={name:object_pair(name,a.size,a.factor) for name in a.phantoms}
    fixed={seed:voxel_coverage_order(A,a.size,a.angles,len(TILTS),max(a.budgets),seed,a.candidate_pool) for seed in a.seeds}
    metrics=[];audits=[];comparisons=[];timing=[]
    for objtype in a.object_types:
      for phantom in a.phantoms:
       truth,fine=objects[phantom][objtype]
       for offset,M in ops.items():
        clean=np.asarray(M@fine).ravel()
        for seed in a.seeds:
         for noise in a.noise_fractions:
          observed=noisy_full_projection(clean,noise,noise_seed_for(seed,phantom,noise))
          for budget in sorted(set(a.budgets)):
           orders={}
           for policy in POLICIES:
            ids,audit,selection_s=online_order(A,observed,a.size,a.angles,fixed[seed],budget,seed,policy=policy,
                warm_rays=a.warm_rays,batch=a.batch,provisional_iterations=a.provisional_iterations,
                diagnostic_iterations=a.diagnostic_iterations,candidate_pool=a.candidate_pool,
                holdout_fraction=a.holdout_fraction,threshold=a.threshold,gate_strength=a.gate_strength,
                constant_strength=a.constant_strength,diagnostic_every=a.diagnostic_every)
            if len(set(ids))!=budget:raise AssertionError('duplicate rays')
            orders[policy]=ids
            before=time.perf_counter();x=sirt_silent(A[ids],observed[ids],a.sirt_iterations)
            reconstruction_s=time.perf_counter()-before
            rmse=float(np.sqrt(np.mean((x-truth)**2)))
            record=dict(object_type=objtype,offset=offset,phantom=phantom,seed=seed,budget=budget,noise_fraction=noise,policy=policy,rmse=rmse)
            metrics.append(record)
            timing.append(dict(**record,selection_s=selection_s,reconstruction_s=reconstruction_s))
            audits.extend([dict(**{k:record[k] for k in ('object_type','offset','phantom','seed','budget','noise_fraction')},policy=policy,**v) for v in audit])
            print(f'{objtype:10s} offset={offset:g} {phantom:7s} b={budget:4d} {policy:20s} rmse={rmse:.6f}',flush=True)
           for policy in POLICIES[1:]:
            comparisons.append(dict(object_type=objtype,offset=offset,phantom=phantom,seed=seed,budget=budget,noise_fraction=noise,policy=policy,**divergence(orders['adaptive_feedback'],orders[policy],a.warm_rays)))
    pairs=paired_table(metrics)
    for filename,rows in [('metrics.csv',metrics),('paired_cases.csv',pairs),('gate_trace.csv',audits),('selection_timing.csv',timing),('divergence.csv',comparisons)]:save(a.output_dir/filename,rows)
    (a.output_dir/'protocol.json').write_text(json.dumps(dict(experiment='04O-C',parameters={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},limitations=['Synthetic only','Gate threshold predeclared heuristic, not validated','Holdout samples from adaptively selected acquired rays','No new independent phantom families','Not a clinical or dose validation','No ground-truth oracle used during selection']),indent=2),encoding='utf8')
    print(f'04O-C completed {len(metrics)} reconstructions and {len(pairs)//3} matched cases; output={a.output_dir}',flush=True)

if __name__=='__main__':main()
