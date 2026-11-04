"""RBYRCT-08I: read-only within-pool ranking mechanism audit of 08E/08G.

Uses existing evaluation-only defect_hit and one_ray_defect_gain labels.
Requires audit_08h.py from the preceding committed milestone.
"""
from __future__ import annotations
import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

from audit_08h import (verify_archive, candidates_by_pool, as_int, as_float,
                       analyze_pool, write_csv)


def _best(items, key):
    return min(items, key=lambda p: (-p[key], p['ray']))


def _midranks_desc(values):
    """Rank 1 is the highest value; tied values get average rank."""
    order = sorted(range(len(values)), key=lambda i: (-values[i], i))
    ranks = [0.] * len(values)
    pos = 0
    while pos < len(order):
        end = pos + 1
        while end < len(order) and values[order[end]] == values[order[pos]]:
            end += 1
        rank = (pos + 1 + end) / 2.
        for idx in order[pos:end]:
            ranks[idx] = rank
        pos = end
    return ranks


def analyze_ranking_pool(rows, source):
    """Use saved candidates only; truth-dependent fields are retrospective."""
    # Reuse 08H's strict pool validation and saved-score-rank checks.
    base = analyze_pool(rows, source, matrix=None)
    points = []
    for r in rows:
        points.append(dict(ray=as_int(r['candidate_ray'], 'candidate_ray'),
                           score=as_float(r['gradient_score'], 'gradient_score'),
                           defect=as_float(r['one_ray_defect_gain'], 'one_ray_defect_gain'),
                           global_gain=as_float(r['one_ray_global_gain'], 'one_ray_global_gain'),
                           hit=as_int(r['defect_hit'], 'defect_hit'),
                           chosen=as_int(r['chosen'], 'chosen'),
                           eligible=as_int(r['eligible'], 'eligible'),
                           **({'disagreement': as_float(r['disagreement_score'], 'disagreement_score')}
                              if source == '08G' else {})))
    hits = [p for p in points if p['hit']]
    misses = [p for p in points if not p['hit']]
    gradient_ranks = _midranks_desc([p['score'] for p in points])
    rank_by_ray = {p['ray']: rank for p, rank in zip(points, gradient_ranks)}
    selected = next(p for p in points if p['chosen'])
    defect_best = _best(points, 'defect')
    global_best = _best(points, 'global_gain')
    gradient_best = _best(points, 'score')
    result = dict(pool_size=len(points), n_hit=len(hits), n_nonhit=len(misses),
                  available_hit=int(bool(hits)), selected_hit=selected['hit'],
                  defect_oracle_hit=defect_best['hit'], global_oracle_hit=global_best['hit'],
                  selected_is_defect_oracle=int(selected['ray'] == defect_best['ray']),
                  gradient_top_hit=gradient_best['hit'],
                  gradient_top_is_defect_oracle=int(gradient_best['ray'] == defect_best['ray']),
                  selected_ray=selected['ray'], defect_oracle_ray=defect_best['ray'],
                  mean_hit_gradient_score=mean(p['score'] for p in hits) if hits else None,
                  mean_nonhit_gradient_score=mean(p['score'] for p in misses) if misses else None,
                  mean_hit_gradient_rank=mean(rank_by_ray[p['ray']] for p in hits) if hits else None,
                  mean_nonhit_gradient_rank=mean(rank_by_ray[p['ray']] for p in misses) if misses else None,
                  mean_hit_defect_gain=mean(p['defect'] for p in hits) if hits else None,
                  mean_nonhit_defect_gain=mean(p['defect'] for p in misses) if misses else None,
                  best_hit_defect_gain=max(p['defect'] for p in hits) if hits else None,
                  best_nonhit_defect_gain=max(p['defect'] for p in misses) if misses else None,
                  selected_defect_gain=selected['defect'],
                  defect_oracle_gain=defect_best['defect'],
                  regret=base['defect_regret'])
    result['hit_minus_nonhit_score'] = (result['mean_hit_gradient_score'] - result['mean_nonhit_gradient_score']
                                        if hits and misses else None)
    result['hit_minus_nonhit_rank'] = (result['mean_hit_gradient_rank'] - result['mean_nonhit_gradient_rank']
                                       if hits and misses else None)
    result['hit_minus_nonhit_defect_gain'] = (result['mean_hit_defect_gain'] - result['mean_nonhit_defect_gain']
                                              if hits and misses else None)
    result['hit_best_minus_nonhit_best_gain'] = (result['best_hit_defect_gain'] - result['best_nonhit_defect_gain']
                                                 if hits and misses else None)
    # Fraction of (hit, nonhit) pairs where the hit has a higher gradient score;
    # tied pairs count as 0.5 (pairwise rank/AUC descriptive metric).
    result['hit_score_pairwise_win_fraction'] = (sum(1. if h['score'] > n['score'] else
                                                        .5 if h['score'] == n['score'] else 0.
                                                        for h in hits for n in misses) / (len(hits) * len(misses))
                                                 if hits and misses else None)
    result['hit_defect_gain_pairwise_win_fraction'] = (sum(1. if h['defect'] > n['defect'] else
                                                             .5 if h['defect'] == n['defect'] else 0.
                                                             for h in hits for n in misses) / (len(hits) * len(misses))
                                                      if hits and misses else None)
    result['hit_candidates_better_than_selected'] = sum(p['defect'] > selected['defect'] for p in hits)
    result['best_hit_beats_selected'] = (int(result['best_hit_defect_gain'] > selected['defect'])
                                        if hits else None)
    if source == '08G':
        disagree_best = _best(points, 'disagreement')
        result['disagreement_top_hit'] = disagree_best['hit']
        result['disagreement_top_is_defect_oracle'] = int(disagree_best['ray'] == defect_best['ray'])
        dis_ranks = _midranks_desc([p['disagreement'] for p in points])
        result['hit_minus_nonhit_disagreement_rank'] = (mean(v for p, v in zip(points, dis_ranks) if p['hit']) -
                                                        mean(v for p, v in zip(points, dis_ranks) if not p['hit'])
                                                        if hits and misses else None)
        result['hit_disagreement_pairwise_win_fraction'] = (sum(1. if h['disagreement'] > n['disagreement'] else
                                                                  .5 if h['disagreement'] == n['disagreement'] else 0.
                                                                  for h in hits for n in misses) / (len(hits) * len(misses))
                                                           if hits and misses else None)
    return result


