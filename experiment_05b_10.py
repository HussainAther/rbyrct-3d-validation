"""05B-10: retrospective mechanism audit on frozen 08B MART acquisitions.

This is NOT a new acquisition policy. Replays 08B, verifies the original endpoint
RMSE and optionally 09 ray fingerprints, then computes spatial, error-location,
and offline candidate-value diagnostics. Truth/future measurements never enter
acquired-only candidate scoring. Candidate pools are diagnostic, NOT historical.
"""
from __future__ import annotations
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
import numpy as np

from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_04qa import project
from experiment_05b_08b import (FAMILIES, POLICIES, new_phantom,
                                nonnegative_noisy_measurements, run_matched_case)
from experiment_05b_09 import load_source, ray_digest, write_csv
from experiment_05b_06 import SCORES, acquired_only_scores, offline_one_ray_value
from experiment_05b_mart import mart_reconstruct
from experiment_05b_resources import validate_grid


def coverage_gini(weights):
    """Gini of nonnegative cumulative voxel ray weight; zero for uniform."""
    w = np.asarray(weights, float)
    if w.ndim != 1 or not len(w) or not np.isfinite(w).all() or (w < 0).any():
        raise ValueError('invalid weights')
    total = float(w.sum())
    if total <= 0: return 0.
    sorted_w = np.sort(w)
    return float((2*np.dot(np.arange(1,len(w)+1), sorted_w)/(len(w)*total))
                 -(len(w)+1)/len(w))


