"""Bounded negative control: unfunded nest care decays without fabricated food."""
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
base=Path(unreal.Paths.project_saved_dir()).resolve()/'BrainLab'
name='scarcity-'+time.strftime('%Y%m%d-%H%M%S')
report=base/(name+'.json')
(base/'scarcity-latest.json').write_text(json.dumps(dict(report=str(report))))
performance=unreal.get_default_object(unreal.load_class(None,'/Script/UnrealEd.EditorPerformanceSettings'))
old=performance.get_editor_property('bThrottleCPUWhenNotForeground')
performance.set_editor_property('bThrottleCPUWhenNotForeground',False)
state=dict(handle=None,started=time.monotonic(),configured=False)

def finish(data):
    report.write_text(json.dumps(data,indent=2)+'\n')
    unreal.unregister_slate_post_tick_callback(state['handle'])
    levels.editor_request_end_play()
    performance.set_editor_property('bThrottleCPUWhenNotForeground',old)

def tick(_):
    try:
        if time.monotonic()-state['started']>180:raise TimeoutError('Scarcity fixture')
        w=editor.get_game_world()
        labs=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.InsectLab) if w else []
        if not labs:return
        lab=labs[0]
        if not state['configured']:
            lab.configure_biome_experiment(json.dumps(dict(name=name,synchronous=True,duration=111,step=.5,
                continuous_economy=True,upkeep_per_adult=.8,ablate=True)))
            state['configured']=True
        snap=json.loads(lab.snapshot_json())
        if snap['elapsed']>=110:
            assert snap['births']==0 and snap['food_delivered']==0 and snap['alive']==6
            assert all(c['store']<.01 and c['condition']<.55 and c['unfunded_seconds']>60 for c in snap['colonies'])
            assert abs(120-snap['maintenance_spent']-snap['spoiled_food']-snap['cyan_store']-snap['amber_store'])<.1
            assert all(a['distance']<1 for a in snap['agents'])
            finish(dict(status='passed',checks=['unfunded_nests_deteriorate','no_unearned_food','food_balance','ablation_still_blocks_motion'],snapshot=snap))
    except Exception:finish(dict(status='failed',error=traceback.format_exc()))

state['handle']=unreal.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
