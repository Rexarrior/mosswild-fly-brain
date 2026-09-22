"""Rendered asynchronous long run. Only this validation mode ends PIE itself."""
import json
from pathlib import Path
import statistics
import time
import traceback
import unreal

root = Path(unreal.Paths.project_dir()).resolve()
command = json.loads((root/'Saved/BrainLab/economy-command.json').read_text())
folder = Path(command['folder']).resolve()
assert folder.parent == root/'Saved/BrainLab/economy'
assert not (folder/'progress.json').exists(), 'Choose a fresh run name'
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not levels.is_in_play_in_editor()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert levels.load_level('/Game/Maps/Mosswild')
performance = unreal.get_default_object(unreal.load_class(None, '/Script/UnrealEd.EditorPerformanceSettings'))
old_throttle = performance.get_editor_property('bThrottleCPUWhenNotForeground')
performance.set_editor_property('bThrottleCPUWhenNotForeground', False)
state = dict(handle=None, launch=time.monotonic(), start=None, last_frame=None,
             last_sample=-10, last_progress=-10, frames=[], last_alive=None, render=None)
trace = (folder/'trace.jsonl').open('x', buffering=1)

def finish(error=None):
    frame_times = sorted(state['frames'])
    result = dict(status='failed' if error else 'completed', error=error,
                  frames=len(frame_times), token=command['token'])
    if frame_times:
        result.update(frame_median_ms=statistics.median(frame_times)*1000,
                      frame_p95_ms=frame_times[int(.95*(len(frame_times)-1))]*1000)
    w = editor.get_game_world()
    if w:
        labs = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.InsectLab)
        if labs: result['final'] = json.loads(labs[0].snapshot_json())
        if state['render']:
            for key, value in state['render'].items(): unreal.SystemLibrary.execute_console_command(w, f'{key} {value}')
    result['wall_seconds'] = time.monotonic()-(state['start'] or state['launch'])
    trace.close()
    (folder/'complete.json').write_text(json.dumps(result, indent=2)+'\n')
    unreal.unregister_slate_post_tick_callback(state['handle'])
    levels.editor_request_end_play()
    performance.set_editor_property('bThrottleCPUWhenNotForeground', old_throttle)

def tick(_):
    try:
        now = time.monotonic()
        if now-state['launch'] > command.get('timeout', 6000): raise TimeoutError('Long-run deadline')
        w = editor.get_game_world()
        if not w:
            if state['start'] is not None: raise RuntimeError('PIE stopped before completion')
            return
        labs = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.InsectLab)
        if not labs: return
        lab = labs[0]
        if state['start'] is None:
            lab.configure_biome_experiment(json.dumps(dict(seed=command['seed'], synchronous=False, **command.get('overrides', {}))))
            state.update(start=now, last_alive=now)
            state['render'] = {k:unreal.SystemLibrary.get_console_variable_float_value(k) for k in ('t.MaxFPS', 'r.ScreenPercentage', 'ShowFlag.Rendering')}
            for key, value in [('t.MaxFPS', 60), ('r.ScreenPercentage', 100), ('ShowFlag.Rendering', 2)]:
                unreal.SystemLibrary.execute_console_command(w, f'{key} {value}')
        age = now-state['start']
        if age > 5 and state['last_frame'] is not None: state['frames'].append(now-state['last_frame'])
        state['last_frame'] = now
        if age-state['last_sample'] >= 2:
            snap = json.loads(lab.snapshot_json())
            row = dict(run_wall=age, **snap)
            trace.write(json.dumps(row)+'\n')
            state['last_sample'] = age
            if snap['status'].startswith('LIVE'): state['last_alive'] = now
            if now-state['last_alive'] > 60: raise RuntimeError('No healthy brain service for 60 seconds')
            if age-state['last_progress'] >= 10:
                (folder/'progress.json').write_text(json.dumps(row))
                state['last_progress'] = age
            if age >= command['minimum_wall'] and snap['elapsed'] >= command['duration_world']:
                finish()
    except Exception:
        finish(traceback.format_exc())

state['handle'] = unreal.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
