"""04O-B: acquired-only reliability checkpoint and leave-one-phantom-family-out audit.

NO selector changes, NO online gate, NO inference of oracle truth from reliability signals.
Requires the 04O-A paired_cases.csv outcome labels; generates new late-prefix
signals by replaying frozen 04J adaptive schedules with the original synthetic setup.
"""
from __future__ import annotations
import argparse,csv,json
from collections import defaultdict
from pathlib import Path
import numpy as np
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04h import voxel_coverage_order
from experiment_04i import noisy_full_projection
from experiment_04j import adaptive_order
from experiment_04k import noise_seed_for
from experiment_04m import high_resolution_matrix
from experiment_04n import object_pair
from experiment_04o import acquired_only_reliability,save

KEY=('object_type','offset','phantom','seed','budget','noise_fraction')

def load_pairs(path):
    with path.open(newline='',encoding='utf-8') as f: rows=list(csv.DictReader(f))
    if not rows:raise ValueError('empty paired_cases.csv')
    out=[];seen=set()
    for r in rows:
        item={k:r[k] for k in KEY}
        item.update(offset=float(r['offset']),seed=int(r['seed']),budget=int(r['budget']),noise_fraction=float(r['noise_fraction']),relative_gain=float(r['relative_gain']))
        key=tuple(item[k] for k in KEY)
        if key in seen:raise ValueError('duplicate case in paired data')
        seen.add(key);out.append(item)
    return out

def auc_score(y,score):
    """Mid-rank ROC AUC for failures (gain <= 0), higher score = greater risk."""
    y=np.asarray(y,dtype=bool);s=np.asarray(score,dtype=float)
    if len(y)!=len(s) or len(y)==0 or not np.all(np.isfinite(s)) or y.all() or (~y).all():return float('nan')
    positives=s[y]; negatives=s[~y]
    return float((np.sum(positives[:,None]>negatives[None,:])+.5*np.sum(positives[:,None]==negatives[None,:]))/(len(positives)*len(negatives)))

def balanced_accuracy(y,guess):
    y=np.asarray(y,dtype=bool);g=np.asarray(guess,dtype=bool)
    if len(y)!=len(g) or y.all() or (~y).all():return float('nan')
    return float(.5*(np.mean(g[y])+np.mean(~g[~y])))

def threshold_for_train(train,feature):
    x=np.asarray([r[feature] for r in train],float)
    y=np.asarray([r['relative_gain']<=0 for r in train],bool)
    if not np.all(np.isfinite(x)) or not y.any() or y.all():return None
    # Only thresholds from training families, no test-label access.
    options=np.unique(x)
    thresholds=[float(np.nextafter(options[0],-np.inf))]+[float((a+b)/2) for a,b in zip(options[:-1],options[1:])]+[float(np.nextafter(options[-1],np.inf))]
    return max(thresholds,key=lambda t:(balanced_accuracy(y,x>t),-abs(t-np.median(x))))

def evaluate_group_holdout(records,feature):
    out=[]
    for budget in sorted({r['budget'] for r in records}):
        cases=[r for r in records if r['budget']==budget]
        for family in sorted({r['phantom'] for r in cases}):
            train=[r for r in cases if r['phantom']!=family]
            test=[r for r in cases if r['phantom']==family]
            if not train or not test:continue
            threshold=threshold_for_train(train,feature)
            y=np.array([r['relative_gain']<=0 for r in test],bool)
            x=np.array([r[feature] for r in test],float)
            guess=x>threshold if threshold is not None else np.zeros(len(test),bool)
            out.append(dict(budget=budget,heldout_phantom=family,feature=feature,n_train=len(train),n_test=len(test),n_failures=int(y.sum()),threshold=threshold if threshold is not None else '',auc=auc_score(y,x),balanced_accuracy=balanced_accuracy(y,guess) if threshold is not None else float('nan'),accuracy=float(np.mean(y==guess)),majority_baseline_accuracy=float(max(y.mean(),1-y.mean())),note='threshold selected using training families only; correlated seeds/offsets, exploratory'))
    return out

