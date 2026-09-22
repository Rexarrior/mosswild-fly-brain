"""Leave a fresh playable biome running until the user stops it. No run timer."""
import json
from pathlib import Path
import time
import unreal

# Optional configuration supplied by a dedicated experiment launcher.
experiment_config = globals().get('experiment_config')
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not levels.is_in_play_in_editor(), 'The existing game is already running'
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert levels.load_level('/Game/Maps/Mosswild')
performance = unreal.get_default_object(unreal.load_class(None, '/Script/UnrealEd.EditorPerformanceSettings'))
old_throttle = performance.get_editor_property('bThrottleCPUWhenNotForeground')
performance.set_editor_property('bThrottleCPUWhenNotForeground', False)
report = Path(unreal.Paths.project_saved_dir()).resolve()/'BrainLab/live-launch.json'
state = dict(handle=None, start=time.monotonic(), render_set=False, ready=False, configured=False)
report.write_text(json.dumps(dict(status='starting')))

def tick(_):
    if state['ready']:
        if not levels.is_in_play_in_editor():
            performance.set_editor_property('bThrottleCPUWhenNotForeground', old_throttle)
            data=json.loads(report.read_text());data['status']='stopped_by_user'
            report.write_text(json.dumps(data,indent=2)+'\n')
            unreal.unregister_slate_post_tick_callback(state['handle'])
        return
    w = editor.get_game_world()
    if w and not state['render_set']:
        for key, value in [('t.MaxFPS', 60), ('r.ScreenPercentage', 100), ('ShowFlag.Rendering', 2)]:
            unreal.SystemLibrary.execute_console_command(w, f'{key} {value}')
        state['render_set'] = True
    labs = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.InsectLab) if w else []
    if labs:
        if not state['configured']:
            if experiment_config:
                labs[0].configure_biome_experiment(json.dumps(experiment_config))
            state['configured'] = True
        snap = json.loads(labs[0].snapshot_json())
        if snap['batches']>=3 and snap['status'].startswith('LIVE'):
            report.write_text(json.dumps(dict(status='live', automatic_stop=False,
                              background_throttling=False, snapshot=snap), indent=2)+'\n')
            # From here the callback only observes user Stop to restore the
            # temporary editor preference. It never requests EndPlay.
            state['ready']=True
            return
    if time.monotonic()-state['start']>90:
        report.write_text(json.dumps(dict(status='startup_not_verified', automatic_stop=False)))
        unreal.unregister_slate_post_tick_callback(state['handle'])
        # Deliberately do not end the user's simulation, even on a health-check timeout.

state['handle'] = unreal.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
