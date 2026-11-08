"""08AJ-K engineering-only numerical MART runner, NOT confirmatory.

Fixed 8^3 engineering phantom, one acquired-ray policy, two forward models.
Never accepts user object seeds, budgets, families, or production execution.
Immutable committed checkpoints and safe resumability. No accuracy endpoints.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
import numpy as np
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_08aj_e import full_resolution_pair, checked_mart
from experiment_08aj_g import fair_orders
from experiment_05b_08b import nonnegative_noisy_measurements
from experiment_04qa import project

N=8
ANGLES=4
BUDGET=128
WARM=8
ENGINEERING_SEED=970099
NOISE_SEED=970119
EPOCHS=2
RELAXATION=.25
POLICY='information_diag'
SOURCE_FILES=('experiment_04b.py','experiment_04g.py','experiment_04h.py',
              'experiment_04qa.py','experiment_05b_08b.py','experiment_05b_mart.py',
              'experiment_08aj_b.py','experiment_08aj_c_view.py',
              'experiment_08aj_d.py','experiment_08aj_e.py','experiment_08aj_g.py',
              'experiment_08aj_k.py','experiment_08aj_k_audit.py')
SCHEMA='RBYRCT-08AJ-K-engineering-v1'


def sha(data:bytes):
    return hashlib.sha256(data).hexdigest()


def source_hashes():
    root=Path(__file__).resolve().parent
    return {name:sha((root/name).read_bytes()) for name in SOURCE_FILES}


def canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('ascii')


def write_exclusive(path, blob):
    with Path(path).open('xb') as f:
        f.write(blob)
        f.flush()
        os.fsync(f.fileno())


def write_npy(path, data):
    with Path(path).open('xb') as f:
        np.save(f,np.asarray(data),allow_pickle=False)
        f.flush()
        os.fsync(f.fileno())


def common():
    A=system_matrix(N,ANGLES,TILTS).tocsr()
    orders,_=fair_orders(A,n=N,angles=ANGLES,seed=940411,budget=BUDGET,warm=WARM,pool=8,batch=8)
    order=np.asarray(orders[POLICY],dtype=np.int64)
    truth,fine=full_resolution_pair('smooth_heterogeneity',ENGINEERING_SEED,N)
    return A,order,truth,fine


def prepare(root):
    root=Path(root)
    if root.exists():
        raise FileExistsError('refusing to replace earlier engineering run')
    root.mkdir(parents=True)
    info={'schema':SCHEMA,'frozen':False,'execution_allowed':False,
          'engineering_only':True,'no_confirmatory_outcomes':True,
          'n':N,'angles':ANGLES,'budget':BUDGET,'object_seed':ENGINEERING_SEED,
          'object_family':'smooth_heterogeneity','acquisition_seed':940411,
          'noise_seed':NOISE_SEED,'mart_epochs':EPOCHS,'mart_relaxation':RELAXATION,
          'mart_initial':.3,'policy':POLICY,'models':['same','independent'],
          'source_sha256':source_hashes(),
          'prohibited':'24-object production jobs and statistical outcomes'}
    write_exclusive(root/'engineering_plan.json',canonical(info))
    (root/'jobs').mkdir()
    return info


def check_plan(root):
    root=Path(root)
    blob=(root/'engineering_plan.json').read_bytes()
    plan=json.loads(blob)
    if blob!=canonical(plan) or plan.get('schema')!=SCHEMA or plan.get('engineering_only') is not True:
        raise ValueError('invalid engineering plan')
    if any(plan.get(k)!=v for k,v in {'n':N,'budget':BUDGET,'object_seed':ENGINEERING_SEED,
             'policy':POLICY,'mart_epochs':EPOCHS,'mart_relaxation':RELAXATION,
             'models':['same','independent'],'frozen':False,'execution_allowed':False}.items()):
        raise ValueError('altered engineering settings')
    if plan.get('source_sha256')!=source_hashes():
        raise ValueError('SOURCE_MISMATCH: engineering code changed')
    return plan,sha(blob)


def execute(root, *, stop_after=None):
    from experiment_08aj_k_audit import audit_one
    root=Path(root)
    _,plan_sha=check_plan(root)
    A,order,truth,fine=common()
    completed=[]
    for model in ('same','independent'):
        target=root/'jobs'/model
        if target.exists():
            check=audit_one(root,model,replay=True)
            if not check['pass']:
                raise ValueError('existing committed checkpoint invalid: '+str(check['errors']))
            completed.append(model)
            continue
        stage=root/'jobs'/('.'+model+'.staging')
        if stage.exists():
            # An incomplete, never-committed staging area can be safely recreated.
            shutil.rmtree(stage)
        stage.mkdir()
        if model=='same':
            clean=np.asarray(A@truth,dtype=np.float64).ravel()
        else:
            clean=np.asarray(project(fine,N,ANGLES,TILTS,factor=2,offset=0.0,step=.5,mode='linear'),dtype=np.float64).ravel()
        noisy=nonnegative_noisy_measurements(clean,.005,NOISE_SEED)
        recon=checked_mart(A,noisy,order,epochs=EPOCHS,relaxation=RELAXATION)
        selected=A[order].tocsr()
        arrays={
            'order.npy':order,'measurements.npy':noisy[order],
            'csr_data.npy':selected.data,'csr_indices.npy':selected.indices,
            'csr_indptr.npy':selected.indptr,'reconstruction.npy':recon,
            'clean_catalogue.npy':clean,'noisy_catalogue.npy':noisy,
        }
        if not np.isfinite(recon).all() or (recon<=0).any():
            raise ValueError('invalid engineering reconstruction')
        for filename,value in arrays.items():
            write_npy(stage/filename,value)
        receipt={'schema':SCHEMA,'model':model,'engineering_only':True,
                 'no_confirmatory_outcomes':True,'plan_sha256':plan_sha,
                 'matrix_shape':[BUDGET,N**3],
                 'array_sha256':{name:sha((stage/name).read_bytes()) for name in arrays}}
        write_exclusive(stage/'receipt.json',canonical(receipt))
        # Commit only fully completed, self-contained checkpoint directories.
        stage.rename(target)
        completed.append(model)
        if stop_after==model:
            raise RuntimeError('SIMULATED_INTERRUPTION_AFTER_COMMIT: '+model)
    result={'verdict':'NUMERICAL_ENGINEERING_PASS','models_complete':completed,
            'reused_or_created':True,'frozen':False,'no_confirmatory_outcomes':True}
    print(json.dumps(result,indent=2))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--mode',choices=('init','run','check','execute'),required=True)
    args=p.parse_args()
    if args.mode=='execute':
        p.error('CONFIRMATORY_EXECUTION_DISABLED: this is an 8^3 engineering fixture')
    if args.mode=='init':
        info=prepare(args.output_dir)
        print(json.dumps({'verdict':'ENGINEERING_PLAN_CREATED','models':info['models'],
                          'no_confirmatory_outcomes':True},indent=2))
    elif args.mode=='check':
        _,digest=check_plan(args.output_dir)
        print(json.dumps({'verdict':'ENGINEERING_SOURCE_MATCH','plan_sha256':digest},indent=2))
    else:
        execute(args.output_dir)

if __name__=='__main__':
    main()
