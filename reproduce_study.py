"""Reproduce full studies without overwriting archived results.
Usage: python reproduce_study.py study1 NEW_OUTPUT_DIRECTORY
       python reproduce_study.py study2 NEW_OUTPUT_DIRECTORY
"""
import json
from pathlib import Path
import subprocess
import sys
root=Path(__file__).resolve().parent
if len(sys.argv)!=3 or sys.argv[1] not in ('study1','study2'):
    raise SystemExit(__doc__)
name,driver={'study1':('experiment04p_full','experiment_04p.py'),
             'study2':('experiment04qb_full','experiment_04qb.py')}[sys.argv[1]]
output=Path(sys.argv[2]).resolve()
if output.exists(): raise SystemExit('Choose a new output directory to preserve existing records.')
params=json.loads((root/'results'/name/'protocol.json').read_text())['parameters']
params['output_dir']=str(output)
command=[sys.executable,str(root/driver)]
for key,value in params.items():
    command.append('--'+key.replace('_','-'))
    command.extend(map(str,value if isinstance(value,list) else [value]))
subprocess.run(command,cwd=root,check=True)
