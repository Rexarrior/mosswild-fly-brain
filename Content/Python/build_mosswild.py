"""Create the six-times-larger Mosswild biome once, from shared ecology coordinates."""
import json
import math
from pathlib import Path
import random
import unreal

MAP='/Game/Maps/Mosswild'
assets=unreal.EditorAssetLibrary
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
tools=unreal.AssetToolsHelpers.get_asset_tools()

def boulder_mesh():
    # Non-uniformly scaled simple sphere collision does not match an ellipsoid.
    # The static boulders use their actual triangles for accurate contact.
    path='/Game/Mosswild/SM_Boulder'
    mesh=unreal.load_asset(path) if assets.does_asset_exist(path) else assets.duplicate_asset('/Engine/BasicShapes/Sphere',path)
    body=mesh.get_editor_property('body_setup')
    body.set_editor_property('collision_trace_flag',unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    assert assets.save_loaded_asset(mesh,False)
    return mesh

def main():
    if assets.does_asset_exist(MAP): unreal.log('MOSSWILD_EXISTS: preserved'); return
    assert not levels.is_in_play_in_editor()
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
    config=json.loads((Path(unreal.Paths.project_dir())/'Config/BrainBiome.json').read_text())
    palette={'Moss':(.13,.24,.115),'Meadow':(.23,.35,.15),'Earth':(.17,.11,.055),'Path':(.31,.25,.13),
             'Bark':(.15,.08,.045),'Leaf':(.12,.30,.19),'LeafLight':(.24,.44,.21),'Fern':(.32,.47,.19),
             'Stone':(.26,.33,.29),'StoneLight':(.43,.49,.36),'Cap':(.56,.19,.13),'CapLight':(.91,.59,.26),
             'Stem':(.64,.61,.41),'Water':(.08,.31,.35),'Foam':(.37,.64,.58),'Flower':(.60,.36,.70),
             'Pollen':(.92,.72,.22),'Rune':(.30,.81,.70)}
    mats={}
    for name,color in palette.items():
        path='/Game/Mosswild/M_'+name
        if assets.does_asset_exist(path): mats[name]=unreal.load_asset(path); continue
        mat=tools.create_asset('M_'+name,'/Game/Mosswild',unreal.Material,unreal.MaterialFactoryNew())
        node=unreal.MaterialEditingLibrary.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector)
        node.constant=unreal.LinearColor(*color,1)
        unreal.MaterialEditingLibrary.connect_material_property(node,'',unreal.MaterialProperty.MP_BASE_COLOR)
        rough=unreal.MaterialEditingLibrary.create_material_expression(mat,unreal.MaterialExpressionConstant)
        rough.r=.22 if name=='Water' else .86
        unreal.MaterialEditingLibrary.connect_material_property(rough,'',unreal.MaterialProperty.MP_ROUGHNESS)
        if name in ('Pollen','Rune','Foam'):
            mul=unreal.MaterialEditingLibrary.create_material_expression(mat,unreal.MaterialExpressionMultiply)
            mul.set_editor_property('const_b',.25)
            unreal.MaterialEditingLibrary.connect_material_expressions(node,'',mul,'A')
            unreal.MaterialEditingLibrary.connect_material_property(mul,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        unreal.MaterialEditingLibrary.recompile_material(mat); assets.save_loaded_asset(mat,False);mats[name]=mat
    for n in ('Cyan','Amber','Green','Eye','Dark'):mats[n]=unreal.load_asset('/Game/BrainLab/M_'+n)
    assert levels.new_level(MAP)
    meshes={n:unreal.load_asset('/Engine/BasicShapes/'+n) for n in ('Cube','Sphere','Cone','Cylinder')}
    meshes['Boulder']=boulder_mesh()
    rng=random.Random(4007)
    def mesh(label,p,size,mat,shape='Cube',rotation=(0,0,0),solid=False,folder='Mosswild / Scenery'):
        a=actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*p),unreal.Rotator(pitch=rotation[0],yaw=rotation[1],roll=rotation[2]))
        a.set_actor_label(label);a.set_folder_path(folder);a.tags=['MosswildGenerated','MosswildRotationV2']
        a.set_actor_scale3d(unreal.Vector(*(v/100 for v in size)))
        c=a.static_mesh_component;c.set_static_mesh(meshes[shape]);c.set_material(0,mats[mat])
        c.set_collision_profile_name('BlockAll' if solid else 'NoCollision')
        if not solid:c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        return a
    def line(label,a,b,width,height,mat):
        dx,dy=b[0]-a[0],b[1]-a[1]
        return mesh(label,((a[0]+b[0])/2,(a[1]+b[1])/2,height/2+1),(math.hypot(dx,dy),width,height),mat,rotation=(0,math.degrees(math.atan2(dy,dx)),0))
    mesh('Mosswild_Ground',(0,0,-90),(11000,9600,180),'Moss',solid=True,folder='Mosswild / Terrain')
    for i in range(70):
        x,y=rng.uniform(-5200,5200),rng.uniform(-4500,4500)
        mesh('Meadow_%03d'%i,(x,y,1.5),(rng.uniform(350,950),rng.uniform(300,800),3),'Meadow','Cylinder')
    # Traversable shallow channels; there is solid ground below the water.
    for i in range(16):
        y=-4000+i*500
        a=(math.sin(i*.6)*350,y);b=(math.sin((i+1)*.6)*350,y+500)
        line('Brook_%02d'%i,a,b,140,3,'Water')
        if i%3==0:line('Brook_glint_%02d'%i,(a[0]-30,a[1]),(b[0]-30,b[1]),8,4,'Foam')
    homes=config['homes']
    for i,h in enumerate(homes):
        line('Colony_path_%d'%i,h,(0,0),210,4,'Path')
    for i,p in enumerate(config['points']):
        x,y=p['x'],p['y']
        if p['kind']==1:
            mesh('Pool_%d'%i,(x,y,3),(580,430,6),'Water','Cylinder',folder='Mosswild / Water')
            for j in range(12):
                a=j*math.tau/12
                mesh('PoolRock_%d_%d'%(i,j),(x+290*math.cos(a),y+220*math.sin(a),15),(70,60,35),'Stone','Sphere')
                if j%2==0:mesh('Reed_%d_%d'%(i,j),(x+260*math.cos(a),y+190*math.sin(a),65),(18,12,130),'Fern','Cone')
        else:
            mesh('ResourceSoil_%d'%i,(x,y,3),(280,260,6),'Earth','Cylinder',folder='Mosswild / Resources')
            for j in range(7):
                a=j*math.tau/7
                px,py=x+115*math.cos(a),y+115*math.sin(a)
                mesh('ResourceLeaf_%d_%d'%(i,j),(px,py,22),(75,30,35),'LeafLight','Sphere',rotation=(0,math.degrees(a),-20))
                if i>=4:
                    mesh('Petal_%d_%d'%(i,j),(px,py,55),(65,35,15),'Flower','Sphere',rotation=(0,math.degrees(a),-15))
                    mesh('Pollen_%d_%d'%(i,j),(px,py,67),(18,18,12),'Pollen','Sphere')
    for c,(x,y) in enumerate(homes):
        color='Cyan' if c==0 else 'Amber'
        mesh('NestSoil_%d'%c,(x,y,5),(640,580,10),'Earth','Cylinder')
        for j in range(11):
            a=j*math.tau/11
            mesh('NestRoot_%d_%d'%(c,j),(x+220*math.cos(a),y+220*math.sin(a),40),(180,75,90),'Bark','Sphere',rotation=(0,math.degrees(a),0))
            mesh('NestLantern_%d_%d'%(c,j),(x+250*math.cos(a),y+250*math.sin(a),70),(24,24,34),color,'Sphere')
        mesh('NestHeart_%d'%c,(x,y,80),(70,70,160),color,'Cone')
        for j in range(48):
            a=j*math.tau/48
            mesh('Territory_%d_%d'%(c,j),(x+1150*math.cos(a),y+1150*math.sin(a),4),(45,12,6),color,rotation=(0,math.degrees(a)+90,0),folder='Mosswild / Territories')
    # Actual blocking rocks share the exact circles used by the NPC contact planner.
    for i,o in enumerate(config['obstacles']):
        x,y,r=o['x'],o['y'],o['radius']
        mesh('BlockingRock_%d'%i,(x,y,140),(r*2,r*2,280),'Stone','Boulder',solid=True,folder='Mosswild / Collision')
        mesh('RockMoss_%d'%i,(x-20,y,240),(r*1.4,r*1.4,60),'Moss','Sphere')
    # Fallen elder, shrine and honey garden make distinct destinations.
    mesh('FallenElder',(-1700,2480,145),(140,140,820),'Bark','Cylinder',rotation=(90,0,0))
    for i in range(6):
        x=-1980+i*100
        mesh('ElderMushroomStem_'+str(i),(x,2500,175),(28,28,150),'Stem','Cylinder')
        mesh('ElderMushroomCap_'+str(i),(x,2500,260),(120,110,65),'Cap','Sphere')
    for j in range(5):
        a=j*math.tau/5
        mesh('ShrinePillar_'+str(j),(290*math.cos(a),290*math.sin(a),190),(100,120,380),'StoneLight',rotation=(0,math.degrees(a),8),folder='Mosswild / Landmarks')
        mesh('ShrineRune_'+str(j),(270*math.cos(a),270*math.sin(a),240),(16,18,85),'Rune')
    # Forest is decorative; open travel lanes and visible collision rocks remain readable.
    important=[(p['x'],p['y']) for p in config['points']]+homes
    count=0
    for _ in range(160):
        x,y=rng.uniform(-5350,5350),rng.uniform(-4650,4650)
        if any(math.hypot(x-a,y-b)<650 for a,b in important):continue
        if abs(y-x*.25)<250:continue
        if count>=50:break
        h=rng.uniform(420,850);w=rng.uniform(220,420)
        mesh('TreeTrunk_%d'%count,(x,y,h*.32),(70,70,h*.64),'Bark','Cylinder')
        for k in range(3):mesh('TreeCrown_%d_%d'%(count,k),(x,y,h*(.52+k*.16)),(w*(1-k*.18),w*(1-k*.18),h*.45),'Leaf' if k<2 else 'LeafLight','Cone')
        count+=1
    for i in range(135):
        x,y=rng.uniform(-5300,5300),rng.uniform(-4600,4600)
        if any(math.hypot(x-a,y-b)<180 for a,b in important):continue
        for j in range(2):mesh('Fern_%d_%d'%(i,j),(x+j*20,y,28),(65,22,60),'Fern','Cone',rotation=(0,rng.uniform(0,180),-22+j*44))
    for side in [-1,1]:
        mesh('BoundaryX_'+str(side),(side*5580,0,90),(120,9800,360),'Stone',solid=True,folder='Mosswild / Boundary')
        mesh('BoundaryY_'+str(side),(0,side*4880,90),(11200,120,360),'Stone',solid=True,folder='Mosswild / Boundary')
    start=actors.spawn_actor_from_class(unreal.PlayerStart,unreal.Vector(-4200,2600,110));start.set_actor_label('Mosswild_PlayerStart')
    lab=actors.spawn_actor_from_class(unreal.load_class(None,'/Script/RPGPrototype.InsectLab'),unreal.Vector())
    lab.set_editor_property('expanded_biome',True);lab.set_actor_label('Mosswild_Controller');lab.set_folder_path('Mosswild / Simulation')
    sun=actors.spawn_actor_from_class(unreal.DirectionalLight,unreal.Vector(0,0,2000),unreal.Rotator(pitch=-48,yaw=-35,roll=0))
    sun.light_component.set_mobility(unreal.ComponentMobility.MOVABLE);sun.light_component.set_editor_property('intensity',3.6)
    sun.light_component.set_editor_property('light_color',unreal.Color(255,233,190,255))
    sky=actors.spawn_actor_from_class(unreal.SkyLight,unreal.Vector(0,0,1000))
    sky.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    sky.light_component.set_editor_property('intensity',1.2);sky.light_component.set_editor_property('real_time_capture',True)
    actors.spawn_actor_from_class(unreal.SkyAtmosphere,unreal.Vector())
    fog=actors.spawn_actor_from_class(unreal.ExponentialHeightFog,unreal.Vector(0,0,-100))
    fog.component.set_editor_property('fog_density',.008)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    world.get_world_settings().set_editor_property('force_no_precomputed_lighting',True)
    unreal.SystemLibrary.execute_console_command(world,'MAP CHECK')
    assert levels.save_current_level()
    unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(unreal.Vector(-6600,6600,7500),unreal.Rotator(pitch=-45,yaw=-45,roll=0))
    unreal.log('MOSSWILD_CREATED')

main()