def object_balance(pool_rows):
    grouped = defaultdict(list)
    for p in pool_rows:
        grouped[(p['source'], p['size'], p['policy'])].append(p)
    metric_names = ('available_hit','selected_hit','gradient_top_hit','defect_oracle_hit',
                    'global_oracle_hit','selected_is_defect_oracle','gradient_top_is_defect_oracle',
                    'mean_hit_gradient_rank','mean_nonhit_gradient_rank',
                    'hit_minus_nonhit_rank','hit_minus_nonhit_score',
                    'hit_score_pairwise_win_fraction','hit_defect_gain_pairwise_win_fraction',
                    'hit_minus_nonhit_defect_gain','hit_best_minus_nonhit_best_gain',
                    'hit_candidates_better_than_selected','best_hit_beats_selected',
                    'regret','disagreement_top_hit','disagreement_top_is_defect_oracle',
                    'hit_minus_nonhit_disagreement_rank','hit_disagreement_pairwise_win_fraction')
    summaries = []
    for (source, size, policy), group in sorted(grouped.items()):
        objects = sorted({p['object_seed'] for p in group})
        res = dict(source=source, size=size, policy=policy,
                   n_objects=len(objects), n_pools=len(group),
                   pools_with_hit=sum(p['available_hit'] for p in group),
                   pools_oracle_hit=sum(p['defect_oracle_hit'] for p in group),
                   pools_hit_beats_selected=sum(p['best_hit_beats_selected'] or 0 for p in group),
                   pools_hit_selected=sum(p['selected_hit'] for p in group))
        for metric in metric_names:
            object_means = []
            for obj in objects:
                values = [p[metric] for p in group if p['object_seed'] == obj and p.get(metric) is not None]
                if values:
                    object_means.append(mean(values))
            res['mean_'+metric] = mean(object_means) if object_means else None
        summaries.append(res)
    return summaries


