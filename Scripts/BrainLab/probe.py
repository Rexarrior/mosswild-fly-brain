"""Stimulus/readout calibration and recurrent-synapse ablation, both full models."""
import json
import statistics
from runtime import NativeBrain, LAB

def main():
    report = {}
    calibration = {}
    for backend in ['siliconfly', 'flybrain']:
        report[backend] = {}
        with NativeBrain(backend, 'probe') as brain:
            for name, turn, drive, threat, ablate in [
                ('rest', 0, 0, 0, False), ('walk', 0, 1, 0, False),
                ('left', 1, 1, 0, False), ('right', -1, 1, 0, False),
                ('loom', 0, 0, 1, False), ('ablated_left', 1, 1, 0, True),
                ('ablated_right', -1, 1, 0, True), ('ablated_walk', 0, 1, 0, True)]:
                trials = []
                for seed in [11, 29, 47]:
                    samples = [brain.step(id='probe', turn=turn, drive=drive, threat=threat, ms=100, seed=seed, ablate=ablate, reset=(i == 0)) for i in range(8)]
                    trials.append({key: statistics.mean(s[key] for s in samples[3:]) for key in ['left', 'right', 'forward', 'escape', 'wall_ms']})
                mean = {key: statistics.mean(t[key] for t in trials) for key in trials[0]}
                report[backend][name] = {'mean': mean, 'trials': trials}
                print(backend, name, json.dumps(mean), flush=True)
        r = report[backend]
        l = r['left']['mean']['left'] - r['left']['mean']['right']
        rr = r['right']['mean']['left'] - r['right']['mean']['right']
        floor = r['ablated_walk']['mean']['forward'] + 2
        calibration[backend] = {'turn_center': (l + rr) / 2, 'turn_scale': (l - rr) / 2,
                                'drive_floor': floor, 'drive_scale': max(5, r['walk']['mean']['forward'] - floor)}
        report[backend]['checks'] = {'direction_separation_hz': l - rr,
                                      'synaptic_walk_gain_hz': r['walk']['mean']['forward'] - r['ablated_walk']['mean']['forward'],
                                      'loom_escape': r['loom']['mean']['escape']}
    (LAB / 'probe-results.json').write_text(json.dumps(report, indent=2))
    (LAB / 'calibration.json').write_text(json.dumps(calibration, indent=2))
    print('Calibration', json.dumps(calibration), flush=True)
    for backend, r in report.items():
        assert r['checks']['direction_separation_hz'] > 10, (backend, 'steering failed')
        assert r['checks']['synaptic_walk_gain_hz'] > 10, (backend, 'walking does not depend on synapses')

if __name__ == '__main__': main()
