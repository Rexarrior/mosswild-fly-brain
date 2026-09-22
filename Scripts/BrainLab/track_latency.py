"""Isolate stale sensory poses using full brains and an explicitly delayed body loop."""
import argparse
import json
import math
from pathlib import Path
import time
from runtime import NativeBrain, decode_learned, LAB, ROOT
from track_motor import clamp


def advance(pose,motor,duration,top):
    x,y,yaw,drive,turn=pose
    while duration>1e-8:
        dt=min(.05,duration);duration-=dt;alpha=1-math.exp(-dt/.08)
        drive+=(motor['drive']-drive)*alpha;turn+=(motor['turn']-turn)*alpha
        yaw+=turn*135*dt
        x+=math.cos(math.radians(yaw))*top*drive*dt
        y+=math.sin(math.radians(yaw))*top*drive*dt
    return x,y,yaw,drive,turn


def trial(brain,backend,form,delay,predict,cal,model,folder):
    pose=(0.,0.,120.,0.,0.);old=dict(drive=0.,turn=0.)
    goals=[(800.,0.),(800.,800.),(0.,800.),(0.,0.)]
    top=[155,200,240][form];trace=[];index=0;started=time.monotonic()
    for tick in range(300):
        gx,gy=goals[index]
        sensory_pose=advance(pose,old,delay,top) if predict else pose
        x,y,yaw,_,_=sensory_pose
        bearing=(math.degrees(math.atan2(gy-y,gx-x))-yaw+180)%360-180
        drive=.08 if math.hypot(gx-x,gy-y)<100 else (.28 if abs(bearing)>70 else 1.)
        raw=brain.step(id='latency',turn=clamp(bearing/65*.75,-1,1),drive=drive,ms=20,seed=1854,reset=tick==0)
        motor=decode_learned(raw,cal,model)
        # During computation the body continues under the preceding answer.
        pose=advance(pose,old,delay,top)
        pose=advance(pose,motor,.4-delay,top)
        old=motor
        trace.append(dict(seconds=(tick+1)*.4,x=pose[0],y=pose[1],yaw=pose[2],goal=index,bearing=bearing,raw=raw))
        if math.hypot(gx-pose[0],gy-pose[1])<155:
            index+=1
            if index==4:break
    name=f'{backend}-form{form}-delay{delay}-predict{int(predict)}'
    (folder/(name+'.json')).write_text(json.dumps(trace))
    return dict(name=name,backend=backend,form=form,delay=delay,predict=predict,completed_waypoints=index,
                body_seconds=(tick+1)*.4,wall_seconds=time.monotonic()-started)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--name',default='latency-benchmark')
    parser.add_argument('--report',type=Path,default=ROOT/'Docs/BrainMotor-latency.json')
    args=parser.parse_args()
    assert Path(args.name).name==args.name and args.name not in ('.','..'),'Use a simple new run name'
    folder=LAB/args.name
    assert not folder.exists() and not args.report.exists(),'Preserve results: choose fresh --name and --report paths'
    folder.mkdir()
    cal=json.loads((LAB/'calibration.json').read_text());models=json.loads((ROOT/'Config/BrainReadout.json').read_text());results=[]
    for backend in ('siliconfly','flybrain'):
        with NativeBrain(backend,'latency') as brain:
            for form in (0,1,2):
                for delay,predict in [(0.,False),(.2,False),(.2,True),(.4,False),(.4,True)]:
                    r=trial(brain,backend,form,delay,predict,cal[backend],models[backend],folder);results.append(r)
                    print(r['name'],'waypoints',r['completed_waypoints'],'body seconds',r['body_seconds'],flush=True)
    args.report.write_text(json.dumps(dict(scope='30 full-brain isolated-body trials. Sensor-to-actuator delay is imposed in body time; rendering/collision/social dynamics are excluded. Prediction extrapolates only the preceding neural motor command.',neural_ms=20,body_step=.4,motor_smoothing=.08,turn_gain=.75,seed=1854,results=results),indent=2)+'\n')


if __name__=='__main__':main()
