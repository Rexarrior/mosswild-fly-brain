"""Capture an unmodified 600-second baseline before the biome/swarm revision."""
import json
from pathlib import Path
import time
import traceback
import unreal
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not levels.is_in_play_in_editor()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert levels.load_level('/Game/Maps/Insectarium')
out=Path(unreal.Paths.project_saved_dir())/'BrainLab/iterations/00-baseline'
out.mkdir(parents=True,exist_ok=True)
stream=(out/'trace.jsonl').open('w',buffering=1)
performance=unreal.get_default_object(unreal.load_class(None,'/Script/UnrealEd.EditorPerformanceSettings'))
old=performance.get_editor_property('bThrottleCPUWhenNotForeground')
performance.set_editor_property('bThrottleCPUWhenNotForeground',False)
state={'start':time.monotonic(),'last':-1.,'handle':None,'samples':0}
def finish(error=None):
    unreal.unregister_slate_post_tick_callback(state['handle'])
    stream.close()
    (out/'status.json').write_text(json.dumps(dict(status='failed' if error else 'completed',error=error,samples=state['samples'],wall_seconds=time.monotonic()-state['start']),indent=2))
    levels.editor_request_end_play()
    performance.set_editor_property('bThrottleCPUWhenNotForeground',old)
def tick(_):
    try:
        if time.monotonic()-state['start']>1200: raise TimeoutError('baseline stalled')
        world=editor.get_game_world()
        if not world:return
        labs=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.load_class(None,'/Script/RPGPrototype.InsectLab'))
        if not labs:return
        data=json.loads(labs[0].snapshot_json())
        if data['elapsed']-state['last']>=1:
            data['wall_seconds']=time.monotonic()-state['start']
            stream.write(json.dumps(data)+'\n');state['last']=data['elapsed'];state['samples']+=1
            (out/'status.json').write_text(json.dumps(dict(status='running',elapsed=data['elapsed'],alive=data['alive'],births=data['births'],deaths=data['deaths'])))
        if data['elapsed']>=600:finish()
        elif data['alive']==0 and data['batches']>10:finish('All organisms died before 600s')
    except Exception:finish(traceback.format_exc())
state['handle']=unreal.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
