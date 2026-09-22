"""Persistent rendered PIE driver; supports live body timing and explicit synchronous audits."""
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
base=Path(unreal.Paths.project_saved_dir())/'BrainLab'
command=base/'audit-command.json';ack=base/'audit-ack.json'
performance=unreal.get_default_object(unreal.load_class(None,'/Script/UnrealEd.EditorPerformanceSettings'))
old=performance.get_editor_property('bThrottleCPUWhenNotForeground')
performance.set_editor_property('bThrottleCPUWhenNotForeground',False)
state={'handle':None,'last':None,'poll':0,'render':None,'config':None,'folder':None,'next_sample':0,'completed':False}
def tick(_):
    try:
        if time.monotonic()<state['poll']:return
        state['poll']=time.monotonic()+.2
        w=editor.get_game_world()
        if not w:
            if state['config'] is not None:
                raise RuntimeError('PIE ended before the audit driver stopped')
            return
        if state['render'] is None:
            state['render']={key:unreal.SystemLibrary.get_console_variable_float_value(key) for key in ('t.MaxFPS','r.ScreenPercentage','ShowFlag.Rendering')}
            unreal.SystemLibrary.execute_console_command(w,'t.MaxFPS 60')
            unreal.SystemLibrary.execute_console_command(w,'r.ScreenPercentage 100')
            # Disabling Rendering left HUD draws in an uncleared viewport, making trails
            # of labels and health bars. Keep the scene rendering during all visible runs.
            unreal.SystemLibrary.execute_console_command(w,'ShowFlag.Rendering 2')
        labs=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.load_class(None,'/Script/RPGPrototype.InsectLab'))
        if not labs:return
        if state['config'] is not None and not state['config'].get('synchronous',False) and not state['completed']:
            snap=json.loads(labs[0].snapshot_json())
            if snap['elapsed']>=state['next_sample']:
                text=json.dumps(snap)
                with (state['folder']/'trace.jsonl').open('a') as trace:trace.write(text+'\n')
                (state['folder']/'latest.json').write_text(text)
                state['next_sample']=snap['elapsed']+1
            if snap['elapsed']>=state['config']['duration']:
                labs[0].toggle_pause()
                (state['folder']/'complete.json').write_text(json.dumps(snap))
                state['completed']=True
        if not command.exists():return
        try:data=json.loads(command.read_text())
        except json.JSONDecodeError:return
        if data['token']==state['last']:return
        if data.get('command')=='stop':
            unreal.unregister_slate_post_tick_callback(state['handle'])
            levels.editor_request_end_play()
            performance.set_editor_property('bThrottleCPUWhenNotForeground',old)
            for key,value in state['render'].items():unreal.SystemLibrary.execute_console_command(w,f'{key} {value}')
        else:
            labs[0].configure_biome_experiment(json.dumps(data['config']))
            state.update(config=data['config'],folder=base/'iterations'/data['config']['name'],next_sample=0,completed=False)
        state['last']=data['token']
        ack.write_text(json.dumps(dict(token=data['token'],success=True)))
    except Exception:
        if state['folder'] is not None:
            (state['folder']/'failed.json').write_text(json.dumps(dict(error=traceback.format_exc())))
        ack.write_text(json.dumps(dict(token=data.get('token') if 'data' in locals() else state['last'],success=False,error=traceback.format_exc())))
        if state['render']:
            for key,value in state['render'].items():unreal.SystemLibrary.execute_console_command(w,f'{key} {value}')
        unreal.unregister_slate_post_tick_callback(state['handle'])
        levels.editor_request_end_play()
        performance.set_editor_property('bThrottleCPUWhenNotForeground',old)
state['handle']=unreal.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
