import hashlib
import numpy as np
import pytest
from figure_02_08m_reconstructions import array_sha, choose_object, select_replay_rows

def test_hash_contiguous():
    a=np.arange(27,dtype=float).reshape(3,3,3)
    assert array_sha(a)==hashlib.sha256(a.tobytes()).hexdigest()

def test_choose_lower_middle_object():
    data=[{'object_id':f'defect_validation_{100+i}', 'acquired':'2048', 'policy':'information_diag', 'n_conditions':'4', 'mean_global_gain':str(.01*i)} for i in range(8)]
    selected,_=choose_object(data)
    assert selected['object_id']=='defect_validation_103'

def test_bad_condition_count():
    data=[{'object_id':f'defect_validation_{100+i}', 'acquired':'2048', 'policy':'information_diag', 'n_conditions':'3' if i==1 else '4', 'mean_global_gain':str(.01*i)} for i in range(8)]
    with pytest.raises(ValueError): choose_object(data)

def test_replay_unique():
    data=[{'object_id':'o','model':'same','acquisition_seed':'1','policy':p,'acquired':'2048'} for p in ('coverage','information_diag')]
    assert len(select_replay_rows(data,'o','same',1))==2
    with pytest.raises(ValueError): select_replay_rows(data+data[:1],'o','same',1)