def compare_signal(records,feature):
    out=[]
    for budget in sorted({r['budget'] for r in records}):
        rr=[r for r in records if r['budget']==budget]
        y=np.array([r['relative_gain']<=0 for r in rr],bool)
        x=np.array([r[feature] for r in rr],float)
        rho=float(np.corrcoef(x,[r['relative_gain'] for r in rr])[0,1]) if np.std(x)>1.e-12 and np.std([r['relative_gain'] for r in rr])>1.e-12 else float('nan')
        out.append(dict(budget=budget,feature=feature,n=len(rr),n_failures=int(y.sum()),failure_auc=auc_score(y,x),pearson_vs_gain=rho))
    return out

def scenario_records(pairs,checkpoints):
    # identical object + geometry + noise need only one simulated observation, but
    # adaptive acquisition can depend on requested final budget, so replay each case.
    by_scenario=defaultdict(list)
    for p in pairs:
        by_scenario[(p['object_type'],p['offset'],p['phantom'],p['seed'],p['noise_fraction'])].append(p)
    n_scenarios=len(by_scenario)
    return by_scenario,n_scenarios

def check_source_protocol(args):
    source=args.paired_cases.parent/'protocol.json'
    if not source.exists():
        raise ValueError(f'04O-A protocol.json missing next to paired cases: {source}')
    payload=json.loads(source.read_text(encoding='utf-8'))
    if payload.get('experiment')!='04O-A':
        raise ValueError('paired cases must originate from 04O-A')
    original=payload.get('parameters',{})
    names=('size','angles','factor','warm_rays','batch','provisional_iterations','candidate_pool','holdout_fraction')
    for name in names:
        if str(original.get(name))!=str(getattr(args,name)):
            raise ValueError(f'04O-A protocol mismatch: {name} was {original.get(name)}, replay requested {getattr(args,name)}')


