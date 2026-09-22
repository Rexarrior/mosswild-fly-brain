"""Real PIE integration: independent brains, feeding, brood, combat, starvation and ablation."""
import json
import math
from pathlib import Path
import time
import traceback
import unreal

levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not levels.is_in_play_in_editor(), 'Stop PIE first'
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), 'Save map edits first'
assert levels.load_level('/Game/Maps/Insectarium')
world=editor.get_editor_world()
unreal.SystemLibrary.execute_console_command(world,'MAP CHECK')
report_path=Path(unreal.Paths.project_saved_dir())/'BrainLab/ue-smoke.json'
performance=unreal.get_default_object(unreal.load_class(None,'/Script/UnrealEd.EditorPerformanceSettings'))
original_throttle=performance.get_editor_property('bThrottleCPUWhenNotForeground')
performance.set_editor_property('bThrottleCPUWhenNotForeground',False)
state={'handle':None,'start':time.monotonic(),'stage':'warmup','t':0,'checks':{},'samples':[],'last_sample':0}
report_path.write_text(json.dumps({'status':'running'}))

def finish(success,error=None):
    report={'status':'completed','success':success,'error':error,'checks':state['checks'],'samples':state['samples']}
    report_path.write_text(json.dumps(report,indent=2))
    unreal.log('BRAINLAB_SMOKE '+json.dumps({k:v for k,v in report.items() if k!='samples'}))
    unreal.unregister_slate_post_tick_callback(state['handle'])
    levels.editor_request_end_play()
    performance.set_editor_property('bThrottleCPUWhenNotForeground',original_throttle)

def tick(_dt):
    try:
        if time.monotonic()-state['start']>360: raise RuntimeError('Timed out at '+state['stage'])
        w=editor.get_game_world()
        if not w: return
        labs=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.load_class(None,'/Script/RPGPrototype.InsectLab'))
        if not labs: return
        lab=labs[0]; hero=unreal.GameplayStatics.get_player_character(w,0)
        now=unreal.GameplayStatics.get_time_seconds(w)
        snap=json.loads(lab.snapshot_json())
        if now-state['last_sample']>2:
            state['samples'].append(dict(stage=state['stage'],**snap)); state['last_sample']=now
            report_path.write_text(json.dumps({'status':'running','stage':state['stage'],'latest':snap,'checks':state['checks']},indent=2))
        def stage(s): state['stage']=s; state['t']=now
        def teleport(actor,x,y,z=55): actor.set_actor_location(unreal.Vector(x,y,z),False,True)
        elapsed=now-state['t']; s=state['stage']
        if s=='warmup' and snap['batches']>=3:
            assert snap['alive']==6
            assert {a['backend'] for a in snap['agents']}=={'siliconfly','flybrain'}
            state['initial']={a['id']:(a['x'],a['y']) for a in snap['agents']}
            state['checks']['six_independent_brains']=True
            stage('ecology')
        elif s=='ecology' and elapsed>65:
            observations=[a for sample in state['samples'] if sample['stage']=='ecology' for a in sample['agents']]
            moved={backend:max([math.hypot(a['x']-state['initial'][a['id']][0],a['y']-state['initial'][a['id']][1]) for a in observations if a['backend']==backend and a['id'] in state['initial']] or [0]) for backend in ['siliconfly','flybrain']}
            assert all(d>100 for d in moved.values()), moved
            assert snap['meals']>0,'No natural feeding'
            assert snap['births']>0,'No natural births after 65 seconds'
            state['checks']['natural_ecology']=dict(moved_cm=moved,meals=snap['meals'],births=snap['births'],fights=snap['fights'],alive=snap['alive'])
            unreal.SystemLibrary.execute_console_command(w,'HighResShot 1600x1000 filename=Insectarium_Ecology')
            stage('ecology_capture')
        elif s=='ecology_capture' and elapsed>1:
            # Controlled encounter fixture: real brains must close 400cm then fight.
            lab.reset_experiment(False)
            agents=list(lab.get_editor_property('agents'))
            teleport(agents[0],-200,0); teleport(agents[3],200,0)
            teleport(hero,-1250,1250,110)
            stage('territory')
        elif s=='territory' and snap['fights']>=2:
            state['checks']['territory_combat']=snap['fights']
            agents=list(lab.get_editor_property('agents'))
            victim=next(a for a in agents if a.get_editor_property('colony')==0)
            teleport(victim,-500,0); teleport(hero,-750,0,110)
            state['hits_before']=snap['player_hits']; stage('player')
        elif s=='territory' and elapsed>35: raise AssertionError('No territory fighting')
        elif s=='player' and snap['player_hits']>state['hits_before']:
            assert snap['player_health']<100
            state['checks']['player_defence']=dict(hits=snap['player_hits'],health=snap['player_health'])
            agents=list(lab.get_editor_property('agents'))
            before={a.get_editor_property('agent_id'):a.get_editor_property('health') for a in agents}
            lab.player_strike()
            assert any(a.get_editor_property('health')<before[a.get_editor_property('agent_id')] for a in agents),'Player strike did not damage nearby insects'
            state['checks']['player_strike']=True
            teleport(hero,-1250,1250,110)
            lab.set_drought(True)
            # Start near starvation to verify the in-engine death path promptly.
            for a in agents:
                a.set_editor_property('energy',.01); a.set_editor_property('health',3.)
            for a in agents: teleport(a, -1300 if a.get_editor_property('colony')==0 else 1300, -1000)
            stage('starvation')
        elif s=='player' and elapsed>35: raise AssertionError('Territorial NPC failed to bite player')
        elif s=='starvation' and snap['alive']==0:
            state['checks']['starvation_death']=snap['deaths']
            lab.reset_experiment(True); stage('ablation_warmup')
        elif s=='starvation' and elapsed>15: raise AssertionError('Starvation did not kill insects')
        elif s=='ablation_warmup' and snap['batches']>=3:
            state['ablated_initial']={a['id']:(a['x'],a['y']) for a in snap['agents']}; stage('ablation')
        elif s=='ablation' and elapsed>12:
            drift=max(math.hypot(a['x']-state['ablated_initial'][a['id']][0],a['y']-state['ablated_initial'][a['id']][1]) for a in snap['agents'])
            assert drift<25, f'Ablation displacement {drift}'
            assert snap['births']==0 and snap['meals']==0
            state['checks']['ablation']=dict(max_drift_cm=drift,meals=snap['meals'],births=snap['births'])
            state['checks']['finite_outputs']=all(math.isfinite(a[k]) for a in snap['agents'] for k in ['turn','drive','left_hz','right_hz','forward_hz'])
            lab.reset_experiment(False); stage('final')
        elif s=='final' and snap['batches']>=5:
            unreal.SystemLibrary.execute_console_command(w,'HighResShot 1600x1000 filename=Insectarium_Ready')
            stage('capture')
        elif s=='capture' and elapsed>1: finish(True)
    except Exception:
        finish(False,traceback.format_exc())

state['handle']=unreal.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
