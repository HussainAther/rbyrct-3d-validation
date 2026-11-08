"""08AJ-B: geometry-only acquisition-baseline engineering validation.

NO phantom, observed data, reconstruction, error metrics, or scientific comparisons.
The uniform policy is a *proposed* deterministic dyadic detector-grid ordering,
not a claim about a standard or executable physical CT protocol.
The stratified policy is the unchanged historical experiment_04h.stratified_order.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import numpy as np

DEFAULTS = {"size":32, "angles":4, "tilts":3, "budget":4096, "seed":930101}


def order_digest(order):
    return hashlib.sha256(np.asarray(order, dtype='<i8').tobytes()).hexdigest()


def _bit_reversal(value:int, bits:int)->int:
    out=0
    for _ in range(bits):
        out=(out<<1)|(value&1)
        value>>=1
    return out


def uniform_multiscale_order(n:int, angles:int, tilts:int)->np.ndarray:
    """Deterministic round-robin views with multiscale detector-cell permutation.

    For each detector coordinate (row, column), interleave binary digits into a
    Morton code, reverse the base-4 digits, and sort by that key. At detector
    resolutions 2^b this visits one cell of each coarser quadrant before
    revisiting a quadrant at the next dyadic level. Each full-view cycle has
    one ray per view; ray ID = view*n*n + detector_row*n + detector_col.
    For non-power-of-two n, padded Morton keys are deterministically filtered.
    No RNG, system matrix, phantom, or detector values are used.
    """
    if min(n,angles,tilts)<1:
        raise ValueError('invalid geometry')
    bits=max(1,(n-1).bit_length())
    cells=[]
    for row in range(n):
        for col in range(n):
            morton=0
            for i in range(bits):
                morton|=((col>>i)&1)<<(2*i)
                morton|=((row>>i)&1)<<(2*i+1)
            key=0
            for i in range(bits):
                key=(key<<2)|((morton>>(2*i))&3)
            cells.append((key,row*n+col))
    cells.sort()
    detector=np.fromiter((x[1] for x in cells),dtype=np.int64,count=n*n)
    views=np.arange(angles*tilts,dtype=np.int64)
    return (detector[:,None]+(n*n)*views[None,:]).ravel()


def build_orders(n:int, angles:int, tilts:int, seed:int):
    from experiment_04h import stratified_order
    return {'uniform_multiscale':uniform_multiscale_order(n,angles,tilts),
            'stratified_random_04h':np.asarray(stratified_order(n,angles,tilts,seed),dtype=np.int64)}


def validate_order(order,n,angles,tilts,budget):
    size=n*n*angles*tilts
    ids=np.asarray(order)
    if ids.ndim!=1 or ids.shape[0]!=size or ids.dtype.kind not in 'iu':
        raise AssertionError('order does not contain full integer catalogue')
    if np.min(ids)<0 or np.max(ids)>=size or len(np.unique(ids))!=size:
        raise AssertionError('order is not a permutation of catalogue')
    if not 1<=budget<=size:
        raise ValueError('invalid budget')
    nviews=angles*tilts
    # Every cycle, when complete, contains exactly one ray from each view.
    cycles=ids.reshape(-1,nviews)//(n*n)
    if not np.all(np.sort(cycles,axis=1)==np.arange(nviews)):
        raise AssertionError('not balanced view-cycle ordering')
    return ids[:budget]


def profile_prefix(prefix,n,angles,tilts):
    nviews=angles*tilts
    view=prefix//(n*n)
    detector=prefix%(n*n)
    vc=np.bincount(view,minlength=nviews)
    dc=np.bincount(detector,minlength=n*n)
    return {'ray_count':int(len(prefix)), 'unique_rays':int(len(np.unique(prefix))),
            'views_covered':int(np.count_nonzero(vc)),
            'view_counts_min':int(vc.min()), 'view_counts_max':int(vc.max()),
            'unique_detector_cells':int(np.count_nonzero(dc)),
            'detector_counts_min':int(dc.min()), 'detector_counts_max':int(dc.max()),
            'selected_sha256':order_digest(prefix)}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--size',type=int,default=DEFAULTS['size'])
    p.add_argument('--angles',type=int,default=DEFAULTS['angles'])
    p.add_argument('--tilts',type=int,default=DEFAULTS['tilts'])
    p.add_argument('--budget',type=int,default=DEFAULTS['budget'])
    p.add_argument('--seed',type=int,default=DEFAULTS['seed'])
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--smoke',action='store_true')
    args=p.parse_args(argv)
    if args.smoke:
        args.size,args.angles,args.tilts,args.budget=8,4,3,64
    total=args.size*args.size*args.angles*args.tilts
    if min(args.size,args.angles,args.tilts,args.budget)<1 or args.budget>total or args.seed<0:
        p.error('invalid geometry, budget or seed')
    root=args.output_dir
    if root.exists():
        raise FileExistsError('refusing to overwrite or reuse an existing result directory')
    root.mkdir(parents=True)
    status={'stage':'08AJ-B geometry-only comparator preflight','complete':False,'no_outcome_data':True}
    (root/'run_status.json').write_text(json.dumps(status,indent=2)+'\n',encoding='utf8')
    rows={}
    for label,order in build_orders(args.size,args.angles,args.tilts,args.seed).items():
        selected=validate_order(order,args.size,args.angles,args.tilts,args.budget)
        verify=build_orders(args.size,args.angles,args.tilts,args.seed)[label]
        if not np.array_equal(order,verify):
            raise AssertionError(f'{label} failed determinism')
        rows[label]={'full_catalogue_sha256':order_digest(order),
                     'prefix':profile_prefix(selected,args.size,args.angles,args.tilts)}
        np.save(root/f'{label}_selected_ray_ids.npy',selected,allow_pickle=False)
    # The two policies should not accidentally have identical selected orders.
    if rows['uniform_multiscale']['prefix']['selected_sha256']==rows['stratified_random_04h']['prefix']['selected_sha256']:
        raise AssertionError('distinct policy histories unexpectedly coincide')
    record={'stage':status['stage'],'size':args.size,'angles':args.angles,'tilts':args.tilts,
            'candidate_rays':total,'budget':args.budget,'seed':args.seed,
            'ray_indexing':'tilt-major, then azimuth, detector row, detector column',
            'uniform_definition':'round-robin view IDs; base-4 digit-reversed Morton detector ordering',
            'stratified_definition':'unchanged experiment_04h.stratified_order',
            'baseline_summaries':rows,
            'limitations':['Geometry-only deterministic output; no MART, phantom, noise, measurement, or RMSE calculations.',
                           'Uniform multiscale schedule is a proposed computational baseline, not a physical scanner sampling protocol.',
                           'The 08AJ confirmatory protocol remains unapproved and not source-locked.']}
    (root/'baseline_report.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n',encoding='utf8')
    status.update(complete=True,verdict='PASS',policies=list(rows))
    (root/'run_status.json').write_text(json.dumps(status,indent=2,sort_keys=True)+'\n',encoding='utf8')
    names=['baseline_report.json','run_status.json']+[f'{label}_selected_ray_ids.npy' for label in rows]
    (root/'manifest.sha256').write_text(''.join(f'{hashlib.sha256((root/name).read_bytes()).hexdigest()}  {name}\n' for name in names),encoding='utf8')
    print(json.dumps({'verdict':'PASS','geometry_only':True,'size':args.size,'candidate_rays':total,
                      'budget':args.budget,'policies':{key:val['prefix'] for key,val in rows.items()}},indent=2))
    return record


if __name__=='__main__':
    main()