def run(e_dir, g_dir, output_dir):
    e_dir, g_dir, out = [Path(p).resolve() for p in (e_dir, g_dir, output_dir)]
    if e_dir == g_dir: raise ValueError('source archives must differ')
    for src in (e_dir, g_dir):
        if out == src or src in out.parents or out in src.parents:
            raise ValueError('output must be separate from archives')
    if out.exists(): raise FileExistsError('refusing to overwrite existing 08I output')
    archive_reports = {}; all_groups = {}; seed_sets = {}
    for source, root in (('08E',e_dir), ('08G',g_dir)):
        rows, manifest, status, hashes = verify_archive(root, source)
        groups = candidates_by_pool(rows, manifest, source)
        archive_reports[source] = dict(path=str(root), verified_sha256_files=hashes,
                                       candidate_rows=len(rows), runs=len(manifest))
        all_groups[source] = groups
        seed_sets[source] = {as_int(r['object_seed'], 'object_seed') for r in manifest}
    if seed_sets['08E'] & seed_sets['08G']:
        raise ValueError('08E and 08G object seeds overlap')
    pool_rows = []
    for source, groups in all_groups.items():
        for (size, object_seed, policy, acquired_before), candidates in sorted(groups.items()):
            pool_rows.append(dict(source=source,size=size,object_seed=object_seed,policy=policy,
                                  acquired_before=acquired_before,**analyze_ranking_pool(candidates,source)))
    summary = object_balance(pool_rows)
    report = dict(verdict='PASS', read_only=True,
                  scope='retrospective within-pool score-vs-defect-hit and immediate benefit diagnostics',
                  sources=archive_reports, candidate_pools=len(pool_rows),
                  candidate_rows=sum(p['candidate_rows'] for p in archive_reports.values()),
                  limitations=[
                      '08E and 08G use distinct development objects and acquisition histories; do not pool as matched trials',
                      'Defect hits and one-ray gains are post-hoc truth-dependent labels, not deployable selector features',
                      'Defect intersection does not guarantee benefit; oracle ranking compares one-ray immediate gains only',
                      'Conditioning, future acquisition effects and causal explanations are not established',
                      'Pools are nested in objects; metrics are averaged within object before group-level means',
                      'Missing hit/nonhit classes yield undefined contrasts, excluded rather than imputed as zero',
                      'No acquisition or MART reconstruction was performed; source data are unchanged'])
    out.mkdir(parents=True,exist_ok=False)
    write_csv(out/'pool_rank_diagnostics.csv',pool_rows)
    write_csv(out/'object_balanced_summary.csv',summary)
    (out/'audit_report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (out/'analysis_protocol.json').write_text(json.dumps(dict(
        source='08E/08G hashed retrospective candidate records',
        gradient_rank='descending gradient_score, tied values midrank',
        hit_minus_nonhit_rank='mean rank(hit candidates) - mean rank(nonhit candidates); positive means hits rank worse',
        hit_score_pairwise_win_fraction='P(score(hit)>score(nonhit)) with ties given 0.5; 0.5 means no preference',
        oracle_hit='whether candidate with largest one_ray_defect_gain intersects evaluation defect mask',
        best_hit_beats_selected='whether any defect-hitting candidate has strictly larger one-ray defect gain than selected ray',
        summary='average per object, then average objects separately by source, size and policy',
        guard='eligibility is recorded, but diagnostic compares all recorded candidates; never modifies selection',
        output_read_only=True),indent=2)+'\n',encoding='utf-8')
    return report, summary


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--08e-dir',dest='e_dir',type=Path,default=Path('../rbyrct-results/experiment08e/feedback_first'))
    ap.add_argument('--08g-dir',dest='g_dir',type=Path,default=Path('../rbyrct-results/experiment08g/disagreement_first'))
    ap.add_argument('--output-dir',type=Path,default=Path('../rbyrct-results/experiment08i/ranking_mechanism_first'))
    args = ap.parse_args()
    report, summary = run(args.e_dir,args.g_dir,args.output_dir)
    print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2))
    print('--- object-balanced ranking mechanism ---')
    for row in summary:
        print(f"{row['source']} {row['size']}^3 {row['policy']:<14} "
              f"pools={row['n_pools']:2} available={row['pools_with_hit']} "
              f"oracle_hits={row['pools_oracle_hit']} "
              f"best_hit_better_than_selected={row['pools_hit_beats_selected']} "
              f"hit_score_pairwise={row['mean_hit_score_pairwise_win_fraction']}")

if __name__ == '__main__': main()
