"""08AJ-C engineering-only complete-detector-view acquisition comparator.

Rows follow experiment_04b.system_matrix: tilt, azimuth, detector row, column.
A complete view is exactly n*n consecutive detector rays. This is a constrained
parallel-beam *simulation* comparator, not evidence of hardware feasibility.
No phantom, measurement, MART reconstruction, or error metric is accessed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def digest(ids):
    return hashlib.sha256(np.asarray(ids, dtype='<i8').tobytes()).hexdigest()


def directions(angles: int, tilts_deg: tuple[float, ...]) -> np.ndarray:
    """Source-aligned ray directions, ordered tilt-major then azimuth."""
    if angles < 1 or not tilts_deg:
        raise ValueError('angles and tilts must be nonempty')
    out=[]
    for tilt in tilts_deg:
        eps=np.deg2rad(float(tilt))
        for theta in np.linspace(0.0,np.pi,angles,endpoint=False):
            out.append([-np.sin(theta)*np.cos(eps), np.cos(theta)*np.cos(eps),np.sin(eps)])
    return np.asarray(out,dtype=np.float64)


def select_views(angles: int, tilts_deg: tuple[float, ...], view_count: int) -> np.ndarray:
    """Deterministic maximin projective angular spacing among discrete views.

    Starts from tilt nearest zero and first azimuth. Subsequent views greedily
    maximize the minimum arccos(abs(dot)) to previously chosen directions;
    tie breaking uses earliest source view ID. This is a *specified numerical*
    selection rule, not a theorem of CT optimality.
    """
    d=directions(angles,tilts_deg)
    if not 1 <= view_count <= len(d):
        raise ValueError('invalid view_count')
    central=min(range(len(tilts_deg)),key=lambda i:(abs(tilts_deg[i]),i))
    selected=[central*angles]
    while len(selected)<view_count:
        best=None
        best_score=-float('inf')
        for j in range(len(d)):
            if j in selected:
                continue
            score=float(np.min(np.arccos(np.clip(np.abs(d[selected]@d[j]),0,1))))
            if score>best_score+1e-12:
                best_score=score
                best=j
        selected.append(best)
    return np.asarray(selected,dtype=np.int64)


def complete_view_order(n:int, angles:int, tilts_deg:tuple[float,...], budget:int):
    """Exactly budget rays, each from fully sampled detector views; no partial views."""
    if n<2 or budget<1:
        raise ValueError('n>=2 and positive budget required')
    view_size=n*n
    total=view_size*angles*len(tilts_deg)
    if budget%view_size:
        raise ValueError(f'INFEASIBLE_COMPLETE_VIEWS: budget={budget} is not divisible by rays_per_view={view_size}; minimum positive complete-view budget={view_size}')
    if budget>total:
        raise ValueError('budget exceeds catalogue')
    vids=select_views(angles,tilts_deg,budget//view_size)
    ids=(vids[:,None]*view_size+np.arange(view_size,dtype=np.int64)[None,:]).reshape(-1)
    assert len(np.unique(ids))==budget
    return ids,vids


def report(n,angles,tilts_deg,budget):
    row={'stage':'08AJ-C complete-view geometry-only comparator',
         'size':n,'angles':angles,'tilts_deg':list(tilts_deg),'candidate_rays':n*n*angles*len(tilts_deg),
         'budget':budget,'rays_per_complete_view':n*n,'geometry_only':True,
         'no_outcome_data':True,'physical_scanner_validated':False,
         'view_rule':'deterministic greedy projective-angular maximin; central tilt/first azimuth initialization; source-index ties',
         'limitations':['Complete detector grids in a simulated parallel-beam catalogue; physical scanner feasibility is not demonstrated.',
                        'Selection at a fixed budget may have very few distinct angles; fairness versus individual-ray policies requires discussion.',
                        'No acquisition-time, hardware, noise, dosimetry, or reconstruction comparisons.']}
    try:
        ids,vids=complete_view_order(n,angles,tilts_deg,budget)
    except ValueError as exc:
        row.update(verdict='INFEASIBLE',complete=True,reason=str(exc),selected_rays=0)
        return row,None
    row.update(verdict='PASS',complete=True,selected_rays=len(ids),view_count=len(vids),
               selected_view_ids=vids.tolist(),ray_order_sha256=digest(ids),
               unique_rays=len(np.unique(ids)),view_counts={str(v):int(n*n) for v in vids})
    return row,ids


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--size',type=int,default=32)
    p.add_argument('--angles',type=int,default=4)
    p.add_argument('--tilts-deg',type=float,nargs='+',default=[-20,0,20])
    p.add_argument('--budget',type=int,default=2048)
    p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args(argv)
    if args.size<2 or args.angles<1 or not args.tilts_deg or args.budget<1:
        p.error('invalid geometry')
    if args.output_dir.exists():
        raise FileExistsError('refusing to overwrite existing output directory')
    args.output_dir.mkdir(parents=True)
    status={'stage':'08AJ-C complete-view geometry-only comparator','complete':False,'no_outcome_data':True}
    (args.output_dir/'run_status.json').write_text(json.dumps(status,indent=2)+'\n',encoding='utf8')
    result,ids=report(args.size,args.angles,tuple(args.tilts_deg),args.budget)
    if ids is not None:
        assert np.array_equal(ids,complete_view_order(args.size,args.angles,tuple(args.tilts_deg),args.budget)[0])
        np.save(args.output_dir/'complete_view_selected_ray_ids.npy',ids,allow_pickle=False)
    (args.output_dir/'view_report.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf8')
    status.update(complete=True,verdict=result['verdict'],reason=result.get('reason'))
    (args.output_dir/'run_status.json').write_text(json.dumps(status,indent=2,sort_keys=True)+'\n',encoding='utf8')
    files=sorted(args.output_dir.iterdir())
    (args.output_dir/'manifest.sha256').write_text(''.join(f'{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.name}\n' for f in files),encoding='utf8')
    print(json.dumps(result,indent=2))
    return result

if __name__=='__main__':
    main()