def run(args):
    check_source_protocol(args)
    pairs=load_pairs(args.paired_cases)
    a=args
    A=system_matrix(a.size,a.angles,TILTS).tocsr()
    if max(r['budget'] for r in pairs)>A.shape[0]:raise ValueError('budget exceeds available rays')
    by_scenario,_=scenario_records(pairs,a.checkpoints)
    operators={offset:high_resolution_matrix(a.size,a.angles,TILTS,a.factor,offset) for offset in sorted({p['offset'] for p in pairs})}
    objects={name:object_pair(name,a.size,a.factor) for name in {p['phantom'] for p in pairs}}
    fixed_by_seed={seed:voxel_coverage_order(A,a.size,a.angles,len(TILTS),max(r['budget'] for r in pairs),seed,a.candidate_pool) for seed in {p['seed'] for p in pairs}}
    signal_records=[]
    for j,((object_type,offset,phantom,seed,noise),rr) in enumerate(sorted(by_scenario.items()),1):
        truth,fine=objects[phantom][object_type]
        clean=np.asarray(operators[offset]@fine).ravel()
        observed=noisy_full_projection(clean,noise,noise_seed_for(seed,phantom,noise))
        for p in sorted(rr,key=lambda x:x['budget']):
            budget=p['budget']
            ids,_,_=adaptive_order(A,observed,a.size,a.angles,fixed_by_seed[seed],budget,seed,a.warm_rays,a.batch,a.provisional_iterations,a.candidate_pool,1.)
            applicable=[c for c in a.checkpoints if a.warm_rays<=c<budget]
            if not applicable:raise ValueError(f'no checkpoint less than budget {budget}')
            for ck in applicable:
                sig=acquired_only_reliability(A,observed,ids[:ck],a.size,a.diagnostic_iterations,a.holdout_fraction,seed=seed+ck*13)
                signal_records.append(dict(**p,acquired=ck,**sig))
        if j%8==0 or j==len(by_scenario):print(f'04O-B scenarios {j}/{len(by_scenario)}; signals={len(signal_records)}',flush=True)
    groups=defaultdict(list)
    for r in signal_records:groups[tuple(r[k] for k in KEY)].append(r)
    rows=[]
    for p in pairs:
        k=tuple(p[f] for f in KEY);s=sorted(groups[k],key=lambda x:x['acquired'])
        if not s:raise ValueError('missing diagnostic signals')
        end=s[-1];start=s[0]
        # The latest checkpoint is selected a priori by budget, not by label.
        rows.append(dict(**p,first_checkpoint=start['acquired'],last_checkpoint=end['acquired'],n_checkpoints=len(s),
           heldout_latest=end['heldout_nrmse'],instability_latest=end['feature_instability'],
           heldout_delta=end['heldout_nrmse']-start['heldout_nrmse'],instability_delta=end['feature_instability']-start['feature_instability'],
           heldout_mean=float(np.mean([v['heldout_nrmse'] for v in s])),instability_mean=float(np.mean([v['feature_instability'] for v in s]))))
    features=('heldout_latest','instability_latest','heldout_delta','instability_delta','heldout_mean','instability_mean')
    assoc=[r for feature in features for r in compare_signal(rows,feature)]
    cv=[r for feature in features for r in evaluate_group_holdout(rows,feature)]
    a.output_dir.mkdir(parents=True,exist_ok=True)
    for file,data in [('checkpoint_signals.csv',signal_records),('case_features.csv',rows),('associations.csv',assoc),('leave_one_phantom_out.csv',cv)]:save(a.output_dir/file,data)
    (a.output_dir/'protocol.json').write_text(json.dumps(dict(experiment='04O-B',purpose='acquired-only reliability audit and out-of-family predictive validation',original_label_file=str(a.paired_cases),parameters={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},limitations=['No online gate implemented','Labels from original 04O-A run; source protocol must match','Checkpoints precede final acquisition; later checkpoints not causal tests of the next-batch outcome','Holdout rays were adaptively sampled','Cases share 4 phantom families and repeated seeds/offsets','Family-holdout is exploratory with only four families; thresholds chosen within training families','AUC undefined if test family has a single outcome class']),indent=2),encoding='utf-8')
    print(f'04O-B complete: {len(rows)} cases, {len(signal_records)} checkpoint diagnostics; output={a.output_dir}',flush=True)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--paired-cases',type=Path,default=Path('results/experiment04o_a/paired_cases.csv'))
    p.add_argument('--output-dir',type=Path,default=Path('results/experiment04ob'))
    p.add_argument('--size',type=int,default=16);p.add_argument('--angles',type=int,default=12);p.add_argument('--factor',type=int,default=2)
    p.add_argument('--warm-rays',type=int,default=128);p.add_argument('--batch',type=int,default=64)
    p.add_argument('--provisional-iterations',type=int,default=60);p.add_argument('--diagnostic-iterations',type=int,default=60)
    p.add_argument('--candidate-pool',type=int,default=64);p.add_argument('--holdout-fraction',type=float,default=.2)
    p.add_argument('--checkpoints',nargs='+',type=int,default=[128,256,448,768,960,1536])
    a=p.parse_args(argv)
    if not a.paired_cases.is_file():p.error(f'paired data missing: {a.paired_cases}')
    if a.size<4 or a.angles<2 or a.factor<2 or a.warm_rays<12 or a.batch<1 or a.provisional_iterations<1 or a.diagnostic_iterations<1 or a.candidate_pool<1 or not 0<a.holdout_fraction<.5 or not a.checkpoints or min(a.checkpoints)<a.warm_rays or len(set(a.checkpoints))!=len(a.checkpoints):p.error('invalid configuration')
    run(a)
if __name__=='__main__':main()
