"""Paired same-input motor replacement, fixed world integration and contact rules.

No evaluation-driven tuning; frozen reactive-v1 coefficients live in reactive_control.py.
Both full engines coexist in the neural arm. The reactive arm drives both colonies
with the SAME policy; backend names there are body/colony labels, not running engines.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from iterate_biome import run_cycle, command
from runtime import ROOT, LAB


def verify(folder, mode):
    rows=[json.loads(line) for line in (folder/'trace.jsonl').read_text().splitlines()]
    rows.append(json.loads((folder/'complete.json').read_text()))
    assert all(r['motor_controller']==mode and r['contact_gate']=='contact' and
               r['controller']=='sensory-populations-v1' and not r['social_steering'] and
               not r['predict_senses'] for r in rows)
    for r in rows:
        for a in r['agents']:
            if a['sensory_channels']:
                assert len(a['sensory_channels'])==8 and a['goal']==a['resource']==-1 and not a['provisioning']
            else:
                assert a['distance']==0
            if mode=='reactive-v1':
                assert a['forward_hz']==a['left_hz']==a['right_hz']==0
    return dict(checked_snapshots=len(rows),same_contact_rule=True,no_planner=True,
                artificial_neural_rates=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--duration',type=float,default=1800)
    p.add_argument('--seeds',type=int,nargs='+',default=[4101,5101,6101,7101])
    p.add_argument('--prefix',default='motor-control-v1')
    p.add_argument('--launch',action='store_true')
    p.add_argument('--only',choices=['connectome','reactive-v1'])
    args=p.parse_args()
    assert 10<=args.duration<=1800 and args.seeds and len(set(args.seeds))==len(args.seeds)
    assert all(0<=s<=10000000 for s in args.seeds)
    assert args.prefix and all(c.isalnum() or c in '-_' for c in args.prefix)
    out=LAB/'controller-control'/args.prefix
    out.mkdir(parents=True,exist_ok=False)
    plan=[]
    for i,seed in enumerate(args.seeds):
        modes=[args.only] if args.only else (['connectome','reactive-v1'] if i%2==0 else ['reactive-v1','connectome'])
        for mode in modes:
            plan.append(dict(stage=10,seed=seed,name=f'{args.prefix}-{mode}-{seed}',
                             synchronous=True,predict_senses=False,swarm=False,step=.4,
                             duration=args.duration,sensory_competition=True,contact_reflexes=True,
                             contact_gate='contact',motor_controller=mode,continuous_economy=True,
                             neural_ms=20,colony_limit=6))
    (out/'plan.json').write_text(json.dumps(dict(created=time.time(),runs=plan,
        primary=['starvation_deaths','dehydration_deaths','both_colonies_persist','food_delivered'],
        secondary=['combat_deaths','low_energy_fraction','coverage','resource_visits','batch_median_ms'],
        caveats=['fixed small world','two engines tied to map sides in neural arm',
                 'contact gate removed in BOTH arms','descriptive paired replications; no biological validity claim',
                 'synchronous 0.4 s command / 0.05 s physics steps, not real-time rendering benchmark']),indent=2)+'\n')
    results=[]
    launched=False
    try:
        if args.launch:
            (LAB/'audit-command.json').unlink(missing_ok=True)
            subprocess.run([sys.executable,'Scripts/ue.py','script','Content/Python/biome_audit.py'],cwd=ROOT,check=True)
            launched=True
        for config in plan:
            print('START',config['name'],flush=True)
            result=run_cycle(config)
            audit=verify(LAB/'iterations'/config['name'],config['motor_controller'])
            results.append(dict(config=config,metrics=result,audit=audit))
            (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
            print('RESULT',config['name'],json.dumps({k:result[k] for k in
                ('alive','births','deaths','starvation_deaths','dehydration_deaths','food_delivered','batch_median_ms')}),flush=True)
        (out/'finished.json').write_text(json.dumps(dict(runs=len(results),finished=time.time()))+'\n')
    except BaseException as e:
        (out/'failed.json').write_text(json.dumps(dict(error=repr(e),completed=len(results)))+'\n')
        raise
    finally:
        if launched: command(stop=True)

if __name__=='__main__':main()
