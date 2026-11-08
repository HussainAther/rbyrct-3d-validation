"""08AJ-N: 32^3 full-16-epoch NON-COHORT engineering MART and durable replay evidence.

This program cannot execute prospective 24-object jobs, authorize a freeze, or
compute comparative RMSE. Both models use the same geometry/order and a fixed
engineering-only object outside the prospective seed lists.
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, time
from pathlib import Path
import numpy as np
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04qa import project
from experiment_05b_08b import nonnegative_noisy_measurements
from experiment_08aj_d import SEEDS
from experiment_08aj_e import full_resolution_pair, checked_mart
from experiment_08aj_g import fair_orders, NOISE_FRACTION

SCHEMA='RBYRCT-08AJ-N-engineering-16epoch-v1'
N=32
BUDGET=2048
EPOCHS=16
HALF=8
RELAXATION=.25
ENGINEERING_SEED=970099
ACQUISITION_SEED=940411
NOISE_SEED=970119
FAMILY='smooth_heterogeneity'
POLICY='information_diag'
MODELS=('same','independent')
FILES=('order.npy','measurements.npy','csr_data.npy','csr_indices.npy',
       'csr_indptr.npy','clean_catalogue.npy','noisy_catalogue.npy',
       'reconstruction_epoch08.npy','reconstruction_epoch16.npy')
SOURCES=('experiment_04b.py','experiment_04g.py','experiment_04h.py',
         'experiment_04qa.py','experiment_05b_08b.py','experiment_05b_mart.py',
         'experiment_08aj_b.py','experiment_08aj_c_view.py',
         'experiment_08aj_d.py','experiment_08aj_e.py','experiment_08aj_f.py',
         'experiment_08aj_g.py','experiment_08aj_n.py','experiment_08aj_n_audit.py',
         'experiment_08j.py','experiment_08k.py')

def sha(b): return hashlib.sha256(b).hexdigest()
def canonical(obj): return (json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('utf-8')
def exclusive(path,data):
    with Path(path).open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
def save(path,arr):
    with Path(path).open('xb') as f:np.save(f,arr,allow_pickle=False);f.flush();os.fsync(f.fileno())
def sources():
    root=Path(__file__).resolve().parent
    return {n:sha((root/n).read_bytes()) for n in SOURCES}
def proposal():
    if ENGINEERING_SEED in {s for seeds in SEEDS.values() for s in seeds}:
        raise RuntimeError('engineering seed overlaps prospective cohort')
    return {'schema':SCHEMA,'verdict':'ENGINEERING_ONLY','frozen':False,
            'execution_allowed':False,'no_confirmatory_outcomes':True,
            'production_480_job_certified':False,
            'n':N,'candidate_rays':12288,'budget':BUDGET,
            'engineering_seed':ENGINEERING_SEED,'family':FAMILY,
            'acquisition_seed':ACQUISITION_SEED,'noise_seed':NOISE_SEED,
            'noise_fraction':NOISE_FRACTION,'policy':POLICY,'models':list(MODELS),
            'mart_initial':.3,'mart_epochs':EPOCHS,'checkpoint_epochs':[HALF,EPOCHS],
            'mart_relaxation':RELAXATION,'source_sha256':sources(),
            'limitations':[
             'One fixed engineering phantom, one ordering, two forward-model cases only',
             'Independent replay verifies recurrence from saved rows, not forward-projector correctness',
             'No complete 480-job executor, scientific sign-off, production source lock, or outcome analysis']}
def init(root):
    root=Path(root)
    if root.exists():raise FileExistsError('refusing to overwrite preexisting evidence')
    p=proposal();root.mkdir(parents=True)
    exclusive(root/'engineering_plan.json',canonical(p))
    (root/'jobs').mkdir()
    exclusive(root/'run_status.json',canonical({'verdict':'N_PLAN_CREATED',
              'frozen':False,'execution_allowed':False,'no_confirmatory_outcomes':True}))
    return p
def check(root):
    root=Path(root)
    blob=(root/'engineering_plan.json').read_bytes();p=json.loads(blob)
    if blob!=canonical(p) or p!=proposal():raise ValueError('SOURCE_OR_PLAN_MISMATCH')
    if {x.name for x in (root/'jobs').iterdir()}-set(MODELS)-{'.same.staging','.independent.staging'}:
        raise ValueError('unexpected engineering jobs')
    return p,sha(blob)
def run(root,*,interrupt_after=None):
    from experiment_08aj_n_audit import audit_one
    root=Path(root);_,plan_hash=check(root)
    # Audit and reuse committed jobs before expensive geometry selection. Never overwrite.
    done=[]
    for model in MODELS:
        if (root/'jobs'/model).exists():
            result=audit_one(root,model)
            if not result['pass']:raise ValueError('committed evidence failed audit: '+str(result['errors']))
            done.append(model)
    if len(done)==len(MODELS):
        return {'verdict':'N_16_EPOCH_ENGINEERING_PASS','models_complete':done,
                'frozen':False,'no_confirmatory_outcomes':True,'production_480_job_certified':False}
    # No prospective seed or family enumerated here; never accept arbitrary object args.
    A=system_matrix(N,4,TILTS).tocsr()
    orders,prefix=fair_orders(A,n=N,angles=4,seed=ACQUISITION_SEED,
                              budget=BUDGET,warm=64,pool=16,batch=32)
    order=np.asarray(orders[POLICY],dtype=np.int64)
    if not np.array_equal(order[:64],prefix):raise AssertionError('prefix mismatch')
    coarse,fine=full_resolution_pair(FAMILY,ENGINEERING_SEED,N)
    for model in MODELS:
        target=root/'jobs'/model
        if model in done:continue
        stage=root/'jobs'/('.'+model+'.staging')
        if stage.exists():shutil.rmtree(stage)
        stage.mkdir()
        t0=time.perf_counter()
        clean=np.asarray(A@coarse if model=='same' else
              project(fine,N,4,TILTS,factor=2,offset=0.,step=.5,mode='linear'),dtype=np.float64).ravel()
        noisy=nonnegative_noisy_measurements(clean,NOISE_FRACTION,NOISE_SEED)
        selected=A[order].tocsr()
        data={'order.npy':order,'measurements.npy':noisy[order],
              'csr_data.npy':selected.data,'csr_indices.npy':selected.indices,
              'csr_indptr.npy':selected.indptr,'clean_catalogue.npy':clean,
              'noisy_catalogue.npy':noisy}
        for epoch,filename in ((HALF,'reconstruction_epoch08.npy'),
                               (EPOCHS,'reconstruction_epoch16.npy')):
            data[filename]=checked_mart(A,noisy,order,epochs=epoch,relaxation=RELAXATION)
        if set(data)!=set(FILES) or any(not np.isfinite(a).all() for a in data.values()):
            raise ValueError('invalid array roster or nonfinite values')
        for name,array in data.items():save(stage/name,array)
        receipt={'schema':SCHEMA,'model':model,'plan_sha256':plan_hash,
                 'engineering_only':True,'no_confirmatory_outcomes':True,
                 'frozen':False,'matrix_shape':[BUDGET,N**3],
                 'epochs':[HALF,EPOCHS],
                 'elapsed_seconds':time.perf_counter()-t0,
                 'artifact_sha256':{name:sha((stage/name).read_bytes()) for name in FILES}}
        exclusive(stage/'receipt.json',canonical(receipt))
        stage.rename(target)
        done.append(model)
        if interrupt_after==model:raise RuntimeError('SIMULATED_INTERRUPTION '+model)
    return {'verdict':'N_16_EPOCH_ENGINEERING_PASS','models_complete':done,
            'frozen':False,'no_confirmatory_outcomes':True,
            'production_480_job_certified':False}
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir',required=True,type=Path)
    ap.add_argument('--mode',required=True,choices=('init','check','run','production','freeze'))
    a=ap.parse_args()
    if a.mode in ('production','freeze'):ap.error('REFUSED: no prospective execution or freeze')
    if a.mode=='init': result={'verdict':'N_PLAN_CREATED','plan_schema':init(a.output_dir)['schema']}
    elif a.mode=='check':result={'verdict':'N_SOURCE_MATCH','plan_sha256':check(a.output_dir)[1]}
    else:result=run(a.output_dir)
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
