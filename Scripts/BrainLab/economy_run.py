"""Launch and analyze a named half-hour rendered ecology run without replacing evidence."""
import argparse
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
import uuid
from iterate_biome import archive_sources
from runtime import LAB, ROOT


def analyze(folder):
    result = json.loads((folder/'complete.json').read_text())
    assert result['status']=='completed', result.get('error')
    rows = [json.loads(line) for line in (folder/'trace.jsonl').read_text().splitlines()]
    final = result['final']
    backend_counts = {b:sum(a['backend']==b for a in final['agents']) for b in ('siliconfly','flybrain')}
    balance_errors = [abs(120+r['food_delivered']-30*(r['births']+r['eggs'])-r['maintenance_spent']-r['spoiled_food']-r['cyan_store']-r['amber_store']) for r in rows]
    late_deliveries = []
    for end in (final['elapsed']-600, final['elapsed']-300, final['elapsed']):
        a = min(rows, key=lambda r:abs(r['elapsed']-(end-300)))
        b = min(rows, key=lambda r:abs(r['elapsed']-end))
        late_deliveries.append([b['colonies'][c]['delivered']-a['colonies'][c]['delivered'] for c in (0,1)])
    duration = 0; hungry = 0
    for a,b in zip(rows,rows[1:]):
        dt=b['elapsed']-a['elapsed'];duration+=dt*len(b['agents'])
        hungry+=dt*sum(v['energy']<25 or v['hydration']<25 for v in b['agents'])
    tail = [r for r in rows if r['elapsed']>final['elapsed']-900]
    latency = sorted(r['batch_ms'] for r in rows if r['batches']>3)
    checks = dict(
        half_hour_world=final['elapsed']>=1800,
        half_hour_wall=result['wall_seconds']>=1800,
        both_colonies=all(n>=4 for n in backend_counts.values()),
        population=final['alive']>=10,
        no_starvation_or_dehydration=final['starvation_deaths']==0 and final['dehydration_deaths']==0,
        sustained_deliveries=all(amount>=30 for window in late_deliveries for amount in window),
        nests_maintained=all(c['condition']>=.7 for r in tail for c in r['colonies']),
        needs_not_critical=hungry/max(duration,1)<.01,
        no_persistent_blocking=final['stuck_fraction']<.04,
        resources_conserved=max(balance_errors)<.5,
        real_upkeep=all(c['upkeep']>200 for c in final['colonies']))
    summary=dict(status='accepted' if all(checks.values()) else 'needs_improvement', checks=checks,
                 world_seconds=final['elapsed'], wall_seconds=result['wall_seconds'],
                 alive=final['alive'], backend_counts=backend_counts, births=final['births'], deaths=final['deaths'],
                 starvation_deaths=final['starvation_deaths'], dehydration_deaths=final['dehydration_deaths'],
                 fights=final['fights'], delivered=final['food_delivered'], colonies=final['colonies'],
                 late_deliveries_per_300_world_seconds=late_deliveries,
                 reserve_conservation_error=max(balance_errors), critical_needs_fraction=hungry/max(duration,1),
                 stuck_fraction=final['stuck_fraction'], batch_median_ms=statistics.median(latency),
                 batch_p95_ms=latency[int(.95*(len(latency)-1))], frame_median_ms=result['frame_median_ms'],
                 frame_p95_ms=result['frame_p95_ms'], telemetry_folder=final['telemetry_folder'])
    (folder/'analysis.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--name',required=True);p.add_argument('--seed',type=int,default=1701)
    p.add_argument('--analyze',action='store_true');p.add_argument('--overrides',default='{}')
    args=p.parse_args()
    assert args.name and all(c.isalnum() or c in '-_' for c in args.name)
    folder=LAB/'economy'/args.name
    if args.analyze: print(json.dumps(analyze(folder),indent=2));return
    assert not folder.exists(),'Preserve previous runs; choose a new name'
    folder.mkdir(parents=True);archive_sources(folder)
    command=dict(folder=str(folder),seed=args.seed,token=uuid.uuid4().hex,
                 duration_world=1800,minimum_wall=1800,timeout=6000,overrides=json.loads(args.overrides))
    (folder/'command.json').write_text(json.dumps(command,indent=2)+'\n')
    (LAB/'economy-command.json').write_text(json.dumps(command))
    subprocess.run([sys.executable,'Scripts/ue.py','script','Content/Python/biome_economy_run.py'],cwd=ROOT,check=True)
    deadline=time.monotonic()+6050;last=-1
    while time.monotonic()<deadline:
        if (folder/'complete.json').exists():
            print(json.dumps(analyze(folder),indent=2),flush=True);return
        try:
            snap=json.loads((folder/'progress.json').read_text());minute=int(snap['run_wall']//60)
            if minute!=last:
                print(args.name,'wall',round(snap['run_wall']),'world',round(snap['elapsed']),
                      'alive',snap['alive'],'delivered',round(snap['food_delivered']),
                      'stores',round(snap['cyan_store']),round(snap['amber_store']),
                      'care',[round(c['condition'],2) for c in snap['colonies']],flush=True)
                last=minute
        except (FileNotFoundError,json.JSONDecodeError):pass
        time.sleep(1)
    raise TimeoutError('Long-run coordinator deadline')


if __name__=='__main__':main()
