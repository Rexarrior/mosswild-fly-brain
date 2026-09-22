"""Upgrade only generated static boulders; preserve the existing biome and edits."""
from pathlib import Path
import runpy
import unreal
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not levels.is_in_play_in_editor()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert levels.load_level('/Game/Maps/Mosswild')
helpers=runpy.run_path(str(Path(unreal.Paths.project_content_dir())/'Python/build_mosswild.py'))
mesh=helpers['boulder_mesh']()
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
changed=[]
for a in actors.get_all_level_actors():
    if a.get_actor_label().startswith('BlockingRock_') and 'MosswildGenerated' in [str(t) for t in a.tags]:
        a.static_mesh_component.set_static_mesh(mesh);changed.append(a.get_actor_label())
assert len(changed)==8,changed
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world,'MAP CHECK')
assert levels.save_current_level()
unreal.log('MOSSWILD_BOULDER_COLLISION '+str(changed))
