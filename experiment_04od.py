"""04O-D: post-hoc audit of prospective gate behavior; no CT reconstructions."""
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

KEY = ('object_type','offset','phantom','seed','budget','noise_fraction')
POLICIES = ('adaptive_feedback','feedback_off_control','constant_feedback','reliability_gate')


def load_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as fh:
        return list(csv.DictReader(fh))


def write_csv(path, rows, columns):
    with open(path, 'w', newline='', encoding='utf-8') as fh:
        wr = csv.DictWriter(fh, fieldnames=columns)
        wr.writeheader()
        wr.writerows(rows)


def case_key(row):
    return (row['object_type'], float(row['offset']), row['phantom'],
            int(row['seed']), int(row['budget']), float(row['noise_fraction']))


def summarize_trace(rows, budget):
    """Treat decision at acquired_before as controlling [checkpoint, next checkpoint)."""
    rows = sorted(rows, key=lambda r: int(r['acquired_before']))
    if not rows:
        raise ValueError('Missing gate checkpoints')
    starts = [int(r['acquired_before']) for r in rows]
    if starts != sorted(set(starts)) or starts[0] < 0 or starts[-1] >= budget:
        raise ValueError('Invalid/duplicate checkpoint or checkpoint at/after budget')
    strengths = [float(r['feedback_strength_next']) for r in rows]
    if any(not math.isfinite(s) or s < 0 or s > 1 for s in strengths):
        raise ValueError('Invalid feedback strength')
    lengths = [b-a for a,b in zip(starts, starts[1:] + [budget])]
    controlled = sum(lengths)
    active = sum(n * s for n,s in zip(lengths,strengths))
    zero = sum(n for n,s in zip(lengths,strengths) if s == 0)
    one = sum(n for n,s in zip(lengths,strengths) if s == 1)
    switches = sum(a != b for a,b in zip(strengths,strengths[1:]))
    first_on = next((p for p,s in zip(starts,strengths) if s == 1), None)
    first_off = next((p for p,s in zip(starts,strengths) if s == 0), None)
    errors = [float(r['heldout_nrmse']) for r in rows]
    if any(not math.isfinite(e) for e in errors):
        raise ValueError('Nonfinite held-out NRMSE')
    return dict(warm_unclassified=starts[0], n_checks=len(rows), n_switches=switches,
                first_on=first_on if first_on is not None else '',
                first_off=first_off if first_off is not None else '',
                final_strength=strengths[-1], on_rays=one, off_rays=zero,
                controlled_rays=controlled, weighted_strength=active / controlled,
                on_fraction=one / controlled, off_fraction=zero / controlled,
                initial_error=errors[0], final_error=errors[-1],
                min_error=min(errors), max_error=max(errors),
                initial_strength=strengths[0],
                later_on_fraction=sum(n for p,n,s in zip(starts,lengths,strengths) if p >= budget/2 and s==1) /
                max(1,sum(n for p,n in zip(starts,lengths) if p >= budget/2)))


def make_audit(gates, metrics, divergence=None, timings=None):
    by_gate = defaultdict(list)
    for r in gates:
        if r.get('policy') != 'reliability_gate':
            raise ValueError('Unexpected policy in gate_trace')
        by_gate[case_key(r)].append(r)
    by_metrics = defaultdict(dict)
    for r in metrics:
        k, pol = case_key(r), r['policy']
        if pol in by_metrics[k]:
            raise ValueError('Duplicated metric case/policy')
        by_metrics[k][pol] = float(r['rmse'])
    if set(by_gate) != set(by_metrics):
        raise ValueError('Gate and metric case keys do not match')
    div_map = {}
    for r in divergence or []:
        k=(case_key(r),r['policy'])
        if k in div_map: raise ValueError('Duplicate divergence')
        div_map[k]=r
    time_map = {}
    for r in timings or []:
        k=(case_key(r),r['policy'])
        if k in time_map: raise ValueError('Duplicate timing')
        time_map[k]=float(r['selection_s'])
    cases=[]
    for k in sorted(by_gate):
        rmses=by_metrics[k]
        if set(rmses)!=set(POLICIES):
            raise ValueError(f'Missing policies for {k}')
        s=summarize_trace(by_gate[k], k[4])
        base=rmses['feedback_off_control']
        if base <= 0: raise ValueError('Feedback-off RMSE must be positive')
        row=dict(zip(KEY,k))
        row.update(s)
        row.update(gate_rmse=rmses['reliability_gate'],full_rmse=rmses['adaptive_feedback'],
                   off_rmse=base,constant_rmse=rmses['constant_feedback'],
                   gate_gain=(base-rmses['reliability_gate'])/base,
                   full_gain=(base-rmses['adaptive_feedback'])/base,
                   constant_gain=(base-rmses['constant_feedback'])/base,
                   gate_minus_full_rmse=rmses['reliability_gate']-rmses['adaptive_feedback'],
                   gate_minus_constant_rmse=rmses['reliability_gate']-rmses['constant_feedback'],
                   gate_worse_than_off=int(rmses['reliability_gate']>base),
                   gate_worse_than_full=int(rmses['reliability_gate']>rmses['adaptive_feedback']))
        dv=div_map.get((k,'reliability_gate'),{})
        row['same_set_fraction']=dv.get('same_set_fraction','')
        row['sequence_identical']=dv.get('sequence_identical','')
        tg=time_map.get((k,'reliability_gate'))
        tf=time_map.get((k,'adaptive_feedback'))
        row['gate_selection_s']=tg if tg is not None else ''
        row['selection_overhead_ratio']=tg/tf-1 if tg is not None and tf and tf>0 else ''
        cases.append(row)
    return cases


