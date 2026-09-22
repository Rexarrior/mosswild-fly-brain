"""Repair the old Euler-angle migration on generated brook segments only."""
import math
import unreal

levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not levels.is_in_play_in_editor()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert levels.load_level('/Game/Maps/Mosswild')
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
by_name={a.get_actor_label():a for a in actors.get_all_level_actors()}
changes=[]
for i in range(16):
    dx=(math.sin((i+1)*.6)-math.sin(i*.6))*350
    yaw=math.degrees(math.atan2(500,dx))
    names=[f'Brook_{i:02d}']+([f'Brook_glint_{i:02d}'] if i%3==0 else [])
    for name in names:
        actor=by_name[name]
        assert 'MosswildGenerated' in [str(t) for t in actor.tags],name
        changes.append((actor,yaw))
for actor,yaw in changes:
    actor.set_actor_rotation(unreal.Rotator(pitch=0,yaw=yaw,roll=0),True)
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world,'MAP CHECK')
assert levels.save_current_level()
unreal.log(f'MOSSWILD_WATER_REPAIRED: {len(changes)} decorative segments')
