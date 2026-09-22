"""Drive the real-editor service-cut test; always restore the local service."""
import json
from pathlib import Path
import subprocess
import sys
import time
from runtime import ROOT, LAB

def run(*args): subprocess.run([sys.executable,*args],cwd=ROOT,check=True)

def main():
    path=LAB/'recovery.json'
    path.unlink(missing_ok=True)
    run('Scripts/BrainLab/lab.py','start')
    run('Scripts/ue.py','script','Content/Python/insectarium_recovery.py')
    seen=set()
    try:
        end=time.monotonic()+190
        while time.monotonic()<end:
            if path.exists():
                try: data=json.loads(path.read_text())
                except json.JSONDecodeError: time.sleep(.2); continue
                stage=data['stage']
                if data['status'] in ['passed','failed']:
                    print(json.dumps(data,indent=2),flush=True)
                    assert data['status']=='passed',data
                    return
                if stage not in seen:
                    print(stage,flush=True); seen.add(stage)
                    if stage=='cut_service': run('Scripts/BrainLab/lab.py','stop')
                    elif stage=='start_service': run('Scripts/BrainLab/lab.py','start')
            time.sleep(.5)
        raise TimeoutError('Recovery test timed out')
    finally: run('Scripts/BrainLab/lab.py','start')

if __name__=='__main__': main()
