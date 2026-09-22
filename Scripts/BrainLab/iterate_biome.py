"""Ten measured improvement cycles on actual Unreal actors and full Metal models."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time
import uuid
from runtime import ROOT,LAB

STAGES=[
('utility','Larger biome; resource utility, committed goals and scouting.'),
('water','Address measured blocking with neighbour separation; hydration priorities and 20ms neural windows.'),
('economy','Fix critical hunger at water and neural feeding activation; carry food to nests and pay for brood.'),
('memory','Fix measured rock contact and premature meal abandonment; bounded resource memory and seasonal flowering.'),
('recruitment','Share discoveries, deposit and follow fading recruitment trails.'),
('separation','Resource reservations and obstacle/stuck recovery after local spacing.'),
('flocking','Local cohort recruitment, alignment and cohesion before neural encoding.'),
('risk','Fix partial-load detours and poor-patch recruitment; patrol acquired territory and avoid outnumbered fights.'),
('readout','Held-out validated ridge readout plus temporal motor smoothing.'),
('joint','Tune remaining bottlenecks from the preceding measured cycles.'),
]

def command(config=None,stop=False):
    data=dict(token=uuid.uuid4().hex,command='stop' if stop else 'start',config=config)
    temp=LAB/'audit-command.tmp';temp.write_text(json.dumps(data));temp.replace(LAB/'audit-command.json')
    end=time.monotonic()+30
    while time.monotonic()<end:
        try:
            ack=json.loads((LAB/'audit-ack.json').read_text())
            if ack.get('token')==data['token']:
                assert ack['success'],ack
                return
        except (FileNotFoundError,json.JSONDecodeError):pass
        time.sleep(.25)
    raise TimeoutError('Unreal did not acknowledge audit configuration')

def analyze(folder):
    rows=[json.loads(line) for line in (folder/'trace.jsonl').read_text().splitlines() if line]
    last=json.loads((folder/'complete.json').read_text())
    movement={};active_backend_seconds={'siliconfly':0,'flybrain':0}
    social_time=group_time=late_social=late_group=0.
    grouped_seconds=late_grouped_seconds=0.
    excursion_eligible=excursion_grouped=0.
    hydration_gain={'siliconfly':0.,'flybrain':0.}
    low_energy={'siliconfly':0.,'flybrain':0.};low_water=dict(low_energy);observed_agent_seconds=0.
    reserve_error=0.
    config=json.loads((folder/'config.json').read_text())
    geometry_path=folder/'source/Config/BrainBiome.json'
    if not geometry_path.exists():geometry_path=ROOT/'Config/BrainBiome.json'
    homes=json.loads(geometry_path.read_text())['homes']
    def group_count(colony):
        grouped=0
        for a in colony:
            near=[n for n in colony if math.hypot(a['x']-n['x'],a['y']-n['y'])<850]
            order=math.hypot(sum(n['vx'] for n in near),sum(n['vy'] for n in near))/len(near)
            grouped+=len(near)>=3 and order>.65
        return grouped
    previous=None
    for row in rows:
        for b in active_backend_seconds:
            if any(a['backend']==b for a in row['agents']):active_backend_seconds[b]+=1.2
        for a in row['agents']:movement[a['id']]=max(movement.get(a['id'],0),a['distance'])
        if row['stage']>=3:
            expected=120+row['food_delivered']-config.get('brood_cost',30)*(row['births']+row['eggs'])-row.get('maintenance_spent',0)-row.get('spoiled_food',0)
            reserve_error=max(reserve_error,abs(expected-row['cyan_store']-row['amber_store']))
        if previous:
            dt=row['elapsed']-previous['elapsed'];old={a['id']:a for a in previous['agents']}
            for a in row['agents']:
                observed_agent_seconds+=dt
                if a['energy']<25:low_energy[a['backend']]+=dt
                if a['hydration']<25:low_water[a['backend']]+=dt
            moving=[]
            for a in row['agents']:
                if a['id'] not in old or dt<=0:continue
                hydration_gain[a['backend']]+=max(0.,a['hydration']-old[a['id']]['hydration'])
                dx=a['x']-old[a['id']]['x'];dy=a['y']-old[a['id']]['y'];distance=math.hypot(dx,dy)
                if distance/dt>30:moving.append(dict(a,vx=dx/distance,vy=dy/distance))
            for colony_index,b in enumerate(active_backend_seconds):
                colony=[a for a in moving if a['backend']==b]
                if len(colony)<3:continue
                grouped=group_count(colony)
                social_time+=dt;group_time+=grouped/len(colony)*dt
                if grouped:grouped_seconds+=dt
                if row['elapsed']>=300:
                    late_social+=dt;late_group+=grouped/len(colony)*dt
                    if grouped:late_grouped_seconds+=dt
                    # Keep the original metric and add a stricter diagnostic:
                    # nest circling is not evidence of a joint foraging trip.
                    hx,hy=homes[colony_index]
                    excursion=[a for a in colony if a['goal']!=6 and math.hypot(a['x']-hx,a['y']-hy)>1150]
                    if len(excursion)>=3:
                        excursion_eligible+=dt
                        if group_count(excursion):excursion_grouped+=dt
        previous=row
    latency=sorted(r['batch_ms'] for r in rows if r['batches']>3)
    result={k:v for k,v in last.items() if k!='agents'}
    result.update(samples=len(rows),distance_cm=sum(movement.values()),final_backend_counts={b:sum(a['backend']==b for a in last['agents']) for b in active_backend_seconds},batch_median_ms=statistics.median(latency),batch_p95_ms=latency[int(.95*(len(latency)-1))],both_colonies_persist=all(any(a['backend']==b for a in last['agents']) for b in active_backend_seconds))
    result.update(observed_swarm_fraction=group_time/social_time if social_time else 0.,observed_social_seconds=social_time,late_swarm_fraction=late_group/late_social if late_social else 0.,late_social_seconds=late_social)
    result.update(grouped_colony_seconds=grouped_seconds,late_grouped_colony_seconds=late_grouped_seconds)
    result.update(late_excursion_eligible_colony_seconds=excursion_eligible,late_excursion_grouped_colony_seconds=excursion_grouped)
    result.update(hydration_replenished=hydration_gain,reserve_conservation_max_error=reserve_error)
    result.update(low_energy_agent_seconds=low_energy,low_hydration_agent_seconds=low_water,total_observed_agent_seconds=observed_agent_seconds,low_energy_fraction=sum(low_energy.values())/observed_agent_seconds if observed_agent_seconds else 0.)
    assert reserve_error<.5, f'Nest resource balance failed: {reserve_error}'
    result['score']=round(35*min(last['alive']/10,1)+15*int(result['both_colonies_persist'])+15*(1-min(last['stuck_fraction']/.25,1))+10*min(last['resource_visits']/16,1)+10*min(last['food_delivered']/1200,1)+15*last['swarm_fraction'],3)
    (folder/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def recommendation(result,params):
    changes={}
    if result['starvation_deaths']>0 or result.get('low_energy_fraction',0)>.005:
        changes['hunger']=min(102,params['hunger']+8)
    if result['dehydration_deaths']>0:changes['thirst']=min(82,params['thirst']+12)
    if result['stuck_fraction']>.06:changes['separation']=min(3.,params['separation']+.35)
    if result['resource_visits']<8:changes['memory_seconds']=max(35,params['memory_seconds']-10)
    if result['late_swarm_fraction']<.2:
        changes['alignment']=min(.85,params['alignment']+.15)
        changes['cohesion']=min(.6,params['cohesion']+.12)
    if result['alive']<6 and result['cyan_store']+result['amber_store']>100:changes['brood_cost']=max(20,params['brood_cost']-5)
    if result['batch_median_ms']>600:changes['colony_limit']=4
    elif result['batch_median_ms']>400:changes['colony_limit']=5
    if not changes:changes['motor_smoothing']=max(.18,params['motor_smoothing']*.85)
    return changes

def run_cycle(config):
    folder=LAB/'iterations'/config['name']
    assert not (folder/'complete.json').exists(),'Preserve completed runs; choose a fresh name'
    assert not (folder/'trace.jsonl').exists(),'Preserve interrupted runs too; choose a fresh name'
    archive_sources(folder)
    (folder/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    command(config)
    deadline=time.monotonic()+3600
    last_progress=-1
    while time.monotonic()<deadline:
        if (folder/'failed.json').exists():raise RuntimeError((folder/'failed.json').read_text())
        if (folder/'complete.json').exists():
            try:result=analyze(folder)
            except json.JSONDecodeError:time.sleep(.5);continue
            assert result['elapsed']>=config['duration']-.1
            return result
        try:
            latest=json.loads((folder/'latest.json').read_text())
            progress=int(latest['elapsed']//60)
            if progress!=last_progress:
                print(config['name'],f"{latest['elapsed']:.0f}s",'alive',latest['alive'],'delivered',round(latest['food_delivered']),'stuck',round(latest['stuck_fraction'],3),flush=True)
                last_progress=progress
        except (FileNotFoundError,json.JSONDecodeError):pass
        time.sleep(1)
    raise TimeoutError('Cycle failed to reach its duration')

def archive_sources(folder):
    """Keep the implementation that actually generated each new trace."""
    paths=list((ROOT/'Source/RPGPrototype').glob('*.*'))+list((ROOT/'Scripts/BrainLab').glob('*.py'))
    paths += [ROOT/'Config/BrainBiome.json',ROOT/'Config/BrainReadout.json']
    paths += list((ROOT/'Scripts/BrainLab/adapters').glob('*'))
    paths += [ROOT/'Content/Python/biome_audit.py',ROOT/'Content/Python/sensory_smoke.py',ROOT/'Content/Python/controller_smoke.py',ROOT/'Docs/Controller-control.md']
    manifest={}
    for path in paths:
        relative=path.relative_to(ROOT);target=folder/'source'/relative
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        manifest[str(relative)]=hashlib.sha256(path.read_bytes()).hexdigest()
    for relative in ['Binaries/Mac/libUnrealEditor-RPGPrototype.dylib','Content/Maps/Mosswild.umap','Saved/BrainLab/provenance.json',
                     'Saved/BrainLab/groups.json','Saved/BrainLab/calibration.json','Saved/BrainLab/silicon-adapter',
                     'Saved/BrainLab/native/target/release/brainlab-flybrain']:
        path=ROOT/relative
        if path.exists():manifest[relative]=hashlib.sha256(path.read_bytes()).hexdigest()
    (folder/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('--start',type=int,default=1);p.add_argument('--end',type=int,default=10);p.add_argument('--duration',type=float,default=600);p.add_argument('--seed',type=int,default=1701);p.add_argument('--neural-ms',type=int,choices=[10,20,40,80]);p.add_argument('--motor-smoothing',type=float);p.add_argument('--turn-gain',type=float);p.add_argument('--prefix',default='');p.add_argument('--launch',action='store_true');args=p.parse_args()
    if not 1<=args.start<=args.end<=10 or not 10<=args.duration<=3600 or not 0<=args.seed<=10000000:p.error('Expected stages 1..10, duration 10..3600s, seed 0..10000000')
    overrides={key:value for key,value in [('motor_smoothing',args.motor_smoothing),('turn_gain',args.turn_gain)] if value is not None}
    if any(not math.isfinite(v) or not .05<=v<=2 for v in overrides.values()):p.error('Motor overrides must be finite and in .05..2')
    if args.launch:
        (LAB/'audit-command.json').unlink(missing_ok=True)
        subprocess.run([sys.executable,'Scripts/ue.py','script','Content/Python/biome_audit.py'],cwd=ROOT,check=True)
    params=json.loads((ROOT/'Config/BrainBiome.json').read_text())['default_parameters'].copy()
    if args.neural_ms is not None:params['neural_ms']=args.neural_ms
    records_path=ROOT/'Docs/BrainBiome-iterations.json'
    records=json.loads(records_path.read_text()) if records_path.exists() else []
    for stage in range(args.start,args.end+1):
        label,description=STAGES[stage-1]
        name=f'{args.prefix}{stage:02d}-{label}'
        config=dict(params,stage=stage,seed=args.seed,name=name,synchronous=True,swarm=True,step=.4,duration=args.duration)
        if stage==10:
            preceding=next(r for r in reversed(records) if r['stage']==9)
            adjustments=recommendation(preceding['metrics'],params);config.update(adjustments)
        else:adjustments={}
        config.update(overrides);adjustments.update(overrides)
        (LAB/'current-cycle.json').write_text(json.dumps(dict(config=config,description=description),indent=2))
        print('START',name,description,'adjustments',adjustments,flush=True)
        result=run_cycle(config)
        previous=records[-1]['metrics'] if records else None
        source_hash=hashlib.sha256((ROOT/'Source/RPGPrototype/InsectBiome.cpp').read_bytes()).hexdigest()
        binary_hash=hashlib.sha256((ROOT/'Binaries/Mac/libUnrealEditor-RPGPrototype.dylib').read_bytes()).hexdigest()
        record=dict(stage=stage,name=name,hypothesis=description,config=config,source_sha256=source_hash,binary_sha256=binary_hash,metrics=result,adjustments=adjustments,score_delta=None if previous is None else result['score']-previous['score'],note='Measured feature addition; ecological constraints differ by stage. Score is diagnostic, not a controlled causal estimate for every added need. Observed swarm uses actual displacements, at least three moving neighbours within 850cm and alignment >0.65.')
        records.append(record);records_path.write_text(json.dumps(records,indent=2)+'\n')
        print('COMPLETE',name,json.dumps({k:result[k] for k in ['score','alive','births','deaths','food_delivered','stuck_fraction','swarm_fraction','resource_visits','final_backend_counts']}),flush=True)
    print('Requested cycles completed',flush=True)

if __name__=='__main__':main()
