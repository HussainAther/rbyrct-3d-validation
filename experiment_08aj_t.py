"""08AJ-T freeze-readiness preflight. No freeze or confirmatory execution path.

Snapshots the current candidate files and 08AJ-S decisions for scientific review.
It does not authorize production, certify source independence, or execute MART.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import platform
import sys
from pathlib import Path

SCHEMA = 'RBYRCT-08AJ-T-freeze-readiness-candidate-v1'
REVIEW_FILE = 'RBYRCT_08AJ_S_Decision_Register.json'
SOURCES = (
    '08AJ_PROTOCOL_DESIGN.md',
    'experiment_04b.py', 'experiment_04g.py', 'experiment_04h.py', 'experiment_04qa.py',
    'experiment_05b_08b.py', 'experiment_05b_mart.py', 'experiment_08j.py', 'experiment_08k.py',
    'experiment_08aj_b.py', 'experiment_08aj_c_view.py', 'experiment_08aj_d.py',
    'experiment_08aj_d_analysis.py', 'experiment_08aj_e.py', 'experiment_08aj_f.py',
    'experiment_08aj_g.py', 'experiment_08aj_h.py', 'experiment_08aj_i.py',
    'experiment_08aj_j.py', 'experiment_08aj_j_audit.py', 'experiment_08aj_k.py',
    'experiment_08aj_k_audit.py', 'experiment_08aj_l.py', 'experiment_08aj_l_audit.py',
    'experiment_08aj_m.py', 'experiment_08aj_m_audit.py',
    'experiment_08aj_n.py', 'experiment_08aj_n_audit.py',
    'experiment_08aj_o.py', 'experiment_08aj_o_audit.py',
    'experiment_08aj_q.py', 'experiment_08aj_q_audit.py',
    'experiment_08aj_r.py', 'experiment_08aj_r_audit.py',
    'experiment_08aj_t.py', 'experiment_08aj_t_audit.py',
)
GATES = (
    ('T-01','Morphology and historical-generator comparison','BLOCKED',
     'Compare shared shapes, defects, textures and parameters with earlier cohorts; retain limitations and prespecified structural summaries.'),
    ('T-02','Inference and precision approval','BLOCKED',
     'Approve object-level estimand, conditional bootstrap assumptions, precision simulation, multiplicity and practical relevance language.'),
    ('T-03','Resource and failure-policy approval','BLOCKED',
     'Set wall-clock and memory ceilings, deterministic retry rules and complete-case failure handling.'),
    ('T-04','Prospective numerical executor and independent outcome audit','BLOCKED',
     'Implement and validate the 480-job production runner, saved-truth/RMSE audit and crash-safe resume on noncohort cases.'),
    ('T-05','Source freeze and accountable scientific signoff','BLOCKED',
     'Record version-control commit/tag, dependency/Windows versions, named scientific and engineering approvals and explicit separate authorization.'),
)

def canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('utf-8')

def sha(data):return hashlib.sha256(data).hexdigest()

def safe_read(p):
    if not p.is_file() or p.is_symlink():
        raise FileNotFoundError('missing/unsafe required file: '+str(p))
    return p.read_bytes()

def source_snapshot(root):
    return {name: sha(safe_read(root/name)) for name in SOURCES}

def review_check(data):
    if data.get('stage')!='08AJ-S' or data.get('verdict')!='REVIEW_DRAFT_PENDING_SIGNOFF':
        raise ValueError('unexpected 08AJ-S review version/status')
    if data.get('frozen') is not False or data.get('confirmatory_execution_allowed') is not False:
        raise ValueError('08AJ-S review gate invalid')
    if set(data.get('decision_ids',[]))!={f'S-{i:02d}' for i in range(1,10)}:
        raise ValueError('08AJ-S decisions incomplete')
    return data

def exclusive(path,data):
    with path.open('xb') as f:
        f.write(data)
        f.flush();os.fsync(f.fileno())

def expected_record(code_root, review_bytes):
    review=review_check(json.loads(review_bytes))
    return {
        'schema':SCHEMA,
        'stage':'08AJ-T',
        'status':'FREEZE_BLOCKED',
        'frozen':False,
        'confirmatory_execution_allowed':False,
        'production_480_job_certified':False,
        'no_confirmatory_outcomes':True,
        'source_hashes':source_snapshot(code_root),
        'review_filename':REVIEW_FILE,
        'review_sha256':sha(review_bytes),
        'review_decision_ids':review['decision_ids'],
        'planned_jobs':480,
        'primary':{'n':32,'rays':2048,'mart_epochs':16,
                   'policies':['information_diag','uniform_multiscale'],
                   'paired_forward_models':['same','independent'],
                   'inference_unit':'object, 24 total, 8 per synthetic family'},
        'locks':[{'id':i,'title':title,'status':status,'required_evidence':ev} for i,title,status,ev in GATES],
        'scientific_approvals':[],
        'source_commit':None,
        'freeze_authorized':False,
        'notes':[
          'This is a candidate snapshot, not a signed source lock.',
          'The 08AJ-R ten-job 32-cubed audit is user-reported; this script cannot authenticate remote Windows evidence.',
          'The 24-object prospective cohort is not executed or sampled by this utility.',
          'A positive statistical CI is not proof of clinical or practical improvement.'
        ]
    }

def prepare(root,code_root,review_path):
    if root.exists():raise FileExistsError('refusing to overwrite existing review evidence')
    review_bytes=safe_read(review_path)
    record=expected_record(code_root,review_bytes)
    root.mkdir(parents=True)
    try:
        exclusive(root/'review_source.json',review_bytes)
        exclusive(root/'freeze_candidate.json',canonical(record))
        status={'verdict':'T_FREEZE_READINESS_REVIEW_REQUIRED','freeze_ready':False,
                'frozen':False,'confirmatory_execution_allowed':False,
                'blocking_gates':len(GATES),'candidate_sha256':sha(canonical(record)),
                'no_confirmatory_outcomes':True}
        exclusive(root/'run_status.json',canonical(status))
    except Exception:
        raise
    return status

def check(root,code_root):
    recorded_review=safe_read(root/'review_source.json')
    blob=safe_read(root/'freeze_candidate.json')
    status_blob=safe_read(root/'run_status.json')
    record=json.loads(blob);status=json.loads(status_blob)
    if blob!=canonical(record) or record!=expected_record(code_root,recorded_review):
        raise ValueError('T_SOURCE_OR_CANDIDATE_MISMATCH')
    expected={'verdict':'T_FREEZE_READINESS_REVIEW_REQUIRED','freeze_ready':False,
              'frozen':False,'confirmatory_execution_allowed':False,
              'blocking_gates':len(GATES),'candidate_sha256':sha(blob),
              'no_confirmatory_outcomes':True}
    if status_blob!=canonical(status) or status!=expected:
        raise ValueError('T_STATUS_MISMATCH')
    return {'verdict':'T_CANDIDATE_SOURCE_MATCH','blocking_gates':len(GATES),
            'freeze_ready':False,'confirmatory_execution_allowed':False,
            'candidate_sha256':sha(blob)}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=('prepare','check','freeze','execute','unlock'),required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--code-root',type=Path,default=Path(__file__).resolve().parent)
    p.add_argument('--review',type=Path,default=Path(__file__).resolve().parent/REVIEW_FILE)
    a=p.parse_args()
    if a.mode in ('freeze','execute','unlock'):
        p.error('FREEZE_BLOCKED: no scientific approval, independent production audit or source lock')
    out=prepare(a.output_dir,a.code_root,a.review) if a.mode=='prepare' else check(a.output_dir,a.code_root)
    print(json.dumps(out,indent=2))

if __name__=='__main__':main()
