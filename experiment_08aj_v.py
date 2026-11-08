"""08AJ-V: hypothetical object-level interval calibration, NO RBYRCT outcomes.

Tests finite-sample coverage for the equally family-weighted mean of 24 object
level paired gains (three fixed families, eight independently sampled hypothetical
objects per family). This is a simulation sensitivity analysis, not a proof of
coverage in the real cohort or approval to freeze the study.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from scipy.stats import t as student_t

SCHEMA = 'RBYRCT-08AJ-V-hypothetical-inference-calibration-v1'
FAMILIES = ('localized_defects', 'smooth_heterogeneity', 'irregular_inclusions')
SCENARIOS = ('normal_equal', 'skewed_centered', 'heavy_tail_t3', 'heteroscedastic_family')
METHODS = ('stratified_percentile', 'stratified_basic', 'stratified_bootstrap_t', 'stratified_welch_t')
SD_LEVELS = (0.01, 0.03, 0.06)
MEAN_LEVELS = (0.0, 0.01, 0.02)
SEED = 941027


def canonical(data):
    return (json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def generate_gain_sample(rng, scenario, mean, sd):
    """3 x 8 hypothetical gains, exactly specified population grand mean."""
    if scenario == 'normal_equal':
        z = rng.normal(size=(3, 8))
    elif scenario == 'skewed_centered':
        z = rng.exponential(size=(3, 8)) - 1.0
    elif scenario == 'heavy_tail_t3':
        z = rng.standard_t(df=3, size=(3, 8)) / np.sqrt(3.0)
    elif scenario == 'heteroscedastic_family':
        z = rng.normal(size=(3, 8)) * np.array([0.5, 1.0, 1.5])[:, None] / np.sqrt((0.25 + 1.0 + 2.25) / 3)
    else:
        raise ValueError('unknown hypothetical scenario')
    return mean + sd * z


def stratified_se(x):
    """SE of equally weighted stratum means (independent objects assumption)."""
    x = np.asarray(x, dtype=float)
    if x.shape[-2:] != (3, 8):
        raise ValueError('expected exactly three families and eight objects each')
    variances = np.var(x, axis=-1, ddof=1)
    # var( (mean_1+mean_2+mean_3)/3 ) = sum(s_f^2/8) / 9
    var_mean = np.sum(variances / 8.0, axis=-1) / 9.0
    return np.sqrt(var_mean)


def intervals(x, *, bootstrap_count, rng):
    """Four prespecified intervals. Bootstrap resamples WHOLE objects per family.

    Studentized interval uses resampled studentized statistics and its estimated
    resample standard error, NOT the original standard error. Welch-Satterthwaite
    df is based on three within-family sample variances with df=7 each.
    """
    if bootstrap_count < 200:
        raise ValueError('bootstrap_count must be >= 200')
    x = np.asarray(x, dtype=np.float64)
    if x.shape != (3, 8) or not np.all(np.isfinite(x)):
        raise ValueError('invalid hypothetical object-level gains')
    observed = float(x.mean())
    se = float(stratified_se(x))
    if not math.isfinite(se) or se <= 0:
        raise ValueError('degenerate sample standard error')
    indices = rng.integers(0, 8, size=(bootstrap_count, 3, 8))
    sampled = np.take_along_axis(np.broadcast_to(x, (bootstrap_count, 3, 8)), indices, axis=2)
    means = sampled.mean(axis=(1, 2))
    lo, hi = np.quantile(means, [0.025, 0.975])
    boot_se = stratified_se(sampled)
    valid = np.isfinite(boot_se) & (boot_se > 0)
    if valid.sum() < 0.98 * bootstrap_count:
        raise ValueError('too many degenerate studentized resamples')
    tstar = (means[valid] - observed) / boot_se[valid]
    tlo, thi = np.quantile(tstar, [0.025, 0.975])
    var_f = np.var(x, axis=1, ddof=1) / 8.0
    df = float((var_f.sum() ** 2) / ((var_f ** 2).sum() / 7.0))
    crit = float(student_t.ppf(0.975, df))
    return {
        'stratified_percentile': (float(lo), float(hi)),
        'stratified_basic': (float(2 * observed - hi), float(2 * observed - lo)),
        'stratified_bootstrap_t': (float(observed - thi * se), float(observed - tlo * se)),
        'stratified_welch_t': (float(observed - crit * se), float(observed + crit * se)),
    }


def calibrate(*, trials=250, bootstrap_count=1000, seed=SEED, scenarios=SCENARIOS,
              sds=SD_LEVELS, means=MEAN_LEVELS):
    if trials < 50 or bootstrap_count < 200:
        raise ValueError('at least 50 simulation trials and 200 resamples required')
    rng = np.random.default_rng(seed)
    rows = []
    for scenario in scenarios:
        if scenario not in SCENARIOS:
            raise ValueError('unknown scenario')
        for sd in sds:
            if sd <= 0:
                raise ValueError('SD must be positive')
            for mu in means:
                stats = {name: {'coverage': 0, 'above_zero': 0, 'above_two_pct': 0, 'widths': []}
                         for name in METHODS}
                for _ in range(trials):
                    x = generate_gain_sample(rng, scenario, mu, sd)
                    bounds = intervals(x, bootstrap_count=bootstrap_count, rng=rng)
                    for method, (lo, hi) in bounds.items():
                        state = stats[method]
                        state['coverage'] += int(lo <= mu <= hi)
                        state['above_zero'] += int(lo > 0)
                        state['above_two_pct'] += int(lo > 0.02)
                        state['widths'].append(hi - lo)
                for method, st in stats.items():
                    coverage = st['coverage'] / trials
                    rows.append({
                        'scenario': scenario, 'true_mean': float(mu), 'object_sd': float(sd),
                        'method': method, 'simulated_coverage': coverage,
                        'coverage_monte_carlo_se': float(np.sqrt(coverage * (1 - coverage) / trials)),
                        'prob_ci_lower_above_zero': st['above_zero'] / trials,
                        'prob_ci_lower_above_2pct': st['above_two_pct'] / trials,
                        'median_ci_width': float(np.median(st['widths'])),
                    })
    return rows


def report(*, trials=250, bootstrap_count=1000, seed=SEED):
    rows = calibrate(trials=trials, bootstrap_count=bootstrap_count, seed=seed)
    coverage_summary = {}
    for method in METHODS:
        vals = [r['simulated_coverage'] for r in rows if r['method'] == method]
        coverage_summary[method] = {
            'minimum_estimated_coverage': float(min(vals)),
            'maximum_estimated_coverage': float(max(vals)),
            'mean_estimated_coverage_across_scenarios': float(np.mean(vals)),
        }
    return {
        'schema': SCHEMA, 'verdict': 'V_STATISTICAL_CALIBRATION_EVIDENCE_PREPARED',
        'study_provenance': '08AJ-D primary estimand: within-object average of 2 acquisition seeds x 2 forward-model gains; fixed 3 families x 8 objects',
        'unit_of_analysis': 'hypothetical independent object-level paired gain, not 96 paired conditions as separate independent samples',
        'estimand': 'equal-weighted mean of the three family-specific mean object gains',
        'scenario_descriptions': {
            'normal_equal': 'three Gaussian families with same mean and SD',
            'skewed_centered': 'exponential minus 1, finite-variance and right-skewed',
            'heavy_tail_t3': 'Student t with 3 df divided by sqrt(3), heavy-tailed with finite variance',
            'heteroscedastic_family': 'Gaussian family SD factors 0.5, 1, 1.5 normalized to target average variance',
        },
        'n_objects': 24, 'n_families': 3, 'objects_per_family': 8,
        'trials_per_scenario_setting': trials, 'bootstrap_replicates_per_trial': bootstrap_count,
        'simulation_seed': seed, 'confidence_level': 0.95,
        'true_mean_grid': list(MEAN_LEVELS), 'object_sd_grid': list(SD_LEVELS),
        'methods': list(METHODS), 'rows': rows,
        'coverage_summary': coverage_summary,
        'interpretation': {
            'nominal_coverage': 0.95,
            'monte_carlo_uncertainty': 'each estimated coverage has binomial MCSE; use 2*MCSE as rough error margin, not formal method approval',
            'practical_threshold': '2 percentage points is illustrative only, not approved as a confirmatory success gate',
            'method_selection': 'NO_METHOD_APPROVED: comparison only; require independent scientific review, and freeze the primary procedure before observing outcomes',
            'population_limit': 'object independence, hypothetical family distributions and fixed-family estimand are assumptions; shared generators and unmodeled effects may invalidate external generalization',
            'significance_limit': 'coverage at 0.95 and lower-bound detection depend on selected scenarios, sample size, and hypothetical distribution; no guarantee for real 08AJ outcomes',
        },
        'frozen': False, 'confirmatory_execution_allowed': False,
        'no_confirmatory_outcomes': True, 'scientific_signoff': False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--trials', type=int, default=250)
    p.add_argument('--bootstraps', type=int, default=1000)
    p.add_argument('--seed', type=int, default=SEED)
    a = p.parse_args(argv)
    if a.output_dir.exists():
        raise FileExistsError('will not overwrite existing evidence')
    document = report(trials=a.trials, bootstrap_count=a.bootstraps, seed=a.seed)
    a.output_dir.mkdir(parents=True, exist_ok=False)
    raw = canonical(document)
    (a.output_dir / 'statistical_calibration_evidence.json').write_bytes(raw)
    status = {
        'verdict': document['verdict'],
        'scenarios': len(SCENARIOS), 'methods': len(METHODS),
        'settings': len(document['rows']),
        'calibration_sha256': sha(raw),
        'method_approved': False, 'frozen': False,
        'confirmatory_execution_allowed': False, 'no_confirmatory_outcomes': True,
    }
    (a.output_dir / 'run_status.json').write_bytes(canonical(status))
    print(json.dumps(status, indent=2))


if __name__ == '__main__':
    main()
