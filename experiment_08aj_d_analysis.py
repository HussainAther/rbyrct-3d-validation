"""08AJ-D exact analysis specification validator; never generates RMSE observations.

Use on future independently produced, locked results only. It guards against
pseudoreplication by aggregating four paired conditions WITHIN each object.
"""
from __future__ import annotations
import csv
import json
from pathlib import Path
import numpy as np
from experiment_08aj_d import FAMILIES,SEEDS,ACQUISITION_SEEDS,MODELS


def summarize(rows, replicates=20000, seed=941007):
    """Expected columns: family,object_seed,acquisition_seed,model,policy,rmse_global.

    Only diag and uniform at the primary checkpoint. All conditions required.
    """
    if not isinstance(replicates,int) or replicates<100:
        raise ValueError('replicates must be >= 100')
    expected={(f,s,a,m,p) for f in FAMILIES for s in SEEDS[f]
              for a in ACQUISITION_SEEDS for m in MODELS
              for p in ('information_diag','uniform_multiscale')}
    indexed={}
    for r in rows:
        key=(r['family'],int(r['object_seed']),int(r['acquisition_seed']),r['model'],r['policy'])
        if key in indexed:
            raise ValueError('duplicate row '+repr(key))
        x=float(r['rmse_global'])
        if not np.isfinite(x) or x<=0:
            raise ValueError('RMSE must be finite positive')
        indexed[key]=x
    if set(indexed)!=expected:
        raise ValueError(f'wrong paired records: missing={len(expected-set(indexed))}; extra={len(set(indexed)-expected)}')
    phantom_results=[]
    for f in FAMILIES:
        for s in SEEDS[f]:
            gains=[]
            for a in ACQUISITION_SEEDS:
                for m in MODELS:
                    k=(f,s,a,m)
                    gains.append(1-indexed[k+('information_diag',)]/indexed[k+('uniform_multiscale',)])
            phantom_results.append({'family':f,'object_seed':s,'gain':float(np.mean(gains))})
    grouped={f:np.asarray([r['gain'] for r in phantom_results if r['family']==f]) for f in FAMILIES}
    rng=np.random.default_rng(seed)
    boots=np.mean(np.stack([rng.choice(grouped[f],size=(replicates,8),replace=True).mean(axis=1)
                            for f in FAMILIES],axis=1),axis=1)
    lower,upper=np.quantile(boots,[.025,.975]).tolist()
    return {'object_count':24,'condition_pairs':96,'mean_gain':float(np.mean([r['gain'] for r in phantom_results])),
            'ci_lower':float(lower),'ci_upper':float(upper),
            'positive_object_count':sum(r['gain']>0 for r in phantom_results),
            'family_means':{f:float(grouped[f].mean()) for f in FAMILIES},
            'directional_criterion_met':bool(lower>0),
            'objects':phantom_results,'bootstrap_replicates':replicates,'bootstrap_seed':seed}


def analyze_csv(path):
    with Path(path).open(newline='',encoding='utf8') as f:
        return summarize(list(csv.DictReader(f)))

if __name__=='__main__':
    raise SystemExit('08AJ-D analysis is a specification module. Outcome analysis must be invoked by a separately locked experiment runner.')
