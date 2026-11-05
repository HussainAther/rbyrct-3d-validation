"""Figure 2: provenance-checked 08M/08Q paired reconstruction slices.

Read-only source archives. Run --inspect-phantom first to verify the 06B source API.
"""
import argparse
import csv
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import numpy as np

N = 32
K = 2048
POLICIES = ('coverage', 'information_diag')

def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()

def array_sha(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()

def rows(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def arrays_from(value, prefix='return', depth=0):
    if depth > 3:
        return []
    if isinstance(value, np.ndarray):
        return [(prefix, value)]
    if isinstance(value, dict):
        ans=[]
        for k,v in value.items():
            ans += arrays_from(v, prefix+'.'+str(k), depth+1)
        return ans
    if isinstance(value, (tuple,list)) and len(value) <= 12:
        ans=[]
        for i,v in enumerate(value):
            ans += arrays_from(v,prefix+f'[{i}]',depth+1)
        return ans
    return []

def call_phantom(fun, seed, inspect_only=False):
    sig=inspect.signature(fun)
    args={'n': N, 'factor': 2, 'seed': seed}
    kw={k:args[k] for k in args if k in sig.parameters}
    if len(kw)==3:
        return fun(**kw)
    return fun(N,2,seed)

def discover_truth_and_mask(seed, manifest_row, inspect_only=False):
    ph = importlib.import_module('experiment_06b')
    ms = importlib.import_module('experiment_07c_preflight')
    pval=call_phantom(ph.defect_phantom, seed)
    p_arrays=arrays_from(pval, 'defect_phantom')
    if inspect_only:
        print('defect_phantom signature:', inspect.signature(ph.defect_phantom))
        print('defect_support signature:', inspect.signature(ms.defect_support))
        print('defect_phantom array returns:',[(n,a.shape,str(a.dtype),array_sha(a)) for n,a in p_arrays])
    # The primary verification gate: match archived 08M ground truth bytes.
    truth_candidates=[]
    for name, a in p_arrays:
        if a.size == N**3 and np.issubdtype(a.dtype,np.number):
            truth_candidates.append((name,a))
    target=manifest_row['truth_sha256'].lower()
    exact=[(name,a) for name,a in truth_candidates if array_sha(a)==target]
    if len(exact)!=1:
        raise RuntimeError('Cannot unambiguously reproduce archive-locked truth. '
            f'Expected SHA256={target}; candidate (name, shape, hash) = '
            +repr([(n,a.shape,array_sha(a)) for n,a in truth_candidates])
            +'. Inspect experiment_06b.defect_phantom; DO NOT bypass the hash check.')
    truth=np.ascontiguousarray(exact[0][1]).reshape((N,N,N))
    # defect_support expected to return the coarse 32^3 defect boolean mask.
    fun=ms.defect_support
    sig=inspect.signature(fun)
    args={'n':N,'factor':2,'seed':seed}
    kw={k:args[k] for k in args if k in sig.parameters}
    val=fun(**kw) if len(kw)==3 else fun(N,2,seed)
    candidates=[]
    for name,a in arrays_from(val,'defect_support'):
        if a.size == N**3:
            candidates.append((name,a))
    mask_target=manifest_row['mask_sha256'].lower()
    matches=[]
    for name,a in candidates:
        for variant,mask in [('native',a),('boolean',a.astype(bool)),('threshold_nonzero',a>0)]:
            if array_sha(mask)==mask_target:
                matches.append((name+'/'+variant, mask))
    if inspect_only:
        print('defect_support arrays:',[(n,a.shape,str(a.dtype),array_sha(a)) for n,a in candidates])
    if not matches:
        raise RuntimeError('Cannot reproduce archive-locked defect mask. '
            f'Expected SHA256={mask_target}; candidates='
            +repr([(n,a.shape,array_sha(a)) for n,a in candidates])
            +'. Do not use an unverified mask.')
    mask=np.asarray(matches[0][1],dtype=bool).reshape((N,N,N))
    if int(mask.sum())!=int(manifest_row['mask_voxels']):
        raise RuntimeError('Defect mask voxel count does not match 08M archive.')
    return truth, mask, exact[0][0], matches[0][0]

def choose_object(objrows):
    cells=[r for r in objrows if int(r['acquired'])==K and r['policy']=='information_diag']
    if len(cells)!=8 or len({r['object_id'] for r in cells})!=8:
        raise ValueError('Expected exactly 8 independent 08M object summaries.')
    for r in cells:
        if int(r['n_conditions'])!=4:
            raise ValueError('Each 08M object must average four paired conditions.')
    ordered=sorted(cells,key=lambda r:(float(r['mean_global_gain']),r['object_id']))
    # for even n, choose LOWER of the two central observations, deterministically
    chosen=ordered[(len(ordered)-1)//2]
    return chosen,ordered

def select_replay_rows(manifest, objid, model, seed):
    result={}
    for r in manifest:
        if (r['object_id']==objid and r['model']==model
                and int(r['acquisition_seed'])==seed and int(r['acquired'])==K
                and r['policy'] in POLICIES):
            if r['policy'] in result:
                raise ValueError('Duplicate replay-volume manifest entry')
            result[r['policy']]=r
    if set(result)!=set(POLICIES):
        raise ValueError('Missing coverage or information reconstruction in replay manifest')
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--08m-dir',required=True,type=Path)
    ap.add_argument('--08q-dir',required=True,type=Path)
    ap.add_argument('--output-dir',required=True,type=Path)
    ap.add_argument('--inspect-phantom',action='store_true',help='Print source return arrays before figure generation')
    opts=ap.parse_args()
    if opts.output_dir.exists():
        raise FileExistsError(f'Output exists; never overwrite: {opts.output_dir}')
    m=opts.__dict__['08m_dir']; q=opts.__dict__['08q_dir']
    object_rows=rows(m/'object_level_summary.csv')
    selected, all_ordered=choose_object(object_rows)
    objid=selected['object_id']; objseed=int(objid.split('_')[-1])
    objects=rows(m/'object_manifest.csv')
    matches=[r for r in objects if r['object_id']==objid]
    if len(matches)!=1: raise RuntimeError('Object manifest lacks unique chosen object')
    locked=matches[0]
    print(f'Chosen object={objid}, median-rule global gain={100*float(selected["mean_global_gain"]):.6f}%')
    truth,mask,truth_name,mask_name=discover_truth_and_mask(objseed,locked,opts.inspect_phantom)
    # Predetermined condition: matched model and smallest acquisition seed.
    pref=rows(m/'prefix_reconstructions.csv')
    seeds=sorted({int(r['acquisition_seed']) for r in pref if r['object_id']==objid})
    if len(seeds)!=2: raise RuntimeError('Expected two acquisition seeds')
    acqseed=seeds[0]; model='same'
    manifest=rows(q/'volume_manifest.csv')
    vr=select_replay_rows(manifest,objid,model,acqseed)
    recon={}
    for policy,r in vr.items():
        fn=Path(r['filename'])
        if fn.is_absolute() or '..' in fn.parts: raise RuntimeError('Unsafe path in replay manifest')
        p=q/fn
        if not p.is_file():
            hits=list(q.rglob(fn.name))
            if len(hits)!=1: raise FileNotFoundError(f'Cannot locate {fn}')
            p=hits[0]
        if digest(p)!=r['sha256']:
            raise RuntimeError(f'Replay volume SHA mismatch: {p}')
        a=np.load(p,allow_pickle=False)
        if a.size!=N**3 or not np.all(np.isfinite(a)):
            raise RuntimeError(f'Invalid replayed reconstruction {p}')
        recon[policy]=a.reshape((N,N,N))
    # validate against independent replayed metric records
    comparison=rows(q/'voxel_rmse_comparison.csv')
    checks={}
    for policy,a in recon.items():
        actual=float(np.sqrt(np.mean(np.square(a-truth))))
        rec=[r for r in comparison if r['object_id']==objid and r['model']==model
             and int(r['acquisition_seed'])==acqseed and r['policy']==policy
             and int(r['acquired'])==K and r['metric']=='global_rmse']
        if len(rec)!=1 or abs(actual-float(rec[0]['replayed_rmse']))>2e-8:
            raise RuntimeError(f'Voxel RMSE mismatch for {policy}: {actual}, archived={rec}')
        checks[policy]={'global_rmse':actual,'replay_archive_rmse':float(rec[0]['replayed_rmse'])}
    # choose slice using defect centroid in the fixed x-axis
    coords=np.argwhere(mask)
    slice_index=int(np.rint(np.median(coords[:,0])))
    slice_index=max(0,min(N-1,slice_index))
    gt=truth[slice_index,:,:]
    cov=recon['coverage'][slice_index,:,:]
    inf=recon['information_diag'][slice_index,:,:]
    errors=[np.abs(cov-gt),np.abs(inf-gt)]
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none'})
    fig,axs=plt.subplots(2,3,figsize=(9.0,6.25),layout='constrained')
    vmax=float(max(np.max(gt),np.max(cov),np.max(inf)))
    err_max=float(max(np.max(errors[0]),np.max(errors[1])))
    images=[gt,cov,inf,np.zeros_like(gt),*errors]
    labels=['Ground truth','Coverage','Diagonal information','Defect mask','Coverage absolute error','Information absolute error']
    for i,ax in enumerate(axs.flat):
        if i==3:
            ax.imshow(mask[slice_index].astype(float),cmap='gray',vmin=0,vmax=1,interpolation='nearest',origin='lower')
        elif i<3:
            ax.imshow(images[i],cmap='gray',vmin=0,vmax=vmax,interpolation='nearest',origin='lower')
        else:
            ax.imshow(images[i],cmap='magma',vmin=0,vmax=err_max,interpolation='nearest',origin='lower')
        ax.set_title(labels[i],fontsize=10)
        ax.set_xticks([]); ax.set_yticks([])
        for spine in ax.spines.values(): spine.set_visible(False)
    fig.suptitle('08M / 08Q: 32³ MART reconstruction at 2,048 rays',fontsize=12,fontweight='semibold')
    # Shared legend scales: signal intensity and absolute voxel error.
    cb1=fig.colorbar(plt.cm.ScalarMappable(norm=Normalize(0,vmax),cmap='gray'),ax=list(axs[0,:]),fraction=.018,pad=.012,shrink=.81)
    cb1.set_label('Voxel attenuation (synthetic units)',fontsize=8)
    cb2=fig.colorbar(plt.cm.ScalarMappable(norm=Normalize(0,err_max),cmap='magma'),ax=list(axs[1,1:]),fraction=.025,pad=.015,shrink=.85)
    cb2.set_label('Absolute voxel error',fontsize=8)
    opts.output_dir.mkdir(parents=True)
    base=opts.output_dir/'Figure_02_08M_reconstruction_comparison'
    fig.savefig(base.with_suffix('.pdf'),bbox_inches='tight')
    fig.savefig(base.with_suffix('.svg'),bbox_inches='tight')
    fig.savefig(base.with_suffix('.png'),dpi=450,bbox_inches='tight')
    plt.close(fig)
    source_paths=[m/'object_level_summary.csv',m/'object_manifest.csv',m/'prefix_reconstructions.csv',q/'volume_manifest.csv',q/'voxel_rmse_comparison.csv']
    report={'status':'PASS','figure':'Figure 2','object_selection':'lower-middle object by 08M primary global gain; deterministic, no visual cherry-picking',
        'selected_object_id':objid,'selected_object_global_gain_percent':100*float(selected['mean_global_gain']),
        'condition_selection':'same forward model and numerically smallest acquisition seed','model':model,'acquisition_seed':acqseed,
        'acquired_rays':K,'slice_axis':0,'slice_index':slice_index,'slice_rule':'rounded median coordinate of archived defect-mask support',
        'truth_source_return':truth_name,'mask_source_return':mask_name,'locked_truth_sha256':locked['truth_sha256'],
        'locked_mask_sha256':locked['mask_sha256'],'defect_voxels':int(mask.sum()),'condition_rmse_checks':checks,
        'figure_scaling':'shared intensity limits across truth and reconstructions; shared error limits across both error maps',
        'source_file_sha256':{str(p):digest(p) for p in source_paths},'source_archives_modified':False,
        'limitations':['One rule-selected phantom and one prespecified seed/model condition, not average performance',
                       'Reconstructed volumes from 08Q and regenerated truth/mask from original repository generators',
                       'Source functions share synthetic model assumptions, not independent physical verification']}
    (opts.output_dir/'figure_02_manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','output_dir':str(opts.output_dir),'object_id':objid,'slice_index':slice_index,'RMSE':checks},indent=2))

if __name__=='__main__':
    main()
