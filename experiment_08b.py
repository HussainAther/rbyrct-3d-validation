"""RBYRCT-08B: acquired-only integration of the 08A incremental coverage guard.

DEVELOPMENT-ONLY acquisition mechanics. No reconstruction-quality endpoint, defect
mask, 06B/07C2 objects, or frozen validation results are loaded. 08A lambda=.25
is carried forward unchanged. The manufactured positive signal is used ONLY to
make an observation oracle, not supplied to a selector.
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
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_05b_04 import select_order
from experiment_05b_adaptive import score_candidates, image_score
from experiment_05b_gate import AcquiredOnly
from experiment_05b_mart import mart_reconstruct
from experiment_08a import incremental_variance, incremental_eligibility, NEW_LAMBDA

ANGLES=4
SIGNAL_SEEDS=(808201, 808202)
ACQUISITION_SEED=808311
DEFAULTS={12:dict(budget=288,warm=24,batch=16,pool=16,epochs=2),
          32:dict(budget=1024,warm=64,batch=32,pool=16,epochs=2)}
RELAXATION=.25
POLICIES=('coverage','gradient','incremental_25')


def select_incremental(A, observations, n, angles, warm_order, budget, seed, *,
                       warm_rays, batch, candidate_pool, provisional_epochs,
                       relaxation=RELAXATION, lam=NEW_LAMBDA):
    """Online selector; observations indexed only for already committed IDs.

    Same RNG seed+317, candidate draw, gradient score and deterministic tie
    handling as experiment_05b_04.select_order. A coverage-score reference is
    guaranteed eligible by experiment_08a.incremental_eligibility.
    """
    A=A.tocsr()
    if A.shape!=(n*n*angles*len(TILTS),n**3):
        raise ValueError('geometry mismatch')
    if not (0<warm_rays<budget<=A.shape[0] and min(batch,candidate_pool,provisional_epochs)>=1
            and np.isfinite(relaxation) and 0<relaxation<=1 and np.isfinite(lam) and 0<=lam<=1):
        raise ValueError('invalid acquisition configuration')
    warm=np.asarray(warm_order[:warm_rays],dtype=np.int64)
    if len(warm)!=warm_rays or len(set(warm.tolist()))!=len(warm) or (warm<0).any() or (warm>=A.shape[0]).any():
        raise ValueError('invalid warm history')
    order=list(map(int,warm))
    remaining=np.ones(A.shape[0],dtype=bool);remaining[warm]=False
    counts=np.asarray(A[warm].sum(axis=0)).ravel().astype(float)
    views=np.bincount(warm//(n*n),minlength=angles*len(TILTS)).astype(int)
    rng=np.random.default_rng(seed+317)
    audit=[]
    start=time.perf_counter()
    while len(order)<budget:
        acquired=np.asarray(order,dtype=np.int64)
        x=mart_reconstruct(A[acquired], observations[acquired], provisional_epochs,
                           relaxation=relaxation)
        features=image_score(x,n)
        b=min(batch,budget-len(order)); choices=[]
        for _ in range(b):
            available=np.flatnonzero(remaining)
            cand=np.asarray(rng.choice(available,size=min(candidate_pool,len(available)),replace=False),dtype=np.int64)
            coverage=score_candidates(A,cand,counts,views,n,np.ones(A.shape[1]),feedback_strength=0.)
            gradient=score_candidates(A,cand,counts,views,n,features,feedback_strength=1.)
            if not np.isfinite(coverage).all() or not np.isfinite(gradient).all():
                raise ArithmeticError('nonfinite candidate score')
            ref_ties=np.flatnonzero(np.isclose(coverage,coverage.max(),rtol=1e-13,atol=1e-14))
            ref=int(min(ref_ties,key=lambda j:int(cand[j])))
            delta=incremental_variance(A,cand,counts)
            eligible,threshold,spread=incremental_eligibility(delta,ref,lam)
            gradient_ties=np.flatnonzero(np.isclose(gradient,gradient.max(),rtol=1e-13,atol=1e-14))
            unconstrained=int(min(gradient_ties,key=lambda j:int(cand[j])))
            best=float(gradient[eligible].max())
            chosen_ties=np.flatnonzero(eligible & np.isclose(gradient,best,rtol=1e-13,atol=1e-14))
            pos=int(min(chosen_ties,key=lambda j:int(cand[j])))
            chosen=int(cand[pos])
            choices.append(dict(eligible=int(eligible.sum()),pool=len(cand),
                                binding=int(not eligible.all()),
                                intervention=int(chosen!=int(cand[unconstrained])),
                                selected_reference=int(pos==ref),
                                range=float(spread),threshold=float(threshold)))
            order.append(chosen);remaining[chosen]=False
            lo,hi=A.indptr[chosen:chosen+2]
            counts[A.indices[lo:hi]]+=A.data[lo:hi]
            views[chosen//(n*n)]+=1
        if hasattr(observations,'commit'):
            observations.commit(order[-b:])
        audit.append(dict(acquired_after=len(order),batch_choices=b,
                          binding_choices=sum(c['binding'] for c in choices),
                          intervention_choices=sum(c['intervention'] for c in choices),
                          reference_choices=sum(c['selected_reference'] for c in choices),
                          mean_eligible=float(np.mean([c['eligible'] for c in choices])),
                          min_eligible=min(c['eligible'] for c in choices)))
    return np.asarray(order,dtype=np.int64),audit,time.perf_counter()-start


def _signal(A,seed):
    # Generator is OUTSIDE selector and results never evaluate against this signal.
    rng=np.random.default_rng(seed)
    x=.10+.65*rng.random(A.shape[1])
    return np.asarray(A@x,dtype=float).ravel()


def _sha(order):
    return hashlib.sha256(np.asarray(order,dtype='<i8').tobytes()).hexdigest()


def run(output_dir, *, sizes=(12,32), signal_seeds=SIGNAL_SEEDS,
        configs=None, acquisition_seed=ACQUISITION_SEED):
    """No outcome-based tuning, no quality evaluation, no overwrite."""
    configs=DEFAULTS if configs is None else configs
    if not sizes or not signal_seeds or len(set(signal_seeds))!=len(signal_seeds):
        raise ValueError('invalid development dimensions or signal seeds')
    if any(int(s) in (104729,130363,707001) or 2077001<=int(s)<=2132434 for s in signal_seeds):
        raise ValueError('cannot reuse reserved frozen study seeds')
    out=Path(output_dir)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError('refusing to overwrite existing output')
    # Validate configuration before writing files.
    for n in sizes:
        if n not in configs:
            raise ValueError('unsupported size')
        cfg=configs[n]
        if not all(k in cfg for k in ('budget','warm','batch','pool','epochs')):
            raise ValueError('incomplete configuration')
        if not 0<cfg['warm']<cfg['budget']<=n*n*ANGLES*len(TILTS):
            raise ValueError('invalid budget')
    out.mkdir(parents=True,exist_ok=True)
    rows=[];batchrows=[]
    for n in sizes:
        cfg=configs[n]
        A=system_matrix(n,ANGLES,TILTS).tocsr()
        warm=voxel_coverage_order(A,n,ANGLES,len(TILTS),cfg['budget'],acquisition_seed+n,cfg['pool'])
        for signal_seed in signal_seeds:
            measured=_signal(A,int(signal_seed))
            orders={}
            for policy in POLICIES:
                oracle=AcquiredOnly(measured)
                oracle.commit(warm[:cfg['warm']])
                if policy=='incremental_25':
                    order,audit,seconds=select_incremental(A,oracle,n,ANGLES,warm,cfg['budget'],acquisition_seed+n,
                        warm_rays=cfg['warm'],batch=cfg['batch'],candidate_pool=cfg['pool'],
                        provisional_epochs=cfg['epochs'])
                else:
                    order,audit,seconds=select_order(A,oracle,n,ANGLES,warm,cfg['budget'],acquisition_seed+n,
                        policy=policy,warm_rays=cfg['warm'],batch=cfg['batch'],candidate_pool=cfg['pool'],
                        provisional_epochs=cfg['epochs'],relaxation=RELAXATION)
                if len(order)!=cfg['budget'] or len(np.unique(order))!=len(order) or not np.array_equal(order[:cfg['warm']],warm[:cfg['warm']]) or oracle.allowed!=set(map(int,order)):
                    raise AssertionError('acquisition integrity check failed')
                orders[policy]=order
                row=dict(size=n,signal_seed=int(signal_seed),policy=policy,
                         budget=len(order),selection_seconds=float(seconds),
                         order_sha256=_sha(order),
                         guard_binding_choices=sum(x.get('binding_choices',0) for x in audit),
                         guard_intervention_choices=sum(x.get('intervention_choices',0) for x in audit),
                         mean_guard_eligible=(float(np.average([x['mean_eligible'] for x in audit],weights=[x['batch_choices'] for x in audit])) if policy=='incremental_25' else None))
                rows.append(row)
                for x in audit:
                    if policy=='incremental_25':
                        batchrows.append(dict(size=n,signal_seed=int(signal_seed),**x))
                print(f'08B size={n:2d} signal_seed={signal_seed} {policy:15s} rays={len(order)} select={seconds:.2f}s',flush=True)
            for row in rows:
                if row['size']==n and row['signal_seed']==int(signal_seed):
                    row['shared_with_gradient']=int(np.count_nonzero(orders[row['policy']]==orders['gradient']))
                    row['same_as_gradient']=bool(np.array_equal(orders[row['policy']],orders['gradient']))
            for policy,order in orders.items():
                # Saved order records enable later read-only parity audits.
                with (out/'acquisition_orders.csv').open('a',newline='',encoding='utf8') as f:
                    w=csv.writer(f)
                    for index,ray in enumerate(order,1):
                        w.writerow((n,int(signal_seed),policy,index,int(ray)))
    with (out/'policy_summary.csv').open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    with (out/'incremental_batch_audit.csv').open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(batchrows[0]));w.writeheader();w.writerows(batchrows)
    protocol=dict(stage='RBYRCT-08B acquired-only developmental acquisition mechanics; NO reconstruction accuracy',
        sizes=list(sizes),signal_seeds=list(signal_seeds),acquisition_seed=acquisition_seed,
        configs={str(k):configs[k] for k in sizes},angles=ANGLES,relaxation=RELAXATION,
        guard_lambda=NEW_LAMBDA,policies=list(POLICIES),
        observation_gate='experiment_05b_gate.AcquiredOnly; committed only after batch selection',
        measured='synthetic positive signal, generated external to selector',
        forbidden='evaluation truth, defect masks, unmeasured measurement reads, frozen 06B/07C2 outcomes',
        limitation='Binding and acquisition divergence do not imply reconstruction quality improvement')
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n',encoding='utf8')
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()}
    (out/'sha256.json').write_text(json.dumps(hashes,indent=2)+'\n',encoding='utf8')
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,default=Path('results/experiment08b/acquisition_first'))
    p.add_argument('--size',type=int,choices=[12,32],nargs='*',default=[12,32])
    args=p.parse_args()
    run(args.output_dir,sizes=tuple(args.size))

if __name__=='__main__':
    main()
