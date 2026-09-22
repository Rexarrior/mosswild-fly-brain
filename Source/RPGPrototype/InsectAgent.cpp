#include "InsectAgent.h"
#include "Components/SphereComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

AInsectAgent::AInsectAgent()
{
    PrimaryActorTick.bCanEverTick=true;
    Body=CreateDefaultSubobject<USphereComponent>(TEXT("Collision")); SetRootComponent(Body);
    Body->InitSphereRadius(32); Body->SetCollisionProfileName(TEXT("Pawn"));
    Visual=CreateDefaultSubobject<USceneComponent>(TEXT("Body")); Visual->SetupAttachment(Body);
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    auto Part=[&](FString Name,UStaticMesh* Mesh,FVector P,FVector S,bool Shell)
    {
        auto* C=CreateDefaultSubobject<UStaticMeshComponent>(*Name); C->SetupAttachment(Visual);
        C->SetStaticMesh(Mesh); C->SetRelativeLocation(P); C->SetRelativeScale3D(S);
        C->SetCollisionEnabled(ECollisionEnabled::NoCollision); if(Shell) Shells.Add(C);
        return C;
    };
    Abdomen=Part(TEXT("Abdomen"),Sphere.Object,FVector(-25,0,12),FVector(.95,.68,.55),true);
    Part(TEXT("Thorax"),Sphere.Object,FVector(20,0,10),FVector(.54,.50,.44),true);
    Head=Part(TEXT("Head"),Sphere.Object,FVector(51,0,17),FVector(.43,.48,.40),true);
    CargoVisual=Part(TEXT("CarriedNectar"),Sphere.Object,FVector(-28,0,48),FVector(.30,.30,.26),false);
    CargoVisual->ComponentTags.Add(TEXT("Food")); CargoVisual->SetVisibility(false);
    for(int I=0;I<3;++I)
    {
        auto* Ridge=Part(FString::Printf(TEXT("CarapaceRidge%d"),I),Cube.Object,FVector(-43+I*18,0,35),FVector(.045,.46,.025),false);
        Ridge->ComponentTags.Add(TEXT("Eye"));
    }
    for(int32 Side=-1;Side<=1;Side+=2)
    {
        auto* Eye=Part(FString::Printf(TEXT("Eye%d"),Side),Sphere.Object,FVector(66,Side*16,26),FVector(.15,.13,.16),false);
        Eye->ComponentTags.Add(TEXT("Eye"));
        auto* Antenna=Part(FString::Printf(TEXT("Antenna%d"),Side),Cube.Object,FVector(75,Side*25,38),FVector(.48,.025,.025),false);
        Antenna->SetRelativeRotation(FRotator(30,Side*35,0));
        Antennae.Add(Antenna);
        for(int32 J=0;J<3;++J)
        {
            auto* Leg=Part(FString::Printf(TEXT("Leg%d_%d"),Side,J),Cylinder.Object,FVector(28-J*29,Side*39,-7),FVector(.07,.07,.60),false);
            Leg->SetRelativeRotation(FRotator(-28,Side*(55+J*35),0)); Legs.Add(Leg);
            Shins.Add(Part(FString::Printf(TEXT("Tibia%d_%d"),Side,J),Cylinder.Object,FVector::ZeroVector,FVector(.05,.05,.45),false));
            Feet.Add(Part(FString::Printf(TEXT("Foot%d_%d"),Side,J),Sphere.Object,FVector::ZeroVector,FVector(.08,.11,.04),false));
        }
        auto* Jaw=Part(FString::Printf(TEXT("Jaw%d"),Side),Cube.Object,FVector(83,Side*15,8),FVector(.38,.055,.07),true);
        Jaw->SetRelativeRotation(FRotator(0,-Side*30,0));
        Mandibles.Add(Jaw);
    }
}
void AInsectAgent::Configure(int32 Id,int32 InColony,int32 InForm,FVector InNest,int32 InGeneration)
{
    AgentId=Id; Colony=InColony; Form=InForm; Nest=InNest; Generation=InGeneration;
    if(Generation>0) { Energy=55; Health=48; Visual->SetRelativeScale3D(FVector(.75)); }
    if(Form==1) { Abdomen->SetRelativeScale3D(FVector(1.15,.35,.34)); Head->SetRelativeScale3D(FVector(.55,.45,.45)); }
    if(Form==2) { Abdomen->SetRelativeScale3D(FVector(.52,.43,.40)); Abdomen->SetRelativeLocation(FVector(-45,0,6)); Visual->SetRelativeScale3D(FVector(.82)); }
    auto* Shell=LoadObject<UMaterialInterface>(nullptr,Colony==0 ? TEXT("/Game/BrainLab/M_Cyan.M_Cyan") : TEXT("/Game/BrainLab/M_Amber.M_Amber"));
    auto* Dark=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/BrainLab/M_Dark.M_Dark"));
    auto* Eye=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/BrainLab/M_Eye.M_Eye"));
    TArray<UStaticMeshComponent*> Parts; GetComponents(Parts);
    for(auto* C:Parts) C->SetMaterial(0,Shells.Contains(C) ? Shell : (C->ComponentTags.Contains(TEXT("Eye")) ? Eye : Dark));
    CargoVisual->SetMaterial(0,LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/BrainLab/M_Green.M_Green")));
}
void AInsectAgent::MoveFromBrain(const FInsectMotor& Command,float Dt)
{
    Motor=Command;
    auto Rotation=GetActorRotation(); Rotation.Yaw+=Motor.Turn*135.f*Dt; SetActorRotation(Rotation);
    const float MaxSpeed=Form==0 ? 155.f : (Form==1 ? 200.f : 240.f);
    Speed=MaxSpeed*Motor.Drive*(Cargo>0?.85f:1.f)*((bFeeding||bDrinking)?FeedingMotionFactor:1.f);
    FHitResult Hit; AddActorWorldOffset(GetActorForwardVector()*Speed*Dt,true,&Hit);
    // Contact changes the next sensory target; it does not inject a hidden steering command.
}
void AInsectAgent::PredictMotion(const FInsectMotor& Command,float Duration,float Smoothing,FVector& Position,float& Yaw) const
{
    Position=GetActorLocation(); Yaw=GetActorRotation().Yaw;
    float Drive=NeuralDrive,Turn=NeuralTurn;
    const float TopSpeed=Form==0?155.f:(Form==1?200.f:240.f);
    const float SpeedScale=(Cargo>0?.85f:1.f)*((bFeeding||bDrinking)?FeedingMotionFactor:1.f);
    FCollisionQueryParams Query(SCENE_QUERY_STAT(BrainPrediction),false,this);
    const FCollisionResponseParams Response(Body->GetCollisionResponseToChannels());
    // Predict only the command already received from the brain. This is a
    // read-only sensory forecast; it never moves the actor or supplies a motor.
    while(Duration>UE_SMALL_NUMBER)
    {
        const float Step=FMath::Min(Duration,.025f); Duration-=Step;
        const float Alpha=Smoothing>0?1-FMath::Exp(-Step/FMath::Max(.05f,Smoothing)):1.f;
        Drive=FMath::Lerp(Drive,Command.Drive,Alpha); Turn=FMath::Lerp(Turn,Command.Turn,Alpha);
        Yaw+=Turn*135.f*Step;
        const FVector Next=Position+FRotator(0,Yaw,0).Vector()*TopSpeed*Drive*SpeedScale*Step;
        FHitResult Hit;
        if(GetWorld()->SweepSingleByChannel(Hit,Position,Next,FQuat::Identity,Body->GetCollisionObjectType(),Body->GetCollisionShape(),Query,Response))
        { if(!Hit.bStartPenetrating) Position=Hit.Location; }
        else Position=Next;
    }
}
void AInsectAgent::Tick(float Dt)
{
    Super::Tick(Dt); Phase+=Dt*(Speed>2?Speed*.065f:.35f);
    const float Growth=Generation>0?FMath::Lerp(.75f,1.f,FMath::Clamp(Age/60,0.f,1.f)):1.f;
    const float BodyScale=(Form==2?.82f:1.f)*Growth;
    Visual->SetRelativeScale3D(FVector(BodyScale));
    AttackPulse=FMath::Max(0.f,AttackPulse-Dt*4); HurtPulse=FMath::Max(0.f,HurtPulse-Dt*3);
    const float Motion=FMath::Clamp(Speed/155.f,0.f,1.4f);
    auto Segment=[](UStaticMeshComponent* C,const FVector& Start,const FVector& End,float Radius)
    {
        const FVector V=End-Start; C->SetRelativeLocation((Start+End)*.5f);
        C->SetRelativeRotation(FRotationMatrix::MakeFromZ(V).Rotator());
        C->SetRelativeScale3D(FVector(Radius/50,Radius/50,V.Size()/100));
    };
    for(int32 I=0;I<Legs.Num();++I)
    {
        const int32 Side=I<3 ? -1 : 1, J=I%3;
        const float T=Phase+I*PI;
        const float Stride=FMath::Cos(T)*23*Motion;
        const float Lift=FMath::Max(0.f,FMath::Sin(T))*18*Motion;
        const float Reach=(Form==1&&J==0)?17.f:0.f;
        const FVector Hip(28-J*29,Side*20,10);
        const FVector Knee(28-J*29+Stride*.4f+Reach,Side*48,2+Lift*.6f+AttackPulse*Reach);
        const FVector Foot(28-J*29+Stride+Reach,Side*(70+J*3),-48+Lift+AttackPulse*Reach*2);
        Segment(Legs[I],Hip,Knee,3.5f); Segment(Shins[I],Knee,Foot,2.4f); Feet[I]->SetRelativeLocation(Foot);
    }
    const float Chew=bFeeding?FMath::Sin(GetWorld()->GetTimeSeconds()*19):0;
    for(int I=0;I<Antennae.Num();++I)
    {
        const int Side=I==0?-1:1;
        Antennae[I]->SetRelativeRotation(FRotator(25+FMath::Sin(GetWorld()->GetTimeSeconds()*2+I)*8-(Energy<30?25:0),Side*(32+Chew*8),0));
        Mandibles[I]->SetRelativeRotation(FRotator(AttackPulse*15,-Side*(27+Chew*12+AttackPulse*25),0));
    }
    Head->SetRelativeRotation(FRotator(bDrinking?-23:(bFeeding?-8:AttackPulse*12),0,0));
    CargoVisual->SetVisibility(Cargo>1); CargoVisual->SetRelativeScale3D(FVector(.12f+.24f*Cargo/30));
    Visual->SetRelativeLocation(FVector(AttackPulse*18,0,-(1-BodyScale)*48+FMath::Sin(Phase*2)*Motion*2+(bFeeding?Chew:0)));
    Visual->SetRelativeRotation(FRotator(-AttackPulse*8,0,Motor.Turn*Motion*5+HurtPulse*12));
}