def mean(values): return sum(values)/len(values) if values else None


def group_summaries(cases):
    result=[]
    for cols in [('object_type','budget'),('object_type','budget','offset'),('phantom','object_type','budget')]:
        groups=defaultdict(list)
        for case in cases:
            groups[tuple(case[c] for c in cols)].append(case)
        for vals,rows in sorted(groups.items()):
            x=dict(zip(cols,vals))
            x.update(grouping='+'.join(cols),n=len(rows),
                     mean_on_fraction=mean([r['on_fraction'] for r in rows]),
                     mean_later_on_fraction=mean([r['later_on_fraction'] for r in rows]),
                     mean_switches=mean([r['n_switches'] for r in rows]),
                     ever_off=sum(r['off_rays']>0 for r in rows),
                     always_on_after_warm=sum(r['off_rays']==0 for r in rows),
                     mean_gate_gain=mean([r['gate_gain'] for r in rows]),
                     mean_full_gain=mean([r['full_gain'] for r in rows]),
                     mean_constant_gain=mean([r['constant_gain'] for r in rows]),
                     gate_failures=sum(r['gate_worse_than_off'] for r in rows),
                     full_failures=sum(r['full_gain']<0 for r in rows),
                     gate_better_than_full=sum(r['gate_minus_full_rmse']<0 for r in rows))
            result.append(x)
    return result


def matched_object_contrasts(cases):
    groups=defaultdict(dict)
    for r in cases:
        key=(r['offset'],r['phantom'],r['seed'],r['budget'],r['noise_fraction'])
        if r['object_type'] in groups[key]: raise ValueError('Duplicate object pair')
        groups[key][r['object_type']]=r
    out=[]
    for k,pair in sorted(groups.items()):
        if set(pair)!= {'replicated','subvoxel'}:
            raise ValueError(f'Missing matched object counterpart: {k}')
        a,b=pair['replicated'],pair['subvoxel']
        out.append(dict(zip(('offset','phantom','seed','budget','noise_fraction'),k),
            on_fraction_rep=a['on_fraction'],on_fraction_sub=b['on_fraction'],
            on_fraction_difference=b['on_fraction']-a['on_fraction'],
            gain_rep=a['gate_gain'],gain_sub=b['gate_gain'],
            gain_difference=b['gate_gain']-a['gate_gain'],
            final_error_rep=a['final_error'],final_error_sub=b['final_error'],
            initial_strength_equal=int(a['initial_strength']==b['initial_strength']),
            final_strength_equal=int(a['final_strength']==b['final_strength'])))
    return out


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input-dir',required=True)
    ap.add_argument('--output-dir',required=True)
    args=ap.parse_args()
    src, dst=Path(args.input_dir),Path(args.output_dir)
    dst.mkdir(parents=True,exist_ok=True)
    gates=load_csv(src/'gate_trace.csv')
    metrics=load_csv(src/'metrics.csv')
    div=load_csv(src/'divergence.csv') if (src/'divergence.csv').exists() else []
    timing=load_csv(src/'selection_timing.csv') if (src/'selection_timing.csv').exists() else []
    cases=make_audit(gates,metrics,div,timing)
    groups=group_summaries(cases)
    contrasts=matched_object_contrasts(cases)
    for name,rows in [('case_audit.csv',cases),('group_summary.csv',groups),('matched_object_contrasts.csv',contrasts)]:
        if rows:
            cols=list(dict.fromkeys(k for row in rows for k in row))
            write_csv(dst/name,rows,cols)
    report={
      'experiment':'04O-D', 'type':'offline post-hoc audit; no new reconstructions',
      'input_dir':str(src),'cases':len(cases),'matched_object_pairs':len(contrasts),
      'observed_checkpoints':len(gates),
      'limitations':['Trace records decisions only at diagnostic checkpoints; strength is assumed constant between checkpoints.',
         'Pre-first-checkpoint warm rays are excluded from controlled fractions.',
         'No saved per-ray sequence; exact divergence between checkpoints cannot be inferred from gate trace.',
         'Associations between intervention timing and RMSE are descriptive, not causal effects.',
         'Existing four phantom families are reused; this is not independent confirmation.',
         'Missing optional timing/divergence inputs yield blank fields.']}
    (dst/'audit_protocol.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f"04O-D complete: {len(cases)} cases; {len(contrasts)} matched replicated/subvoxel pairs; output={dst}")

if __name__=='__main__':main()
