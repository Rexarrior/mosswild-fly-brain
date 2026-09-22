"""Controlled gameplay checks; long ecological runs are recorded separately."""
import json
import math
from pathlib import Path
import time
import traceback
import unreal
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not levels.is_in_play_in_editor()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert levels.load_level('/Game/Maps/Mosswild')
report=Path(unreal.Paths.project_saved_dir())/'BrainLab/biome-smoke.json'
performance=unreal.get_default_object(unreal.load_class(None,'/Script/UnrealEd.EditorPerformanceSettings'))
old=performance.get_editor_property('bThrottleCPUWhenNotForeground')
performance.set_editor_property('bThrottleCPUWhenNotForeground',False)
state=dict(handle=None,start=time.monotonic(),stage='warmup',t=0,checks={},samples=[])
report.write_text(json.dumps({'status':'running'}))
def finish(success,error=None):
    if error:
        w=editor.get_game_world()
        labs=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.InsectLab) if w else []
        if labs:state['samples'].append(dict(check='failed_'+state['stage'],**json.loads(labs[0].snapshot_json())))
    report.write_text(json.dumps(dict(status='completed',success=success,error=error,checks=state['checks'],samples=state['samples']),indent=2))
    unreal.unregister_slate_post_tick_callback(state['handle'])
    levels.editor_request_end_play()
    performance.set_editor_property('bThrottleCPUWhenNotForeground',old)
