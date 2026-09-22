"""Summarize completed, paired motor controls; never select only successful runs."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
from runtime import ROOT, LAB


def collect(prefix):
    base=LAB/'controller-control'/prefix
    plan=json.loads((base/'plan.json').read_text())
    runs=[]
    sources={}
    def read(path):
        raw=path.read_bytes();sources[str(path.relative_to(ROOT))]=hashlib.sha256(raw).hexdigest()
        return raw.decode()
    for cfg in plan['runs']:
        folder=LAB/'iterations'/cfg['name']
        final=json.loads(read(folder/'complete.json'))
        rows=[json.loads(line) for line in read(folder/'trace.jsonl').splitlines() if line]
        if not rows or rows[-1]['elapsed']<final['elapsed']:rows.append(final)
        else:rows[-1]=final
        saved=json.loads(read(folder/'config.json'))
        assert saved==cfg and final['elapsed']>=cfg['duration']-.1
        assert all(r['motor_controller']==cfg['motor_controller'] and r['contact_gate']=='contact' for r in rows)
        raw_latency=[r['batch_ms'] for r in rows if r['batches']>3]
        agents={};distance={};low_e=low_h=observed=0.
        for row in rows:
            for a in row['agents']:
                key=(a['backend'],a['id'],a['generation'])
                distance[key]=max(distance.get(key,0),a['distance'])
                agents[key]=max(agents.get(key,0),a['consumed'])
        for previous,row in zip(rows,rows[1:]):
            dt=row['elapsed']-previous['elapsed']
            assert dt>=0
            observed+=dt*len(row['agents'])
            low_e+=dt*sum(a['energy']<25 for a in row['agents'])
            low_h+=dt*sum(a['hydration']<25 for a in row['agents'])
        manifest=json.loads(read(folder/'source-manifest.json'))
        runs.append(dict(name=cfg['name'],seed=cfg['seed'],mode=cfg['motor_controller'],
            **{k:final[k] for k in ['elapsed','wall_seconds','alive','births','deaths','starvation_deaths',
                                   'dehydration_deaths','combat_deaths','food_delivered','coverage','resource_visits',
                                   'meals','batches','colonies']},
            final_colony_counts={b:sum(a['backend']==b for a in final['agents']) for b in ['siliconfly','flybrain']},
            total_path_m=sum(distance.values())/100,total_consumed=sum(agents.values()),
            low_energy_fraction=low_e/max(1,observed),low_hydration_fraction=low_h/max(1,observed),
            min_energy=min(a['energy'] for row in rows for a in row['agents']),
            min_hydration=min(a['hydration'] for row in rows for a in row['agents']),
            batch_median_ms=statistics.median(raw_latency),
            trace_samples=len(rows),source_manifest=manifest,
            series=[[r['elapsed'],r['alive'],r['food_delivered']] for r in rows]))
    # Implementations used in every arm must be identical, not changed between seeds.
    def implementation(manifest):
        return {p:h for p,h in manifest.items() if p.startswith(('Source/','Config/','Binaries/','Scripts/BrainLab/adapters/'))
                or p in ('Scripts/BrainLab/server.py','Scripts/BrainLab/runtime.py','Scripts/BrainLab/reactive_control.py',
                         'Content/Python/biome_audit.py','Saved/BrainLab/groups.json','Saved/BrainLab/calibration.json',
                         'Saved/BrainLab/silicon-adapter','Saved/BrainLab/native/target/release/brainlab-flybrain')}
    assert all(implementation(r['source_manifest'])==implementation(runs[0]['source_manifest']) for r in runs)
    pairs=[]
    for seed in sorted({r['seed'] for r in runs}):
        neural=next(r for r in runs if r['seed']==seed and r['mode']=='connectome')
        control=next(r for r in runs if r['seed']==seed and r['mode']=='reactive-v1')
        pairs.append(dict(seed=seed,food_difference=control['food_delivered']-neural['food_delivered'],
                          food_relative_percent=100*(control['food_delivered']/neural['food_delivered']-1)))
    result=dict(protocol=plan,runs=runs,paired=pairs,sources_sha256=sources)
    (base/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    lines=['# Same-input controller comparison','',
           '| Mode | Seed | Alive | Hunger / thirst / combat deaths | Delivered | Batch median, ms |',
           '|---|---:|---:|---:|---:|---:|']
    for r in runs:
        lines.append(f"| {r['mode']} | {r['seed']} | {r['alive']} | {r['starvation_deaths']} / {r['dehydration_deaths']} / {r['combat_deaths']} | {r['food_delivered']:.1f} | {r['batch_median_ms']:.4f} |")
    lines+=['','Paired delivery differences (reactive minus connectome):',json.dumps(pairs,indent=2),
            '', 'All final snapshots included. Runtime implementation hashes match across every run (analysis scripts excluded).',
            'Low-need fractions are sampled diagnostics; they omit unobserved moments between snapshots.',
            'Synchronous world stepping removes response-frequency advantage, not physical/ecological differences caused by the resulting actions.',
            'Baseline backend labels denote colony slots; their reported neural rates are zero.']
    (base/'report.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines[:4+len(runs)]))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prefix',default='motor-control-v1')
    collect(p.parse_args().prefix)
