"""04Q-A: independent trilinear ray-marching forward-projector audit.

No adaptive policy is modified or executed in this validation-first stage.
Physical coordinates are in coarse-voxel units and the volume is indexed z,y,x.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from experiment_04b import system_matrix
from experiment_04g import TILTS
from experiment_04m import high_resolution_matrix
from experiment_04p import FAMILIES, object_pair


def rays(n, angles, tilts, offset=0.0):
    """Yield (origin_xyz, unit_direction_xyz) in established 04B ray order.

    Coordinate geometry is specified independently of sparse voxel intersections.
    Detector shifts intentionally reproduce 04M's declared perturbation convention.
    """
    dc=np.arange(n,dtype=float)+0.5-n/2
    for t, tilt in enumerate(tilts):
        e=np.deg2rad(tilt)
        for a,theta in enumerate(np.linspace(0,np.pi,angles,endpoint=False)):
            u=np.array([np.cos(theta),np.sin(theta),0.0])
            d=np.array([-np.sin(theta)*np.cos(e),np.cos(theta)*np.cos(e),np.sin(e)])
            v=np.cross(u,d)
            for j,dv in enumerate(dc):
                for i,du in enumerate(dc):
                    su=offset*np.sin(.83*a+.47*t+.19*i+.31*j)
                    sv=offset*np.cos(.61*a-.29*t+.37*i-.23*j)
                    yield (du+su)*u+(dv+sv)*v,d


def box_interval(origin, direction, half_width):
    lo,hi=-np.inf,np.inf
    for o,d in zip(origin,direction):
        if abs(d)<1e-14:
            if abs(o)>half_width:return None
            continue
        t0=(-half_width-o)/d;t1=(half_width-o)/d
        lo=max(lo,min(t0,t1));hi=min(hi,max(t0,t1))
    return (lo,hi) if hi>lo else None


def sampled_density(vol, xyz, mode='linear'):
    """Trilinear interpolation on voxel-center samples, boundary clamp.

    'nearest' is an auxiliary convergence check for piecewise-constant voxels,
    NOT the independently tested smooth interpolating projector.
    """
    n=vol.shape[0]
    p=np.asarray(xyz,dtype=float)+n/2-.5
    if mode=='nearest':
        q=np.clip(np.floor(p+.5).astype(int),0,n-1)
        return vol[q[:,2],q[:,1],q[:,0]]
    if mode!='linear':raise ValueError('mode must be linear or nearest')
    p=np.clip(p,0,n-1)
    low=np.floor(p).astype(int)
    high=np.minimum(low+1,n-1)
    f=p-low
    out=np.zeros(len(p),dtype=float)
    for bx in (0,1):
        for by in (0,1):
            for bz in (0,1):
                ix=high[:,0] if bx else low[:,0]
                iy=high[:,1] if by else low[:,1]
                iz=high[:,2] if bz else low[:,2]
                wx=f[:,0] if bx else 1-f[:,0]
                wy=f[:,1] if by else 1-f[:,1]
                wz=f[:,2] if bz else 1-f[:,2]
                out+=wx*wy*wz*vol[iz,iy,ix]
    return out


def march_ray(vol, origin, direction, step, mode='linear'):
    vol=np.asarray(vol,dtype=float)
    if vol.ndim!=3 or len(set(vol.shape))!=1:raise ValueError('cubic volume required')
    if step<=0 or not np.isfinite(step):raise ValueError('positive finite step required')
    origin=np.asarray(origin,dtype=float)
    direction=np.asarray(direction,dtype=float)
    norm=np.linalg.norm(direction)
    if not np.isfinite(norm) or norm<=0:raise ValueError('nonzero direction required')
    d=direction/norm
    interval=box_interval(origin,d,vol.shape[0]/2)
    if interval is None:return 0.0
    start,end=interval
    intervals=max(1,int(np.ceil((end-start)/step)))
    dt=(end-start)/intervals
    t=start+(np.arange(intervals)+.5)*dt
    xyz=origin[None,:]+t[:,None]*d[None,:]
    return float(dt*np.sum(sampled_density(vol,xyz,mode)))


def project(vol,n,angles,tilts,factor=1,offset=0.0,step=0.5,mode='linear'):
    """Project fine-grid voxels in coarse-unit coordinates.

    For fine factor f, scale ray origin and integration sampling into fine units,
    then divide path integral by f to return coarse-unit line integrals.
    """
    if factor<1 or int(factor)!=factor or vol.shape!=(n*factor,)*3:raise ValueError('incompatible shape/factor')
    if not np.isfinite(offset) or offset<0:raise ValueError('invalid offset')
    result=[]
    for o,d in rays(n,angles,tilts,offset):
        result.append(march_ray(vol,np.asarray(o)*factor,d,step*factor,mode)/factor)
    return np.asarray(result)


def discrepancy(a,b):
    a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float)
    if a.shape!=b.shape:raise ValueError('projection shapes differ')
    return {'relative_l2':float(np.linalg.norm(a-b)/max(np.linalg.norm(b),1e-12)),
            'rmse':float(np.sqrt(np.mean((a-b)**2))),
            'max_abs':float(np.max(np.abs(a-b)))}


def write_csv(path,rows):
    if not rows:return
    with path.open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--size',type=int,default=16);p.add_argument('--angles',type=int,default=12)
    p.add_argument('--factor',type=int,default=2)
    p.add_argument('--phantoms',nargs='+',choices=FAMILIES,default=['branches','pores'])
    p.add_argument('--object-types',nargs='+',choices=['replicated','subvoxel'],default=['replicated','subvoxel'])
    p.add_argument('--offsets',nargs='+',type=float,default=[0.,.15])
    p.add_argument('--steps',nargs='+',type=float,default=[.5,.25])
    p.add_argument('--output-dir',type=Path,default=Path('results/experiment04qa'))
    a=p.parse_args(argv)
    if a.size<4 or a.angles<2 or a.factor<2 or not a.steps or min(a.steps)<=0 or max(a.steps)>1 or min(a.offsets)<0:p.error('invalid configuration')
    a.output_dir.mkdir(parents=True,exist_ok=True)
    coarse=system_matrix(a.size,a.angles,TILTS)
    records=[]
    for family in a.phantoms:
        objects=object_pair(family,a.size,a.factor)
        for typ in a.object_types:
            truth,fine=objects[typ]
            volume=fine.reshape((a.size*a.factor,)*3)
            ideal=np.asarray(coarse@truth).ravel()
            for offset in a.offsets:
                # Existing Siddon-like forward projector is a comparator only.
                reference=np.asarray(high_resolution_matrix(a.size,a.angles,TILTS,a.factor,offset)@fine).ravel()
                prev=None
                for step in sorted(set(a.steps),reverse=True):
                    projected=project(volume,a.size,a.angles,TILTS,a.factor,offset,step,'linear')
                    comparison=discrepancy(projected,reference)
                    fidelity=discrepancy(projected,ideal)
                    record=dict(phantom=family,object_type=typ,offset=offset,step_coarse=step,
                                rays=len(projected),**{'vs_siddon_'+k:v for k,v in comparison.items()},
                                **{'vs_coarse_'+k:v for k,v in fidelity.items()})
                    if prev is not None:record['vs_previous_step_relative_l2']=discrepancy(projected,prev)['relative_l2']
                    else:record['vs_previous_step_relative_l2']=''
                    records.append(record)
                    prev=projected
                    print(f'04Q-A {family:8s} {typ:10s} offset={offset:g} step={step:g} '
                          f'siddon_relative_l2={comparison["relative_l2"]:.6f}',flush=True)
    write_csv(a.output_dir/'projector_comparison.csv',records)
    (a.output_dir/'protocol.json').write_text(json.dumps({'experiment':'04Q-A',
        'purpose':'projector-independent numerical measurement cross-check; no policy evaluation',
        'parameters':{k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},
        'method':'midpoint integration of trilinearly interpolated center samples with boundary clamping',
        'limitations':['Same ideal parallel-ray coordinate specification as prior experiments',
                       'Different interpolation physics from piecewise-constant Siddon; disagreement is expected',
                       'Finite-step numerical integration; check step convergence',
                       'Not independent hardware or physical detector validation',
                       'No physical dose or clinical claims']},indent=2),encoding='utf8')
    print(f'04Q-A complete: {len(records)} projector comparisons; output={a.output_dir}',flush=True)

if __name__=='__main__':main()