def tick(_):
    try:
        if time.monotonic()-state['start']>450:raise TimeoutError(state['stage'])
        w=editor.get_game_world()
        if not w:return
        labs=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.InsectLab)
        if not labs:return
        lab=labs[0];hero=unreal.GameplayStatics.get_player_character(w,0)
        now=unreal.GameplayStatics.get_time_seconds(w);snap=json.loads(lab.snapshot_json());elapsed=now-state['t']
        def stage(name):
            state.update(stage=name,t=now)
            state['samples'].append(dict(check=name,**snap))
            report.write_text(json.dumps(dict(status='running',stage=name,checks=state['checks']),indent=2))
        def teleport(actor,x,y,z=55):actor.set_actor_location(unreal.Vector(x,y,z),False,True)
        def agents():return list(lab.get_editor_property('agents'))
        s=state['stage']
        if s=='warmup' and snap['batches']>=3:
            assert snap['stage']==10 and snap['alive']==6
            assert {a['backend'] for a in snap['agents']}=={'siliconfly','flybrain'}
            state['checks']['full_backends']=True
            assert snap['continuous_economy'] and snap['maintenance_spent']>0
            expected=120+snap['food_delivered']-30*(snap['births']+snap['eggs'])-snap['maintenance_spent']-snap['spoiled_food']
            assert abs(expected-snap['cyan_store']-snap['amber_store'])<.1
            state['checks']['continuous_upkeep_and_resource_balance']=True
            assert all(unreal.load_asset('/Game/BrainLab/M_'+name).get_editor_property('used_with_instanced_static_meshes') for name in ('Cyan','Amber'))
            state['checks']['colony_material_instancing']=True
            assert snap['predict_senses'] and 0<snap['sensory_lookahead_ms']<=400.1
            state['checks']['latency_prediction_enabled']=snap['sensory_lookahead_ms']
            hero.toggle_map();assert hero.is_map_open();state['pos']=hero.get_actor_location();stage('map')
        elif s=='map':
            hero.move_forward(1);hero.move_right(1)
            if elapsed>1:
                assert hero.get_actor_location().distance(state['pos'])<3
                hero.toggle_map();state['checks']['map_blocks_movement']=True
                a=agents()[0];teleport(a,-2250,-200);a.set_editor_property('hydration',15.);a.set_editor_property('energy',100.)
                state['victim']=a;stage('water')
        elif s=='water' and state['victim'].get_editor_property('hydration')>75:
            state['checks']['water_trip']=True
            # Start the feeding fixture with replenished food and no unfinished
            # drinking commitment from the preceding independent check.
            lab.reset_experiment(False)
            a=agents()[0];teleport(a,-3100,-1650);a.set_editor_property('energy',65.);a.set_editor_property('hydration',100.)
            state['victim']=a
            stage('food')
        elif s=='water' and elapsed>35:raise AssertionError('No drinking after approaching spring')
        elif s=='food' and state['victim'].get_editor_property('energy')>105:
            state['checks']['feeding']=True
            stage('cargo')
        elif s=='food' and elapsed>35:raise AssertionError('No food after approaching orchard')
        elif s=='cargo' and snap['food_delivered']>0:
            state['checks']['natural_delivery']=snap['food_delivered']
            lab.reset_experiment(False);teleport(hero,-4200,2600,110)
            a=agents()[0];teleport(a,-180,0);a.set_editor_property('energy',65.);a.set_editor_property('hydration',100.)
            stage('claim_food')
        elif s=='claim_food' and snap['resources'][8]['owner']==0 and snap['resources'][8]['claim']>2:
            state['checks']['remote_food_claimed']=True
            teleport(hero,-300,0,110);stage('claim_player')
        elif s=='claim_food' and elapsed>35:raise AssertionError('No claim after feeding at remote shrine')
        elif s=='claim_player' and snap['player_hits']>0:
            state['checks']['claimed_patch_defends_against_player']=True
            lab.reset_experiment(False);teleport(hero,-4200,2600,110)
            aa=agents();teleport(aa[0],-2450,-700);teleport(aa[3],-2050,-700)
            stage('territory')
        elif s=='claim_player' and elapsed>35:raise AssertionError('No defence of acquired territory outside nest')
        elif s=='cargo' and elapsed>65:raise AssertionError('No delivery to a nest')
        elif s=='territory' and snap['fights']>0:
            state['checks']['territory_combat']=snap['fights']
            lab.reset_experiment(False)
            # Keep the normal separated spawn positions. The nest centre is
            # already occupied by NPC2; teleporting NPC1 there traps both bodies.
            teleport(hero,-3130,-860,110)
            stage('player')
        elif s=='territory' and elapsed>35:raise AssertionError('No NPC territory defence')
        elif s=='player' and snap['player_hits']>0:
            assert snap['player_health']<100
            state['checks']['player_attacked']=snap['player_hits']
            before={a.get_editor_property('agent_id'):a.get_editor_property('health') for a in agents()}
            lab.player_strike()
            assert any(a.get_editor_property('health')<before[a.get_editor_property('agent_id')] for a in agents())
            state['checks']['player_strike']=True
            state['struck']=next(a for a in agents() if a.get_editor_property('health')<before[a.get_editor_property('agent_id')])
            state['struck_health']=state['struck'].get_editor_property('health');state['cooldown_checked']=False
            stage('strike_cooldown')
        elif s=='player' and elapsed>35:raise AssertionError('No attack on territorial player')
        elif s=='strike_cooldown':
            a=state['struck']
            if elapsed>.4 and not state['cooldown_checked']:
                lab.player_strike();assert abs(a.get_editor_property('health')-state['struck_health'])<.01,'Strike cooldown too short'
                state['cooldown_checked']=True
            if elapsed>.8:
                p=a.get_actor_location();teleport(hero,p.x-100,p.y,110)
                before=a.get_editor_property('health');lab.player_strike();assert a.get_editor_property('health')<before,'Repeated strike failed after cooldown'
                state['checks']['strike_cooldown']=True
                teleport(hero,-4200,2600,110);lab.reset_experiment(True);stage('ablation_warmup')
        elif s=='ablation_warmup' and snap['batches']>=3:
            state['initial']={a['id']:(a['x'],a['y']) for a in snap['agents']};stage('ablation')
        elif s=='ablation' and elapsed>10:
            drift=max(math.hypot(a['x']-state['initial'][a['id']][0],a['y']-state['initial'][a['id']][1]) for a in snap['agents'])
            assert drift<1 and snap['meals']==0 and snap['births']==0,(drift,snap)
            assert all(a['forward_hz']==0 for a in snap['agents'])
            state['checks']['synapse_ablation_stops_behaviour']=dict(drift_cm=drift,meals=snap['meals'])
            lab.reset_experiment(False);stage('recovered')
        elif s=='recovered' and snap['batches']>=5:
            assert any(a['drive']>.1 for a in snap['agents'])
            state['checks']['reset_restores_brain']=True
            state['extinction_time']=snap['elapsed']
            for a in agents():a.set_editor_property('health',0.)
            stage('extinction')
        elif s=='extinction' and elapsed>2:
            assert snap['alive']==0 and not snap['agents'],snap
            assert snap['elapsed']>state['extinction_time']+.5,'Empty-world ecology stopped before cleanup'
            state['checks']['extinction_cleans_up_and_clock_continues']=True
            lab.reset_experiment(False);stage('extinction_reset')
        elif s=='extinction_reset' and snap['batches']>=3:
            assert snap['alive']==6
            state['checks']['reset_after_extinction']=True
            lab.set_drought(True)
            dry=json.loads(lab.snapshot_json())
            assert all(p['amount']==0 for p in dry['resources'][:13])
            assert all(p['amount']>999 for p in dry['resources'][13:])
            a=agents()[0];a.set_editor_property('energy',1.);a.set_editor_property('health',10.)
            stage('drought')
        elif s=='drought' and snap['starvation_deaths']>0:
            state['checks']['food_absence_causes_starvation']=True
            state['checks']['drought_preserves_springs']=all(p['amount']>999 for p in snap['resources'][13:])
            assert state['checks']['drought_preserves_springs']
            lab.set_drought(False);lab.reset_experiment(False);stage('rain_reset')
        elif s=='drought' and elapsed>25:raise AssertionError('Starvation fixture did not consume its last energy')
        elif s=='rain_reset' and snap['batches']>=3:
            assert snap['alive']==6 and snap['resources'][0]['amount']>0
            state['checks']['rain_and_reset_restore_food']=True
            finish(True)
    except Exception:finish(False,traceback.format_exc())
state['handle']=unreal.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
