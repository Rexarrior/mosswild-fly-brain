"""Loopback bridge. Two backend workers; one independent model state per live NPC."""
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import signal
import threading
import time
from runtime import NativeBrain, decode, decode_learned, LAB, ROOT
from reactive_control import motor as reactive_motor

class Runtime:
    def __init__(self):
        self.lock = threading.Lock()
        self.workers = {}
        self.active = {}
        self.session = None
        self.last_window = None
        self.pool = ThreadPoolExecutor(max_workers=2)
        self.calibration = json.loads((LAB / 'calibration.json').read_text())
        model_path=ROOT/'Config/BrainReadout.json'
        self.readouts=json.loads(model_path.read_text()) if model_path.exists() else {}
        self.log = (LAB / 'batches.jsonl').open('a', buffering=1)

    def reset(self, session, controller):
        for worker in self.workers.values(): worker.close()
        self.workers = ({name: NativeBrain(name) for name in ['siliconfly', 'flybrain']}
                        if controller == 'connectome' else {})
        self.active = {name: set() for name in self.workers}
        self.session = session
        self.controller = controller

    def batch(self, body):
        controller = body.get('motor_controller', 'connectome')
        if controller not in ('connectome', 'reactive-v1'): raise ValueError('Unknown motor controller')
        agents = body['agents']
        if not isinstance(agents, list) or not 1 <= len(agents) <= 12: raise ValueError('Expected 1..12 agents')
        if len({a['id'] for a in agents}) != len(agents): raise ValueError('Duplicate ids')
        for a in agents:
            if a['backend'] not in self.calibration: raise ValueError('Unknown backend')
            if not isinstance(a['id'], int) or not 0 < a['id'] < 1000000: raise ValueError('Invalid id')
            for key in ['turn', 'drive', 'threat']:
                if not isinstance(a[key], (float, int)) or not math.isfinite(a[key]) or abs(a[key]) > 1: raise ValueError('Invalid sensory input')
            if controller == 'reactive-v1' and 'channels' not in a:
                raise ValueError('Reactive control requires sensory channels')
            if 'channels' in a:
                c = a['channels']
                if not isinstance(c, list) or len(c) != 8 or any(not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in c):
                    raise ValueError('Expected eight sensory channels in [0,1]')
        session = body['session']
        if not isinstance(session, str) or not 1 <= len(session) <= 64: raise ValueError('Invalid session')
        with self.lock:
            start = time.perf_counter()
            if session != self.session: self.reset(session, controller)
            elif controller != self.controller: raise ValueError('Controller changed without a new session')
            ablate = bool(body.get('ablate', False))
            window=max(10,min(100,int(body.get('neural_ms',40))))
            self.last_window=window
            seed=int(body.get('seed',1701))
            if not 0<=seed<=4000000000:raise ValueError('Invalid seed')
            learned=bool(body.get('learned',False))
            if controller == 'reactive-v1':
                if ablate: raise ValueError('Synaptic ablation does not apply to the reactive control')
                rows = []
                for a in agents:
                    began = time.perf_counter()
                    motor = reactive_motor(a['channels'])
                    motor.update(id=a['id'], backend=a['backend'], wall_ms=(time.perf_counter()-began)*1000)
                    rows.append(motor)
                out = dict(agents=rows, wall_ms=(time.perf_counter()-start)*1000, neural_ms=0,
                           session=session, learned=False, motor_controller=controller)
                self.log.write(json.dumps(dict(time=time.time(), ablate=False, inputs=agents, **out)) + '\n')
                return out
            def work(name):
                group = [a for a in agents if a['backend'] == name]
                ids = {a['id'] for a in group}
                for old in self.active[name] - ids: self.workers[name].step(id=old, release=True)
                rows = []
                for a in group:
                    raw = self.workers[name].step(id=a['id'], turn=a['turn'], drive=a['drive'], threat=a['threat'], ms=window, seed=seed + a['id'] * 17, ablate=ablate, channels=a.get('channels'))
                    model=self.readouts.get(name)
                    use_readout=learned and model and model.get('enabled') and model.get('neural_ms',40)==window
                    motor = decode_learned(raw,self.calibration[name],model) if use_readout else decode(raw,self.calibration[name])
                    motor['decoder']='trained' if use_readout else 'calibrated'
                    motor.update(id=a['id'], backend=name)
                    rows.append(motor)
                self.active[name] = ids
                return rows
            futures = [self.pool.submit(work, name) for name in self.workers]
            rows, errors = [], []
            for future in futures:
                try: rows.extend(future.result())
                except Exception as error: errors.append(error)
            if errors:
                # Drain both workers before another request may reset processes.
                self.session = None
                raise errors[0]
            out = dict(agents=rows, wall_ms=(time.perf_counter()-start)*1000, neural_ms=window, session=session,learned=learned,motor_controller=controller)
            self.log.write(json.dumps(dict(time=time.time(), ablate=ablate, inputs=agents, **out)) + '\n')
            return out

runtime = Runtime()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def respond(self, code, data):
        payload = json.dumps(data, allow_nan=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        try: self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError): pass

    def do_GET(self):
        if self.path != '/health': return self.respond(404, {'error': 'not found'})
        self.respond(200, dict(service='brainlab', version=3, motor_controllers=['connectome','reactive-v1'], sensory_channels=8, root=str(ROOT), models=['siliconfly', 'flybrain'],
                              default_neural_ms=40,last_neural_ms=runtime.last_window,
                              readouts={name:{'enabled':model.get('enabled',False),'neural_ms':model.get('neural_ms',40)} for name,model in runtime.readouts.items()}))

    def do_POST(self):
        if self.path != '/step': return self.respond(404, {'error': 'not found'})
        if self.headers.get('Origin') or self.headers.get('X-BrainLab') != '1': return self.respond(403, {'error': 'local clients only'})
        try:
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size < 32768: raise ValueError('Invalid body size')
            self.connection.settimeout(35)
            body = json.loads(self.rfile.read(size))
            self.respond(200, runtime.batch(body))
        except (ValueError, KeyError, TypeError) as e:
            self.respond(400, {'error': str(e)})
        except Exception as e:
            print('BRAIN ERROR', repr(e), flush=True)
            self.respond(503, {'error': str(e)})

if __name__ == '__main__':
    server = ThreadingHTTPServer(('127.0.0.1', 18765), Handler)
    def stop(*_):
        for worker in runtime.workers.values(): worker.close()
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    print('BrainLab listening at http://127.0.0.1:18765', flush=True)
    try: server.serve_forever()
    finally: stop()
