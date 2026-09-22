"""Create an isolated experiment map once; preserve existing maps and edited assets."""
import math
import random
import unreal

MAP='/Game/Maps/Insectarium'
assets=unreal.EditorAssetLibrary
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
tools=unreal.AssetToolsHelpers.get_asset_tools()

def main():
    recovering=globals().get('RECOVER_EMPTY_BUILD',False)
    if assets.does_asset_exist(MAP) and not recovering:
        unreal.log('INSECTARIUM_EXISTS: preserved'); return
    assert not levels.is_in_play_in_editor()
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), 'Save map edits first'
    if recovering:
        assert levels.load_level(MAP)
        assert not any(a.get_actor_label().startswith('Lab_') for a in actors.get_all_level_actors()), 'Recovery is only for an empty initial map'
    else:
        assert levels.new_level(MAP)
    palette={'Cyan':(.06,.68,.60),'Amber':(.94,.39,.07),'Dark':(.028,.065,.078),'Eye':(.85,.94,.57),
             'Green':(.39,.81,.12),'Ground':(.10,.16,.15),'Tile':(.16,.23,.21),'Stone':(.26,.34,.31),
             'Pale':(.60,.70,.59),'Soil':(.12,.10,.07),'Leaf':(.16,.34,.20),'Glass':(.16,.32,.36)}
    materials={}
    for name,color in palette.items():
        path='/Game/BrainLab/M_'+name
        if assets.does_asset_exist(path): materials[name]=unreal.load_asset(path); continue
        mat=tools.create_asset('M_'+name,'/Game/BrainLab',unreal.Material,unreal.MaterialFactoryNew())
        if name in ('Cyan','Amber'):
            mat.set_editor_property('used_with_instanced_static_meshes',True)
        node=unreal.MaterialEditingLibrary.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector)
        node.constant=unreal.LinearColor(*color,1)
        unreal.MaterialEditingLibrary.connect_material_property(node,'',unreal.MaterialProperty.MP_BASE_COLOR)
        rough=unreal.MaterialEditingLibrary.create_material_expression(mat,unreal.MaterialExpressionConstant)
        rough.r=.38 if name in ('Cyan','Amber','Eye') else .85
        unreal.MaterialEditingLibrary.connect_material_property(rough,'',unreal.MaterialProperty.MP_ROUGHNESS)
        if name in ('Cyan','Amber','Eye','Green'):
            mult=unreal.MaterialEditingLibrary.create_material_expression(mat,unreal.MaterialExpressionMultiply)
            mult.set_editor_property('const_b',.2)
            unreal.MaterialEditingLibrary.connect_material_expressions(node,'',mult,'A')
            unreal.MaterialEditingLibrary.connect_material_property(mult,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        unreal.MaterialEditingLibrary.recompile_material(mat)
        assets.save_loaded_asset(mat,False); materials[name]=mat
    meshes={name:unreal.load_asset('/Engine/BasicShapes/'+name) for name in ['Cube','Sphere','Cylinder','Cone']}
    def mesh(label,p,size,material,shape='Cube',yaw=0,solid=False,folder='Lab / Scenery'):
        a=actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*p),unreal.Rotator(0,yaw,0))
        a.set_actor_label(label); a.set_folder_path(folder); a.tags=['InsectariumGenerated']
        a.set_actor_scale3d(unreal.Vector(*(v/100 for v in size)))
        c=a.static_mesh_component; c.set_static_mesh(meshes[shape]); c.set_material(0,materials[material])
        c.set_collision_profile_name('BlockAll' if solid else 'NoCollision')
        if not solid: c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        return a
    mesh('Lab_Floor',(0,0,-60),(4400,4000,120),'Ground',solid=True,folder='Lab / Terrain')
    for x in range(-2000,2001,400):
        mesh('Floor_GridX_'+str(x),(x,0,1),(3,3900,2),'Tile')
    for y in range(-1800,1801,400):
        mesh('Floor_GridY_'+str(y),(0,y,1),(4300,3,2),'Tile')
    for side in [-1,1]:
        mesh('Lab_WallX_'+str(side),(side*2200,0,70),(50,4050,260),'Stone',solid=True,folder='Lab / Terrain')
        mesh('Lab_WallY_'+str(side),(0,side*2000,70),(4400,50,260),'Stone',solid=True,folder='Lab / Terrain')
        for x in range(-2000,2001,500):
            mesh('EdgeLamp_%s_%s'%(x,side),(x,side*1960,160),(35,35,25),'Eye')
    for colony,x,mat in [('Silicon',-650,'Cyan'),('FlyBrain',650,'Amber')]:
        for i in range(64):
            a=2*math.pi*i/64
            mesh(colony+'_Territory_%02d'%i,(x+850*math.cos(a),850*math.sin(a),3),(57,9,4),mat,yaw=math.degrees(a)+90,folder='Lab / Territories')
        mesh(colony+'_Nest',(x,0,8),(245,245,16),'Soil','Cylinder')
        for i in range(7):
            a=i*2*math.pi/7
            mesh(colony+'_NestStone_'+str(i),(x+95*math.cos(a),95*math.sin(a),17),(55,45,32),mat,'Sphere')
        mesh(colony+'_NestBeacon',(x,0,45),(20,20,90),mat,'Cone')
    for i,(x,y) in enumerate([(-750,-460),(-750,460),(750,-460),(750,460),(0,-300),(0,300),(-220,0),(220,0)]):
        mesh('FoodBed_'+str(i),(x,y,4),(175,175,8),'Soil','Cylinder')
        for j in range(5):
            a=j*2*math.pi/5
            mesh('Sprout_%d_%d'%(i,j),(x+65*math.cos(a),y+65*math.sin(a),20),(25,14,45),'Leaf','Cone',yaw=math.degrees(a))
    rng=random.Random(17)
    for i in range(28):
        x=rng.uniform(-2050,2050); y=rng.choice([-1,1])*rng.uniform(1650,1850)
        mesh('BoundaryFern_%02d'%i,(x,y,35),(rng.uniform(80,150),80,90),'Leaf','Cone')
    mesh('Observation_Deck',(-1450,1350,5),(650,700,10),'Tile')
    for i in range(7):
        mesh('Deck_Stripe_'+str(i),(-1650+i*70,1300,12),(35,430,4),'Pale')
    start=actors.spawn_actor_from_class(unreal.PlayerStart,unreal.Vector(-1250,1250,110))
    start.set_actor_label('Insectarium_PlayerStart')
    lab=actors.spawn_actor_from_class(unreal.load_class(None,'/Script/RPGPrototype.InsectLab'),unreal.Vector())
    lab.set_actor_label('Insectarium_Controller'); lab.set_folder_path('Lab / Simulation')
    light=actors.spawn_actor_from_class(unreal.DirectionalLight,unreal.Vector(0,0,1500),unreal.Rotator(-55,-35,0))
    light.set_actor_label('Lab_Sun'); light.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    light.light_component.set_editor_property('intensity',4.0)
    sky=actors.spawn_actor_from_class(unreal.SkyLight,unreal.Vector(0,0,600))
    sky.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    sky.light_component.set_editor_property('intensity',1.3)
    sky.light_component.set_editor_property('real_time_capture',True)
    actors.spawn_actor_from_class(unreal.SkyAtmosphere,unreal.Vector())
    fog=actors.spawn_actor_from_class(unreal.ExponentialHeightFog,unreal.Vector(0,0,-300))
    fog.component.set_editor_property('fog_density',.006)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    world.get_world_settings().set_editor_property('force_no_precomputed_lighting',True)
    unreal.SystemLibrary.execute_console_command(world,'MAP CHECK')
    assert levels.save_current_level()
    unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(unreal.Vector(-2500,2500,2600),unreal.Rotator(-42,-45,0))
    unreal.log('INSECTARIUM_CREATED')

main()
