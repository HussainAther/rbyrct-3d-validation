"""08AJ-L: draft protocol and 32^3 NON-CONFIRMATORY numerical replay fixture.

No prospective cohort seed accepted. No accuracy metrics, comparative policy results,
protocol freeze or production authorization. Immutable engineering artifacts.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import time
from pathlib import Path
import numpy as np
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_08aj_d import FAMILIES, SEEDS, ACQUISITION_SEEDS, MODELS, POLICIES
from experiment_08aj_e import full_resolution_pair, checked_mart
from experiment_08aj_g import fair_orders, NOISE_FRACTION
from experiment_05b_08b import nonnegative_noisy_measurements
from experiment_04qa import project
from experiment_08aj_h import statistical_rules

SCHEMA='RBYRCT-08AJ-L-draft-v1'
ENGINEERING_SEED=970099
N=32
BUDGET=2048
EPOCHS=2
RELAXATION=.25
NOISE_SEED=970119
POLICY='information_diag'
SOURCE_FILES=(
    'experiment_04b.py','experiment_04g.py','experiment_04h.py','experiment_04qa.py',
    'experiment_05b_08b.py','experiment_05b_mart.py','experiment_08aj_b.py',
    'experiment_08aj_c_view.py','experiment_08aj_d.py','experiment_08aj_d_analysis.py',
    'experiment_08aj_e.py','experiment_08aj_f.py','experiment_08aj_g.py',
    'experiment_08aj_h.py','experiment_08aj_i.py','experiment_08aj_j.py',
    'experiment_08aj_j_audit.py','experiment_08aj_k.py','experiment_08aj_k_audit.py',
    'experiment_08aj_l.py','experiment_08aj_l_audit.py',
    'experiment_08j.py','experiment_08k.py'
)
ARTIFACTS=('order.npy','measurements.npy','csr_data.npy','csr_indices.npy',
           'csr_indptr.npy','reconstruction.npy','clean_catalogue.npy','noisy_catalogue.npy')


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('utf-8')


def write_exclusive(path, payload):
    with Path(path).open('xb') as f:
        f.write(payload);f.flush();os.fsync(f.fileno())


def save_array(path, a):
    with Path(path).open('xb') as f:
        np.save(f,np.asarray(a),allow_pickle=False);f.flush();os.fsync(f.fileno())


def source_hashes():
    root=Path(__file__).resolve().parent
    return {name:digest((root/name).read_bytes()) for name in SOURCE_FILES}


def review_register():
    """Only evidence-backed statuses: no sign-off inferred from engineering tests."""
    return [
        {'id':'R1_generator_independence','status':'REVIEW_REQUIRED',
         'finding':'Historical six-study manifest audit found no identical seed or truth hash; generator/morphology novelty not established',
         'acceptance':'Document structural comparison and independent scientific reviewer approval'},
        {'id':'R2_primary_inference','status':'REVIEW_REQUIRED',
         'finding':'Proposed n=24, 8/family, 20k stratified percentile bootstrap, primary CI lower bound >0; precision/power not justified',
         'acceptance':'Review effect-size precision, object independence, hypotheses, multiplicity and practical interpretation'},
        {'id':'R3_resources','status':'REVIEW_REQUIRED',
         'finding':'8 GiB proposed peak gate; single 32^3 full projector succeeded; worst-case 24-object total runtime and failure ceilings unknown',
         'acceptance':'Approve full-run wall-clock/peak gates, retry/no-imputation rules'},
        {'id':'R4_64cubed_complete_view','status':'SCOPED_OUT_OF_PRIMARY',
         'finding':'64^3 complete view needs 4096 rays; 32^3 2048 primary is feasible',
         'acceptance':'Keep 64^3 complete-view out of primary and label any later feasible-budget study exploratory'},
        {'id':'R5_production_execution_and_audit','status':'REVIEW_REQUIRED',
         'finding':'08AJ-J is receipt-only; 08AJ-K is 8^3 numerical rehearsal; 08AJ-L is a 32^3 single-policy fixture',
         'acceptance':'Implement and externally check full 480-job resumable production runner and all outcome computations'},
        {'id':'R6_source_protocol_signoff','status':'REVIEW_REQUIRED',
         'finding':'Draft source SHA-256s are recorded but not formally signed/frozen; production always disabled',
         'acceptance':'Record Git commit, reviewer identities/approvals, versioned manifest and signed source lock before prospective execution'},
    ]


def protocol():
    all_seeds={x for seeds in SEEDS.values() for x in seeds}
    if ENGINEERING_SEED in all_seeds: raise AssertionError('engineering phantom collides with cohort')
    reviews=review_register()
    return {
      'schema':SCHEMA,'verdict':'DRAFT_REVIEW_REQUIRED','frozen':False,
      'execution_allowed':False,'no_confirmatory_outcomes':True,
      'primary':{'size':32,'budget':2048,'policy':'information_diag',
                 'reference':'uniform_multiscale','mart_epochs':16,'mart_relaxation':.25,
                 'mart_initial':.3,'noise_fraction':NOISE_FRACTION,
                 'object_count':24,'families':list(FAMILIES),
                 'objects_per_family':{f:len(SEEDS[f]) for f in FAMILIES},
                 'acquisition_seeds':list(ACQUISITION_SEEDS),
                 'forward_models':list(MODELS), 'policies':list(POLICIES),
                 'total_planned_policy_conditions':24*2*2*5,
                 'fine_grid':64,'coarse_truth':'block mean of fine-grid generator'},
      'statistics':statistical_rules(),
      'review_register':reviews,
      'review_required':sum(r['status']=='REVIEW_REQUIRED' for r in reviews),
      'engineering_fixture':{'size':N,'budget':BUDGET,'seed':ENGINEERING_SEED,
          'family':'smooth_heterogeneity','policy':POLICY,
          'models':list(MODELS),'mart_epochs':EPOCHS,'noise_seed':NOISE_SEED,
          'acquisition_seed':940411,'no_accuracy_metrics':True,'not_full_epoch_certification':True},
      'source_sha256':source_hashes(),
      'history':'08AJ-D direct 32^3 truth superseded prospectively by 08AJ-F fine-grid/block-average definition; original draft not modified',
      'disclaimer':'This is freeze preparation, never a source-lock certificate or authorization to run the 24-object study.'
    }


def init(root):
    root=Path(root)
    if root.exists(): raise FileExistsError('refusing to replace previous protocol draft')
    data=protocol();root.mkdir(parents=True)
    write_exclusive(root/'protocol_review_draft.json',canonical(data))
    (root/'engineering_jobs').mkdir()
    write_exclusive(root/'run_status.json',canonical({
        'verdict':'DRAFT_PREPARED','frozen':False,'execution_allowed':False,
        'no_confirmatory_outcomes':True,'review_required':data['review_required']}))
    return data


def check(root):
    root=Path(root)
    blob=(root/'protocol_review_draft.json').read_bytes()
    doc=json.loads(blob)
    if blob!=canonical(doc) or doc.get('schema')!=SCHEMA or doc.get('frozen') is not False or doc.get('execution_allowed') is not False:
        raise ValueError('invalid protocol draft')
    expected=protocol()
    if doc!=expected: raise ValueError('SOURCE_OR_PROTOCOL_MISMATCH')
    return doc,digest(blob)


def run(root, *, interrupt_after=None):
    from experiment_08aj_l_audit import audit_one
    root=Path(root);doc,doc_sha=check(root)
    A=system_matrix(N,4,TILTS).tocsr()
    orders,prefix=fair_orders(A,n=N,angles=4,seed=940411,budget=BUDGET,warm=64,pool=16,batch=32)
    order=np.asarray(orders[POLICY],dtype=np.int64)
    if not np.array_equal(order[:64],prefix): raise AssertionError('shared warm prefix mismatch')
    coarse,fine=full_resolution_pair('smooth_heterogeneity',ENGINEERING_SEED,N)
    records=[]
    for model in MODELS:
        target=root/'engineering_jobs'/model
        if target.exists():
            audit=audit_one(root,model)
            if not audit['pass']: raise ValueError('existing committed artifact invalid: '+str(audit['errors']))
            records.append(model);continue
        stage=root/'engineering_jobs'/('.'+model+'.staging')
        if stage.exists():
            import shutil
            shutil.rmtree(stage)
        stage.mkdir()
        start=time.perf_counter()
        clean=np.asarray(A@coarse if model=='same' else project(fine,N,4,TILTS,factor=2,offset=0.,step=.5,mode='linear'),dtype=np.float64).ravel()
        noisy=nonnegative_noisy_measurements(clean,NOISE_FRACTION,NOISE_SEED)
        recon=checked_mart(A,noisy,order,epochs=EPOCHS,relaxation=RELAXATION)
        selected=A[order].tocsr()
        arrays={'order.npy':order,'measurements.npy':noisy[order],
                'csr_data.npy':selected.data,'csr_indices.npy':selected.indices,
                'csr_indptr.npy':selected.indptr,'reconstruction.npy':recon,
                'clean_catalogue.npy':clean,'noisy_catalogue.npy':noisy}
        if set(arrays)!=set(ARTIFACTS) or any(not np.isfinite(x).all() for x in arrays.values()):
            raise ValueError('invalid engineering arrays')
        for name,arr in arrays.items():save_array(stage/name,arr)
        receipt={'schema':SCHEMA,'model':model,'protocol_sha256':doc_sha,
                 'engineering_only':True,'no_confirmatory_outcomes':True,
                 'matrix_shape':[BUDGET,N**3],
                 'elapsed_seconds':time.perf_counter()-start,
                 'artifact_sha256':{name:digest((stage/name).read_bytes()) for name in ARTIFACTS}}
        write_exclusive(stage/'receipt.json',canonical(receipt))
        stage.rename(target)
        records.append(model)
        if interrupt_after==model:raise RuntimeError('SIMULATED_INTERRUPTION_AFTER_COMMIT '+model)
    result={'verdict':'L_NUMERICAL_ENGINEERING_PASS','models_complete':records,
            'frozen':False,'no_confirmatory_outcomes':True,
            'production_validation_certified':False}
    print(json.dumps(result,indent=2));return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--mode',choices=('init','check','run','freeze','production'),required=True)
    a=p.parse_args()
    if a.mode in ('freeze','production'):
        p.error('REFUSED: scientific sign-off and production runner audit incomplete')
    if a.mode=='init':
        doc=init(a.output_dir)
        print(json.dumps({'verdict':'DRAFT_PREPARED','review_required':doc['review_required'],
                          'frozen':False,'no_confirmatory_outcomes':True},indent=2))
    elif a.mode=='check':
        _,sha=check(a.output_dir)
        print(json.dumps({'verdict':'DRAFT_SOURCE_MATCH','protocol_sha256':sha},indent=2))
    else:run(a.output_dir)

if __name__=='__main__':main()