def geometry_metrics(A, ids, n, angles):
    ids = np.asarray(ids, dtype=np.int64)
    if ids.ndim != 1 or not len(ids) or len(np.unique(ids)) != len(ids) or (ids < 0).any() or (ids >= A.shape[0]).any():
        raise ValueError('invalid ray sequence')
    weights = np.asarray(A[ids].sum(axis=0)).ravel()
    touched = np.asarray((A[ids] != 0).sum(axis=0)).ravel()
    viewcounts = np.bincount(ids//(n*n),minlength=angles*len(TILTS))
    p = viewcounts[viewcounts > 0] / float(len(ids))
    entropy = -float(np.dot(p,np.log(p)))/np.log(len(viewcounts)) if len(viewcounts)>1 else 0.
    return dict(touched_fraction=float(np.mean(touched>0)),
                voxel_hit_cv=float(np.std(touched)/max(np.mean(touched),1e-12)),
                voxel_weight_cv=float(np.std(weights)/max(np.mean(weights),1e-12)),
                voxel_weight_gini=coverage_gini(weights),
                view_entropy=entropy,
                mean_voxel_hits=float(np.mean(touched)))


def error_metrics(x, truth):
    """Top-quartile truth is a fixed descriptive ROI; not a lesion segmentation."""
    truth=np.asarray(truth, float); x=np.asarray(x,float)
    if truth.shape != x.shape or not np.isfinite(x).all() or not np.isfinite(truth).all():
        raise ValueError('invalid reconstruction')
    mask = truth >= np.quantile(truth,.75)
    if not np.any(~mask):
        mask=np.zeros_like(truth,dtype=bool)
        mask[np.argsort(truth)[-max(1,len(truth)//4):]]=True
    err=(x-truth)**2
    return dict(rmse=float(np.sqrt(np.mean(err))),
                top_quartile_rmse=float(np.sqrt(np.mean(err[mask]))),
                remainder_rmse=float(np.sqrt(np.mean(err[~mask]))),
                top_quartile_error_share=float(err[mask].sum()/max(err.sum(),1e-15)))


def diagnostic_pool(n_rays, prefix, seed, object_seed, model_index, noise_index, checkpoint, count):
    """Same diagnostic sample for all policies for the same case/checkpoint,
    excluding that policy's acquired prefix; not its historical selection pool."""
    available=np.setdiff1d(np.arange(n_rays),np.asarray(prefix,dtype=int))
    if count>len(available)-1: raise ValueError('need heldout rays after diagnostic pool')
    rng=np.random.default_rng(np.random.SeedSequence([seed,object_seed,model_index,noise_index,checkpoint,7919]))
    return rng.choice(available,size=count,replace=False)


def audit_candidates(A, observed, truth, prefix, candidates, n, angles, *,
                     provisional_epochs, epochs, relaxation, feature_cap):
    """Scores calculated first from acquired-only data, then offline value.

    Prefix-specific candidate pools are sampled, not actual historical pools;
    the winner is the *diagnostic* top-score ray, not the online next ray.
    """
    prefix=np.asarray(prefix,dtype=np.int64)
    candidates=np.asarray(candidates,dtype=np.int64)
    if len(prefix)<2 or not len(candidates) or np.any(np.isin(prefix,candidates)):
        raise ValueError('invalid diagnostic prefix/pool')
    heldout=np.setdiff1d(np.arange(A.shape[0]),np.r_[prefix,candidates])
    if not len(heldout): raise ValueError('need heldout projections')
    scores=acquired_only_scores(A,observed,prefix,candidates,n,angles,
                                provisional_epochs,relaxation,feature_cap)
    # Ground truth and future measurements are touched ONLY here, after scoring.
    effects=[offline_one_ray_value(A,observed,truth,prefix,int(c),epochs,relaxation,heldout)
             for c in candidates]
    benefit=np.asarray([e['rmse_reduction'] for e in effects],float)
    oracle_idx=int(np.argmax(benefit))
    rows=[]
    for i,c in enumerate(candidates):
        rows.append(dict(candidate=int(c),**{s+'_score':float(scores[s][i]) for s in SCORES},**effects[i]))
    rankings=[]
    for policy in SCORES:
        values=np.asarray(scores[policy],float)
        high=values.max()
        chosen=int(np.min(candidates[np.isclose(values,high,rtol=1e-13,atol=1e-14)]))
        chosen_i=int(np.flatnonzero(candidates==chosen)[0])
        # Import only where necessary; scipy already required by original 05B-06.
        from scipy.stats import spearmanr
        rho=float(spearmanr(values,benefit).statistic) if len(np.unique(values))>1 and len(np.unique(benefit))>1 else float('nan')
        rankings.append(dict(score_policy=policy,chosen_ray=chosen,
                             chosen_rmse_reduction=float(benefit[chosen_i]),
                             oracle_ray=int(candidates[oracle_idx]),
                             oracle_rmse_reduction=float(benefit[oracle_idx]),
                             regret=float(benefit[oracle_idx]-benefit[chosen_i]),
                             spearman=rho,chosen_harms=int(benefit[chosen_i]<0)))
    return rows,rankings


def read_fingerprints(path):
    if path is None: return None
    if not path.is_file(): raise ValueError('05B-09 ray_fingerprints.csv missing')
    with path.open(newline='',encoding='utf8') as f: rows=list(csv.DictReader(f))
    index={}
    for r in rows:
        k=(r['object_id'],r['model'],float(r['noise_fraction']),int(r['seed']),r['policy'])
        if k in index: raise ValueError('duplicate 05B-09 fingerprint')
        index[k]=r['ray_order_sha256']
    return index


def make_parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--size',type=int,default=8)
    p.add_argument('--angles',type=int,default=4)
    p.add_argument('--factor',type=int,default=2)
    p.add_argument('--families',nargs='+',choices=FAMILIES,default=list(FAMILIES))
    p.add_argument('--objects-per-family',type=int,default=2)
    p.add_argument('--object-seed-base',type=int,default=900001)
    p.add_argument('--seeds',nargs='+',type=int,default=[104729,130363])
    p.add_argument('--models',nargs='+',choices=['same','independent'],default=['same','independent'])
    p.add_argument('--noise-fractions',nargs='+',type=float,default=[0.,.005])
    p.add_argument('--offset',type=float,default=.15)
    p.add_argument('--step',type=float,default=.25)
    p.add_argument('--budget',type=int,default=128)
    p.add_argument('--warm-rays',type=int,default=16)
    p.add_argument('--batch',type=int,default=8)
    p.add_argument('--candidate-pool',type=int,default=16)
    p.add_argument('--provisional-epochs',type=int,default=4)
    p.add_argument('--mart-epochs',type=int,default=16)
    p.add_argument('--mart-relaxation',type=float,default=.25)
    p.add_argument('--feature-cap',type=float,default=3.)
    p.add_argument('--checkpoints',type=int,nargs='+',default=[48,112])
    p.add_argument('--audit-candidates',type=int,default=6)
    p.add_argument('--audit-source-policies',nargs='+',choices=POLICIES,default=['coverage','gradient'])
    p.add_argument('--source-dir',type=Path,default=Path('results/experiment05b/robustness_08b_frozen_first'))
    p.add_argument('--fingerprints-dir',type=Path,default=Path('results/experiment05b/frozen_rays_09_first'))
    p.add_argument('--output-dir',type=Path,default=Path('results/experiment05b/mechanism_10_first'))
    p.add_argument('--allow-large',action='store_true')
    return p


def main(argv=None):
    p=make_parser(); a=p.parse_args(argv)
    try:
        validate_grid(a.size,a.factor,a.allow_large)
        if (a.angles<2 or not a.families or not a.models or not a.noise_fractions or not a.seeds
            or a.objects_per_family<1 or min(a.seeds)<0 or a.object_seed_base<0
            or not np.isfinite(a.offset) or a.offset<0 or not np.isfinite(a.step) or not 0<a.step<=1
            or any(not np.isfinite(v) or v<0 for v in a.noise_fractions)
            or min(a.batch,a.candidate_pool,a.provisional_epochs,a.mart_epochs,a.audit_candidates)<1
            or not np.isfinite(a.mart_relaxation) or not 0<a.mart_relaxation<=1
            or not np.isfinite(a.feature_cap) or a.feature_cap<1
            or not 2<=a.warm_rays<48<a.budget<a.size*a.size*a.angles*len(TILTS)
            or (48-a.warm_rays)%a.batch or not a.checkpoints or not a.audit_source_policies
            or len(set(a.audit_source_policies)) != len(a.audit_source_policies)
            or any(not a.warm_rays<=k<a.budget or (k-a.warm_rays)%a.batch for k in a.checkpoints)
            or a.audit_candidates>=a.size*a.size*a.angles*len(TILTS)-a.budget):
            raise ValueError('invalid 05B-10 configuration')
        if a.output_dir.exists() and any(a.output_dir.iterdir()):
            raise ValueError('output directory must be new or empty')
        source=load_source(a.source_dir,a)
        fingerprint_path=None if a.fingerprints_dir is None else a.fingerprints_dir/'ray_fingerprints.csv'
        expected_fingerprints=read_fingerprints(fingerprint_path)
    except (ValueError,OSError,KeyError) as exc:
        p.error(str(exc))
    A=system_matrix(a.size,a.angles,TILTS).tocsr()
    warm={seed:voxel_coverage_order(A,a.size,a.angles,len(TILTS),a.budget,seed,a.candidate_pool) for seed in a.seeds}
    geometry=[]; errors=[]; details=[]; rankings=[]; verified=0; fingerprints_verified=0
    for fi,family in enumerate(a.families):
        for instance in range(a.objects_per_family):
            objseed=a.object_seed_base+1009*fi+instance
            truth,fine=new_phantom(a.size,a.factor,family,objseed)
            oid=f'{family}_{objseed}'
            for mi,model in enumerate(a.models):
                clean=np.asarray(A@truth).ravel() if model=='same' else project(
                    fine,a.size,a.angles,TILTS,factor=a.factor,offset=a.offset,step=a.step,mode='linear')
                for ni,noise in enumerate(a.noise_fractions):
                    noise_seed=(objseed*37+mi*100003+ni*17011)%(2**32)
                    observed=nonnegative_noisy_measurements(clean,noise,noise_seed)
                    for seed in a.seeds:
                        original,orders=run_matched_case(A,observed,truth,warm[seed],n=a.size,angles=a.angles,
                            budget=a.budget,acquisition_seed=seed,warm_rays=a.warm_rays,batch=a.batch,
                            candidate_pool=a.candidate_pool,provisional_epochs=a.provisional_epochs,
                            mart_epochs=a.mart_epochs,relaxation=a.mart_relaxation,feature_cap=a.feature_cap)
                        for r in original:
                            policy=r['policy']; key=(oid,model,float(noise),seed,policy)
                            if key not in source or not np.isclose(source[key],r['rmse'],rtol=1e-10,atol=1e-11):
                                raise AssertionError(f'05B-08B anchor mismatch {key}')
                            verified+=1
                            digest=ray_digest(orders[policy])
                            if expected_fingerprints is not None:
                                if expected_fingerprints.get(key)!=digest:
                                    raise AssertionError(f'05B-09 fingerprint mismatch {key}')
                                fingerprints_verified+=1
                            x=mart_reconstruct(A[orders[policy]],observed[orders[policy]],a.mart_epochs,
                                               relaxation=a.mart_relaxation)
                            em=error_metrics(x,truth)
                            if not np.isclose(em['rmse'],r['rmse'],rtol=1e-10,atol=1e-11):
                                raise AssertionError('05B-10 reconstruction does not match 08B anchor')
                            g=geometry_metrics(A,orders[policy],a.size,a.angles)
                            common=dict(object_id=oid,family=family,model=model,noise_fraction=noise,
                                        acquisition_seed=seed,policy=policy,ray_order_sha256=digest)
                            geometry.append(dict(**common,**g,
                                shared_with_coverage=len(set(orders[policy])&set(orders['coverage']))))
                            errors.append(dict(**common,**em))
                        for srcpolicy in a.audit_source_policies:
                            for k in sorted(set(a.checkpoints)):
                                prefix=orders[srcpolicy][:k]
                                candidates=diagnostic_pool(A.shape[0],prefix,seed,objseed,mi,ni,k,a.audit_candidates)
                                candidate_rows,ranking_rows=audit_candidates(A,observed,truth,prefix,candidates,
                                    a.size,a.angles,provisional_epochs=a.provisional_epochs,
                                    epochs=a.mart_epochs,relaxation=a.mart_relaxation,feature_cap=a.feature_cap)
                                common=dict(object_id=oid,family=family,model=model,
                                            noise_fraction=noise,acquisition_seed=seed,
                                            source_policy=srcpolicy,acquired=k,
                                            prefix_sha256=ray_digest(prefix))
                                details.extend(dict(**common,**r) for r in candidate_rows)
                                rankings.extend(dict(**common,**r) for r in ranking_rows)
                        print(f'{oid} {model} noise={noise:g} seed={seed}: anchors/fingerprints verified, mechanism audit complete',flush=True)
    a.output_dir.mkdir(parents=True,exist_ok=True)
    for name,rows in [('geometry.csv',geometry),('error_localization.csv',errors),
                      ('candidate_counterfactuals.csv',details),('candidate_rankings.csv',rankings)]:
        write_csv(a.output_dir/name,rows)
    (a.output_dir/'protocol.json').write_text(json.dumps(dict(
        study='05B-10 retrospective acquisition failure mechanism audit',
        parameters={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},
        source_08b_anchors_verified=verified,source_09_fingerprints_verified=fingerprints_verified,
        limitations=['No algorithm or acquisition parameters changed',
                     'Candidate pools are sampled diagnostic pools, not historical selector pools',
                     'Each source policy has its own acquired history and eligible candidate pool',
                     'Offline truth/future measurements only used after acquired-only scoring',
                     'Top quartile of truth is descriptive ROI, not ground-truth clinical lesion mask',
                     'Repeated conditions on eight synthetic objects are not independent cases',
                     'Rank correlations/one-step regret do not establish final-budget causality',
                     'No clinical dose or physics inference']),indent=2),encoding='utf8')
    print(f'05B-10 complete: {verified} 08B anchors, {fingerprints_verified} 09 fingerprints, '
          f'{len(geometry)} geometry, {len(errors)} error, {len(details)} candidate, '
          f'{len(rankings)} ranking records; output={a.output_dir}')
    return geometry,errors,details,rankings

if __name__=='__main__': main()
