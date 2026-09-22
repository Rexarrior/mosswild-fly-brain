"""Summarize completed paired runs and validate the conditions actually recorded."""
import argparse
import json
from runtime import LAB

def movement_diagnostic(rows):
    """Use the same gate for both controllers; never consult the chosen goal."""
    eligible=slow=0.
    distances={}
    for row in rows:
        for a in row['agents']:
            key=(a['backend'],a['id'])
            distances[key]=max(distances.get(key,0),a['distance'])
    for previous,row in zip(rows,rows[1:]):
        dt=row['elapsed']-previous['elapsed']
        assert dt>0, 'Non-increasing biome time'
        old={(a['backend'],a['id']):a for a in previous['agents']}
        for a in row['agents']:
            before=old.get((a['backend'],a['id']))
            if before is None:continue
            if (before['contact_resource']!=-1 or a['contact_resource']!=-1
                    or min(before['drive'],a['drive'])<=.1):continue
            eligible+=dt
            # Accumulated path length avoids mistaking a loop for a motion stall.
            slow+=dt*int(max(0,a['distance']-before['distance'])/dt<17.5)
    return dict(distance_metres=sum(distances.values())/100,
                noncontact_motion_eligible_agent_seconds=eligible,
                noncontact_slow_agent_seconds=slow,
                noncontact_slow_fraction=slow/eligible if eligible else None)

def main():
    p=argparse.ArgumentParser();p.add_argument('--prefix',default='sensory-visible-v1');args=p.parse_args()
    runs=json.loads((LAB/'sensory'/f'{args.prefix}-results.json').read_text())
    records=[]
    for run in runs:
        config=run['config'];folder=LAB/'iterations'/config['name']
        rows=[json.loads(line) for line in (folder/'trace.jsonl').read_text().splitlines()]
        final=json.loads((folder/'complete.json').read_text())
        assert final['elapsed']>=config['duration'], 'Incomplete duration'
        if final['elapsed']>rows[-1]['elapsed']:rows.append(final)
        expected='sensory-populations-v1' if config['sensory_competition'] else 'planner'
        assert all(r['controller']==expected and r['seed']==config['seed'] and not r['ablation']
                   and r['contact_reflexes'] and not r['social_steering'] for r in rows), 'Experimental conditions changed mid-run'
        assert len({r['neural_session'] for r in rows})==1, 'Run was reset during measurement'
        last=rows[-1];metrics=run['metrics']
        anchor=min(rows,key=lambda r:abs(r['elapsed']-(last['elapsed']-300)))
        water_gains={};last_seen={}
        for row in rows:
            for a in row['agents']:
                key=(a['backend'],a['id'])
                if key in last_seen:water_gains[key]=water_gains.get(key,0)+max(0,a['hydration']-last_seen[key])
                last_seen[key]=a['hydration']
        audit=run['audit']['backends']
        seconds=sum(v['agent_seconds'] for v in audit.values())
        record=dict(mode='sensory' if config['sensory_competition'] else 'planner',seed=config['seed'],
                    name=config['name'],world_seconds=last['elapsed'],wall_seconds=last['wall_seconds'],
                    brain_batches=last['batches'],neural_window_ms=last['neural_ms'],
                    alive=last['alive'],births=last['births'],deaths=last['deaths'],
                    starvation_deaths=last['starvation_deaths'],dehydration_deaths=last['dehydration_deaths'],
                    combat_deaths=last['combat_deaths'],
                    fights=last['fights'],food_delivered=last['food_delivered'],
                    backend_counts=metrics['final_backend_counts'],stuck_fraction=last['stuck_fraction'],
                    critical_fraction=sum(v['critical_seconds'] for v in audit.values())/max(seconds,1),
                    minimum_energy=min((a['energy'] for r in rows for a in r['agents']),default=None),
                    minimum_hydration=min((a['hydration'] for r in rows for a in r['agents']),default=None),
                    batch_median_ms=metrics['batch_median_ms'],batch_p95_ms=metrics['batch_p95_ms'],
                    resource_visits=last['resource_visits'],colonies=last['colonies'],
                    delivered_last_300_seconds=[last['colonies'][c]['delivered']-anchor['colonies'][c]['delivered'] for c in (0,1)],
                    individuals_with_observed_drinking=sum(v>=5 for v in water_gains.values()),
                    competing_modalities_fraction=run['audit']['competing_modalities_fraction'],
                    reserve_conservation_error=metrics['reserve_conservation_max_error'],
                    observed_swarm_fraction=metrics['observed_swarm_fraction'],
                    food_consumed_by_backend={name:values['food'] for name,values in audit.items()},
                    movement=movement_diagnostic(rows))
        records.append(record)
    comparison=[]
    for seed in sorted({r['seed'] for r in records}):
        pair={r['mode']:r for r in records if r['seed']==seed}
        if len(pair)!=2:continue
        s,c=pair['sensory'],pair['planner']
        comparison.append(dict(seed=seed,delivered_ratio=s['food_delivered']/max(c['food_delivered'],1),
                               alive_delta=s['alive']-c['alive'],critical_fraction_delta=s['critical_fraction']-c['critical_fraction']))
    result=dict(runs=records,paired=comparison,note='Descriptive experiment; no statistical superiority claim. Engine identity is tied to colony location.')
    target=LAB/'sensory'/f'{args.prefix}-summary.json'
    target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
