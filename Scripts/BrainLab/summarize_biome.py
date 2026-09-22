"""Refresh compact evidence from completed traces, preserving recorded configurations."""
import json
from pathlib import Path
from iterate_biome import analyze
from diagnose_biome import diagnose
from runtime import LAB,ROOT


def main():
    for filename in ['BrainBiome-iterations.json','BrainBiome-controls.json']:
        path=ROOT/'Docs'/filename
        if not path.exists():continue
        records=json.loads(path.read_text())
        for r in records:
            folder=LAB/'iterations'/r['name']
            r['metrics']=analyze(folder)
            d=diagnose(folder)
            r['diagnostics']=dict(opposing_colonies_nearby_seconds=d['opposing_colonies_nearby_seconds'],observed_goal_switches=d['observed_goal_switches'],goal_samples=d['goal_samples'],longest_stall_seconds=max((s['seconds'] for s in d['longest_stalls']),default=0),territory_changes=d['territory_changes'],combat_examples=d['combat'][:5])
        path.write_text(json.dumps(records,indent=2)+'\n')
    records=json.loads((ROOT/'Docs/BrainBiome-iterations.json').read_text())
    lines=['| Cycle | Living | Deaths | Delivered | Blocked | Late grouping | Median batch |','|---|---:|---:|---:|---:|---:|---:|']
    for r in records:
        m=r['metrics'];lines.append(f"| {r['name']} | {m['alive']} | {m['deaths']} | {m['food_delivered']:.0f} | {m['stuck_fraction']:.2%} | {m['late_swarm_fraction']:.1%} | {m['batch_median_ms']:.0f} ms |")
    text='\n'.join(lines)+'\n';(LAB/'iteration-table.md').write_text(text);print(text)

if __name__=='__main__':main()
