"""RBYRCT-08F: read-only within-pool ranking/regret audit of 08E outputs.

No acquisition, MART, detector observation, or synthetic truth generation occurs.
The retrospective 08E candidate outcomes are diagnostics, NOT admissible input to
any live selector. Pools are nested within a small number of development objects.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean

EXPECTED_POLICIES = {'gradient', 'incremental_25'}
INPUT_FILES = ('candidate_probes.csv', 'acquisition_manifest.csv',
               'descriptive_summary.csv', 'run_status.json', 'protocol.json')
NUMERIC = ('gradient_score', 'one_ray_global_gain', 'one_ray_defect_gain',
           'prior_path_coverage', 'defect_path_fraction')


def read_csv(path):
    with path.open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def verify_archive(root):
    """Verify 08E's recorded hashes and completion, without writing to root."""
    if not root.is_dir():
        raise ValueError(f'08E directory not found: {root}')
    for name in INPUT_FILES:
        if not (root / name).is_file():
            raise ValueError(f'missing 08E input: {name}')
    hashes_path = root / 'sha256.json'
    if not hashes_path.is_file():
        raise ValueError('missing 08E sha256.json')
    hashes = json.loads(hashes_path.read_text(encoding='utf-8'))
    if not isinstance(hashes, dict) or not all(name in hashes for name in INPUT_FILES):
        raise ValueError('incomplete 08E hash inventory')
    for name, digest in hashes.items():
        if name == 'sha256.json' or Path(name).name != name:
            raise ValueError('invalid hash inventory entry')
        path = root / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f'08E archive hash mismatch: {name}')
    status = json.loads((root / 'run_status.json').read_text(encoding='utf-8'))
    if status.get('complete') is not True or status.get('evaluation_only_confirmed') is not True:
        raise ValueError('08E acquisition/retrospective evaluation not complete')
    return status, len(hashes)


def _int(value, name):
    try:
        if str(value).strip() != str(int(value)):
            raise ValueError
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f'invalid integer {name}: {value!r}') from None


def _float(value, name):
    try:
        val = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'invalid float {name}: {value!r}') from None
    if not math.isfinite(val):
        raise ValueError(f'nonfinite {name}')
    return val


def rank_indices(values, rays, largest=True):
    """Stable ordering, best first, tie broken by ascending ray ID."""
    return sorted(range(len(values)), key=lambda i: ((-values[i] if largest else values[i]), rays[i]))


def pearson(xs, ys):
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    ax = mean(xs); ay = mean(ys)
    a = [x-ax for x in xs]; b = [y-ay for y in ys]
    den = math.sqrt(sum(x*x for x in a)*sum(y*y for y in b))
    return sum(x*y for x,y in zip(a,b))/den if den > 1e-15 else None


def spearman(xs, ys):
    """Midrank Spearman; return None if ranks have zero variance."""
    def midranks(vals):
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        result = [0.0]*len(vals); i=0
        while i < len(vals):
            j=i+1
            while j<len(vals) and vals[order[j]] == vals[order[i]]:
                j+=1
            mid = (i+1+j)/2.0
            for k in range(i,j): result[order[k]]=mid
            i=j
        return result
    return pearson(midranks(xs), midranks(ys))


