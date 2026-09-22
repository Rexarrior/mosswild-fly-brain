"""Controlled closed-loop steering on full native brains, outside social ecology.

The body uses the same 0.4s response credit, eight 0.05s steps and 135 deg/s
turn scale as Unreal. No collision or social guide is present; this isolates
motor decoding/smoothing, not the complete biome.
"""
import json
import math
from pathlib import Path
import time
from runtime import LAB, ROOT, NativeBrain, decode, decode_learned


def clamp(x,a,b):return max(a,min(b,x))


def trial(brain,backend,form,kind,tau,gain,cal,model,seed=1854):
    x=y=0.;yaw=120.;drive=turn=0.;elapsed=travel=0.;index=0
    goals=[(800.,0.),(800.,800.),(0.,800.),(0.,0.)]
    top=[155,200,240][form];trace=[];started=time.monotonic();arrival=[]
    for tick in range(300):
        gx,gy=goals[index];distance=math.hypot(gx-x,gy-y)
        bearing=(math.degrees(math.atan2(gy-y,gx-x))-yaw+180)%360-180
        sensory_drive=.08 if distance<100 else (.28 if abs(bearing)>70 else 1.)
        raw=brain.step(id='tracking',turn=clamp(bearing/65*gain,-1,1),drive=sensory_drive,ms=20,seed=seed,reset=tick==0)
        motor=decode_learned(raw,cal,model) if kind=='trained' else decode(raw,cal)
        for _ in range(8):
            alpha=1-math.exp(-.05/tau) if tau else 1.
            drive+=(motor['drive']-drive)*alpha;turn+=(motor['turn']-turn)*alpha
            yaw+=turn*135*.05
            step=top*drive*.05;x+=math.cos(math.radians(yaw))*step;y+=math.sin(math.radians(yaw))*step
            elapsed+=.05;travel+=step
        trace.append(dict(seconds=elapsed,x=x,y=y,yaw=yaw,goal=index,bearing=bearing,sensory_drive=sensory_drive,drive=drive,turn=turn,raw=raw))
        if math.hypot(gx-x,gy-y)<155:
            arrival.append(elapsed);index+=1
            if index==len(goals):break
    folder=LAB/'tracking-benchmark';folder.mkdir(exist_ok=True)
    name=f'{backend}-form{form}-{kind}-tau{tau}-gain{gain}'
    (folder/(name+'.json')).write_text(json.dumps(trace))
    return dict(name=name,backend=backend,form=form,decoder=kind,smoothing=tau,turn_gain=gain,seed=seed,completed_waypoints=index,world_seconds=elapsed,wall_seconds=time.monotonic()-started,path_cm=travel,arrival_seconds=arrival,final_position=[x,y],final_distance=math.hypot(goals[min(index,3)][0]-x,goals[min(index,3)][1]-y))


def main():
    cal=json.loads((LAB/'calibration.json').read_text());models=json.loads((ROOT/'Config/BrainReadout.json').read_text());results=[]
    for backend in ('siliconfly','flybrain'):
        model=dict(models[backend],enabled=True)
        with NativeBrain(backend,'tracking') as brain:
            for form in (0,1,2):
                for kind,tau,gain in [('calibrated',0,1),('calibrated',.35,1),('trained',.35,1),('trained',.08,1),('trained',.08,.75)]:
                    r=trial(brain,backend,form,kind,tau,gain,cal[backend],model);results.append(r)
                    (LAB/'tracking-benchmark/results.json').write_text(json.dumps(results,indent=2))
                    print(r['name'],'waypoints',r['completed_waypoints'],'time',round(r['world_seconds'],1),'distance',round(r['path_cm']),flush=True)
    (ROOT/'Docs/BrainMotor-tracking.json').write_text(json.dumps(dict(neural_ms=20,body_step=.4,integration_substep=.05,scope='Full native brains with isolated 2D body; no ecology, collisions or social signals.',results=results),indent=2)+'\n')

if __name__=='__main__':main()
