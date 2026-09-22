"""Competition probes through full native graphs; never fit the decoder to these cases."""
import argparse
import json
import statistics
import time
from runtime import NativeBrain, LAB, ROOT, decode_learned

def main():
    p = argparse.ArgumentParser(); p.add_argument('--name', default='probes-v2'); args=p.parse_args()
    assert args.name and all(c.isalnum() or c in '-_' for c in args.name)
    folder = LAB / 'sensory' / args.name
    folder.mkdir(parents=True, exist_ok=False)
    calibration = json.loads((LAB / 'calibration.json').read_text())
    models = json.loads((ROOT / 'Config/BrainReadout.json').read_text())
    cases = {}
    for i, modality in enumerate(('food', 'water', 'home')):
        for side in range(2):
            c = [0.] * 8
            c[2*i+side] = .7
            c[6] = .7
            cases[f'{modality}_{side}'] = c
    cases.update(hungry=[.9,0,0,.15,0,0,.7,0], thirsty=[.15,0,0,.9,0,0,.7,0],
                 balanced=[.6,0,0,.6,0,0,.7,0], neutral=[0.]*8,
                 ablated=[.9,0,0,.15,0,0,.7,0])
    summaries = []
    with (folder / 'trace.jsonl').open('w') as log:
        for backend in ('siliconfly', 'flybrain'):
            with NativeBrain(backend, 'sensory-probe') as brain:
                for name, channels in cases.items():
                    for seed in (1701, 2701, 3701):
                        motors = []
                        for step in range(32):
                            raw = brain.step(id='sensory', channels=channels, ms=20, seed=seed,
                                             reset=step==0, ablate=name=='ablated')
                            motor = decode_learned(raw, calibration[backend], models[backend])
                            log.write(json.dumps(dict(backend=backend, case=name, seed=seed, step=step,
                                                      channels=channels, raw=raw, motor=motor))+'\n')
                            if step >= 12: motors.append(motor)
                        row = dict(backend=backend, case=name, seed=seed,
                                   **{key:statistics.mean(m[key] for m in motors) for key in ('turn','drive','left_hz','right_hz','forward_hz')})
                        summaries.append(row)
                    print(backend, name, json.dumps(summaries[-1]), flush=True)
    (folder / 'summary.json').write_text(json.dumps(summaries, indent=2)+'\n')

if __name__ == '__main__': main()
