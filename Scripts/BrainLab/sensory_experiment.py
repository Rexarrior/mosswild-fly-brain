"""Paired embodied runs: identical contact economics, no flocking, frozen readout."""
import argparse
import json
import subprocess
import sys
from iterate_biome import run_cycle, command
from runtime import ROOT, LAB

def audit(folder):
    rows = [json.loads(line) for line in (folder/'trace.jsonl').read_text().splitlines()]
    sensory = rows[-1]['controller'] != 'planner'
    if sensory:
        for r in rows:
            for a in r['agents']:
                if a['sensory_channels']:
                    assert a['goal']==-1 and a['resource']==-1 and not a['provisioning'], 'Planner leaked into sensory mode'
                else:
                    # A hatchling can appear in the post-step snapshot before its first sensory batch.
                    assert a['distance']==0 and a['forward_hz']==0, 'Moving agent has no sensory inputs'
        assert all(len(a['sensory_channels'])==8 for r in rows[1:] for a in r['agents'] if a['distance']>0)
    seconds=overlap=0.
    backend={name:dict(agent_seconds=0.,critical_seconds=0.,food=0.,water_contacts=0)
             for name in ('siliconfly','flybrain')}
    consumed={}
    for prev,row in zip(rows,rows[1:]):
        dt=row['elapsed']-prev['elapsed']
        for a in row['agents']:
            b=backend[a['backend']];b['agent_seconds']+=dt
            b['critical_seconds']+=dt*int(a['energy']<25 or a['hydration']<25)
            b['water_contacts']+=int(a['contact_resource']>=13)
            consumed[(a['backend'],a['id'])]=max(consumed.get((a['backend'],a['id']),0),a['consumed'])
            if sensory:
                c=a['sensory_channels'];seconds+=dt
                if c: overlap+=dt*int(sum(c[i]+c[i+1]>.05 for i in (0,2,4))>=2)
    for (name,_),value in consumed.items():backend[name]['food']+=value
    result=dict(no_planner_targets=sensory,competing_modalities_fraction=overlap/max(seconds,1),backends=backend)
    (folder/'sensory-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--duration',type=float,default=600)
    p.add_argument('--seeds',type=int,nargs='+',default=[1701,2701])
    p.add_argument('--prefix',default='sensory-visible-v1')
    p.add_argument('--launch',action='store_true')
    p.add_argument('--only',choices=['sensory','planner'])
    p.add_argument('--synchronous',action='store_true',help='Use stepped body timing instead of smooth rendered gameplay')
    args=p.parse_args()
    assert 10<=args.duration<=3600 and all(0<=s<=10000000 for s in args.seeds)
    assert args.prefix and all(c.isalnum() or c in '-_' for c in args.prefix)
    if args.launch:
        (LAB/'audit-command.json').unlink(missing_ok=True)
        subprocess.run([sys.executable,'Scripts/ue.py','script','Content/Python/biome_audit.py'],cwd=ROOT,check=True)
    results=[]
    try:
        for index,seed in enumerate(args.seeds):
            modes=[args.only] if args.only else (['sensory','planner'] if index%2==0 else ['planner','sensory'])
            for mode in modes:
                config=dict(stage=10,seed=seed,name=f'{args.prefix}-{mode}-{seed}',synchronous=args.synchronous,
                            swarm=False,step=.4,duration=args.duration,sensory_competition=mode=='sensory',
                            contact_reflexes=True,continuous_economy=True)
                result=run_cycle(config)
                extra=audit(LAB/'iterations'/config['name'])
                results.append(dict(config=config,metrics=result,audit=extra))
                out=LAB/'sensory'/f'{args.prefix}-results.json';out.parent.mkdir(parents=True,exist_ok=True)
                out.write_text(json.dumps(results,indent=2)+'\n')
                print('RESULT',config['name'],json.dumps({k:result[k] for k in
                      ('alive','births','deaths','starvation_deaths','dehydration_deaths','food_delivered','resource_visits')}),flush=True)
    finally:
        command(stop=True)

if __name__=='__main__':main()