def calculate_pool(rows):
    """Validate one actual 08E probe pool and derive regret and rankings."""
    if len(rows) < 2:
        raise ValueError('candidate pool too small')
    selected = []
    parsed = []
    rays = set()
    for row in rows:
        ray = _int(row['candidate_ray'], 'candidate_ray')
        if ray < 0 or ray in rays:
            raise ValueError('duplicate or negative candidate ray')
        rays.add(ray)
        r = {key:_float(row[key], key) for key in NUMERIC}
        r.update(ray=ray, rank=_int(row['score_rank'],'score_rank'),
                 eligible=_int(row['eligible'],'eligible'),
                 chosen=_int(row['chosen'],'chosen'),
                 reference=_int(row['reference'],'reference'),
                 defect_hit=_int(row['defect_hit'],'defect_hit'))
        if any(r[k] not in (0,1) for k in ('eligible','chosen','reference','defect_hit')):
            raise ValueError('nonbinary flag')
        if r['defect_path_fraction'] < 0 or r['defect_path_fraction'] > 1+1e-12:
            raise ValueError('invalid defect path fraction')
        parsed.append(r)
        if r['chosen']:
            selected.append(r)
    if len(selected)!=1 or sum(r['reference'] for r in parsed)!=1:
        raise ValueError('pool must have exactly one selected and one reference ray')
    if not selected[0]['eligible'] or any(r['reference'] and not r['eligible'] for r in parsed):
        raise ValueError('selected/reference ray must be eligible')
    scores=[r['gradient_score'] for r in parsed]
    ids=[r['ray'] for r in parsed]
    order=rank_indices(scores, ids)
    for k,idx in enumerate(order,1):
        if parsed[idx]['rank'] != k:
            raise ValueError('stored score rank inconsistent with values')
    # Score ties in the original 08E selector use np.isclose, while stored
    # rank uses lexsort. We do NOT claim the selected ray is exactly rank 1.
    chosen=selected[0]
    selected_idx=next(i for i,r in enumerate(parsed) if r['chosen'])
    eligible=[r for r in parsed if r['eligible']]
    pool_out={'pool_size':len(parsed),'eligible_count':len(eligible),
              'selected_ray':chosen['ray'], 'selected_score_rank':chosen['rank'],
              'score_top_ray':parsed[order[0]]['ray'],
              'selected_is_score_top':int(selected_idx==order[0]),
              'selected_defect_hit':chosen['defect_hit'],
              'score_top_defect_hit':parsed[order[0]]['defect_hit'],
              'hit_rate_in_pool':mean(r['defect_hit'] for r in parsed),
              'score_vs_defect_hit_spearman':spearman(scores,[r['defect_hit'] for r in parsed]),
              'score_vs_redundancy_spearman':spearman(scores,[r['prior_path_coverage'] for r in parsed])}
    for metric,short in (('one_ray_global_gain','global'),('one_ray_defect_gain','defect')):
        vals=[r[metric] for r in parsed]
        best_idx=rank_indices(vals,ids)[0]
        all_best=parsed[best_idx]
        elig_best=sorted(eligible,key=lambda r:(-r[metric],r['ray']))[0]
        delta_all=max(0., all_best[metric]-chosen[metric])
        delta_eligible=max(0.,elig_best[metric]-chosen[metric])
        pool_out.update({
            f'selected_{short}_gain':chosen[metric],
            f'best_{short}_gain':all_best[metric],
            f'best_{short}_ray':all_best['ray'],
            f'best_eligible_{short}_gain':elig_best[metric],
            f'{short}_regret_all':delta_all,
            f'{short}_regret_eligible':delta_eligible,
            f'{short}_restriction_gap':max(0.,all_best[metric]-elig_best[metric]),
            f'selected_is_{short}_best':int(chosen['ray']==all_best['ray']),
            f'score_top_is_{short}_best':int(parsed[order[0]]['ray']==all_best['ray']),
            f'score_vs_{short}_gain_spearman':spearman(scores,vals),
        })
    if chosen['rank'] < 1 or chosen['rank'] > len(parsed):
        raise ValueError('invalid selection rank')
    return pool_out


def analyze(candidate_rows, manifest_rows, status):
    """Return auditable per-pool and object-balanced summaries."""
    expected = {}
    for item in manifest_rows:
        key=(_int(item['size'],'size'),_int(item['object_seed'],'object_seed'),item['policy'])
        if key in expected or key[2] not in EXPECTED_POLICIES:
            raise ValueError('duplicate/invalid acquisition manifest')
        expected[key]=_int(item['probes'],'probes')
        if _int(item['evaluated_candidates'],'evaluated_candidates') <= 0:
            raise ValueError('invalid candidate count')
    if len(expected)!=_int(status['runs'],'runs'):
        raise ValueError('manifest/run count mismatch')
    pools=defaultdict(list)
    for row in candidate_rows:
        size=_int(row['size'],'size'); obj=_int(row['object_seed'],'object_seed')
        pol=row['policy']; before=_int(row['acquired_before'],'acquired_before')
        if pol not in EXPECTED_POLICIES or (size,obj,pol) not in expected or before<0:
            raise ValueError('candidate absent from run manifest')
        pools[(size,obj,pol,before)].append(row)
    if len(candidate_rows)!=_int(status['probed_candidate_rows'],'probed_candidate_rows'):
        raise ValueError('candidate count does not match completed status')
    per_run=defaultdict(list); pool_rows=[]
    for (size,obj,policy,before), rows in sorted(pools.items()):
        value=calculate_pool(rows)
        value=dict(size=size,object_seed=obj,policy=policy,acquired_before=before,**value)
        pool_rows.append(value)
        per_run[(size,obj,policy)].append(value)
    if set(per_run)!=set(expected):
        raise ValueError('missing complete candidate histories')
    counts=defaultdict(int)
    for row in candidate_rows:
        counts[(_int(row['size'],'size'),_int(row['object_seed'],'object_seed'),row['policy'])]+=1
    for key, count in expected.items():
        if len(per_run[key])!=count:
            raise ValueError('incorrect number of probes')
        item=next(x for x in manifest_rows if (_int(x['size'],'size'),_int(x['object_seed'],'object_seed'),x['policy'])==key)
        if counts[key]!=_int(item['evaluated_candidates'],'evaluated_candidates'):
            raise ValueError('candidate count mismatch with manifest')
    groupings=defaultdict(list)
    for row in pool_rows:
        groupings[(row['size'],row['policy'])].append(row)
    output=[]
    for (size,policy), rr in sorted(groupings.items()):
        objects=sorted({r['object_seed'] for r in rr})
        def obmean(field):
            # Objects are the independent replication unit; probes are nested.
            values=[mean(r[field] for r in rr if r['object_seed']==obj) for obj in objects]
            return mean(values)
        def obcor(field):
            per_obj=[]
            for obj in objects:
                valid=[r[field] for r in rr if r['object_seed']==obj and r[field] is not None]
                if valid: per_obj.append(mean(valid))
            return mean(per_obj) if per_obj else None
        output.append(dict(size=size,policy=policy,n_objects=len(objects),n_pools=len(rr),
            mean_selected_score_rank=obmean('selected_score_rank'),
            score_top_selection_fraction=obmean('selected_is_score_top'),
            selected_defect_hit_fraction=obmean('selected_defect_hit'),
            mean_pool_defect_hit_fraction=obmean('hit_rate_in_pool'),
            mean_eligible_count=obmean('eligible_count'),
            mean_defect_regret_all=obmean('defect_regret_all'),
            mean_defect_regret_eligible=obmean('defect_regret_eligible'),
            mean_defect_restriction_gap=obmean('defect_restriction_gap'),
            mean_global_regret_all=obmean('global_regret_all'),
            mean_global_regret_eligible=obmean('global_regret_eligible'),
            mean_global_restriction_gap=obmean('global_restriction_gap'),
            selected_is_defect_best_fraction=obmean('selected_is_defect_best'),
            selected_is_global_best_fraction=obmean('selected_is_global_best'),
            mean_within_pool_score_defect_spearman=obcor('score_vs_defect_gain_spearman'),
            mean_within_pool_score_global_spearman=obcor('score_vs_global_gain_spearman'),
            mean_within_pool_score_hit_spearman=obcor('score_vs_defect_hit_spearman'),
            mean_within_pool_score_redundancy_spearman=obcor('score_vs_redundancy_spearman')))
    return pool_rows,output


