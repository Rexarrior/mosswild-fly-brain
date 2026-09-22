"""Closed-loop motor/energy experiment before UE: foraging, brood cost, drought, ablation."""
import json
import math
import random
import statistics
import time
from runtime import NativeBrain, decode, LAB

def run(brain, calibration, seed, condition):
    rng = random.Random(seed)
    x, y, heading, energy, health = 0., 0., rng.uniform(-math.pi, math.pi), 55., 60.
    patches = [[-330., -180., 65.], [360., 180., 65.], [-180., 380., 65.], [150., -380., 65.]]
    meals, eggs, distance, cooldown = 0, 0, 0., 0.
    wall = []; trace = []; eating = False; dt = .3
    for tick in range(500 if condition == 'drought' else 360):
        t = tick * dt
        if condition == 'drought':
            tx, ty = 500 * math.cos(t * .13), 500 * math.sin(t * .13)
            target = None
        else:
            candidates = [p for p in patches if p[2] > 2]
            target = min(candidates, key=lambda p: math.hypot(p[0]-x, p[1]-y)) if candidates else None
            tx, ty = target[:2] if target else (0, 0)
        bearing = (math.atan2(ty-y, tx-x) - heading + math.pi) % (2*math.pi) - math.pi
        demand = .08 if math.hypot(tx-x, ty-y) < 90 else (.35 if abs(bearing) > math.radians(70) else 1.)
        raw = brain.step(id='ecology', turn=max(-1., min(1., bearing/math.radians(65))), drive=demand, ms=40, seed=seed, reset=(tick==0), ablate=condition=='ablation')
        motor = decode(raw, calibration)
        wall.append(raw['wall_ms'])
        heading += motor['turn'] * math.radians(135) * dt
        step = 200 * motor['drive'] * dt
        x += math.cos(heading) * step; y += math.sin(heading) * step; distance += step
        energy = max(0., energy - dt*(.48+.28*motor['drive']))
        if energy <= 0: health -= dt*5
        now_eating = target is not None and math.hypot(target[0]-x, target[1]-y)<125 and raw['forward']>4
        if now_eating:
            amount = min(target[2],dt*22,120-energy); target[2]-=amount; energy+=amount
            if not eating: meals+=1
        eating = now_eating
        cooldown -= dt
        if energy >= 105 and t > 15 and cooldown <= 0:
            energy -= 48; eggs += 1; cooldown=35
        for patch in patches: patch[2]=min(75,patch[2]+dt*1.4)
        if tick%10==0: trace.append(dict(t=t,x=x,y=y,energy=energy,drive=motor['drive'],turn=motor['turn']))
        if health<=0: break
    return dict(seed=seed,condition=condition,meals=meals,eggs=eggs,distance=distance,alive=health>0,energy=energy,duration=t,wall_ms_mean=statistics.mean(wall),wall_ms_p95=sorted(wall)[int(len(wall)*.95)],trace=trace)

def assess(report):
    checks=[]
    for backend, trials in report.items():
        for t in trials:
            # Intrinsic SiliconFly noise survives synaptic ablation. Record its
            # small drift rather than equating synaptic ablation with neuron death.
            ok = (t['meals']>0 and t['eggs']>0 and t['alive']) if t['condition']=='normal' else (t['distance']<50 and t['meals']==0 and t['eggs']==0 if t['condition']=='ablation' else not t['alive'])
            checks.append(dict(backend=backend,condition=t['condition'],seed=t['seed'],passed=ok))
    (LAB/'experiment-checks.json').write_text(json.dumps(checks,indent=2))
    assert all(c['passed'] for c in checks), checks
    print('PASS:',len(checks),'closed-loop trials')

def main():
    calibration=json.loads((LAB/'calibration.json').read_text())
    report={}
    for backend in ['siliconfly','flybrain']:
        report[backend]=[]
        with NativeBrain(backend,'experiment') as brain:
            for condition in ['normal','ablation','drought']:
                for seed in [11,29,47]:
                    result=run(brain,calibration[backend],seed,condition)
                    report[backend].append(result)
                    print(backend,json.dumps({k:v for k,v in result.items() if k!='trace'}),flush=True)
                    (LAB/'experiment-results.json').write_text(json.dumps(report,indent=2))
    assess(report)

if __name__=='__main__': main()
