"""Persist instanced-mesh support on the two materials used by colony trails."""
import unreal

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not levels.is_in_play_in_editor()
for name in ('Cyan', 'Amber'):
    material = unreal.load_asset('/Game/BrainLab/M_' + name)
    assert material
    material.set_editor_property('used_with_instanced_static_meshes', True)
    unreal.MaterialEditingLibrary.recompile_material(material)
    assert unreal.EditorAssetLibrary.save_loaded_asset(material, False)
    assert material.get_editor_property('used_with_instanced_static_meshes')
unreal.log('BRAIN_MATERIAL_INSTANCING_SAVED')