def write_csv(path, rows):
    if not rows: raise ValueError('cannot write empty diagnostics')
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def run(results_dir, output_dir):
    root=Path(results_dir).resolve();out=Path(output_dir).resolve()
    if out==root or root in out.parents or out in root.parents:
        raise ValueError('08F output must be separate from 08E archive')
    if out.exists():
        raise FileExistsError('refusing to overwrite existing 08F output')
    status,n_hashes=verify_archive(root)
    pools,summaries=analyze(read_csv(root/'candidate_probes.csv'),read_csv(root/'acquisition_manifest.csv'),status)
    # No output is created until all input validation succeeds.
    out.mkdir(parents=True,exist_ok=False)
    write_csv(out/'pool_regret.csv',pools)
    write_csv(out/'object_balanced_summary.csv',summaries)
    report=dict(verdict='PASS',scope='read-only retrospective 08E candidate-pool ranking analysis',
        original_data_unchanged=True,verified_sha256_files=n_hashes,
        candidate_rows=status['probed_candidate_rows'],acquisition_runs=status['runs'],
        candidate_pools=len(pools),
        limitations=[
            'The 08E probes and simulated candidate one-ray outcomes are development-only, not held-out validation',
            'Truth and defect masks enter retrospective gains only; they are never selector inputs',
            'One-ray regret is a post-hoc local counterfactual, not a guarantee of cumulative policy performance',
            'Candidate sets and reconstructions differ between gradient and guarded histories; regret comparisons are descriptive',
            'Candidate pools and probe states are nested within objects; object is replication unit',
            'Missing/degenerate per-pool Spearman correlations are omitted, not treated as zeros',
        ])
    (out/'audit_report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (out/'analysis_protocol.json').write_text(json.dumps(dict(
        metric='relative RMSE improvement of a one-ray counterfactual over its pre-probe MART baseline',
        regret='best retrospective candidate gain minus selected candidate gain',
        eligible_regret='best eligible gain minus selected candidate gain',
        restriction_gap='best overall gain minus best eligible gain',
        ranking='descending score, then ascending ray ID; Spearman midranks on ties',
        averaging='pool metrics averaged within object, then object-balanced within size and policy',
        scope='no new MART reconstructions or acquisition histories',
    ),indent=2)+'\n',encoding='utf-8')
    return report,summaries


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results-dir',type=Path,default=Path('../rbyrct-results/experiment08e/feedback_first'))
    p.add_argument('--output-dir',type=Path,default=Path('../rbyrct-results/experiment08f/ranking_first'))
    args=p.parse_args()
    report,summaries=run(args.results_dir,args.output_dir)
    print(json.dumps(report,indent=2))
    print('\n--- object-balanced ranking / regret ---')
    for row in summaries:
        print(f"{row['size']}^3 {row['policy']:<14} pools={row['n_pools']:2d} "
              f"defect_regret={100*row['mean_defect_regret_all']:.4f} pp "
              f"global_regret={100*row['mean_global_regret_all']:.4f} pp "
              f"defect_hit={row['selected_defect_hit_fraction']:.3f}")


if __name__=='__main__':
    main()
