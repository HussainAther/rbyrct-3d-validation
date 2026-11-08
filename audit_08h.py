"""RBYRCT-08H: read-only candidate availability, selection, oracle and geometry audit.

Input: completed 08E and 08G *development* archives. No acquisition, no MART,
no new truth labels; retrospective defect flags and one-ray gains were written
by the source experiments. Source archives MUST remain unchanged.
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

SOURCES = {
    '08E': ('candidate_probes.csv', 'probed_candidate_rows'),
    '08G': ('candidate_diagnostics.csv', 'candidate_rows'),
}
BASE_FILES = ('acquisition_manifest.csv', 'protocol.json', 'run_status.json')
POLICIES = {'gradient', 'incremental_25'}


def read_csv(path):
    with path.open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def as_int(value, name):
    try:
        v = int(value)
        if str(v) != str(value).strip():
            raise ValueError
        return v
    except (ValueError, TypeError):
        raise ValueError(f'invalid integer {name}: {value!r}') from None


def as_float(value, name):
    try: v = float(value)
    except (ValueError, TypeError): raise ValueError(f'invalid float {name}') from None
    if not math.isfinite(v): raise ValueError(f'nonfinite {name}')
    return v


def verify_archive(root, source):
    if source not in SOURCES: raise ValueError('unknown source')
    if not root.is_dir(): raise ValueError(f'missing {source} archive {root}')
    filename, countfield = SOURCES[source]
    required = (filename, *BASE_FILES)
    inventory_file = root / 'sha256.json'
    if not inventory_file.is_file(): raise ValueError(f'missing {source} hashes')
    hashes = json.loads(inventory_file.read_text(encoding='utf-8'))
    if not isinstance(hashes,dict) or any(x not in hashes for x in required):
        raise ValueError(f'incomplete {source} hash inventory')
    for name, digest in hashes.items():
        if Path(name).name != name or name == 'sha256.json' or len(digest) != 64:
            raise ValueError(f'unsafe hash entry: {name}')
        if not (root/name).is_file() or hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:
            raise ValueError(f'archive hash mismatch: {source}/{name}')
    status=json.loads((root/'run_status.json').read_text(encoding='utf-8'))
    if status.get('complete') is not True: raise ValueError(f'{source} incomplete')
    rows=read_csv(root/filename);manifest=read_csv(root/'acquisition_manifest.csv')
    if len(rows)!=as_int(status[countfield],countfield): raise ValueError(f'{source} row count mismatch')
    expected_runs=as_int(status['runs'] if source=='08E' else status['histories'],'runs')
    if len(manifest)!=expected_runs: raise ValueError(f'{source} manifest count mismatch')
    if source=='08E' and status.get('evaluation_only_confirmed') is not True:
        raise ValueError('08E evaluation-only status not confirmed')
    return rows,manifest,status,len(hashes)


def candidates_by_pool(rows, manifest, source):
    expected={}; per_run=defaultdict(list)
    for m in manifest:
        key=(as_int(m['size'],'size'),as_int(m['object_seed'],'object_seed'),m['policy'])
        if key in expected or key[2] not in POLICIES: raise ValueError(f'{source} invalid manifest')
        expected[key]=(as_int(m['probes'],'probes'),as_int(m['evaluated_candidates'] if source=='08E' else m['n_candidates'],'n_candidates'))
    pools=defaultdict(list)
    for r in rows:
        key=(as_int(r['size'],'size'),as_int(r['object_seed'],'object_seed'),r['policy'])
        before=as_int(r['acquired_before'],'acquired_before')
        if key not in expected or before<0: raise ValueError(f'{source} row absent from manifest')
        pools[(*key,before)].append(r)
        per_run[key].append(r)
    if set(per_run)!=set(expected): raise ValueError(f'{source} incomplete runs')
    for key,(probes,candidates) in expected.items():
        if len(per_run[key])!=candidates: raise ValueError(f'{source} candidate count mismatch')
        if sum(k[:3]==key for k in pools)!=probes: raise ValueError(f'{source} probe count mismatch')
    return pools


def _pearson(x,y):
    if len(x)<2:return None
    mx=mean(x);my=mean(y)
    a=[v-mx for v in x];b=[v-my for v in y]
    denom=math.sqrt(sum(v*v for v in a)*sum(v*v for v in b))
    return sum(u*v for u,v in zip(a,b))/denom if denom>1e-15 else None


def _ranks(vals):
    order=sorted(range(len(vals)),key=lambda i:vals[i]); result=[0.0]*len(vals)
    i=0
    while i<len(vals):
        j=i+1
        while j<len(vals) and vals[order[j]]==vals[order[i]]:j+=1
        rank=(i+1+j)/2
        for k in range(i,j):result[order[k]]=rank
        i=j
    return result


def spearman(a,b):
    return _pearson(_ranks(a),_ranks(b))


def geometry_diagnostics(matrix, rays, selected_ray, defect_best_ray):
    """Cosine overlap of known ray paths (NOT a detector-information metric)."""
    import numpy as np
    if matrix is None: return dict(mean_pairwise_cosine=None, pool_path_diversity=None,
        selected_mean_cosine=None, defect_best_mean_cosine=None)
    if max(rays)>=matrix.shape[0] or min(rays)<0: raise ValueError('candidate outside projection geometry')
    A=matrix[rays].tocsr()
    norms=np.sqrt(np.asarray(A.multiply(A).sum(axis=1)).ravel())
    if np.any(norms<=0):raise ValueError('empty candidate ray geometry')
    gram=(A@A.T).toarray()/np.outer(norms,norms)
    np.fill_diagonal(gram,0.)
    gram=np.maximum(gram,0.)
    n=len(rays)
    pair=float(gram.sum()/(n*(n-1)))
    return dict(mean_pairwise_cosine=pair,pool_path_diversity=1.-pair,
        selected_mean_cosine=float(gram[rays.index(selected_ray)].sum()/(n-1)),
        defect_best_mean_cosine=float(gram[rays.index(defect_best_ray)].sum()/(n-1)))


def analyze_pool(rows, source, matrix=None):
    if len(rows)<2: raise ValueError('pool too small')
    parsed=[]; seen=set()
    for r in rows:
        ray=as_int(r['candidate_ray'],'candidate_ray')
        if ray<0 or ray in seen:raise ValueError('duplicate/invalid candidate ray')
        seen.add(ray)
        p=dict(ray=ray,hit=as_int(r['defect_hit'],'defect_hit'),
            chosen=as_int(r['chosen'],'chosen'),eligible=as_int(r['eligible'],'eligible'),
            score=as_float(r['gradient_score'],'gradient_score'),
            defect=as_float(r['one_ray_defect_gain'],'one_ray_defect_gain'),
            global_gain=as_float(r['one_ray_global_gain'],'one_ray_global_gain'),
            redundancy=as_float(r['prior_path_coverage'],'prior_path_coverage'))
        if source=='08G':p['disagreement']=as_float(r['disagreement_score'],'disagreement_score')
        if any(p[k] not in (0,1) for k in ('hit','chosen','eligible')):
            raise ValueError('invalid binary flag')
        parsed.append(p)
    chosen=[p for p in parsed if p['chosen']]
    if len(chosen)!=1 or not chosen[0]['eligible']:
        raise ValueError('not exactly one eligible selected ray')
    if source=='08E':
        if sum(as_int(r['reference'],'reference') for r in rows)!=1:
            raise ValueError('08E must have one reference ray')
        ranks=sorted(parsed,key=lambda p:(-p['score'],p['ray']))
        stored={as_int(r['candidate_ray'],'candidate_ray'):as_int(r['score_rank'],'score_rank') for r in rows}
        if any(stored[p['ray']]!=i for i,p in enumerate(ranks,1)):
            raise ValueError('08E saved score ranks inconsistent')
    best=lambda name:sorted(parsed,key=lambda p:(-p[name],p['ray']))[0]
    selected=chosen[0]; top=best('score'); defect_best=best('defect');global_best=best('global_gain')
    hits=[p for p in parsed if p['hit']];eligible=[p for p in parsed if p['eligible']]
    best_hit=best('defect')['hit']
    best_defect_eligible=sorted(eligible,key=lambda p:(-p['defect'],p['ray']))[0]
    result=dict(pool_size=len(parsed),eligible_count=len(eligible),
        has_defect_candidate=int(bool(hits)),hit_candidate_count=len(hits),
        pool_defect_hit_fraction=len(hits)/len(parsed),selected_defect_hit=selected['hit'],
        top_gradient_defect_hit=top['hit'],
        hit_missed_when_available=int(bool(hits) and not selected['hit']),
        gradient_top_missed_hit=int(bool(hits) and not top['hit']),
        selected_ray=selected['ray'],gradient_top_ray=top['ray'],
        defect_oracle_ray=defect_best['ray'],global_oracle_ray=global_best['ray'],
        defect_oracle_hits_defect=best_hit,
        selected_is_defect_oracle=int(selected['ray']==defect_best['ray']),
        selected_is_global_oracle=int(selected['ray']==global_best['ray']),
        gradient_top_is_defect_oracle=int(top['ray']==defect_best['ray']),
        global_oracle_gain=global_best['global_gain'],defect_oracle_gain=defect_best['defect'],
        selected_global_gain=selected['global_gain'],selected_defect_gain=selected['defect'],
        defect_regret=max(0.,defect_best['defect']-selected['defect']),
        global_regret=max(0.,global_best['global_gain']-selected['global_gain']),
        defect_eligible_ceiling=best_defect_eligible['defect'],
        defect_guard_exclusion_gap=max(0.,defect_best['defect']-best_defect_eligible['defect']),
        defect_best_vs_worst=defect_best['defect']-min(p['defect'] for p in parsed),
        gradient_score_vs_hit_spearman=spearman([p['score'] for p in parsed],[p['hit'] for p in parsed]),
        gradient_score_vs_defect_spearman=spearman([p['score'] for p in parsed],[p['defect'] for p in parsed]),
        gradient_score_vs_global_spearman=spearman([p['score'] for p in parsed],[p['global_gain'] for p in parsed]),
        mean_candidate_redundancy=mean(p['redundancy'] for p in parsed),
        selected_redundancy=selected['redundancy'],
        defect_oracle_redundancy=defect_best['redundancy'])
    if source=='08G':
        top_dis=best('disagreement')
        result.update(disagreement_top_ray=top_dis['ray'],disagreement_top_defect_hit=top_dis['hit'],
            disagreement_missed_hit=int(bool(hits) and not top_dis['hit']),
            disagreement_is_defect_oracle=int(top_dis['ray']==defect_best['ray']),
            disagreement_defect_regret=max(0.,defect_best['defect']-top_dis['defect']),
            disagreement_global_regret=max(0.,global_best['global_gain']-top_dis['global_gain']),
            disagreement_score_vs_defect_spearman=spearman([p['disagreement'] for p in parsed],[p['defect'] for p in parsed]))
    result.update(geometry_diagnostics(matrix,[p['ray'] for p in parsed],selected['ray'],defect_best['ray']))
    return result


def aggregate(poolrows):
    """Within object first; object balanced per archive / size / policy."""
    by=defaultdict(list)
    for p in poolrows:by[(p['source'],p['size'],p['policy'])].append(p)
    out=[]
    descriptors=('has_defect_candidate','hit_missed_when_available','selected_defect_hit',
        'gradient_top_missed_hit','disagreement_missed_hit','pool_defect_hit_fraction',
        'defect_oracle_hits_defect','selected_is_defect_oracle','selected_is_global_oracle',
        'gradient_top_is_defect_oracle','disagreement_is_defect_oracle',
        'defect_oracle_gain','selected_defect_gain','global_oracle_gain','selected_global_gain',
        'defect_regret','global_regret','defect_guard_exclusion_gap','defect_best_vs_worst',
        'gradient_score_vs_hit_spearman','gradient_score_vs_defect_spearman',
        'gradient_score_vs_global_spearman','disagreement_score_vs_defect_spearman',
        'mean_candidate_redundancy','selected_redundancy','defect_oracle_redundancy',
        'mean_pairwise_cosine','pool_path_diversity','selected_mean_cosine','defect_best_mean_cosine')
    for (source,size,policy),rows in sorted(by.items()):
        objects=sorted(set(p['object_seed'] for p in rows))
        result=dict(source=source,size=size,policy=policy,n_objects=len(objects),n_pools=len(rows),
            pools_with_hits=sum(r['has_defect_candidate'] for r in rows),
            pools_with_hit_missed=sum(r['hit_missed_when_available'] for r in rows),
            missed_given_available=(sum(r['hit_missed_when_available'] for r in rows)/
                                    sum(r['has_defect_candidate'] for r in rows)
                                    if any(r['has_defect_candidate'] for r in rows) else None))
        for field in descriptors:
            objmeans=[]
            for obj in objects:
                values=[r.get(field) for r in rows if r['object_seed']==obj and r.get(field) is not None]
                if values:objmeans.append(mean(values))
            result['mean_'+field]=mean(objmeans) if objmeans else None
        out.append(result)
    return out


def write_csv(path, rows):
    if not rows: raise ValueError('empty CSV')
    names=[]
    for row in rows:
        for k in row:
            if k not in names:names.append(k)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=names);w.writeheader();w.writerows(rows)


def run(e_dir,g_dir,output_dir, *, geometry=True, matrix_provider=None):
    e_dir=Path(e_dir).resolve();g_dir=Path(g_dir).resolve();out=Path(output_dir).resolve()
    for archive in (e_dir,g_dir):
        if out==archive or archive in out.parents or out in archive.parents:
            raise ValueError('output must be separate from input archive')
    if e_dir==g_dir:raise ValueError('08E and 08G archives must differ')
    if out.exists():raise FileExistsError('refusing to overwrite existing 08H output')
    archives={}; counts={};allpools={}; input_seeds={}
    for source,path in (('08E',e_dir),('08G',g_dir)):
        rows,manifest,status,nhashes=verify_archive(path,source)
        archives[source]=dict(path=str(path),sha256_verified_files=nhashes,candidate_rows=len(rows),
            runs=len(manifest),status=status)
        grouped=candidates_by_pool(rows,manifest,source)
        allpools[source]=grouped
        input_seeds[source]={as_int(m['object_seed'],'object_seed') for m in manifest}
    if input_seeds['08E'] & input_seeds['08G']:
        raise ValueError('shared object seeds: sources must not be pooled as matched comparisons')
    matrices={}
    if geometry:
        if matrix_provider is None:
            from experiment_04b import system_matrix
            from experiment_04g import TILTS
            from experiment_08e import ANGLES
            matrix_provider=lambda n: system_matrix(n,ANGLES,TILTS).tocsr()
        sizes=sorted({key[0] for pools in allpools.values() for key in pools})
        matrices={n:matrix_provider(n) for n in sizes}
    poolrows=[]
    for source,pools in allpools.items():
        for (size,obj,policy,before),rows in sorted(pools.items()):
            values=analyze_pool(rows,source,matrices.get(size))
            poolrows.append(dict(source=source,size=size,object_seed=obj,policy=policy,
                acquired_before=before,**values))
    summary=aggregate(poolrows)
    report=dict(verdict='PASS',read_only=True,scope='retrospective development-only 08E/08G candidate availability and one-ray oracle audit',
        sources=archives,pools=len(poolrows),candidate_rows=sum(v['candidate_rows'] for v in archives.values()),
        geometry_enabled=geometry,distinct_source_object_seeds=True,
        limitations=['08E and 08G use different development objects and different probe histories: do not treat as paired trials',
        'Defect masks and simulated candidate gains are retrospective evaluation-only labels, never acquisition inputs',
        'Oracle is best among observed candidates for immediate one-ray gain, NOT an accessible live policy',
        'A geometric ray-defect intersection does not certify independent information or successful defect detection',
        'Pairwise path cosine is a descriptive geometric overlap statistic, not a conditioning or information-gain certificate',
        'Object is the replication unit; nested pools and candidates must not be used as independent observations',
        'No acquisitions or MART reconstructions were performed; all source archives remain unmodified'])
    out.mkdir(parents=True,exist_ok=False)
    write_csv(out/'pool_diagnostics.csv',poolrows)
    write_csv(out/'object_balanced_summary.csv',summary)
    (out/'audit_report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (out/'analysis_protocol.json').write_text(json.dumps(dict(
        input_sources=['08E candidate_probes.csv','08G candidate_diagnostics.csv'],
        grouping='source x size x object seed x policy x acquisition prefix',
        candidate_available='at least one defect_hit=1 in pool',
        missed_hit='there is a hit candidate but selected ray defect_hit=0',
        oracle='maximum retrospective one-ray gain within actual pool; ties ascending candidate ray ID',
        regret='oracle gain - selected gain (nonnegative)',
        guard_exclusion_gap='best all-candidate defect gain minus best eligible-candidate defect gain',
        path_cosine='mean nonnegative pairwise dot(row_i,row_j)/(L2_i*L2_j), off diagonal',
        summary='average within object then object-balanced within each separate source / size / policy',
        source_archives_unchanged=True),indent=2)+'\n',encoding='utf-8')
    return report,summary


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--08e-dir',dest='e_dir',type=Path,default=Path('../rbyrct-results/experiment08e/feedback_first'))
    ap.add_argument('--08g-dir',dest='g_dir',type=Path,default=Path('../rbyrct-results/experiment08g/disagreement_first'))
    ap.add_argument('--output-dir',type=Path,default=Path('../rbyrct-results/experiment08h/candidate_diagnostic_first'))
    ap.add_argument('--no-geometry',action='store_true',help='omit projection-matrix cosine diagnostics')
    args=ap.parse_args()
    report,summary=run(args.e_dir,args.g_dir,args.output_dir,geometry=not args.no_geometry)
    print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2))
    print('--- object-balanced availability, missed hits and oracle opportunity ---')
    for r in summary:
        print(f"{r['source']} {r['size']}^3 {r['policy']:<14} pools={r['n_pools']:2} "
              f"available={r['pools_with_hits']} missed_hits={r['pools_with_hit_missed']} "
              f"defect_regret={100*r['mean_defect_regret']:.3f} pp "
              f"global_regret={100*r['mean_global_regret']:.3f} pp")

if __name__=='__main__':main()
