#!/usr/bin/env python3
"""Run only after every frozen arm is complete; preserve all outcomes."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import hashlib,json,subprocess,sys
from pathlib import Path
p=Path(__file__).resolve().parent
freeze=json.loads((p/'statistics-code-freeze.json').read_text())
for name,want in freeze['files'].items():assert hashlib.sha256((p/name).read_bytes()).hexdigest()==want
for a in ['A_original','B_generated','C_roundtrip','D_matched_random','E_extractive']:assert (p/f'complete-{a}.json').exists()
for script in ['analyze.py','qa-independent.py','diagnose-candidates.py']:
 print('RUN',script,flush=True)
 subprocess.run([sys.executable,str(p/script)],check=True)
