"""08AJ-X: outcome-free estimand and independence decision gate. No freeze facility."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

SCHEMA='RBYRCT-08AJ-X-estimand-review-v1'
DEPENDENCIES=('experiment_08aj_d.py','experiment_08aj_f.py','experiment_08aj_u.py','experiment_08aj_w.py')
W_REVIEW_SHA='6d50397ac98b54448d88d3a32f5c97b9a09a920f1845df71c88873e2d7c71cfd'


def canonical(value):
    return (json.dumps(value,sort_keys=True,ensure_ascii=True,separators=(',',':'),allow_nan=False)+'\n').encode('utf8')

def sha(data): return hashlib.sha256(data).hexdigest()

def source_snapshot(root):
    result={}
    for name in DEPENDENCIES:
        p=Path(root)/name
        if not p.is_file(): raise FileNotFoundError('Required review source missing: '+str(p))
        result[name]=sha(p.read_bytes())
    return result

def content(sources):
    return {
        'schema':SCHEMA,'review_only':True,'scientific_signoff':False,
        'frozen':False,'confirmatory_execution_allowed':False,'no_confirmatory_outcomes':True,
        'source_sha256':sources,'prior_windows_w_review_sha256':W_REVIEW_SHA,
        'design':{'objects':24,'fixed_families':['localized_defects','smooth_heterogeneity','irregular_inclusions'],
                  'objects_per_family':8,'acquisition_seeds':[940411,940829],
                  'forward_models':['same','independent'],'primary_budget_rays':2048,
                  'primary_contrast':'information_diag versus uniform_multiscale',
                  'primary_metric':'whole-volume MART RMSE',
                  'four_conditions_per_object':4},
        'gain_definition':{'condition':'1 - RMSE_diag / RMSE_uniform',
                           'object':'arithmetic mean of the four condition gains (2 seeds x 2 forward models)',
                           'family':'arithmetic mean of eight object gains',
                           'overall':'equal-weight mean of the three family means',
                           'denominator_rule':'uniform RMSE must be finite and strictly positive; otherwise stop and document failure',
                           'paired_unit':'object, not condition or voxel',
                           'mean_ratio_not_ratio_of_means':True},
        'targets':{
            'fixed_cohort':{'status':'PRIMARY_DESCRIPTIVE_TARGET_RECOMMENDED',
                'estimand':'exact arithmetic mean of condition-averaged paired gains for the 24 prespecified objects',
                'uncertainty':'no sampling confidence interval for this finite list; report its exact mean, family means, dispersion and all 24 gains',
                'scope':'only this fixed synthetic benchmark under the fixed two acquisition seeds and two model conditions'},
            'generator_superpopulation':{'status':'CONDITIONAL_SECONDARY_INFERENTIAL_TARGET',
                'estimand':'one-third sum over the three fixed families of E[g(object) | family, fixed acquisition/model conditions]',
                'uncertainty':'family-stratified Welch-Satterthwaite t interval, conditional on justified independent object draws and adequate sampling-model approximation',
                'requirements':['seeds select independently generated object-level draws within each family, not reused or adaptively chosen',
                    'common generator parameters and fixed sampling rules',
                    'no unmodeled common object-level shocks or design selection based on outcomes',
                    'the three families are fixed strata, not a random sample of real-world imaging populations'],
                'caution':'deterministic pseudorandom seeds permit an assumed generator-resampling model, but do not by themselves prove probabilistic independence'}},
        'analysis':{'point_estimate':'fixed_cohort mean across 24 objects',
                    'inference_recommendation':'Welch-t interval only for conditional generator estimand, not fixed cohort',
                    'sensitivity':'stratified bootstrap-t under same conditional assumptions',
                    'statistical_evidence':'separately assess lower confidence bound > 0 if an inferential target is approved',
                    'practical_relevance':'report whether the point estimate reaches a preapproved practical threshold; never equate lower bound > 0 with useful effect',
                    'dependence':'if effective within-family dependence remains credible/unresolved, do not report conventional 24-independent-object CI as validated',
                    'family_level_limit':'only three fixed families; no reliable population-of-families cluster inference',
                    'do_not_tune':'No change to methods, thresholds, or object selection after prospective outcomes'},
        'decisions':[
            {'id':'X01','topic':'fixed-cohort descriptive estimand','recommendation':'ADOPT_AS_PRIMARY_DESCRIPTIVE','approval':'PENDING'},
            {'id':'X02','topic':'conditional generator estimand','recommendation':'ALLOW_ONLY_WITH_DOCUMENTED_INDEPENDENCE_ASSUMPTIONS','approval':'PENDING'},
            {'id':'X03','topic':'Welch-t interval','recommendation':'CONDITIONAL_SECONDARY_INFERENCE','approval':'PENDING'},
            {'id':'X04','topic':'family structural novelty','recommendation':'DESCRIBE_AS_THREE_RELATED_SYNTHETIC_STRESS_TEST_FAMILIES','approval':'PENDING'},
            {'id':'X05','topic':'practical effect and numerical failures','recommendation':'SIGN_OFF_BEFORE_FREEZE','approval':'PENDING'},
            {'id':'X06','topic':'live 480-job executor and independent outcome audit','recommendation':'IMPLEMENT_AND_AUDIT_BEFORE_FREEZE','approval':'PENDING'},
            {'id':'X07','topic':'signed source/protocol freeze','recommendation':'BLOCK_UNTIL_APPROVALS','approval':'PENDING'}],
        'interpretation_limits':['no inference to clinical CT performance, patient benefit, dose, or real measurements',
                                 'no evidence of diagonal-policy superiority from engineering replays',
                                 'repeated acquisitions and forward models are paired conditions, not extra independent objects']}

def prepare(out,source_root):
    out=Path(out)
    if out.exists(): raise FileExistsError('Refusing to overwrite previous decision evidence')
    snapshot=source_snapshot(source_root)
    review=content(snapshot)
    blob=canonical(review)
    out.mkdir(parents=True)
    (out/'estimand_review.json').write_bytes(blob)
    status={'verdict':'X_ESTIMAND_REVIEW_PREPARED','review_sha256':sha(blob),'decisions_pending':len(review['decisions']),
            'scientific_signoff':False,'frozen':False,'confirmatory_execution_allowed':False,'no_confirmatory_outcomes':True}
    (out/'run_status.json').write_bytes(canonical(status))
    return status

def check(out,source_root):
    out=Path(out)
    blob=(out/'estimand_review.json').read_bytes()
    review=json.loads(blob)
    status=json.loads((out/'run_status.json').read_bytes())
    if canonical(review)!=blob or sha(blob)!=status['review_sha256']:
        raise ValueError('Review was modified')
    if review!=content(source_snapshot(source_root)):
        raise ValueError('Review or source snapshot differs from current review definition')
    if status!= {'verdict':'X_ESTIMAND_REVIEW_PREPARED','review_sha256':sha(blob),'decisions_pending':7,
            'scientific_signoff':False,'frozen':False,'confirmatory_execution_allowed':False,'no_confirmatory_outcomes':True}:
        raise ValueError('Unexpected status, including possible execution unlock')
    return {'verdict':'X_ESTIMAND_SOURCE_MATCH','decisions_pending':7,'review_sha256':sha(blob),'confirmatory_execution_allowed':False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parent)
    p.add_argument('--mode',choices=('prepare','check'),required=True)
    a=p.parse_args()
    print(json.dumps(prepare(a.output_dir,a.source_root) if a.mode=='prepare' else check(a.output_dir,a.source_root),indent=2))
if __name__=='__main__':main()
