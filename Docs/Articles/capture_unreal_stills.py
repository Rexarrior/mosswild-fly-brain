"""Capture real NPC geometry in a temporary PIE session, without saving assets.

Run with: python3 Scripts/ue.py script Docs/Articles/capture_unreal_stills.py
Requires this project's editor to be open, stopped, and without dirty maps.
The neural service is not needed: the lab is paused for the portrait.
"""
import json
from pathlib import Path
import time
import traceback

import unreal

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not levels.is_in_play_in_editor(), 'Stop the current game before taking portraits'
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), 'A map has unsaved changes'
original_map = editor.get_editor_world().get_path_name().split('.')[0]
original_view = editor.get_level_viewport_camera_info()
root = Path(unreal.Paths.project_dir()).resolve()
output = root / 'Docs/Articles/assets/mosswild-beetle.jpg'
assert not output.exists(), 'Existing article portrait will not be overwritten'
report = root / 'Saved/BrainLab/analysis/habr-editing-20260921/capture.json'
report.parent.mkdir(parents=True, exist_ok=True)
performance = unreal.get_default_object(unreal.load_class(None, '/Script/UnrealEd.EditorPerformanceSettings'))
old_throttle = performance.get_editor_property('bThrottleCPUWhenNotForeground')
performance.set_editor_property('bThrottleCPUWhenNotForeground', False)
assert levels.load_level('/Game/Maps/Mosswild')
state = {'handle': None, 'started': time.monotonic(), 'stage': 'starting', 'shot_at': None, 'agent': None, 'error': None}


def finish(error=None):
    state['error'] = error
    state['stage'] = 'ending'
    levels.editor_request_end_play()


def tick(_):
    try:
        now = time.monotonic()
        if state['stage'] == 'ending':
            if levels.is_in_play_in_editor():
                return
            performance.set_editor_property('bThrottleCPUWhenNotForeground', old_throttle)
            if original_map != '/Game/Maps/Mosswild':
                levels.load_level(original_map)
            editor.set_level_viewport_camera_info(*original_view)
            report.write_text(json.dumps({
                'status': 'error' if state['error'] else 'complete',
                'error': state['error'], 'output': str(output), 'agent': state['agent'],
                'kind': 'real Unreal screenshot in paused PIE, newly captured for the article',
                'original_map': original_map,
                'dirty_maps': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
            }, indent=2))
            unreal.unregister_slate_post_tick_callback(state['handle'])
            return
        if now - state['started'] > 90:
            raise TimeoutError('Portrait capture took too long')
        world = editor.get_game_world()
        if not world:
            return
        if state['stage'] == 'starting':
            labs = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InsectLab)
            if not labs or not labs[0].get_editor_property('agents'):
                return
            lab = labs[0]
            if not lab.get_editor_property('paused'):
                lab.toggle_pause()
            insects = lab.get_editor_property('agents')
            beetle = next(a for a in insects if a.get_editor_property('colony') == 0 and a.get_editor_property('form') == 0)
            # Move the paused actor onto open ground for a staged portrait.
            # This only changes the temporary PIE world, never the saved map.
            beetle.set_actor_location(beetle.get_actor_location() + unreal.Vector(650, -500, 0), False, True)
            state['agent'] = {'id': beetle.get_editor_property('agent_id'), 'form': 0, 'colony': 0}
            hero = unreal.GameplayStatics.get_player_character(world, 0)
            controller = unreal.GameplayStatics.get_player_controller(world, 0)
            controller.client_set_hud(unreal.HUD)
            camera = hero.get_component_by_class(unreal.CameraComponent)
            camera.set_absolute(True, True, False)
            target = beetle.get_actor_location() + unreal.Vector(10, 0, 8)
            location = target + unreal.Vector(230, -260, 180)
            rotation = unreal.MathLibrary.find_look_at_rotation(location, target)
            camera.set_world_location_and_rotation(location, rotation, False, True)
            camera.set_field_of_view(48)
            unreal.SystemLibrary.execute_console_command(world, 'r.ScreenPercentage 100')
            unreal.SystemLibrary.execute_console_command(world, 'ShowFlag.Rendering 2')
            state['stage'] = 'settling'
            state['ready_at'] = now + 3
        elif state['stage'] == 'settling' and now >= state['ready_at']:
            unreal.SystemLibrary.execute_console_command(world, f'Shot filename={output} -nosuffix')
            state['stage'] = 'capturing'
            state['shot_at'] = now
        elif state['stage'] == 'capturing' and now - state['shot_at'] >= 2:
            assert output.is_file() and output.stat().st_size > 10000, 'Screenshot file missing'
            finish()
    except Exception:
        finish(traceback.format_exc())


state['handle'] = unreal.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
