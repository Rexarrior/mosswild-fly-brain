"""Run real gameplay checks sequentially after the ecology audit has stopped."""
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
from runtime import ROOT,LAB


def run(*args):
    subprocess.run([sys.executable,*args],cwd=ROOT,check=True)


def editor_check(script,report,timeout):
    report.unlink(missing_ok=True)
    run('Scripts/ue.py','script',script)
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if report.exists():
            try:data=json.loads(report.read_text())
            except json.JSONDecodeError:time.sleep(.25);continue
            if data.get('status') not in (None,'running'):
                assert data.get('success',data['status']=='passed'),{k:v for k,v in data.items() if k!='samples'}
                print('PASS',script,flush=True)
                time.sleep(1) # EndPlay is queued by the editor callback.
                return data
        time.sleep(.5)
    raise TimeoutError(script)


def main():
    evidence={'binary_sha256':hashlib.sha256((ROOT/'Binaries/Mac/libUnrealEditor-RPGPrototype.dylib').read_bytes()).hexdigest()}
    run('Scripts/BrainLab/lab.py','start')
    gameplay=editor_check('Content/Python/biome_smoke.py',LAB/'biome-smoke.json',480)
    evidence['gameplay']={k:v for k,v in gameplay.items() if k!='samples'}
    play=editor_check('Content/Python/biome_playcheck.py',LAB/'biome-play.json',780)
    evidence['rendered_play']={k:v for k,v in play.items() if k!='samples'}
    evidence['rendered_play']['final']=play['samples'][-1]
    latencies=sorted(s['batch_ms'] for s in play['samples'] if s['batches']>3)
    evidence['rendered_play'].update(
        batch_median_ms=statistics.median(latencies),batch_p95_ms=latencies[int(.95*(len(latencies)-1))],
        minimum_energy=min(a['energy'] for s in play['samples'] for a in s['agents']),
        minimum_hydration=min(a['hydration'] for s in play['samples'] for a in s['agents']),
        backend_counts={b:sum(a['backend']==b for a in play['samples'][-1]['agents']) for b in ('siliconfly','flybrain')})
    evidence['capture_note']='Frame timings are Slate post-tick intervals in an editor viewport, not GPU kernel times or a packaged-game benchmark.'
    run('Scripts/BrainLab/check_recovery.py')
    evidence['service_recovery']=json.loads((LAB/'recovery.json').read_text())
    run('Scripts/ue.py','exec',"import unreal; levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem); assert not levels.is_in_play_in_editor(); assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(); assert levels.load_level('/Game/Maps/Mosswild'); world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(); unreal.SystemLibrary.execute_console_command(world,'MAP CHECK')")
    time.sleep(1)
    log=(Path.home()/'Library/Logs/Unreal Engine/RPGPrototypeEditor/RPGPrototype.log').read_text(errors='replace')
    checks=[line for line in log.splitlines() if 'MapCheck:' in line]
    assert checks and ('0 ошибок, 0 предупреждений' in checks[-1] or '0 Error' in checks[-1]),checks[-3:]
    evidence['map_check']=checks[-1]
    (ROOT/'Docs/BrainBiome-validation.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print('PASS all gameplay, rendered play, service recovery and Map Check',flush=True)


if __name__=='__main__':main()
