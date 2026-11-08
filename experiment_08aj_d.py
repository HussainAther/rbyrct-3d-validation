"""08AJ-D: prospective design, synthetic phantom manifest, and source-lock utility.

NO reconstruction or outcome-dependent policy selection. Review protocol before freeze.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np

SCHEMA='RBYRCT-08AJ-D-draft-v1'
SIZE=32
FAMILIES=('localized_defects','smooth_heterogeneity','irregular_inclusions')
SEEDS={family:tuple(940100+100*i+j for j in range(1,9)) for i,family in enumerate(FAMILIES)}
ACQUISITION_SEEDS=(940411,940829)
MODELS=('same','independent')
POLICIES=('information_diag','uniform_multiscale','coverage','stratified_random_04h','complete_view')
PRIMARY_POLICY='information_diag'
PRIMARY_REFERENCE='uniform_multiscale'
CHECKPOINTS=(1024,2048,4096)
SOURCE_MODULES=('experiment_08aj_d','experiment_08aj_b','experiment_08aj_c_view',
                'experiment_08k','experiment_08j','experiment_04b','experiment_04g',
                'experiment_04h','experiment_05b_08b','experiment_05b_mart')


def digest_array(x):
    return hashlib.sha256(np.ascontiguousarray(x,dtype='<f8').tobytes()).hexdigest()


def phantom(family, seed, n=SIZE):
    """Three prespecified *development-proposal* object families; no acquisition access.

    Coordinate origin and ranges fixed, deterministic independent RNG per object.
    All arrays nonnegative, distinct, and finite; outputs are not observed scanner data.
    """
    if family not in FAMILIES or n<8:
        raise ValueError('invalid family or volume size')
    rng=np.random.default_rng(int(seed))
    z,y,x=np.mgrid[:n,:n,:n].astype(np.float64)
    z=(z+0.5)/n; y=(y+0.5)/n; x=(x+0.5)/n
    # All objects have a common, nonzero synthetic attenuation backdrop.
    field=np.full((n,n,n),0.15,dtype=np.float64)
    sphere=(x-.5)**2+(y-.5)**2+(z-.5)**2 < (.31+rng.uniform(-.015,.015))**2
    field[sphere]=.8
    if family=='localized_defects':
        for _ in range(3):
            ctr=rng.uniform(.34,.66,3)
            r=rng.uniform(.035,.075)
            mask=(x-ctr[0])**2+(y-ctr[1])**2+(z-ctr[2])**2 < r*r
            field[mask]=rng.uniform(.22,.48)
    elif family=='smooth_heterogeneity':
        freq=rng.uniform(1.0,2.3,3)
        phase=rng.uniform(0,2*np.pi,3)
        smooth=(np.sin(2*np.pi*freq[0]*x+phase[0]) +
                np.sin(2*np.pi*freq[1]*y+phase[1]) +
                np.sin(2*np.pi*freq[2]*z+phase[2]))/3
        field[sphere]=.8+.15*smooth[sphere]
        ctr=rng.uniform(.37,.63,3)
        gauss=np.exp(-sum((coord-c)**2 for coord,c in zip((x,y,z),ctr))/.018)
        field[sphere]-=.19*gauss[sphere]
    else:
        for _ in range(8):
            ctr=rng.uniform(.22,.78,3)
            axes=rng.uniform(.028,.11,3)
            ellipsoid=sum(((coord-c)/a)**2 for coord,c,a in zip((x,y,z),ctr,axes))<1
            field[ellipsoid]=rng.uniform(.22,1.10)
        # Deterministic multiscale texture restricted to background sphere.
        a=rng.uniform(3,7,3); phase=rng.uniform(0,2*np.pi,3)
        texture=.08*np.sin(2*np.pi*(a[0]*x+a[1]*y+a[2]*z)+phase[0])
        field[sphere]+=texture[sphere]
    if not (field.shape==(n,n,n) and np.isfinite(field).all() and np.min(field)>0):
        raise AssertionError('invalid phantom')
    return field


def source_hashes():
    result={}
    for module in SOURCE_MODULES:
        spec=importlib.util.find_spec(module)
        if spec is None or spec.origin is None:
            raise FileNotFoundError('missing source module: '+module)
        result[module+'.py']=hashlib.sha256(Path(spec.origin).read_bytes()).hexdigest()
    return result


def design(n=SIZE):
    if n!=SIZE:
        raise ValueError('current main protocol specifies n=32 only; 64 study is separate')
    seeds=[s for values in SEEDS.values() for s in values]
    if len(seeds)!=24 or len(set(seeds))!=24:
        raise AssertionError('object seeds must be unique')
    objects=[{'family':f,'object_seed':seed,'truth_sha256':digest_array(phantom(f,seed,n))}
             for f in FAMILIES for seed in SEEDS[f]]
    return {'schema':SCHEMA,'status':'DRAFT_NOT_FROZEN','size':n,'objects':objects,
            'object_count':24,'acquisition_seeds':list(ACQUISITION_SEEDS),
            'models':list(MODELS),'policies':list(POLICIES),'checkpoints':list(CHECKPOINTS),
            'primary_checkpoint':2048,'primary_policy':PRIMARY_POLICY,'primary_reference':PRIMARY_REFERENCE,
            'primary_endpoint':'Within each object: mean of four paired condition-level (1-RMSE_diag/RMSE_uniform); then equal-weight mean of 24 objects',
            'primary_unit':'phantom object; acquisition seeds and models are paired conditions',
            'analysis':'two-sided 95% percentile bootstrap CI, stratified by family, 20000 replicates, seeded 941007; directional success only if lower limit >0',
            'family_weights':'8 objects per family; equal object weights',
            'secondary':'coverage/stratified/complete-view, defect and nondefect RMSE, Gini, runtime, budget sensitivity, family effects; exploratory',
            'complete_view_note':'32-cubed budgets 1024, 2048, 4096 permit 1/2/4 whole views; limited angular diversity, secondary only',
            'mathematical_geometry':'4 azimuth angles, tilts (-20,0,20), 12 views, n*n detector cells each',
            'mart':{'epochs':16,'relaxation':0.25,'initial':0.3,'noise_fraction':0.005},
            'implementation_status':'phantom generator and analysis formula implemented; main reconstruction driver and independent mismatch forward model adapter NOT implemented',
            'lock_blockers':['Confirm phantom families are substantively distinct and do not overlap earlier study source objects',
                             'Define and test independent forward-model for each new phantom family, without using same-model-only results',
                             'Verify uniform policy geometry and admissibility against diagonal selector and warm-history constraints',
                             'Define full experimental driver, noise seeds, failure rules and time/resource ceilings',
                             'Document precision/power rationale, bootstrap assumptions and effect-size criterion',
                             'Peer review design, commit source hashes and frozen lock before outcomes'],
            'no_reconstruction_or_outcome_data':True,'source_sha256':source_hashes()}


def write_json(path,data):
    Path(path).write_text(json.dumps(data,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf8')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--check-lock',type=Path)
    p.add_argument('--freeze',type=Path,help='EXPLICIT optional lock after design review; does not run outcomes')
    a=p.parse_args(argv)
    if a.freeze:
        raise RuntimeError('REFUSE_TO_FREEZE: unresolved independent-model and main-driver blockers; design remains draft')
    if a.check_lock:
        locked=json.loads(a.check_lock.read_text(encoding='utf8'))
        if locked!=design():
            raise RuntimeError('lock mismatch: design or source changed')
        print('DESIGN_LOCK_MATCH')
        return
    if a.output_dir.exists():
        raise FileExistsError('output exists; preserving prior evidence')
    a.output_dir.mkdir(parents=True)
    d=design()
    write_json(a.output_dir/'08aj_d_design_draft.json',d)
    write_json(a.output_dir/'run_status.json',{'verdict':'DRAFT_PASS','complete':True,'no_outcome_data':True,
            'frozen':False,'object_count':24,'lock_blockers':len(d['lock_blockers'])})
    print(json.dumps({'verdict':'DRAFT_PASS','object_count':24,'family_counts':{f:8 for f in FAMILIES},
                      'no_outcome_data':True,'frozen':False,'remaining_lock_blockers':len(d['lock_blockers'])},indent=2))

if __name__=='__main__':
    main()
