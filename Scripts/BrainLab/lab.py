"""Run with python3 Scripts/BrainLab/lab.py start|stop|status|setup|probe|experiment."""
from pathlib import Path
import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from runtime import ROOT, LAB

def health():
    try:
        with urllib.request.urlopen('http://127.0.0.1:18765/health', timeout=2) as r: return json.load(r)
    except OSError: return None

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['start', 'stop', 'status', 'setup', 'probe', 'experiment'])
    args = p.parse_args()
    here = Path(__file__).resolve().parent
    python = LAB / 'venv/bin/python'
    if args.action in ['setup', 'probe', 'experiment']:
        if not python.exists():
            import shutil
            uv = shutil.which('uv') or str(Path.home() / '.local/bin/uv')
            subprocess.run([str(uv), 'venv', str(LAB / 'venv')], check=True)
            subprocess.run([str(uv), 'pip', 'install', '--python', str(python), 'numpy==2.5.3', 'pyarrow==25.0.1'], check=True)
        return subprocess.run([str(python), str(here / (args.action + '.py'))], cwd=ROOT).returncode
    status = health()
    if args.action == 'status': print(json.dumps(status or {'status': 'offline'}, indent=2)); return 0
    if status and status.get('root') != str(ROOT): raise RuntimeError('Port belongs to another project')
    pidfile = LAB / 'server.pid'
    if args.action == 'stop':
        if pidfile.exists():
            pid = int(pidfile.read_text())
            command = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True).stdout
            if str(here / 'server.py') in command: os.kill(pid, signal.SIGTERM)
            pidfile.unlink()
        print('BrainLab stopped'); return 0
    if status: print('BrainLab already running'); return 0
    if not (LAB / 'calibration.json').exists(): raise RuntimeError('Run setup, then probe first')
    with (LAB / 'server.log').open('a') as log:
        child = subprocess.Popen([str(python), '-u', str(here / 'server.py')], cwd=ROOT, stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
    pidfile.write_text(str(child.pid))
    for _ in range(40):
        if health(): print('BrainLab started; open /Game/Maps/Mosswild and press Play'); return 0
        if child.poll() is not None: raise RuntimeError('Service failed; see Saved/BrainLab/server.log')
        time.sleep(.25)
    raise TimeoutError('Service did not become ready')

if __name__ == '__main__': sys.exit(main())
