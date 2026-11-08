"""08T: retrospective covariance-score fidelity on frozen 08M acquisition prefixes.

No truth, measurement values, reconstruction errors or model outcomes are read.
The exact reference is linear-Gaussian A-optimal score, not MART posterior.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, time
from pathlib import Path
import numpy as np
from scipy import linalg, sparse
from scipy.stats import spearmanr
from experiment_04b import system_matrix
from experiment_04g import TILTS
# Same frozen 08J parameter values and formula, implemented locally to allow
# independent scoring diagnostics without importing the 08E probe pipeline.
PRIOR_VARIANCE=1.0
OBSERVATION_VARIANCE=1.0


def diagonal_scores(H,Q, *, prior_variance=1.0, observation_variance=1.0):
    H=H.tocsr();Q=Q.tocsr()
    if H.shape[1]!=Q.shape[1] or H.shape[0]<1:
        raise ValueError('invalid diagonal proxy geometry')
    d=1./(1./prior_variance + np.asarray(H.power(2).sum(axis=0)).ravel()/observation_variance)
    squared=Q.power(2)
    return np.asarray(squared@(d*d)).ravel()/(observation_variance+np.asarray(squared@d).ravel())

POLICIES=('coverage','information_diag')
SEEDS=(820443,820861)
PREFIXES=(64,256,512)
POOL=16
N=32
ANGLES=4


def full_covariance_scores(H, candidates, *, prior_variance=1.0, observation_variance=1.0):
    """Exact Gaussian trace reduction via measurement-space Woodbury identity.

    C = tau2 I - tau2**2 H.T (sigma2 I + tau2 H H.T)^-1 H.
    Score(a) = ||C a||_2^2 / (sigma2 + a.T C a).
    Does not form dense voxel-by-voxel posterior covariance.
    """
    if not sparse.isspmatrix(H) or not sparse.isspmatrix(candidates):
        raise TypeError('sparse matrices required')
    if H.shape[1]!=candidates.shape[1] or candidates.shape[0]<1:
        raise ValueError('shape mismatch')
    if not (np.isfinite(prior_variance) and prior_variance>0 and np.isfinite(observation_variance) and observation_variance>0):
        raise ValueError('invalid variance')
    H=H.tocsr();Q=candidates.tocsr()
    if not np.isfinite(H.data).all() or not np.isfinite(Q.data).all():
        raise ValueError('nonfinite matrix')
    # n_voxels x n_candidates; limited pool size by protocol.
    q=Q.T.toarray()
    if H.shape[0]:
        gram=(H@H.T).toarray()
        gram*=prior_variance
        gram.flat[::len(gram)+1]+=observation_variance
        rhs=np.asarray(H@q)
        cho=linalg.cho_factor(gram,lower=True,check_finite=True)
        z=linalg.cho_solve(cho,rhs,check_finite=False)
        cq=prior_variance*q-(prior_variance**2)*np.asarray(H.T@z)
    else:
        cq=prior_variance*q
    numer=np.einsum('ij,ij->j',cq,cq)
    denom=observation_variance+np.einsum('ij,ij->j',q,cq)
    if (denom<=0).any() or not np.isfinite(numer/denom).all():
        raise ArithmeticError('nonpositive exact score denominator')
    return numer/denom


def read_orders(path):
    # Use one object and same-model history for each policy x seed. Avoid treating
    # object/model duplicates as independent acquisition-design replications.
    rows={}
    with Path(path).open(newline='',encoding='utf8') as f:
        for r in csv.DictReader(f):
            if r['policy'] not in POLICIES or int(r['acquisition_seed']) not in SEEDS:
                continue
            if r['model']!='same' or r['object_id']!='defect_validation_820101':
                continue
            key=(r['policy'],int(r['acquisition_seed']))
            rows.setdefault(key,[]).append((int(r['acquired_index']),int(r['ray_id'])))
    if set(rows)!={(p,s) for p in POLICIES for s in SEEDS}:
        raise ValueError('missing reference histories; check archived 08M CSV')
    out={}
    for key,seq in rows.items():
        seq.sort()
        ids=np.array([r for _,r in seq],dtype=np.int64)
        if len(ids)!=4096 or [x for x,_ in seq]!=list(range(1,4097)) or len(set(ids))!=4096:
            raise ValueError(f'invalid archived order: {key}')
        out[key]=ids
    return out


def candidate_pool(A, history, prefix, policy, seed, pool=POOL):
    if prefix<1 or prefix>=len(history):raise ValueError('invalid prefix')
    # independent predeclared seed, not phantom/measurement data
    salt=int.from_bytes(hashlib.sha256(f'08T|{policy}|{seed}|{prefix}'.encode()).digest()[:8],'little')
    rng=np.random.default_rng(salt)
    remaining=np.ones(A.shape[0],dtype=bool);remaining[history[:prefix]]=False
    available=np.flatnonzero(remaining)
    # Include next actual ray, so ordering can be compared with the policy continuation.
    next_ray=int(history[prefix]);others=available[available!=next_ray]
    chosen=rng.choice(others,size=min(pool-1,len(others)),replace=False)
    candidates=np.sort(np.r_[chosen,next_ray]).astype(np.int64)
    return candidates,next_ray


def compare(A, history, policy, seed, prefix, pool=POOL):
    candidates,next_ray=candidate_pool(A,history,prefix,policy,seed,pool)
    H=A[history[:prefix]];Q=A[candidates]
    t=time.perf_counter();approx=diagonal_scores(H,Q,prior_variance=PRIOR_VARIANCE,observation_variance=OBSERVATION_VARIANCE)
    diag_seconds=time.perf_counter()-t
    t=time.perf_counter();exact=full_covariance_scores(H,Q,prior_variance=PRIOR_VARIANCE,observation_variance=OBSERVATION_VARIANCE)
    exact_seconds=time.perf_counter()-t
    idx_diag=int(np.lexsort((candidates,-approx))[0]);idx_exact=int(np.lexsort((candidates,-exact))[0]);jnext=int(np.flatnonzero(candidates==next_ray)[0])
    rho=float(spearmanr(approx,exact).statistic)
    exact_regret=float(np.max(exact)-exact[idx_diag])
    return dict(size=N,policy=policy,acquisition_seed=seed,acquired_before=prefix,
        pool_size=len(candidates),next_archived_ray=next_ray,
        diag_selected_ray=int(candidates[idx_diag]),exact_selected_ray=int(candidates[idx_exact]),
        diag_matches_exact=int(idx_diag==idx_exact),diag_matches_archived_next=int(idx_diag==jnext),
        exact_matches_archived_next=int(idx_exact==jnext),spearman=rho,
        exact_regret_of_diag=float(max(0.,exact_regret)),
        exact_best_score=float(exact[idx_exact]),diag_best_score=float(approx[idx_diag]),
        diagonal_compute_s=diag_seconds,exact_compute_s=exact_seconds,
        acquired_order_sha256=hashlib.sha256(np.asarray(history[:prefix],dtype='<i8').tobytes()).hexdigest(),
        candidate_ids_sha256=hashlib.sha256(candidates.astype('<i8').tobytes()).hexdigest())


def run(results_dir,output_dir):
    source=Path(results_dir)/'acquisition_orders.csv'
    if not source.is_file():raise FileNotFoundError(source)
    out=Path(output_dir)
    if out.exists():raise FileExistsError('refusing to overwrite output directory')
    orders=read_orders(source)
    A=system_matrix(N,ANGLES,TILTS).tocsr()
    rows=[]
    for policy in POLICIES:
        for seed in SEEDS:
            for prefix in PREFIXES:
                r=compare(A,orders[(policy,seed)],policy,seed,prefix)
                rows.append(r)
                print(f"08T {policy:17} seed={seed} prefix={prefix:4d} rho={r['spearman']:+.4f} match={r['diag_matches_exact']} exact_s={r['exact_compute_s']:.3f}",flush=True)
    summary=[]
    for prefix in PREFIXES:
        for policy in POLICIES:
            rr=[r for r in rows if r['policy']==policy and r['acquired_before']==prefix]
            summary.append(dict(policy=policy,acquired_before=prefix,n_seeds=len(rr),
                mean_spearman=float(np.mean([r['spearman'] for r in rr])),
                diagonal_top1_matches_exact=sum(r['diag_matches_exact'] for r in rr),
                mean_exact_regret_of_diagonal=float(np.mean([r['exact_regret_of_diag'] for r in rr])),
                mean_exact_seconds=float(np.mean([r['exact_compute_s'] for r in rr]))))
    out.mkdir(parents=True)
    with (out/'candidate_rank_diagnostics.csv').open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    with (out/'summary.csv').open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
    report=dict(complete=True,scope='08T retrospective geometry-only method comparison',
        pools=len(rows),candidate_rows=sum(r['pool_size'] for r in rows),
        exact_reference='linear-Gaussian full covariance via measurement-space Woodbury',
        approximation='08J/08K inverse-diagonal-precision proxy',
        limitations=['Not MART posterior', 'No new acquisition trajectories or reconstruction outcomes',
          'Only sampled candidate pools and 08M acquisition prefixes',
          'Two acquisition seeds do not imply independent phantom replications'])
    (out/'run_status.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results-dir',required=True)
    p.add_argument('--output-dir',required=True)
    args=p.parse_args()
    print(json.dumps(run(args.results_dir,args.output_dir),indent=2))
