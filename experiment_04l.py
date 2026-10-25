"""04L: frozen 04J/04K mechanism, negative-case, cost, and stress audit.

Analyze existing 04K CSVs, or run a NEW stress set using unchanged 04J
adaptive_order and sirt_silent. This is post-validation diagnosis, not
another independent validation or a new acquisition algorithm.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, time
from collections import defaultdict
from pathlib import Path
import numpy as np
from experiment_04b import system_matrix
from experiment_04g import TILTS, policies
from experiment_04h import voxel_coverage_order, coverage
from experiment_04i import noisy_full_projection
from experiment_04j import adaptive_order, sirt_silent, divergence
from experiment_04k import new_phantoms, noise_seed_for


def read_rows(path):
    with Path(path).open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def write_rows(path, rows):
    if not rows: return
    with Path(path).open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def pairwise(metrics, reference='feedback_off_control', target='adaptive_feedback'):
    grouped=defaultdict(dict)
    for row in metrics:
        key=(row['phantom'],int(row['seed']),int(row['budget']),float(row['noise_fraction']),int(row.get('sirt_iterations',400)))
        if row['policy'] in grouped[key]:raise ValueError(f'duplicate policy in case: {key} {row["policy"]}')
        grouped[key][row['policy']]=float(row['rmse'])
    result=[]
    for (phantom,seed,budget,noise,iters),policies_ in sorted(grouped.items()):
        if target not in policies_ or reference not in policies_:continue
        a,b=policies_[target],policies_[reference]
        result.append(dict(phantom=phantom,seed=seed,budget=budget,noise_fraction=noise,
                           sirt_iterations=iters,adaptive_rmse=a,comparator_rmse=b,
                           relative_gain=(b-a)/max(b,1e-12),win=int(a<b)))
    return result


def audit_existing(input_dir, output_dir):
    input_dir=Path(input_dir);output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    metrics=read_rows(input_dir/'metrics.csv'); pairs=pairwise(metrics)
    write_rows(output_dir/'paired_cases.csv',pairs)
    groups=defaultdict(list)
    for row in pairs:groups[(row['phantom'],row['budget'])].append(row['relative_gain'])
    write_rows(output_dir/'family_budget.csv',[
        dict(phantom=phantom,budget=budget,n=len(vals),wins=sum(v>0 for v in vals),
             mean_gain=float(np.mean(vals)),median_gain=float(np.median(vals)),min_gain=float(min(vals)))
        for (phantom,budget),vals in sorted(groups.items())])
    losses=sorted((p for p in pairs if not p['win']),key=lambda r:r['relative_gain'])
    write_rows(output_dir/'negative_cases.csv',losses)
    costs=[]
    if (input_dir/'orders.csv').exists():
        orderrows=read_rows(input_dir/'orders.csv')
        for r in orderrows:
            if r['policy'] not in ('adaptive_feedback','feedback_off_control','voxel_coverage_greedy'):continue
            costs.append(dict(phantom=r['phantom'],seed=r['seed'],budget=r['budget'],noise_fraction=r['noise_fraction'],
                policy=r['policy'],selection_s=float(r['selection_s']),timing_scope=r.get('timing_scope','unknown')))
        write_rows(output_dir/'timing_inventory.csv',costs)
    divergence_stats=[]
    if (input_dir/'divergence.csv').exists():
        for r in read_rows(input_dir/'divergence.csv'):
            divergence_stats.append(dict(phantom=r['phantom'],seed=r['seed'],budget=int(r['budget']),
                noise_fraction=float(r['noise_fraction']),comparator=r['comparator'],
                same_set_fraction=float(r['same_set_fraction']),
                sequence_identical=str(r['sequence_identical']).lower()=='true'))
        write_rows(output_dir/'divergence_inventory.csv',divergence_stats)
    report=dict(experiment='04L',analysis_type='retrospective 04K result audit',
      total_metrics=len(metrics),total_paired_cases=len(pairs),negative_cases=len(losses),
      groups=[dict(phantom=p,budget=b,n=len(v),wins=sum(x>0 for x in v),mean_gain=float(np.mean(v))) for (p,b),v in sorted(groups.items())],
      warnings=['Seeds and noise realizations within each phantom are repeated/correlated, not independent anatomical replicates.',
                '04K cases were already inspected; this is exploratory mechanism/failure analysis.',
                'Fixed max-budget greedy selection_s cannot be compared directly with per-case online adaptive selection_s.',
                'Random/geometry-balanced selection costs were not measured in 04K.',
                '04J/04K use a matched forward/reconstruction operator; no experimental dose model.'])
    (output_dir/'audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(f'04L audit: {len(pairs)} paired conditions; {len(losses)} adaptive non-wins; results: {output_dir}',flush=True)
    return report


def stress(args):
    out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    if args.size<4 or args.angles<2 or args.warm_rays<1 or args.batch<1 or args.candidate_pool<1 or args.provisional_iterations<1:
        raise ValueError('invalid geometry/acquisition parameters')
    if not args.budgets or min(args.budgets)<=args.warm_rays or max(args.budgets)>len(TILTS)*args.angles*args.size**2:
        raise ValueError('invalid budgets')
    if not args.noise_fractions or min(args.noise_fractions)<0 or not args.sirt_iterations or min(args.sirt_iterations)<1:
        raise ValueError('invalid noise/reconstruction settings')
    phantoms=new_phantoms(args.size)
    if any(name not in phantoms for name in args.phantoms): raise ValueError('unknown phantom')
    t=time.perf_counter();A=system_matrix(args.size,args.angles,TILTS).tocsr()
    print(f'04L stress: size={args.size} rays={A.shape[0]} nnz={A.nnz} build_s={time.perf_counter()-t:.2f}',flush=True)
    metrics=[];orders=[]; coverage_rows=[];deltas=[];traces=[]
    for seed in args.seeds:
        t=time.perf_counter();fixed=voxel_coverage_order(A,args.size,args.angles,len(TILTS),max(args.budgets),seed,args.candidate_pool)
        fixed_s=time.perf_counter()-t
        baseline=policies(args.size,args.angles,len(TILTS),seed)
        for name in args.phantoms:
            truth=phantoms[name].ravel();clean=np.asarray(A@truth)
            for noise in args.noise_fractions:
                observed=noisy_full_projection(clean,noise,noise_seed_for(seed,name,noise))
                for budget in args.budgets:
                    # Acquire ONCE per case, regardless of final SIRT iteration count.
                    selected,trace,selection_s=adaptive_order(A,observed,args.size,args.angles,fixed,budget,seed,
                        args.warm_rays,args.batch,args.provisional_iterations,args.candidate_pool,1.0)
                    off,_,off_s=adaptive_order(A,observed,args.size,args.angles,fixed,budget,seed,
                        args.warm_rays,args.batch,args.provisional_iterations,args.candidate_pool,0.0)
                    ids_by_policy={'adaptive_feedback':selected,'feedback_off_control':off,
                                   'voxel_coverage_greedy':fixed[:budget],
                                   'random':baseline['random'][:budget],
                                   'geometry_balanced':baseline['geometry_balanced'][:budget]}
                    d=divergence(selected,off,args.warm_rays)
                    deltas.append(dict(phantom=name,seed=seed,budget=budget,noise_fraction=noise,
                        reference='feedback_off_control',**d))
                    for entry in trace:traces.append(dict(phantom=name,seed=seed,budget=budget,noise_fraction=noise,**entry))
                    for policy,ids in ids_by_policy.items():
                        sub=A[ids].tocsr(); y=observed[ids]
                        ordered_hash=hashlib.sha256(ids.astype('<i8').tobytes()).hexdigest()
                        sel_s=selection_s if policy=='adaptive_feedback' else off_s if policy=='feedback_off_control' else fixed_s if policy=='voxel_coverage_greedy' else float('nan')
                        orders.append(dict(phantom=name,seed=seed,budget=budget,noise_fraction=noise,policy=policy,
                            order_hash=ordered_hash,selection_s=sel_s,
                            selection_scope='per-case online' if policy in ('adaptive_feedback','feedback_off_control') else 'full-max-budget shared' if policy=='voxel_coverage_greedy' else 'not timed'))
                        coverage_rows.append(dict(phantom=name,seed=seed,budget=budget,noise_fraction=noise,policy=policy,
                            **coverage(A,ids,args.size,args.angles,len(TILTS),budget)))
                        for iteration in args.sirt_iterations:
                            t=time.perf_counter();x=sirt_silent(sub,y,iteration);solver_s=time.perf_counter()-t
                            rmse=float(np.sqrt(np.mean((x-truth)**2)))
                            metrics.append(dict(phantom=name,seed=seed,budget=budget,noise_fraction=noise,
                                 sirt_iterations=iteration,policy=policy,rmse=rmse,solver_s=solver_s))
                            print(f'{name:7} seed={seed} budget={budget} noise={noise:.4g} iters={iteration:4} {policy:22} rmse={rmse:.6f}',flush=True)
    write_rows(out/'stress_metrics.csv',metrics)
    write_rows(out/'stress_orders.csv',orders)
    write_rows(out/'stress_coverage.csv',coverage_rows)
    write_rows(out/'stress_divergence.csv',deltas)
    write_rows(out/'stress_trace.csv',traces)
    pairs=pairwise(metrics);write_rows(out/'stress_pairs.csv',pairs)
    groups=defaultdict(list)
    for p in pairs:groups[(p['phantom'],p['budget'],p['noise_fraction'],p['sirt_iterations'])].append(p['relative_gain'])
    write_rows(out/'stress_summary.csv',[dict(phantom=ph,budget=b,noise_fraction=n,sirt_iterations=it,
        n=len(vals),wins=sum(v>0 for v in vals),mean_gain=float(np.mean(vals))) for (ph,b,n,it),vals in sorted(groups.items())])
    (out/'stress_protocol.json').write_text(json.dumps(dict(experiment='04L',mode='exploratory stress',
         parameters={k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()},
         selection_rule='Imported frozen 04J adaptive_order; feedback_strength=1.0 / off=0.0',
         notes=['SIRT iteration count affects final reconstruction ONLY; it does not alter ray selections.',
         'Measurement oracle generated for simulation; adaptive_order only indexes acquired measurements.',
         'Noise fractions 0.03 and 0.1 are stress tests, not a photon-counting model.',
         'Selection costs include repeated provisional SIRT; timing comparisons are not normalized for setup and reuse.',
         'Stress results reuse previously examined 04K phantoms; they are not independent validation.']),indent=2),encoding='utf-8')
    print(f'04L stress completed {len(metrics)} reconstructions; {len(pairs)} paired cases; {out}',flush=True)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=['audit','stress'],default='audit')
    p.add_argument('--input-dir',type=Path,default=Path('results/experiment04k'))
    p.add_argument('--output-dir',type=Path,default=Path('results/experiment04l'))
    p.add_argument('--size',type=int,default=16);p.add_argument('--angles',type=int,default=12)
    p.add_argument('--budgets',nargs='+',type=int,default=[512,1024,2048])
    p.add_argument('--warm-rays',type=int,default=128);p.add_argument('--batch',type=int,default=64)
    p.add_argument('--provisional-iterations',type=int,default=60)
    p.add_argument('--candidate-pool',type=int,default=64)
    p.add_argument('--sirt-iterations',nargs='+',type=int,default=[200,400,800])
    p.add_argument('--noise-fractions',nargs='+',type=float,default=[0,0.01,0.03,0.1])
    p.add_argument('--seeds',nargs='+',type=int,default=[104729,130363,155921])
    p.add_argument('--phantoms',nargs='+',default=['torus','slats','beads','wedges'])
    args=p.parse_args(argv)
    if args.mode=='audit': audit_existing(args.input_dir,args.output_dir)
    else:stress(args)

if __name__=='__main__':main()
