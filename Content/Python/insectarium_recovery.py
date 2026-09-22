"""Travel and external-service interruption check. Host responds to cut_service/start_service."""
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
path=Path(unreal.Paths.project_saved_dir())/'BrainLab/recovery.json'
state={'stage':'laboratory','start':time.monotonic(),'t':None,'checks':{},'handle':None}
performance=unreal.get_default_object(unreal.load_class(None,'/Script/UnrealEd.EditorPerformanceSettings'))
previous=performance.get_editor_property('bThrottleCPUWhenNotForeground')
performance.set_editor_property('bThrottleCPUWhenNotForeground',False)

def report(status='running',error=None):
    path.write_text(json.dumps(dict(status=status,stage=state['stage'],checks=state['checks'],error=error),indent=2))

def finish(ok,error=None):
    report('passed' if ok else 'failed',error)
    unreal.unregister_slate_post_tick_callback(state['handle'])
    levels.editor_request_end_play()
    performance.set_editor_property('bThrottleCPUWhenNotForeground',previous)

def tick(_dt):
    try:
        now=time.monotonic()
        if now-state['start']>180: raise RuntimeError('Recovery test timed out at '+state['stage'])
        w=editor.get_game_world()
        if not w: return
        hero=unreal.GameplayStatics.get_player_character(w,0)
        if not hero: return
        labs=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.load_class(None,'/Script/RPGPrototype.InsectLab'))
        lab=labs[0] if labs else None
        snap=json.loads(lab.snapshot_json()) if lab else None
        if state['t'] is None: state['t']=now
        elapsed=now-state['t']; s=state['stage']
        def stage(name): state['stage']=name; state['t']=now; report()
        if s=='laboratory' and elapsed>1:
            assert lab and not lab.get_editor_property('expanded_biome')
            hero.toggle_insect_lab(); stage('entering')
        elif s=='entering' and lab and lab.get_editor_property('expanded_biome') and snap['batches']>=8:
            assert 'Mosswild' in w.get_path_name(),w.get_path_name()
            state['checks']['laboratory_to_biome']=True
            stage('cut_service')
        elif s=='cut_service' and snap and 'OFFLINE' in snap['status']:
            state['before']=snap; stage('offline')
        elif s=='offline' and elapsed>4:
            before=state['before']
            assert abs(snap['elapsed']-before['elapsed'])<.01
            assert snap['alive']==before['alive']
            for a,b in zip(snap['agents'],before['agents']):
                assert abs(a['x']-b['x'])+abs(a['y']-b['y'])<.01
                assert abs(a['energy']-b['energy'])<.01
            state['checks']['offline_freezes_movement_and_energy']=True
            for key in ('cyan_store','amber_store','maintenance_spent','spoiled_food','food_delivered'):
                assert abs(snap[key]-before[key])<.01,(key,before[key],snap[key])
            state['checks']['offline_freezes_economy']=True
            state['old_batches']=snap['batches']; stage('start_service')
        elif s=='start_service' and snap and snap['batches']>state['old_batches']+3:
            state['checks']['service_recovery']=True
            state['session_folder']=Path(snap['telemetry_folder'])
            hero.toggle_insect_lab(); stage('returning')
        elif s=='returning' and lab and not lab.get_editor_property('expanded_biome') and elapsed>1:
            state['checks']['biome_to_laboratory']=True
            final=json.loads((state['session_folder']/'final.json').read_text())
            assert final['agents'] and final['colonies'] and final['maintenance_spent']>0
            assert (state['session_folder']/'end-reason.txt').read_text()=='end_play'
            state['checks']['ordinary_play_final_snapshot']=True
            hero.toggle_insect_lab(); stage('return_lab')
        elif s=='return_lab' and lab and snap['elapsed']>14:
            state['checks']['second_lab_session']=snap['alive']==6
            unreal.SystemLibrary.execute_console_command(w,'HighResShot 1600x1000 filename=Mosswild_Final')
            stage('capture')
        elif s=='capture' and elapsed>1.5:
            assert all(state['checks'].values())
            finish(True)
    except Exception: finish(False,traceback.format_exc())

report()
state['handle']=unreal.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
