"""Explain measured deaths, goal churn and stationary travel from a recorded run."""
import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from runtime import LAB, ROOT


def diagnose(folder):
    rows=[json.loads(line) for line in (folder/'trace.jsonl').read_text().splitlines() if line]
    config=json.loads((ROOT/'Config/BrainBiome.json').read_text())
    deaths=[];goals=defaultdict(Counter);switches=Counter();stalls=[];stationary={};previous=None
    encounter_seconds=0.;food_presence=defaultdict(Counter)
    established_owners={};territory_changes=[];combat=[]
    for row in rows:
        for resource in row.get('resources',[]):
            if resource['owner']>=0 and resource['claim']>2:
                index=resource['index'];owner=resource['owner']
                if index in established_owners and established_owners[index]!=owner:
                    territory_changes.append(dict(time=row['elapsed'],resource=index,previous_owner=established_owners[index],new_owner=owner))
                established_owners[index]=owner
        for a in row['agents']:
            goals[a['backend']][a['intent']]+=1
            if a['goal']==1:food_presence[a['backend']][a['resource']]+=1
        if previous:
            dt=row['elapsed']-previous['elapsed'];old={a['id']:a for a in previous['agents']};current={a['id']:a for a in row['agents']}
            if row['fights']>previous['fights']:
                injured=[dict(id=a['id'],backend=a['backend'],health_before=old[a['id']]['health'],health_after=a['health'],x=a['x'],y=a['y']) for a in row['agents'] if a['id'] in old and a['health']<old[a['id']]['health']-5]
                combat.append(dict(time=row['elapsed'],strikes=row['fights']-previous['fights'],injured=injured))
            if any(a['backend']!=b['backend'] and math.hypot(a['x']-b['x'],a['y']-b['y'])<550 for i,a in enumerate(row['agents']) for b in row['agents'][i+1:]):encounter_seconds+=dt
            for aid,a in old.items():
                if aid not in current:
                    nearest=min(config['obstacles'],key=lambda b:math.hypot(a['x']-b['x'],a['y']-b['y']))
                    deaths.append(dict(time=row['elapsed'],agent=a,nearest_rock=nearest,rock_distance=math.hypot(a['x']-nearest['x'],a['y']-nearest['y'])))
            for aid,a in current.items():
                if aid not in old:continue
                b=old[aid]
                switches[a['backend']]+=int((a['goal'],a['resource'])!=(b['goal'],b['resource']))
                target_distance=math.hypot(a['x']-a['target_x'],a['y']-a['target_y'])
                displacement=math.hypot(a['x']-b['x'],a['y']-b['y'])
                stopped=dt>0 and displacement/dt<15 and target_distance>300 and a['drive']>.1
                if stopped:
                    if aid not in stationary:stationary[aid]=dict(start=previous['elapsed'],seconds=0,agent=a)
                    stationary[aid]['seconds']+=dt
                elif aid in stationary:stalls.append(stationary.pop(aid))
            for aid in list(stationary):
                if aid not in current:stalls.append(stationary.pop(aid))
        previous=row
    stalls.extend(stationary.values());stalls.sort(key=lambda x:x['seconds'],reverse=True)
    result=dict(run=folder.name,elapsed=rows[-1]['elapsed'],deaths=deaths,goal_samples=dict(goals),forage_target_samples=dict(food_presence),opposing_colonies_nearby_seconds=encounter_seconds,observed_goal_switches=dict(switches),longest_stalls=stalls[:12],territory_changes=territory_changes,combat=combat)
    (folder/'diagnostics.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(run=folder.name,deaths=[dict(time=round(d['time'],1),id=d['agent']['id'],energy=round(d['agent']['energy'],1),hydration=round(d['agent']['hydration'],1),goal=d['agent']['intent'],rock_distance=round(d['rock_distance'])) for d in deaths],goal_samples=dict(goals),longest_stalls=[dict(seconds=round(s['seconds'],1),id=s['agent']['id'],goal=s['agent']['intent']) for s in stalls[:6]]),indent=2))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run');a=p.parse_args();diagnose(LAB/'iterations'/a.run)
