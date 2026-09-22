"""Repeat the final configuration with a held-out ecology seed and social ablation."""
import argparse
import hashlib
import json
import subprocess
import sys
from iterate_biome import run_cycle
from diagnose_biome import diagnose
from runtime import LAB, ROOT


def main():
    p=argparse.ArgumentParser();p.add_argument('--reference',default='10-joint');p.add_argument('--launch',action='store_true');p.add_argument('--prefix',default='control-');p.add_argument('--seeds',type=int,nargs='+',default=[1701,431]);args=p.parse_args()
    if args.launch:
        (LAB/'audit-command.json').unlink(missing_ok=True)
        subprocess.run([sys.executable,'Scripts/ue.py','script','Content/Python/biome_audit.py'],cwd=ROOT,check=True)
    records=json.loads((ROOT/'Docs/BrainBiome-iterations.json').read_text())
    reference=next(r for r in reversed(records) if r['name']==args.reference)
    path=ROOT/'Docs/BrainBiome-controls.json';controls=json.loads(path.read_text()) if path.exists() else []
    for seed in args.seeds:
        for social in (True,False):
            name=f'{args.prefix}{seed}-social-{int(social)}'
            # The measured reference already supplies its original social-on run.
            if social and seed==reference['config']['seed']:
                if not any(r['name']==reference['name'] for r in controls):controls.append(dict(name=reference['name'],reference=args.reference,config=reference['config'],metrics=reference['metrics'],binary_sha256=reference['binary_sha256']))
                continue
            if any(r['name']==name for r in controls):continue
            config=dict(reference['config'],name=name,seed=seed,swarm=social,duration=600)
            print('CONTROL',name,flush=True)
            result=run_cycle(config);diagnose(LAB/'iterations'/name)
            controls.append(dict(name=name,reference=args.reference,config=config,metrics=result,binary_sha256=hashlib.sha256((ROOT/'Binaries/Mac/libUnrealEditor-RPGPrototype.dylib').read_bytes()).hexdigest()))
            path.write_text(json.dumps(controls,indent=2)+'\n')
            print('COMPLETE',name,'alive',result['alive'],'late observed group',result['late_swarm_fraction'],flush=True)
    path.write_text(json.dumps(controls,indent=2)+'\n')

if __name__=='__main__':main()
