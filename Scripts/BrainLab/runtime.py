"""Persistent native brain processes and the explicit, calibrated motor decoder."""
from pathlib import Path
import json
import math
import selectors
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / 'Saved/BrainLab'

class NativeBrain:
    def __init__(self, backend, log_name='runtime'):
        self.backend = backend
        self.log = (LAB / f'{log_name}-{backend}.log').open('a')
        command = ([str(LAB / 'silicon-adapter'), str(LAB / 'groups.json')] if backend == 'siliconfly' else
                   [str(LAB / 'native/target/release/brainlab-flybrain'), str(LAB / 'pack783'), str(LAB / 'groups.json')])
        self.process = subprocess.Popen(command, cwd=LAB / 'upstream/siliconfly', stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log, text=True, bufsize=1)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)

    def step(self, id='probe', turn=0., drive=0., threat=0., ms=100, seed=1, ablate=False, reset=False, release=False, channels=None):
        request = dict(id=str(id), turn=float(turn), drive=float(drive), threat=float(threat), ms=int(ms), seed=int(seed), ablate=bool(ablate), reset=bool(reset), release=bool(release))
        if channels is not None:
            if len(channels) != 8 or any(not math.isfinite(v) or not 0 <= v <= 1 for v in channels):
                raise ValueError('Expected eight finite sensory channels in [0,1]')
            request['channels'] = list(channels)
        self.process.stdin.write(json.dumps(request) + '\n')
        self.process.stdin.flush()
        if not self.selector.select(25):
            self.close()
            raise TimeoutError(f'{self.backend} exceeded 25 seconds')
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError(f'{self.backend} exited: {self.process.poll()}')
        response = json.loads(line)
        if 'error' in response:
            raise RuntimeError(response['error'])
        return response

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.selector.close()
        self.log.close()

    def __enter__(self): return self
    def __exit__(self, *_): self.close()

def decode(raw, calibration):
    """Only measured neural outputs enter this decoder, never the requested bearing."""
    difference = raw['left'] - raw['right']
    turn = max(-1., min(1., (difference - calibration['turn_center']) / calibration['turn_scale']))
    drive = max(0., min(1., (raw['forward'] - calibration['drive_floor']) / calibration['drive_scale']))
    return {'turn': turn, 'drive': drive, 'escape': raw['escape'], 'left_hz': raw['left'], 'right_hz': raw['right'], 'forward_hz': raw['forward'], 'wall_ms': raw['wall_ms'], 'neural_ms': raw['neural_ms']}

def neural_features(raw):
    l,r,f=raw['left']/400,raw['right']/400,raw['forward']/250
    return [1.,l,r,f,l*l,r*r,f*f,l*r,l*f,r*f]

def decode_learned(raw, calibration, model):
    result=decode(raw,calibration)
    if not model or not model.get('enabled'): return result
    x=neural_features(raw)
    turn=sum(a*b for a,b in zip(x,model['turn']))
    drive=sum(a*b for a,b in zip(x,model['drive']))
    result['turn']=max(-1.,min(1.,turn)) if raw['left']+raw['right']>4 else 0.
    result['drive']=max(0.,min(1.,drive)) if raw['forward']>4 else 0.
    return result
