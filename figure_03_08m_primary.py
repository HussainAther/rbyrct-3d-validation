"""08AF Figure 3: verified, object-level 08M primary evidence.

Read-only against frozen 08M and independently replayed 08Q archives.
Creates PDF, SVG, PNG, a numeric CSV, and JSON provenance manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PRIMARY_RAYS = 2048
POLICY = 'information_diag'
EXPECTED_OBJECTS = 8
EXPECTED_CONDITIONS = 4
PRIMARY_TOL = 1e-11


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def check(condition: bool, detail: str) -> None:
    if not condition:
        raise ValueError('Figure 3 validation failed: ' + detail)


def load_verified_data(results_dir: Path, replay_dir: Path) -> tuple[pd.DataFrame, dict, dict]:
    obj_path = results_dir / 'object_level_summary.csv'
    agg_path = results_dir / 'aggregate_summary.csv'
    primary_path = results_dir / 'primary_endpoint.json'
    replay_obj_path = replay_dir / 'object_level_replayed.csv'
    replay_agg_path = replay_dir / 'aggregate_replayed.csv'
    for p in (obj_path, agg_path, primary_path, replay_obj_path, replay_agg_path):
        check(p.is_file(), f'missing source: {p}')
    objs = pd.read_csv(obj_path)
    agg = pd.read_csv(agg_path)
    repl = pd.read_csv(replay_obj_path)
    ragg = pd.read_csv(replay_agg_path)
    primary = json.loads(primary_path.read_text(encoding='utf-8'))['primary']

    check(int(primary['acquired']) == PRIMARY_RAYS, 'primary ray checkpoint mismatch')
    check(primary['policy'] == POLICY, 'primary policy mismatch')
    check(int(primary['n_objects']) == EXPECTED_OBJECTS, 'primary n_objects mismatch')
    subset = objs.loc[(objs['acquired'] == PRIMARY_RAYS) & (objs['policy'] == POLICY)].copy()
    check(len(subset) == EXPECTED_OBJECTS, f'expected 8 independent objects; found {len(subset)}')
    check(subset['object_id'].is_unique, 'duplicate independent object IDs')
    check((subset['n_conditions'] == EXPECTED_CONDITIONS).all(), 'unexpected condition count')
    check((subset['size'] == 32).all(), 'unexpected grid size')
    check(subset[['mean_global_gain','mean_defect_gain']].notna().all().all(), 'missing gain data')
    check(np.isfinite(subset[['mean_global_gain','mean_defect_gain']].to_numpy(float)).all(), 'nonfinite gain')

    rsub = repl.loc[repl['acquired'] == PRIMARY_RAYS].copy()
    check(len(rsub) == EXPECTED_OBJECTS and rsub['object_id'].is_unique, '08Q replay objects malformed')
    aligned = subset.merge(rsub, on='object_id', suffixes=('_08m','_08q'), validate='one_to_one')
    check(len(aligned) == EXPECTED_OBJECTS, '08M/08Q object IDs differ')
    for metric in ('mean_global_gain','mean_defect_gain'):
        actual = aligned[f'{metric}_08m'].to_numpy(float)
        replay = aligned[f'{metric}_08q'].to_numpy(float)
        check(np.allclose(actual, replay, rtol=0, atol=PRIMARY_TOL), f'08M vs 08Q {metric} disagreement')
        check(np.isclose(actual.mean(), float(primary[metric]), atol=PRIMARY_TOL, rtol=0), f'primary {metric} mismatch')

    a = agg.loc[(agg['acquired'] == PRIMARY_RAYS) & (agg['policy'] == POLICY)]
    b = ragg.loc[ragg['acquired'] == PRIMARY_RAYS]
    check(len(a) == len(b) == 1, 'summary rows missing or duplicated')
    for metric in ('mean_global_gain','mean_defect_gain'):
        check(np.isclose(float(a.iloc[0][metric]), float(primary[metric]), atol=PRIMARY_TOL, rtol=0), f'08M aggregate {metric} mismatch')
        check(np.isclose(float(b.iloc[0][metric]), float(primary[metric]), atol=PRIMARY_TOL, rtol=0), f'08Q aggregate {metric} mismatch')
    for metric in ('object_global_wins','object_defect_wins'):
        check(int(a.iloc[0][metric]) == int(primary[metric]) == EXPECTED_OBJECTS, metric + ' not 8/8')
        check(int(b.iloc[0][metric]) == EXPECTED_OBJECTS, '08Q ' + metric + ' not 8/8')

    # Sort stable by numerical object seed, rather than by observed effect size.
    subset['object_seed'] = subset['object_id'].str.extract(r'(\d+)$')[0].astype(int)
    check(subset['object_seed'].is_unique, 'object seed duplicated')
    subset = subset.sort_values('object_seed').reset_index(drop=True)
    output = subset[['object_id','object_seed','n_conditions','mean_global_gain','mean_defect_gain']].copy()
    output['global_gain_percent'] = 100 * output['mean_global_gain']
    output['defect_gain_percent'] = 100 * output['mean_defect_gain']

    sources = [obj_path, agg_path, primary_path, replay_obj_path, replay_agg_path]
    provenance = {
        'figure': 'Figure 3',
        'study': 'RBYRCT-08M',
        'replay': 'RBYRCT-08Q',
        'primary_checkpoint_rays': PRIMARY_RAYS,
        'policy': POLICY,
        'reference': 'coverage',
        'independent_units': 'synthetic phantom objects',
        'n_independent_objects': EXPECTED_OBJECTS,
        'paired_conditions_per_object': EXPECTED_CONDITIONS,
        'gain_definition': '100 * (1 - policy_RMSE / paired_coverage_RMSE), mean within object across two acquisition seeds and two forward-model conditions',
        'source_sha256': {str(p.resolve()): sha256(p) for p in sources},
        'validated_against': ['08M primary_endpoint.json', '08M aggregate_summary.csv', '08Q object_level_replayed.csv', '08Q aggregate_replayed.csv'],
        'mean_global_gain_percent': float(output['global_gain_percent'].mean()),
        'mean_defect_gain_percent': float(output['defect_gain_percent'].mean()),
        'global_object_wins': int((output['global_gain_percent'] > 0).sum()),
        'defect_object_wins': int((output['defect_gain_percent'] > 0).sum()),
        'selection_of_objects': 'all eight; ascending frozen seed; no effect-size sorting or cherry-picking',
        'uncertainty_intervals': 'not drawn; n=8, all individual independent units shown',
        'read_only_sources': True,
    }
    return output, primary, provenance


def draw_figure(data: pd.DataFrame, output_dir: Path, mean_global: float, mean_defect: float) -> None:
    plt.rcParams.update({
        'font.family': 'DejaVu Sans', 'font.size': 8.5,
        'axes.labelsize': 9, 'axes.titlesize': 10,
        'xtick.labelsize': 8, 'ytick.labelsize': 8,
        'pdf.fonttype': 42, 'ps.fonttype': 42,
        'axes.spines.top': False, 'axes.spines.right': False,
        'savefig.facecolor': 'white',
    })
    palette = ['#2269A6', '#CA743C']
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 3.45), sharey=True, layout='constrained')
    labels = [str(int(v)) for v in data['object_seed'].to_numpy()]
    y = np.arange(len(data))
    series = [
        ('global_gain_percent', 'A  Whole-volume RMSE', mean_global),
        ('defect_gain_percent', 'B  Defect-region RMSE', mean_defect),
    ]
    for ax, color, (key, title, mean) in zip(axs, palette, series):
        values = data[key].to_numpy(float)
        ax.axvline(0, color='#6D737B', linewidth=0.9, linestyle=(0,(3,3)), zorder=1)
        for yy, xx in zip(y, values):
            ax.plot([0, xx], [yy, yy], color=color, alpha=0.38, linewidth=1.25, zorder=2)
        ax.scatter(values, y, s=36, color=color, edgecolor='white', linewidth=0.75, zorder=3, label='Object')
        ax.axvline(mean, color=color, linewidth=1.5, linestyle='-', alpha=0.75, zorder=1)
        ax.set_title(title, loc='left', pad=12, fontweight='bold')
        ax.set_xlabel('Paired RMSE improvement vs coverage (%)')
        ax.grid(axis='x', alpha=0.14, linewidth=0.7)
        ax.set_axisbelow(True)
        ax.tick_params(axis='both', length=0)
        ax.set_yticks(y)
        ax.set_yticklabels(labels)
        ax.invert_yaxis()
        ax.text(0.98, 0.025, f'Mean {mean:+.2f}%  |  8/8 wins',
                transform=ax.transAxes, ha='right', va='bottom',
                fontsize=8, color=color, fontweight='bold')
        left = min(-0.65, values.min() - 1.1)
        right = max(values.max() + 1.4, mean + 1)
        ax.set_xlim(left, right)
    axs[0].set_ylabel('Independent phantom seed')
    fig.suptitle('08M  |  Frozen 32³ acquisition study  |  2,048 rays', x=0.51, fontsize=11, fontweight='bold')
    stem = output_dir / 'Figure_03_08M_primary_evidence'
    fig.savefig(stem.with_suffix('.pdf'), bbox_inches='tight')
    fig.savefig(stem.with_suffix('.svg'), bbox_inches='tight')
    fig.savefig(stem.with_suffix('.png'), dpi=600, bbox_inches='tight')
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--08m-dir', required=True, type=Path)
    parser.add_argument('--08q-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    # Load and validate *before* creating any figure artifact.
    values, primary, provenance = load_verified_data(args.__dict__['08m_dir'], args.__dict__['08q_dir'])
    args.output_dir.mkdir(parents=True, exist_ok=False)
    draw_figure(values, args.output_dir,
                100 * float(primary['mean_global_gain']),
                100 * float(primary['mean_defect_gain']))
    values.to_csv(args.output_dir / 'figure_03_object_values.csv', index=False, float_format='%.17g')
    (args.output_dir / 'figure_03_manifest.json').write_text(json.dumps(provenance, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'PASS', 'output_dir': str(args.output_dir),
                      'n_objects': len(values),
                      'mean_global_percent': provenance['mean_global_gain_percent'],
                      'mean_defect_percent': provenance['mean_defect_gain_percent'],
                      'output_files': [p.name for p in sorted(args.output_dir.iterdir())]}, indent=2))


if __name__ == '__main__':
    main()
