"""Record real rendered gameplay frames with timestamps for a reproducible clip."""
import json
from pathlib import Path
import time
import traceback
import unreal
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not levels.is_in_play_in_editor()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert levels.load_level('/Game/Maps/Mosswild')
base=Path(unreal.Paths.project_saved_dir()).resolve()/'BrainLab'/('animation-'+time.strftime('%Y%m%d-%H%M%S'))
base.mkdir(parents=True)
performance=unreal.get_default_object(unreal.load_class(None,'/Script/UnrealEd.EditorPerformanceSettings'))
old=performance.get_editor_property('bThrottleCPUWhenNotForeground')
performance.set_editor_property('bThrottleCPUWhenNotForeground',False)
state=dict(handle=None,started=time.monotonic(),t=None,last=0,frames=[],cyan=False,switched=False)
def finish(error=None):
    (base/'frames.json').write_text(json.dumps(dict(error=error,frames=state['frames']),indent=2))
    (base.parent/'animation-latest.json').write_text(json.dumps(dict(folder=str(base),error=error)))
    unreal.unregister_slate_post_tick_callback(state['handle']);levels.editor_request_end_play()
    performance.set_editor_property('bThrottleCPUWhenNotForeground',old)
def tick(_):
    try:
        now=time.monotonic()
        if now-state['started']>90:raise TimeoutError('Capture startup')
        w=editor.get_game_world()
        if not w:return
        labs=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.InsectLab)
        if not labs:return
        lab=labs[0];snap=json.loads(lab.snapshot_json());hero=unreal.GameplayStatics.get_player_character(w,0)
        if state['t'] is None:
            if snap['batches']<6 or snap['births']<2:return
            unreal.SystemLibrary.execute_console_command(w,'ShowFlag.Rendering 2')
            unreal.SystemLibrary.execute_console_command(w,'r.ScreenPercentage 100')
            state['t']=now+1;return
        t=now-state['t']
        if t<0:return
        if t>21:finish();return
        if t>3 and not state['cyan']:hero.focus_insect_colony(0);state['cyan']=True
        if t>12 and not state['switched']:hero.focus_insect_colony(1);state['switched']=True
        if now-state['last']<.12:return
        if state['frames'] and not Path(state['frames'][-1]['path']).exists():return
        # JPEG avoids the long synchronous PNG compression stall at Retina size.
        path=base/f"frame-{len(state['frames']):04d}.jpg"
        # Keep the live temporal-AA history. HighResShot resets it and leaves
        # bright trails on the small animated carapace/leg details.
        unreal.SystemLibrary.execute_console_command(w,f'Shot filename={path} -nosuffix')
        state['frames'].append(dict(path=str(path),wall_seconds=t,world_seconds=snap['elapsed']))
        state['last']=now
    except Exception:finish(traceback.format_exc())
state['handle']=unreal.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
