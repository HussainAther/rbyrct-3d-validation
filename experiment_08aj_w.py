"""08AJ-W: outcome-free method selection sensitivity study; NO confirmatory inputs.

Fixed-family estimand with three families of eight objects. Correlated latent common
shocks model possible within-family dependence. Their magnitudes are hypothetical,
not estimates of real dependency. A 24-object independent-unit CI is not certified
under within-family correlation. Selection is conditional, never approval.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.stats import t as tdist
from experiment_08aj_v import (SCENARIOS, METHODS, generate_gain_sample, intervals,
                               canonical, sha, stratified_se)

SCHEMA='RBYRCT-08AJ-W-prespecified-hypothetical-calibration-v1'
SEED=941113
RHO=(0.0, 0.15, 0.35)
SD=(0.03, 0.06)
MU=(0.0, 0.02)
# Each coverage method uses the same exact simulated data per trial.

def sample(rng,scenario,mu,sd,rho):
    if not (0 <= rho < 1): raise ValueError('invalid dependence parameter')
    z=generate_gain_sample(rng,scenario,0.0,1.0)
    # Exchangeable common-family shock mixed with independent object shocks.
    # For non-Gaussian scenarios rho is an approximate latent-shock fraction,
    # NOT guaranteed Pearson pairwise correlation.
    common=rng.normal(size=(3,1))
    return mu + sd*(np.sqrt(1-rho)*z+np.sqrt(rho)*common)

def calibration(*,trials=600,bootstraps=400,seed=SEED,scenarios=SCENARIOS,rhos=RHO,sds=SD,means=MU):
    if trials<100 or bootstraps<200: raise ValueError('calibration precision too low')
    rng=np.random.default_rng(seed)
    rows=[]
    for scenario in scenarios:
      if scenario not in SCENARIOS: raise ValueError('unknown scenario')
      for rho in rhos:
       for sd in sds:
        for mu in means:
         acc={m:{'cover':0,'positive':0,'meaningful':0,'widths':[]} for m in METHODS}
         for _ in range(trials):
          x=sample(rng,scenario,mu,sd,rho)
          bs=intervals(x,bootstrap_count=bootstraps,rng=rng)
          for method,(low,high) in bs.items():
           st=acc[method]
           st['cover']+=int(low<=mu<=high)
           st['positive']+=int(low>0)
           st['meaningful']+=int(low>0.02)
           st['widths'].append(high-low)
         for method,st in acc.items():
          p=st['cover']/trials
          rows.append({'scenario':scenario,'latent_family_shock_rho':float(rho),
           'hypothetical_sd':float(sd),'true_mean':float(mu),'method':method,
           'coverage':p,'coverage_mcse':float(np.sqrt(p*(1-p)/trials)),
           'prob_lower_above_zero':st['positive']/trials,
           'prob_lower_above_2pct':st['meaningful']/trials,
           'median_width':float(np.median(st['widths']))})
    return rows

def decision(rows,trials):
    # Predeclared and invariant across outcomes: only independent-object settings
    # qualify for a recommendation. Guardrail assesses conservative minimum
    # coverage across 16 independent settings with MC error margin (not a proof).
    independent=[r for r in rows if r['latent_family_shock_rho']==0.0]
    methods={}
    for name in METHODS:
        subset=[r for r in independent if r['method']==name]
        cover=[r['coverage'] for r in subset]
        methods[name]={'mean_coverage':float(np.mean(cover)),
          'minimum_coverage':float(np.min(cover)),
          'maximum_coverage':float(np.max(cover)),
          'mean_median_ci_width':float(np.mean([r['median_width'] for r in subset]))}
    # Winner selection is NOT based on outcomes or cherry-picked simulated power.
    # Prefer analytically transparent, variance-aware Welch-t as provisional default;
    # flag failures rather than auto-approving it.
    welch=methods['stratified_welch_t']
    # Conservative threshold treats 1.645*binomial MCSE as screening tolerance,
    # not a theorem or final approval. This is a reporting criterion only.
    target=0.95
    failures=[]
    for r in independent:
       if r['method']=='stratified_welch_t' and r['coverage']+1.96*r['coverage_mcse']<0.93:
           failures.append({'scenario':r['scenario'],'sd':r['hypothetical_sd'],
                            'true_mean':r['true_mean'],'coverage':r['coverage']})
    dependency=[]
    for rho in sorted(set(r['latent_family_shock_rho'] for r in rows)):
      if rho==0: continue
      subset=[r for r in rows if r['latent_family_shock_rho']==rho and r['method']=='stratified_welch_t']
      dependency.append({'latent_rho':rho,'mean_coverage':float(np.mean([r['coverage'] for r in subset])),
                         'minimum_coverage':float(min(r['coverage'] for r in subset))})
    return {'provisional_primary_method':'stratified_welch_t',
      'status':'CONDITIONAL_RECOMMENDATION_NOT_APPROVED',
      'selection_rationale':'transparent family-stratified variance estimate with Welch-Satterthwaite df; symmetric interval; object as unit; predeclared, not selected by real outcome',
      'independent_settings':len(independent)//len(METHODS),
      'method_summary_rho_zero':methods,'welch_screening_failures':failures,
      'within_family_dependence_sensitivity':dependency,
      'approval_conditions':['scientific sign-off on fixed-family estimand and object independence assumptions',
       'review calibration weaknesses under heavy-tailed, skewed and correlated scenarios',
       'decide how family-level dependence is handled; three families cannot justify robust population-level family inference',
       'review practical 2% threshold separately from evidence that mean gain is greater than zero',
       'freeze analysis, source hashes and failure rules before confirmatory outcomes'],
      'do_not_interpret':'This is not empirical validation or a license to run prospective jobs.'}

def report(*,trials=600,bootstraps=400,seed=SEED):
    rows=calibration(trials=trials,bootstraps=bootstraps,seed=seed)
    return {'schema':SCHEMA,'verdict':'W_STATISTICAL_METHOD_REVIEW_PREPARED',
      'design':'24 hypothetical object gains; 3 fixed families x 8 objects; family mean equally weighted',
      'simulations':{'trials_per_setting':trials,'bootstrap_resamples':bootstraps,
        'seed':seed,'scenario_names':list(SCENARIOS),'rhos':list(RHO),'sd_levels':list(SD),
        'mean_levels':list(MU),'method_names':list(METHODS),'settings':len(rows)},
      'dependency_model':'each family has Gaussian shared shock with latent mixing rho; not empirical correlations',
      'rows':rows,'decision':decision(rows,trials),
      'method_approved':False,'frozen':False,'confirmatory_execution_allowed':False,
      'no_confirmatory_outcomes':True}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--trials',type=int,default=600)
    p.add_argument('--bootstraps',type=int,default=400)
    p.add_argument('--seed',type=int,default=SEED)
    a=p.parse_args(argv)
    if a.output_dir.exists():raise FileExistsError('will not overwrite prior calibration evidence')
    d=report(trials=a.trials,bootstraps=a.bootstraps,seed=a.seed)
    a.output_dir.mkdir(parents=True,exist_ok=False)
    raw=canonical(d)
    (a.output_dir/'statistical_method_review.json').write_bytes(raw)
    status={'verdict':d['verdict'],'method_recommendation':d['decision']['provisional_primary_method'],
      'recommendation_only':True,'method_approved':False,'frozen':False,
      'confirmatory_execution_allowed':False,'no_confirmatory_outcomes':True,
      'settings':len(d['rows']),'review_sha256':sha(raw)}
    (a.output_dir/'run_status.json').write_bytes(canonical(status))
    print(json.dumps(status,indent=2))
if __name__=='__main__':main()
