"""Ten-minute rendered, asynchronous gameplay soak with actual frame timings."""
import json
from pathlib import Path
import statistics
import time
import traceback
import unreal
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not levels.is_in_play_in_editor()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert levels.load_level('/Game/Maps/Mosswild')
base=Path(unreal.Paths.project_saved_dir())/'BrainLab';report=base/'biome-play.json'
perf=unreal.get_default_object(unreal.load_class(None,'/Script/UnrealEd.EditorPerformanceSettings'))
old_throttle=perf.get_editor_property('bThrottleCPUWhenNotForeground')
perf.set_editor_property('bThrottleCPUWhenNotForeground',False)
state=dict(handle=None,start=time.monotonic(),play_start=None,last_frame=None,last_sample=0,frames=[],samples=[],captures=set(),render=None)
report.write_text(json.dumps({'status':'running'}))
def finish(error=None):
    frames=sorted(state['frames'])
    result=dict(status='failed' if error else 'passed',error=error,wall_seconds=time.monotonic()-state['play_start'] if state['play_start'] else 0,samples=state['samples'],frames=len(frames),frame_median_ms=statistics.median(frames)*1000 if frames else None,frame_p95_ms=frames[int(.95*(len(frames)-1))]*1000 if frames else None)
    report.write_text(json.dumps(result,indent=2))
    w=editor.get_game_world()
    if w and state['render']:
        for key,value in state['render'].items():unreal.SystemLibrary.execute_console_command(w,f'{key} {value}')
    unreal.unregister_slate_post_tick_callback(state['handle']);levels.editor_request_end_play()
    perf.set_editor_property('bThrottleCPUWhenNotForeground',old_throttle)
def tick(_):
    try:
        now=time.monotonic()
        if now-state['start']>750:raise TimeoutError('Rendered play soak')
        w=editor.get_game_world()
        if not w:return
        labs=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.InsectLab)
        if not labs:return
        lab=labs[0];hero=unreal.GameplayStatics.get_player_character(w,0)
        if state['play_start'] is None:
            state['play_start']=now
            state['render']={k:unreal.SystemLibrary.get_console_variable_float_value(k) for k in ('t.MaxFPS','r.ScreenPercentage','ShowFlag.Rendering')}
            for k,v in [('t.MaxFPS',60),('r.ScreenPercentage',100),('ShowFlag.Rendering',2)]:unreal.SystemLibrary.execute_console_command(w,f'{k} {v}')
        age=now-state['play_start']
        if age>5 and state['last_frame'] is not None:state['frames'].append(now-state['last_frame'])
        state['last_frame']=now
        if now-state['last_sample']>=1:
            snap=json.loads(lab.snapshot_json());state['samples'].append(dict(wall=age,**snap));state['last_sample']=now
            (base/'biome-play-latest.json').write_text(json.dumps(dict(wall=age,**snap)))
        for threshold,label,focus in [(12,'Mosswild_Overview',None),(40,'Mosswild_Cyan',0),(75,'Mosswild_Amber',1),(105,'Mosswild_Map',2)]:
            if age>threshold-2 and label+'camera' not in state['captures']:
                if focus in (0,1):hero.focus_insect_colony(focus)
                if focus==2:hero.toggle_map()
                state['captures'].add(label+'camera')
            if age>threshold and label not in state['captures']:
                unreal.SystemLibrary.execute_console_command(w,f'HighResShot 1600x1000 filename={label}')
                state['captures'].add(label)
        if age>42 and 'normal_screenshot' not in state['captures']:
            unreal.SystemLibrary.execute_console_command(w,'Shot filename=Mosswild_Cyan_Normal')
            state['captures'].add('normal_screenshot')
        if age>109 and 'map_closed' not in state['captures']:
            if hero.is_map_open():hero.toggle_map()
            state['captures'].add('map_closed')
        if age>=600:
            snap=state['samples'][-1]
            assert snap['batches']>30 and snap['elapsed']>120 and snap['alive']>=8,snap
            assert snap['status'].startswith('LIVE'),snap['status']
            assert snap['starvation_deaths']<=1,'Rendered gameplay has excessive starvation despite stable audit'
            assert all(any(a['backend']==b and a['distance']>100 for a in snap['agents']) for b in ('siliconfly','flybrain'))
            finish()
    except Exception:finish(traceback.format_exc())
state['handle']=unreal.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
