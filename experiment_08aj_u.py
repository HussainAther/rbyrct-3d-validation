"""08AJ-U outcome-free generator morphology + hypothetical precision audit.

Historical reference = experiment_06b.defect_phantom, eight fixed 08M object seeds.
The analysis does not execute acquisition, MART, or prospective study outcome routines.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
from experiment_08aj_d import FAMILIES, SEEDS
from experiment_08aj_f import reconciled_object
from experiment_08aj_e import full_resolution_pair
from experiment_06b import defect_phantom

SCHEMA='RBYRCT-08AJ-U-morphology-precision-draft-v1'
HISTORICAL_SEEDS=tuple(820101+7919*i for i in range(8))
SIGMAS=(.01,.03,.06)
TRUE_GAINS=(0.,.01,.02,.04)

def digest(x):return hashlib.sha256(np.ascontiguousarray(x,dtype='<f8').tobytes()).hexdigest()

def features(x):
    x=np.asarray(x,dtype=np.float64).reshape(32,32,32)
    if not np.all(np.isfinite(x)) or np.min(x)<=0:raise ValueError('invalid truth')
    diffs=[np.diff(x,axis=a) for a in range(3)]
    e=np.mean([np.mean(a*a) for a in diffs])
    high=np.quantile(x,.9); low=np.quantile(x,.1)
    return {'mean':float(x.mean()),'std':float(x.std()),
            'p10':float(low),'p50':float(np.median(x)),'p90':float(high),
            'gradient_rms':float(np.sqrt(e)),
            'above_0_5_fraction':float(np.mean(x>.5)),
            'low_0_2_fraction':float(np.mean(x<.2)),
            'range':float(x.max()-x.min())}

def cohort():
    proposed=[]; old=[]
    for family in FAMILIES:
        for seed in SEEDS[family]:
            obj=reconciled_object(family,seed)
            x,_=full_resolution_pair(family,seed,32,factor=2)
            proposed.append({'cohort':family,'seed':int(seed),'sha256':digest(x),**features(x)})
            if digest(x)!=obj['coarse_truth_sha256']:raise AssertionError('truth hash mismatch')
    for seed in HISTORICAL_SEEDS:
        x,_,_=defect_phantom(32,2,seed)
        old.append({'cohort':'historical_06b_generator_08m_seeds','seed':int(seed),'sha256':digest(x),**features(x)})
    return proposed,old

def summary(rows):
    numeric=('mean','std','p10','p50','p90','gradient_rms','above_0_5_fraction','low_0_2_fraction','range')
    return {k:{name:float(np.mean([r[name] for r in rows if r['cohort']==k])) for name in numeric}
            for k in sorted({r['cohort'] for r in rows})}

def precision_sim(*, trials=250, bootstraps=1000, seed=941017):
    if trials<10 or bootstraps<100:raise ValueError('insufficient simulation repetitions')
    rng=np.random.default_rng(seed)
    output=[]
    # Generative assumption: 24 exchangeable Gaussian object-level paired gains
    # per setting, 8 each family, identical family means, no within-object pseudo-replication.
    for sd in SIGMAS:
        for mu in TRUE_GAINS:
            cover=0;positive=0;practical=0;widths=[]
            for _ in range(trials):
                x=rng.normal(mu,sd,size=(3,8))
                idx=rng.integers(0,8,size=(bootstraps,3,8))
                means=np.take_along_axis(np.broadcast_to(x,(bootstraps,3,8)),idx,axis=2).mean(axis=(1,2))
                lo,hi=np.quantile(means,[.025,.975]);widths.append(float(hi-lo))
                cover+=bool(lo<=mu<=hi);positive+=bool(lo>0);practical+=bool(lo>.02)
            output.append({'assumed_true_mean_gain':mu,'assumed_object_sd':sd,
                           'median_ci_width':float(np.median(widths)),
                           'estimated_coverage':cover/trials,
                           'prob_lower_bound_above_zero':positive/trials,
                           'prob_lower_bound_above_2pct':practical/trials})
    return output

def build(*,trials=250,bootstraps=1000):
    proposed,history=cohort()
    if len(proposed)!=24 or len(history)!=8:raise AssertionError('unexpected cohort count')
    return {'schema':SCHEMA,'verdict':'SCIENTIFIC_REVIEW_EVIDENCE_PREPARED',
            'frozen':False,'confirmatory_execution_allowed':False,
            'no_confirmatory_outcomes':True,
            'comparison_scope':'24 proposed 08AJ fine-to-coarse truths vs 8 historical 06B-generator objects using 08M seed roster; not all historical cohorts',
            'proposed_objects':proposed,'historical_reference_objects':history,
            'feature_means':summary(proposed+history),
            'generator_review':{
                'shared_properties':['synthetic positive 3D attenuation','localized low-attenuation structures','seeded procedural generator'],
                'differences':['08AJ: central hard-boundary sphere on uniform .15 background','06B: softly tapered randomized ellipsoidal host on .04 baseline','08AJ localized: 3 hard-mask spherical defects vs 06B: 2-4 rotated Gaussian ellipsoidal defects','08AJ smooth: periodic modulation and smooth Gaussian depression','08AJ irregular: hard ellipsoids plus sinusoidal texture'],
                'structural_independence_proven':False,
                'recommendation':'Three synthetic stress-test families within a shared spherical design, not independent imaging populations; report generator provenance and morphology.'},
            'precision_simulation':{'trial_count':trials,'bootstraps_per_trial':bootstraps,
               'assumptions':'hypothetical independent Gaussian object-level paired gains with same mean/SD in each of three fixed families; eight objects per family; seeded percentile stratified bootstrap; no empirical effects used',
               'assumption_limitations':['not a power guarantee','non-Gaussian/heavy-tailed gain distributions may behave differently','shared template/latent structure reduces effective generalizability','four conditions per object treated as paired repeated measures, not 96 independent units'],
               'results':precision_sim(trials=trials,bootstraps=bootstraps)},
            'remaining_decisions':['Review and approve bounded synthetic benchmark claim','Approve statistical uncertainty and practical-effect interpretation','Approve resource/failure limits','Build and audit production 480-job execution','Obtain scientific signoff and immutable source lock']}

def canonical(obj):return (json.dumps(obj,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--trials',type=int,default=250)
    p.add_argument('--bootstraps',type=int,default=1000)
    a=p.parse_args(argv)
    if a.output_dir.exists():raise FileExistsError('will not overwrite evidence')
    report=build(trials=a.trials,bootstraps=a.bootstraps)
    a.output_dir.mkdir(parents=True)
    (a.output_dir/'scientific_review_evidence.json').write_bytes(canonical(report))
    status={'verdict':report['verdict'],'frozen':False,'no_confirmatory_outcomes':True,
            'reference_objects':8,'proposed_objects':24,'scientific_signoff':False}
    (a.output_dir/'run_status.json').write_bytes(canonical(status))
    print(json.dumps(status,indent=2))
if __name__=='__main__':main()
