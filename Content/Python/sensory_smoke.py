"""Real PIE contact mechanics and ablation, with goal selection disabled."""
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
unreal.SystemLibrary.execute_console_command(editor.get_editor_world(),'MAP CHECK')
control=globals().get('motor_controller','connectome')
report=Path(unreal.Paths.project_saved_dir())/globals().get('report_name','BrainLab/sensory/smoke.json')
report.parent.mkdir(parents=True,exist_ok=True)
assert not report.exists(),'Preserve the previous smoke evidence'
performance=unreal.get_default_object(unreal.load_class(None,'/Script/UnrealEd.EditorPerformanceSettings'))
old_throttle=performance.get_editor_property('bThrottleCPUWhenNotForeground')
performance.set_editor_property('bThrottleCPUWhenNotForeground',False)
state=dict(handle=None,start=time.monotonic(),stage='start',t=0,checks={},samples=[])

def finish(error=None):
    report.write_text(json.dumps(dict(status='failed' if error else 'passed',error=error,
                                     checks=state['checks'],samples=state['samples']),indent=2)+'\n')
    unreal.unregister_slate_post_tick_callback(state['handle'])
    levels.editor_request_end_play()
    performance.set_editor_property('bThrottleCPUWhenNotForeground',old_throttle)

def tick(_):
    try:
        if time.monotonic()-state['start']>180:raise TimeoutError(state['stage'])
        w=editor.get_game_world()
        if not w:return
        labs=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.InsectLab)
        if not labs:return
        lab=labs[0];snap=json.loads(lab.snapshot_json());now=unreal.GameplayStatics.get_time_seconds(w)
        def transition(name):
            state.update(stage=name,t=now);state['samples'].append(dict(check=name,**snap))
            report.write_text(json.dumps(dict(status='running',stage=name,checks=state['checks'])))
        def teleport(actor,x,y,z=55):actor.set_actor_location(unreal.Vector(x,y,z),False,True)
        s=state['stage']
        if s=='start':
            lab.configure_biome_experiment(json.dumps(dict(sensory_competition=True,synchronous=False,seed=1701,swarm=False,
                motor_controller=control,contact_gate='contact' if control=='reactive-v1' else 'neural')))
            transition('warmup')
        elif s=='warmup' and snap['batches']>=4:
            assert snap['controller']=='sensory-populations-v1' and not snap['social_steering']
            assert all(a['goal']==-1 and a['resource']==-1 and len(a['sensory_channels'])==8 for a in snap['agents'])
            assert all(any(a['backend']==b and a['drive']>.05 for a in snap['agents']) for b in ('siliconfly','flybrain'))
            state['checks']['eight_channels_no_planner_both_colonies']=True
            assert snap['motor_controller']==control
            if control=='reactive-v1':
                assert snap['contact_gate']=='contact' and all(a['forward_hz']==a['left_hz']==a['right_hz']==0 for a in snap['agents'])
                state['checks']['reactive_without_fictitious_neural_rates']=True
            agents=list(lab.get_editor_property('agents'));state['pair']=[agents[0],agents[3]]
            for a,(x,y) in zip(state['pair'],[(-3100,-1470),(3100,1470)]):
                teleport(a,x,y);a.set_editor_property('energy',55.)
            transition('food')
        elif s=='food' and all(a.get_editor_property('energy')>85 for a in state['pair']):
            state['checks']['contact_feeding_both']=True
            for a,(x,y) in zip(state['pair'],[(-2000,-270),(2000,270)]):
                teleport(a,x,y);a.set_editor_property('hydration',15.)
            transition('water')
        elif s=='water' and all(a.get_editor_property('hydration')>65 for a in state['pair']):
            state['checks']['contact_drinking_both']=True
            state['delivered']=snap['food_delivered']
            for a,(x,y) in zip(state['pair'],[(-2920,-820),(2920,820)]):
                teleport(a,x,y);a.set_editor_property('cargo',20.)
            transition('delivery')
        elif s=='delivery' and snap['food_delivered']>=state['delivered']+39:
            state['checks']['contact_delivery_both']=True
            lab.reset_experiment(False)
            hero=unreal.GameplayStatics.get_player_character(w,0);teleport(hero,-2920,-860,110)
            transition('player')
        elif s=='player' and snap['player_hits']>0:
            state['checks']['contact_territorial_bite']=True
            hero=unreal.GameplayStatics.get_player_character(w,0)
            before={a.get_editor_property('agent_id'):a.get_editor_property('health') for a in lab.get_editor_property('agents')}
            lab.player_strike()
            assert any(a.get_editor_property('health')<before[a.get_editor_property('agent_id')] for a in lab.get_editor_property('agents'))
            state['checks']['player_strike']=True
            teleport(hero,-4200,3200,110)
            if control=='reactive-v1':
                lab.set_sensory_competition(False);transition('planner_restored')
            else:
                lab.reset_experiment(True);transition('ablation_warmup')
        elif s=='ablation_warmup' and snap['batches']>=4:
            state['initial']={a['id']:(a['x'],a['y']) for a in snap['agents']};transition('ablation')
        elif s=='ablation' and now-state['t']>6:
            drift=max(math.hypot(a['x']-state['initial'][a['id']][0],a['y']-state['initial'][a['id']][1]) for a in snap['agents'])
            assert drift<1 and all(a['forward_hz']==0 and a['drive']==0 for a in snap['agents'])
            assert snap['meals']==0
            state['checks']['ablation_no_hidden_steering']=dict(drift_cm=drift)
            lab.set_sensory_competition(False);transition('planner_restored')
        elif s=='planner_restored' and snap['batches']>=4:
            assert snap['controller']=='planner' and not snap['ablation']
            assert snap['motor_controller']=='connectome' and snap['contact_gate']=='neural'
            assert all(a['goal']>=0 and not a['sensory_channels'] for a in snap['agents'])
            state['checks']['toggle_restores_planner']=True
            finish()
        elif now-state['t']>35:raise AssertionError('No progress in '+s)
    except Exception:finish(traceback.format_exc())

state['handle']=unreal.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
