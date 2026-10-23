"""Audit archived study rows and repeatability; optionally check manuscript tables.

Usage: python audit_results.py [manuscript.docx]
Only Python's standard library is required.
"""
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parent
KEYS = ('object_type', 'offset', 'phantom', 'seed', 'budget', 'noise_fraction')
POLICIES = {'adaptive_feedback', 'feedback_off_control', 'geometry_balanced',
            'voxel_coverage_greedy', 'reliability_gate'}
FILES = ('metrics.csv', 'paired_cases.csv', 'paired_summary.csv',
         'gate_trace.csv', 'mismatch_diagnostics.csv')


def read(path):
    with path.open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def subset(rows, **kwargs):
    return [r for r in rows if all(str(r[k]) == str(v) for k, v in kwargs.items())]


def summary(rows):
    gains = [100 * float(r['relative_gain']) for r in rows]
    return f'{statistics.mean(gains):+.2f}%', f'{sum(g > 0 for g in gains)}/{len(gains)}'


def audit(manuscript=None):
    datasets = []
    for folder, repeat in [('experiment04p_full', '04p_full'),
                           ('experiment04qb_full', '04qb_full')]:
        base = ROOT / 'results' / folder
        rows = read(base / 'metrics.csv')
        pairs = read(base / 'paired_cases.csv')
        groups = {}
        for r in rows:
            key = tuple(r[k] for k in KEYS)
            assert math.isfinite(float(r['rmse'])) and float(r['rmse']) > 0
            assert r['policy'] not in groups.setdefault(key, {})
            groups[key][r['policy']] = float(r['rmse'])
        assert len(rows) == 480 and len(groups) == 96 and len(pairs) == 384
        assert all(set(g) == POLICIES for g in groups.values())
        pair_keys = set()
        for r in pairs:
            key = tuple(r[k] for k in KEYS)
            pkey = key + (r['policy'],)
            assert pkey not in pair_keys
            pair_keys.add(pkey)
            g = groups[key]
            off, val = g['feedback_off_control'], g[r['policy']]
            assert math.isclose(float(r['rmse']), val, abs_tol=1e-14)
            assert math.isclose(float(r['feedback_off_rmse']), off, abs_tol=1e-14)
            assert math.isclose(float(r['relative_gain']), (off-val)/off, abs_tol=1e-14)
            assert int(r['win']) == int(val < off)
        for name in FILES:
            assert (base/name).read_bytes() == (ROOT/'validation/04r'/repeat/name).read_bytes()
        a = json.loads((base/'protocol.json').read_text())
        b = json.loads((ROOT/'validation/04r'/repeat/'protocol.json').read_text())
        a['parameters'].pop('output_dir'); b['parameters'].pop('output_dir')
        assert a == b
        datasets.append(pairs)

    expected = []
    for rows in datasets:
        expected.append([[ot, f'{budget:,}', *summary(subset(rows, policy='adaptive_feedback', object_type=ot, budget=budget))]
                         for ot in ['replicated', 'subvoxel'] for budget in [1024, 2048]])
    for rows in datasets:
        expected.append([[family.capitalize(), *[summary(subset(rows, policy='adaptive_feedback', budget=2048, phantom=family, object_type=ot))[0]
                         for ot in ['replicated','subvoxel']]] for family in ['branches','defects','layers','pores']])
    expected.append([[ot, off, *summary(subset(datasets[1], policy='adaptive_feedback', budget=2048, object_type=ot, offset=off))]
                     for ot in ['replicated','subvoxel'] for off in ['0.0','0.15']])
    expected.append([[ot, f'{budget:,}', *summary(subset(datasets[1], policy='reliability_gate', object_type=ot, budget=budget))]
                     for ot in ['replicated','subvoxel'] for budget in [1024,2048]])
    dispersion=[]
    for study, rows in enumerate(datasets, 1):
        for ot in ['replicated','subvoxel']:
            for budget in [1024,2048]:
                selected=subset(rows,policy='adaptive_feedback',object_type=ot,budget=budget)
                fm=[statistics.mean(100*float(r['relative_gain']) for r in subset(selected,phantom=f)) for f in ['branches','defects','layers','pores']]
                dispersion.append([f'Study {study}',ot,f'{budget:,}',summary(selected)[0],f'{statistics.stdev(fm):.2f} pp',f'{min(fm):+.1f} to {max(fm):+.1f}%'])
    expected.append(dispersion)
    if manuscript:
        with zipfile.ZipFile(manuscript) as z:
            root=ET.fromstring(z.read('word/document.xml'))
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        tables=root.findall('.//w:body/w:tbl',ns)
        def norm(s): return s.replace('−','-').replace('0.0','0') if s == '0.0' else s.replace('−','-')
        for i, wanted in enumerate(expected):
            actual=[]
            for row in tables[i].findall('w:tr',ns)[1:]:
                actual.append([''.join(t.text or '' for t in c.findall('.//w:t',ns)) for c in row.findall('w:tc',ns)])
            assert [[norm(c) for c in r] for r in actual] == [[norm(c) for c in r] for r in wanted], (i+1,actual,wanted)
    print('PASS: 960 metrics; 768 paired comparisons; complete unique scenarios; recomputed gains; ten byte-identical repeat files; protocols agree except output_dir.')
    if manuscript: print('PASS: all values in manuscript Tables 1–7 match independent CSV recomputation.')
    for i, table in enumerate(expected,1):
        print('Table',i)
        for row in table: print(' | '.join(row))


if __name__ == '__main__':
    audit(sys.argv[1] if len(sys.argv)>1 else None)
