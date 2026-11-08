"""08AJ-F reconciled phantom design manifest and lock-readiness audit.

NO reconstruction outcomes. Does not modify 08AJ-D/E or freeze the protocol.
The proposed authoritative truth is generated at 2*n then block-averaged to n.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np
from experiment_08aj_d import (FAMILIES, SEEDS, SIZE, ACQUISITION_SEEDS, MODELS,
                                POLICIES, CHECKPOINTS, phantom, digest_array)
from experiment_08aj_e import full_resolution_pair

SCHEMA = 'RBYRCT-08AJ-F-reconciliation-draft-v1'
SOURCE_NAMES = ('experiment_08aj_d', 'experiment_08aj_e', 'experiment_08aj_b',
                'experiment_08aj_c_view', 'experiment_08aj_d_analysis',
                'experiment_08aj_f', 'experiment_04qa', 'experiment_04b',
                'experiment_04g', 'experiment_04h', 'experiment_05b_08b',
                'experiment_05b_mart', 'experiment_08j', 'experiment_08k')


def hashes_of_sources():
    hashes = {}
    for name in SOURCE_NAMES:
        spec = importlib.util.find_spec(name)
        if spec is None or spec.origin is None:
            raise FileNotFoundError('missing source module ' + name)
        path = Path(spec.origin)
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(sorted(hashes.items()))


def reconciled_object(family, seed, size=SIZE, *, factor=2):
    if family not in FAMILIES or seed not in SEEDS[family]:
        raise ValueError('object not in prespecified 08AJ-D family/seed roster')
    if size != SIZE or factor != 2:
        raise ValueError('only proposed 32^3/64^3 fine-to-coarse design supported')
    coarse, fine = full_resolution_pair(family, seed, size, factor=factor)
    expected = fine.reshape(size,factor,size,factor,size,factor).mean(axis=(1,3,5)).ravel()
    if not np.array_equal(coarse, expected):
        raise AssertionError('coarse truth is not exact block average')
    direct = phantom(family, seed, size)
    if coarse.shape != (size**3,) or fine.shape != (size*factor,)*3:
        raise AssertionError('unexpected object dimensions')
    if not np.isfinite(coarse).all() or np.min(coarse) <= 0 or not np.isfinite(fine).all():
        raise AssertionError('invalid phantom values')
    return {
        'family': family,
        'object_seed': int(seed),
        'fine_shape': list(fine.shape),
        'coarse_shape': [size,size,size],
        'fine_truth_sha256': digest_array(fine),
        'coarse_truth_sha256': digest_array(coarse.reshape(size,size,size)),
        'old_direct_32_truth_sha256': digest_array(direct),
        'changed_from_08aj_d_direct_truth': bool(not np.array_equal(coarse.reshape(size,size,size),direct)),
        'coarse_min': float(np.min(coarse)),
        'coarse_max': float(np.max(coarse)),
    }


def design():
    records = [reconciled_object(f,s) for f in FAMILIES for s in SEEDS[f]]
    if len(records) != 24 or len({x['object_seed'] for x in records}) != 24:
        raise AssertionError('incorrect object roster')
    if len({x['fine_truth_sha256'] for x in records}) != 24 or len({x['coarse_truth_sha256'] for x in records}) != 24:
        raise AssertionError('duplicate new synthetic object')
    # This verifies internal uniqueness only, not independence from all older studies.
    locks = [
        {'id':'F1_phantom_definition','status':'RECONCILED_DRAFT',
         'evidence':'Fine 64^3 generator and exact 2x block-averaged 32^3 truth; all 24 fine/coarse hashes recorded'},
        {'id':'F2_prior_study_overlap','status':'OPEN',
         'evidence':'Internal uniqueness verified; historical generator/seed/structural overlap not exhaustively audited'},
        {'id':'F3_warm_prefix_fairness','status':'OPEN',
         'evidence':'08AJ-E shared prefix observed for information/coverage; policy-specific warm starts and complete-view compatibility need written decision and tests'},
        {'id':'F4_noise_pairing','status':'OPEN',
         'evidence':'Noise seed derivation and shared realization across policies/conditions not prospectively specified'},
        {'id':'F5_inference_and_failure_rules','status':'OPEN',
         'evidence':'08AJ-D proposes family-stratified bootstrap; precision rationale, resource ceilings and failure policy remain to be reviewed'},
        {'id':'F6_independent_forward_model','status':'PARTIAL',
         'evidence':'08AJ-E projector passed 8^3 engineering fixture; 32^3 full-family adapter and 64^3 projection cost not independently vetted'},
        {'id':'F7_complete_view_budget','status':'PARTIAL',
         'evidence':'32^3 budgets permit whole views; 64^3 2048-ray complete-view policy infeasible and must be excluded or budget changed'},
        {'id':'F8_runner_audit_and_freeze','status':'OPEN',
         'evidence':'Full resumable 24-object driver, independent audit, commit and signed source lock still pending'},
    ]
    return {
        'schema': SCHEMA, 'status':'DRAFT_NOT_FROZEN', 'frozen':False,
        'no_reconstruction_or_outcome_data':True,
        'original_draft_preserved':True,
        'original_schema':'RBYRCT-08AJ-D-draft-v1',
        'authoritative_proposed_phantom_path':'experiment_08aj_d.phantom(family,seed,2*n) -> exact block average -> coarse truth',
        'reconstruction_size':SIZE, 'fine_size':2*SIZE, 'factor':2,
        'object_count':len(records), 'objects':records,
        'acquisition_seeds':list(ACQUISITION_SEEDS), 'models':list(MODELS),
        'policies':list(POLICIES), 'checkpoints':list(CHECKPOINTS),
        'primary_policy':'information_diag', 'primary_reference':'uniform_multiscale',
        'primary_checkpoint':2048,
        'primary_unit':'independent synthetic object (24); seed and forward-model settings paired within object',
        'lock_readiness':'NOT_READY', 'lock_items':locks,
        'open_or_partial_count':sum(x['status']!='RECONCILED_DRAFT' for x in locks),
        'source_sha256':hashes_of_sources(),
        'limitations':['The label independent forward model refers to forward-projection arithmetic, not independent phantom subjects.',
                       'No exhaustive historical object-family overlap check was performed.',
                       'Changing truth definition invalidates the old 08AJ-D truth hashes; old draft remains historical.',
                       'No comparative accuracy, RMSE, or policy success was computed.']
    }


def write_json(path, payload):
    path.write_text(json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+'\n',encoding='utf8')


def run(output_dir):
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError('output path exists; refusing to overwrite earlier draft')
    result = design()
    output_dir.mkdir(parents=True)
    write_json(output_dir/'08aj_f_reconciled_design_draft.json',result)
    status={'complete':True,'verdict':'RECONCILIATION_PASS','frozen':False,
            'no_outcome_data':True, 'object_count':24,
            'lock_readiness':'NOT_READY','open_or_partial_count':result['open_or_partial_count']}
    write_json(output_dir/'run_status.json',status)
    files = ('08aj_f_reconciled_design_draft.json','run_status.json')
    (output_dir/'manifest.sha256').write_text(''.join(hashlib.sha256((output_dir/f).read_bytes()).hexdigest()+'  '+f+'\n' for f in files),encoding='ascii')
    print(json.dumps({'verdict':status['verdict'],'objects':24,
                      'changed_truth_objects':sum(x['changed_from_08aj_d_direct_truth'] for x in result['objects']),
                      'open_or_partial_lock_items':result['open_or_partial_count'],
                      'frozen':False,'no_outcome_data':True},indent=2))
    return status


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--freeze',action='store_true',help='not permitted until blockers resolved')
    a=ap.parse_args()
    if a.freeze:
        raise RuntimeError('REFUSE_TO_FREEZE: outstanding scientific and execution blockers')
    run(a.output_dir)

if __name__=='__main__':
    main()
