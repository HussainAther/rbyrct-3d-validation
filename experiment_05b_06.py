"""05B-06: frozen candidate-score ranking against offline one-ray MART value.

This is a diagnostic, NOT a new online acquisition policy. All candidate readings,
truth, and unacquired validation projections are used *only* in retrospective
counterfactual evaluation. Candidate pools are diagnostic samples, not the
historical pools drawn during the frozen 05B selector's run.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_04m import high_resolution_matrix
from experiment_05b_04p import object_pair
from experiment_05b_adaptive import image_score, score_candidates
from experiment_05b_04 import select_order
from experiment_05b_mart import mart_reconstruct
from experiment_05b_resources import validate_grid

SCORES = ('coverage', 'gradient', 'capped_gradient', 'projection_disagreement')


def offline_one_ray_value(A, observed, truth, prefix, candidate, epochs, relaxation, heldout):
    """Offline only: expose candidate measurement, evaluate its one-ray RMSE effect.

    Both reconstructions restart at positive 0.3, retaining the MART update rule.
    This is NOT incremental warm-starting nor final-budget causal benefit.
    """
    prefix = np.asarray(prefix, dtype=np.int64)
    if candidate in prefix or len(prefix) == 0:
        raise ValueError('candidate must be unacquired')
    x0 = mart_reconstruct(A[prefix], observed[prefix], epochs, relaxation=relaxation)
    ids = np.append(prefix, int(candidate))
    x1 = mart_reconstruct(A[ids], observed[ids], epochs, relaxation=relaxation)
    rmse0 = float(np.sqrt(np.mean((x0-truth)**2)))
    rmse1 = float(np.sqrt(np.mean((x1-truth)**2)))
    def err(x):
        pred = np.asarray(A[heldout] @ x).ravel()
        b = np.asarray(observed[heldout]).ravel()
        return float(np.linalg.norm(pred-b)/max(np.linalg.norm(b), 1.e-12))
    return dict(baseline_rmse=rmse0, augmented_rmse=rmse1,
                rmse_reduction=rmse0-rmse1,
                validation_projection_reduction=err(x0)-err(x1))


def acquired_only_scores(A, observed, prefix, candidates, n, angles, provisional_epochs,
                         relaxation, feature_cap):
    """Only acquired observations + public geometry enter these score values."""
    prefix=np.asarray(prefix,dtype=np.int64)
    candidates=np.asarray(candidates,dtype=np.int64)
    if (not len(prefix) or len(np.unique(prefix))!=len(prefix)
        or np.any(np.isin(candidates,prefix)) or len(np.unique(candidates))!=len(candidates)):
        raise ValueError('invalid acquired/candidate sets')
    counts=np.asarray(A[prefix].sum(axis=0)).ravel().astype(float)
    views=np.bincount(prefix//(n*n),minlength=angles*len(TILTS)).astype(int)
    flat=np.ones(A.shape[1])
    geom=score_candidates(A,candidates,counts,views,n,flat,feedback_strength=0.)
    x=mart_reconstruct(A[prefix],observed[prefix],provisional_epochs,relaxation=relaxation)
    gradient=image_score(x,n)
    raw=score_candidates(A,candidates,counts,views,n,gradient,feedback_strength=1.)
    capped=score_candidates(A,candidates,counts,views,n,np.minimum(gradient,feature_cap),feedback_strength=1.)
    left,right=prefix[::2],prefix[1::2]
    if len(right)==0: raise ValueError('need >=2 acquired rays')
    xl=mart_reconstruct(A[left],observed[left],provisional_epochs,relaxation=relaxation)
    xr=mart_reconstruct(A[right],observed[right],provisional_epochs,relaxation=relaxation)
    delta=np.abs(np.asarray(A[candidates]@(xl-xr)).ravel())
    scale=max(float(np.sqrt(np.mean(np.asarray(observed[prefix])**2))),1.e-12)
    return {'coverage':geom,'gradient':raw,'capped_gradient':capped,
            'projection_disagreement':geom*(1.+delta/scale)}


def analyze_prefix(A, observed, truth, prefix, candidates, n, angles, *,
                   provisional_epochs, final_epochs, relaxation, feature_cap):
    """Return candidate-level offline benefit and score/rank summary.

    For validation, use ALL nonacquired, noncandidate rays. Their measurements
    NEVER participate in candidate ranking or the counterfactual reconstructions.
    """
    prefix=np.asarray(prefix,dtype=np.int64)
    candidates=np.asarray(candidates,dtype=np.int64)
    if not len(candidates) or np.any(candidates<0) or np.any(candidates>=A.shape[0]):
        raise ValueError('invalid candidates')
    heldout=np.setdiff1d(np.arange(A.shape[0]),np.r_[prefix,candidates])
    if not len(heldout): raise ValueError('no offline validation rays')
    scores=acquired_only_scores(A,observed,prefix,candidates,n,angles,
                               provisional_epochs,relaxation,feature_cap)
    effects=[offline_one_ray_value(A,observed,truth,prefix,int(c),final_epochs,
                                   relaxation,heldout) for c in candidates]
    benefit=np.asarray([e['rmse_reduction'] for e in effects])
    rows=[]
    for i,c in enumerate(candidates):
        rows.append(dict(candidate=int(c),**{f'{p}_score':float(scores[p][i]) for p in SCORES},
                         **effects[i]))
    best_idx=int(np.argmax(benefit))
    reports=[]
    for policy in SCORES:
        s=np.asarray(scores[policy])
        maxs=np.max(s)
        # Match original min-ID tie break, including tolerance.
        winner=int(np.min(candidates[np.isclose(s,maxs,rtol=1.e-13,atol=1.e-14)]))
        ix=int(np.flatnonzero(candidates==winner)[0])
        corr=(float(spearmanr(s,benefit).statistic)
              if len(np.unique(s))>1 and len(np.unique(benefit))>1 else float('nan'))
        reports.append(dict(policy=policy,spearman_score_vs_rmse_reduction=corr,
                            chosen_ray=winner,chosen_rmse_reduction=float(benefit[ix]),
                            best_candidate_ray=int(candidates[best_idx]),
                            best_candidate_rmse_reduction=float(benefit[best_idx]),
                            one_step_regret=float(max(0.,benefit[best_idx]-benefit[ix])),
                            chosen_improves_rmse=int(benefit[ix]>0)))
    return rows,reports


def write_csv(path,rows):
    if not rows: raise ValueError('no rows')
    with path.open('w',newline='',encoding='utf8') as file:
        w=csv.DictWriter(file,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--size',type=int,default=8)
    p.add_argument('--angles',type=int,default=4)
    p.add_argument('--factor',type=int,default=2)
    p.add_argument('--phantoms',nargs='+',choices=['branches','layers','pores','defects'],default=['branches','defects'])
    p.add_argument('--representations',nargs='+',choices=['replicated','subvoxel'],default=['replicated'])
    p.add_argument('--seeds',nargs='+',type=int,default=[271828,314159,577215])
    p.add_argument('--source-policy',choices=SCORES,default='coverage',
                   help='Frozen trajectory from which to audit prefixes')
    p.add_argument('--offset',type=float,default=0.)
    p.add_argument('--budget',type=int,default=128)
    p.add_argument('--warm-rays',type=int,default=16)
    p.add_argument('--batch',type=int,default=8)
    p.add_argument('--candidate-pool',type=int,default=16)
    p.add_argument('--audit-candidates',type=int,default=8)
    p.add_argument('--checkpoints',nargs='+',type=int,default=[16,48,80,112])
    p.add_argument('--provisional-epochs',type=int,default=4)
    p.add_argument('--mart-epochs',type=int,default=16)
    p.add_argument('--mart-relaxation',type=float,default=.25)
    p.add_argument('--feature-cap',type=float,default=3.)
    p.add_argument('--output-dir',type=Path,default=Path('results/experiment05b/ranking_audit_8'))
    p.add_argument('--allow-large',action='store_true')
    a=p.parse_args(argv)
    try: validate_grid(a.size,a.factor,a.allow_large)
    except (ValueError,OSError) as exc: p.error(str(exc))
    nr=a.size*a.size*a.angles*len(TILTS)
    if (a.angles<2 or not 2<=a.warm_rays<a.budget<nr
        or min(a.batch,a.candidate_pool,a.audit_candidates,a.provisional_epochs,a.mart_epochs)<1
        or a.audit_candidates>nr-a.budget
        or not np.isfinite(a.mart_relaxation) or not 0<a.mart_relaxation<=1
        or not np.isfinite(a.feature_cap) or a.feature_cap<1
        or not np.isfinite(a.offset) or a.offset<0
        or not a.checkpoints
        or any(not a.warm_rays<=k<a.budget or (k-a.warm_rays)%a.batch for k in a.checkpoints)):
        p.error('invalid 05B-06 configuration')
    if a.output_dir.exists() and any(a.output_dir.iterdir()):
        p.error('output directory must be empty')
    A=system_matrix(a.size,a.angles,TILTS).tocsr()
    M=high_resolution_matrix(a.size,a.angles,TILTS,a.factor,a.offset)
    candidates_out=[];ranking_out=[]
    for phantom in a.phantoms:
        pairs=object_pair(phantom,a.size,a.factor)
        for rep in a.representations:
            truth,fine=pairs[rep]
            observed=np.asarray(M@fine).ravel()
            for seed in a.seeds:
                warm=voxel_coverage_order(A,a.size,a.angles,len(TILTS),a.budget,seed,a.candidate_pool)
                order,_,_=select_order(A,observed,a.size,a.angles,warm,a.budget,seed,
                                       policy=a.source_policy,warm_rays=a.warm_rays,
                                       batch=a.batch,candidate_pool=a.candidate_pool,
                                       provisional_epochs=a.provisional_epochs,
                                       relaxation=a.mart_relaxation,feature_cap=a.feature_cap)
                for k in sorted(set(a.checkpoints)):
                    prefix=order[:k]
                    remaining=np.setdiff1d(np.arange(A.shape[0]),prefix)
                    rng=np.random.default_rng(seed+1000003*k+sum(map(ord,phantom))*17)
                    sample=rng.choice(remaining,size=a.audit_candidates,replace=False)
                    rows,reports=analyze_prefix(A,observed,truth,prefix,sample,a.size,a.angles,
                        provisional_epochs=a.provisional_epochs,final_epochs=a.mart_epochs,
                        relaxation=a.mart_relaxation,feature_cap=a.feature_cap)
                    meta=dict(phantom=phantom,representation=rep,seed=seed,acquired=k,
                              source_policy=a.source_policy)
                    candidates_out.extend(dict(**meta,**r) for r in rows)
                    ranking_out.extend(dict(**meta,**r) for r in reports)
                    print(f'{phantom} {rep} seed={seed} rays={k} '+
                          ' '.join(f"{r['policy']}:rho={r['spearman_score_vs_rmse_reduction']:+.3f}" for r in reports),flush=True)
    a.output_dir.mkdir(parents=True,exist_ok=True)
    write_csv(a.output_dir/'candidate_counterfactuals.csv',candidates_out)
    write_csv(a.output_dir/'ranking_diagnostics.csv',ranking_out)
    protocol=dict(experiment='05B-06 offline candidate-ranking audit',
                  parameters={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},
                  candidate_pool='Independent diagnostic candidate sample, not historical online RNG pool',
                  one_ray_target='RMSE reduction after appending ONE candidate and restarting MART from initial=0.3 for fixed epochs',
                  validation='Projection residual improvement on all rays excluding prefix and diagnostic candidate pool (offline only)',
                  limitations=['Counterfactual candidate observations and truth used offline only',
                    'One-ray effects are not final-budget policy effects',
                    'Validation projections are from the same synthetic forward model and not independent experimental data',
                    'Multiple prefixes/seeds of fixed synthetic phantom are dependent',
                    'No physical CT/dose claims','Score correlations based on small candidate samples; exploratory'])
    (a.output_dir/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf8')
    print(f'05B-06 complete: {len(ranking_out)} score summaries, {len(candidates_out)} candidate counterfactuals in {a.output_dir}')
    return ranking_out

if __name__=='__main__': main()
