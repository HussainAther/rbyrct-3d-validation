"""Standalone MART feasibility and matched SIRT comparison; not a clinical experiment."""
from __future__ import annotations
import argparse
import json
import time
from pathlib import Path
import numpy as np
from experiment_04b import system_matrix
from experiment_04j import sirt_silent
from experiment_05b_mart import mart_reconstruct


def run(size=16, angles=12, budget=256, mart_epochs=8, sirt_iterations=40,
        relaxation=0.15, seed=271828):
    if not (4 <= size <= 16) or angles < 2 or budget < 1 or mart_epochs < 1 or sirt_iterations < 1:
        raise ValueError('Safe feasibility range: size 4..16 and positive parameters')
    tilts=[-20.,0.,20.]
    A=system_matrix(size,angles,tilts)
    if budget > A.shape[0]:
        raise ValueError('Budget exceeds available rays')
    z,y,x=np.indices((size,)*3)
    c=(size-1)/2
    truth=(((x-c)**2+(y-c)**2+(z-c)**2)<=(size/4)**2).astype(float).ravel()
    rng=np.random.default_rng(seed)
    ids=np.sort(rng.choice(A.shape[0],size=budget,replace=False))
    sub=A[ids].tocsr(); b=sub@truth
    results={}
    for label,solver in (
        ('MART',lambda:mart_reconstruct(sub,b,mart_epochs,relaxation=relaxation)),
        ('SIRT',lambda:sirt_silent(sub,b,sirt_iterations)),
    ):
        t=time.perf_counter(); estimate=solver(); elapsed=time.perf_counter()-t
        initial=np.full(sub.shape[1],0.3)
        residual=float(np.linalg.norm(sub@estimate-b))
        baseline=float(np.linalg.norm(sub@initial-b))
        results[label]={'seconds':elapsed,'rmse':float(np.sqrt(np.mean((estimate-truth)**2))),
                        'residual':residual,'initial_residual':baseline,
                        'passed':bool(np.isfinite(estimate).all() and (estimate>=0).all() and residual<baseline)}
    return {'experiment':'05B-01','size':size,'budget':budget,'seed':seed,
            'mart_epochs':mart_epochs,'mart_relaxation':relaxation,
            'sirt_iterations':sirt_iterations,'results':results,
            'limitation':'Same coarse operator creates and inverts noiseless synthetic data; no adaptive policy.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--size',type=int,default=16)
    p.add_argument('--budget',type=int,default=256)
    p.add_argument('--mart-epochs',type=int,default=8)
    p.add_argument('--sirt-iterations',type=int,default=40)
    p.add_argument('--mart-relaxation',type=float,default=0.15)
    p.add_argument('--output',type=Path,default=Path('results/experiment05b/benchmark.json'))
    args=p.parse_args()
    r=run(size=args.size,budget=args.budget,mart_epochs=args.mart_epochs,
          sirt_iterations=args.sirt_iterations,relaxation=args.mart_relaxation)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(r,indent=2),encoding='utf-8')
    print(json.dumps(r,indent=2))
    if not all(v['passed'] for v in r['results'].values()):
        raise SystemExit(1)

if __name__=='__main__':main()
