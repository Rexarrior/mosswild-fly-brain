#include "InsectLab.h"
#include "InsectAgent.h"
#include "InsectBrainBridge.h"
#include "RPGCharacter.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInterface.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"
#include "Serialization/JsonSerializer.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"

AInsectLab::AInsectLab()
{
    PrimaryActorTick.bCanEverTick=true;
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
    Bridge=CreateDefaultSubobject<UInsectBrainBridge>(TEXT("BrainAdapter"));
}
AInsectLab* AInsectLab::Find(const UWorld* World)
{
    if(!World) return nullptr;
    TActorIterator<AInsectLab> It(World);
    return It ? *It : nullptr;
}
void AInsectLab::BeginPlay()
{
    Super::BeginPlay();
    if(bExpandedBiome)
    {
        if(LoadBiome()) ResetExperiment(false);
        else { bPaused=true; Bridge->Status=TEXT("Invalid or missing Config/BrainBiome.json"); }
        return;
    }
    const FVector Positions[]={FVector(-750,-460,35),FVector(-750,460,35),FVector(750,-460,35),FVector(750,460,35),FVector(0,-300,35),FVector(0,300,35),FVector(-220,0,35),FVector(220,0,35)};
    for(int32 I=0;I<8;++I)
    {
        FInsectFood F; F.Position=Positions[I];
        F.Visual=Orb(FString::Printf(TEXT("Food%d"),I),F.Position,FVector(.85,.85,.55),TEXT("Green")); Food.Add(F);
    }
    ResetExperiment(false);
}
UStaticMeshComponent* AInsectLab::Orb(FString Name,FVector P,FVector Scale,const TCHAR* Material)
{
    auto* C=NewObject<UStaticMeshComponent>(this,*Name); AddInstanceComponent(C); C->SetupAttachment(RootComponent);
    C->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Sphere.Sphere")));
    C->SetCollisionEnabled(ECollisionEnabled::NoCollision); C->SetWorldLocation(P); C->SetWorldScale3D(Scale);
    C->SetMaterial(0,LoadObject<UMaterialInterface>(nullptr,*FString::Printf(TEXT("/Game/BrainLab/M_%s.M_%s"),Material,Material)));
    C->RegisterComponent(); return C;
}
AInsectAgent* AInsectLab::SpawnInsect(int32 Colony,int32 Form,FVector P,int32 Generation)
{
    FActorSpawnParameters Params; Params.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn;
    auto* Agent=GetWorld()->SpawnActor<AInsectAgent>(P,FRotator(0,Colony==0 ? 0 : 180,0),Params);
    if(Agent)
    {
        Agent->Configure(NextId++,Colony,Form,Home(Colony),Generation);
        if(bExpandedBiome&&bSensoryCompetition)
        { Agent->GoalKind=INDEX_NONE; Agent->GoalIndex=INDEX_NONE; Agent->Target=Agent->GetActorLocation(); Agent->Intent=TEXT("Sensing"); }
        Agent->FeedingMotionFactor=bExpandedBiome&&ImprovementStage>=3?.18f:1.f;
        Agents.Add(Agent);
    }
    return Agent;
}
void AInsectLab::ResetExperiment(bool Ablate)
{
    if(bExpandedBiome) FinishBiomeRecording(TEXT("reset"));
    for(AInsectAgent* A:Agents) if(IsValid(A)) A->Destroy(); Agents.Empty();
    for(auto& E:Eggs) if(E.Visual) E.Visual->DestroyComponent(); Eggs.Empty();
    NextId=1; Random.Initialize(1701); Elapsed=0; Meals=Fights=PlayerHits=Births=Deaths=EggsLaid=0;
    PlayerHealth=100; PlayerAttackTimer=0; bPaused=false; bDrought=false; RequestTimer=0;
    for(auto& F:Food) F.Amount=75;
    Bridge->Reset(Ablate);
    if(bExpandedBiome)
    {
        if(Food.IsEmpty()) { bPaused=true; Bridge->Status=TEXT("Biome configuration unavailable"); return; }
        ResetBiome(); return;
    }
    for(int32 C=0;C<2;++C) for(int32 F=0;F<3;++F)
        SpawnInsect(C,F,Home(C)+FVector(0,(F-1)*210,0),0);
    Record(Ablate ? TEXT("RESET / SYNAPSES DISABLED") : TEXT("RESET / FULL CONNECTOMES"));
}
int32 AInsectLab::LivingCount() const
{
    int32 Count=0; for(const AInsectAgent* A:Agents) if(IsValid(A)&&A->Health>0) ++Count; return Count;
}
void AInsectLab::SetDrought(bool Enabled)
{
    bDrought=Enabled; if(Enabled) for(auto& F:Food) if(F.Kind==0) F.Amount=0;
    Record(Enabled ? TEXT("Drought: food exhausted; no regrowth") : TEXT("Rain returns: food regrows"));
}
void AInsectLab::Record(const FString& Event)
{
    LastEvent=Event;
    UE_LOG(LogTemp,Display,TEXT("BRAINLAB %.1fs %s"),Elapsed,*Event);
    const FString Path=FPaths::ProjectSavedDir()/TEXT("BrainLab/events.log");
    IFileManager::Get().MakeDirectory(*(FPaths::ProjectSavedDir()/TEXT("BrainLab")),true);
    FFileHelper::SaveStringToFile(FString::Printf(TEXT("%.2f %s\n"),Elapsed,*Event),*Path,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,&IFileManager::Get(),FILEWRITE_Append);
    if(!TelemetryFolder.IsEmpty())
        FFileHelper::SaveStringToFile(FString::Printf(TEXT("%.2f %s\n"),Elapsed,*Event),*(TelemetryFolder/TEXT("events.log")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,&IFileManager::Get(),FILEWRITE_Append);
}
void AInsectLab::EndPlay(const EEndPlayReason::Type Reason)
{
    if(bExpandedBiome) FinishBiomeRecording(TEXT("end_play"));
    Super::EndPlay(Reason);
}
void AInsectLab::Plan(AInsectAgent* A)
{
    A->Rival=nullptr; A->bPlayerTarget=false; A->FoodTarget=INDEX_NONE;
    const FVector P=A->GetActorLocation();
    auto* Player=UGameplayStatics::GetPlayerPawn(this,0);
    if(A->Health<25) A->bRetreating=true;
    if(A->Health>=50) A->bRetreating=false;
    if(A->bRetreating)
    {
        A->Target=A->Nest+FVector(A->Colony==0 ? -400 : 400,0,0);
        if(A->Energy<35)
        {
            float Best=1.e9;
            for(int32 I=0;I<Food.Num();++I) if(Food[I].Amount>2 && FVector::Dist2D(Food[I].Position,A->Nest)<550)
            {
                const float D=FVector::Dist2D(P,Food[I].Position);
                if(D<Best) { Best=D; A->FoodTarget=I; A->Target=Food[I].Position; }
            }
        }
        A->Intent=TEXT("Retreat / recover"); return;
    }
    // Territory defence and target choice are game rules, not inferred fly cognition.
    if(Player && FVector::Dist2D(Player->GetActorLocation(),A->Nest)<850 && FVector::Dist2D(P,Player->GetActorLocation())<900 && A->Energy>22)
    { A->bPlayerTarget=true; A->Target=Player->GetActorLocation(); A->Intent=TEXT("Defend / player"); return; }
    float BestRival=350;
    for(AInsectAgent* B:Agents)
    {
        if(!IsValid(B)||B==A||B->Colony==A->Colony||B->Health<=0) continue;
        const float D=FVector::Dist2D(P,B->GetActorLocation());
        if(D<BestRival && FVector::Dist2D(B->GetActorLocation(),A->Nest)<1000 && A->Energy>25)
        { BestRival=D; A->Rival=B; }
    }
    if(A->Rival.IsValid()) { A->Target=A->Rival->GetActorLocation(); A->Intent=TEXT("Defend / rival"); return; }
    if(A->Energy<112)
    {
        float Best=1.e9;
        for(int32 I=0;I<Food.Num();++I) if(Food[I].Amount>2)
        {
            const float Score=FVector::Dist2D(P,Food[I].Position)+(75-Food[I].Amount)*2;
            if(Score<Best) { Best=Score; A->FoodTarget=I; }
        }
        if(A->FoodTarget!=INDEX_NONE) { A->Target=Food[A->FoodTarget].Position; A->Intent=TEXT("Forage"); return; }
    }
    if(A->Energy>=105) { A->Target=A->Nest; A->Intent=TEXT("Nest / brood"); return; }
    // Deterministic wandering demand, translated into sensory input by the adapter.
    const float Angle=Elapsed*.13f+A->AgentId*2.4f;
    A->Target=A->Nest+FVector(FMath::Cos(Angle)*600,FMath::Sin(Angle)*600,0);
    A->Intent=bDrought ? TEXT("Search / starving") : TEXT("Patrol");
}
void AInsectLab::Ecology(AInsectAgent* A,float Dt)
{
    A->Age+=Dt; A->AttackCooldown-=Dt; A->BirthCooldown-=Dt;
    A->Energy=FMath::Max(0.f,A->Energy-Dt*(.48f+A->Motor.Drive*.28f));
    if(A->Energy<=0) A->Health-=Dt*5;
    const FVector P=A->GetActorLocation();
    if(A->bRetreating && FVector::Dist2D(P,A->Nest)<800 && A->Energy>15)
    { A->Health=FMath::Min(60.f,A->Health+Dt*2); A->Energy-=Dt*.7f; }
    bool Eating=false;
    if(A->FoodTarget!=INDEX_NONE && FVector::Dist2D(P,Food[A->FoodTarget].Position)<125 && A->Motor.ForwardHz>4)
    {
        auto& F=Food[A->FoodTarget];
        const float Eaten=FMath::Min3(F.Amount,Dt*22.f,120-A->Energy);
        if(Eaten>0)
        {
            if(!A->bWasEating) { ++Meals; }
            Eating=true;
            A->Intent=TEXT("Eating"); A->Energy+=Eaten; F.Amount-=Eaten;
            A->Health=FMath::Min(60.f,A->Health+Dt*2);
        }
    }
    A->bWasEating=Eating;
    if(A->AttackCooldown<=0 && A->Motor.ForwardHz>4)
    {
        if(A->Rival.IsValid() && FVector::Dist2D(P,A->Rival->GetActorLocation())<155)
        {
            A->Rival->Health-=10; A->Energy=FMath::Max(0.f,A->Energy-2); A->AttackCooldown=1.4f; ++Fights;
            if(Fights%5==1) Record(TEXT("Territory clash: cyan and amber colonies"));
        }
        if(A->bPlayerTarget)
        {
            auto* Player=UGameplayStatics::GetPlayerPawn(this,0);
            if(Player&&FVector::Dist2D(P,Player->GetActorLocation())<160)
            { PlayerHealth-=8; ++PlayerHits; A->AttackCooldown=1.4f; Record(TEXT("Player bitten inside a colony's territory")); }
        }
    }
    if(A->Energy>=105 && A->Age>15 && A->Health>=40 && A->BirthCooldown<=0 && LivingCount()+Eggs.Num()<12 && FVector::Dist2D(P,A->Nest)<750)
    {
        FInsectEgg Egg; Egg.Colony=A->Colony; Egg.Form=A->Form; Egg.Generation=A->Generation+1;
        Egg.Position=P+FVector(-80,40,0); Egg.Position.Z=35;
        Egg.Visual=Orb(FString::Printf(TEXT("Egg%d"),++EggsLaid),Egg.Position,FVector(.32,.26,.45),A->Colony==0 ? TEXT("Cyan") : TEXT("Amber"));
        Eggs.Add(Egg); A->Energy-=48; A->BirthCooldown=35;
        Record(FString::Printf(TEXT("%s #%d laid an egg (48 energy)"),*A->Backend(),A->AgentId));
    }
}
void AInsectLab::PlayerStrike()
{
    if(PlayerAttackTimer>0||bPaused) return;
    auto* Player=UGameplayStatics::GetPlayerPawn(this,0); if(!Player) return;
    PlayerAttackTimer=.65f;
    for(AInsectAgent* A:Agents) if(IsValid(A)&&FVector::Dist2D(A->GetActorLocation(),Player->GetActorLocation())<220)
    { A->Health-=22; A->HurtPulse=1; Record(TEXT("Player strikes an insect")); }
}
void AInsectLab::Tick(float Dt)
{
    Super::Tick(Dt); PlayerAttackTimer-=Dt; Dt=FMath::Min(Dt,.1f);
    if(bExpandedBiome) { TickBiome(Dt); return; }
    if(bPaused) { for(AInsectAgent* A:Agents) A->Speed=0; return; }
    RequestTimer-=Dt;
    if(RequestTimer<=0&&!Bridge->IsPending())
    {
        TArray<FInsectSenses> Senses;
        for(AInsectAgent* A:Agents) if(IsValid(A)&&A->Health>0)
        {
            Plan(A);
            FVector Delta=A->Target-A->GetActorLocation(); Delta.Z=0;
            // A whisker-like collision sensor supplies an avoidance target via the brain.
            FHitResult Hit; FCollisionQueryParams Query(SCENE_QUERY_STAT(BrainWhisker),false,A);
            const FVector P=A->GetActorLocation();
            const bool Blocked=GetWorld()->LineTraceSingleByChannel(Hit,P,P+A->GetActorForwardVector()*100,ECC_Pawn,Query);
            float Bearing=FMath::FindDeltaAngleDegrees(A->GetActorRotation().Yaw,Delta.Rotation().Yaw);
            if(Blocked&&Delta.Size2D()>160) Bearing+=(A->AgentId%2 ? 70.f : -70.f);
            FInsectSenses S; S.AgentId=A->AgentId; S.Backend=A->Backend();
            S.Bearing=FMath::Clamp(Bearing/65.f,-1.f,1.f);
            S.Drive=Delta.Size2D()<90 ? .08f : (FMath::Abs(Bearing)>70 ? .35f : 1.f);
            S.Threat=A->Health<20 ? .35f : 0.f;
            Senses.Add(S);
        }
        Bridge->SubmitSenses(Senses); RequestTimer=.3f;
    }
    bool Active=false;
    for(AInsectAgent* A:Agents) if(IsValid(A)&&A->Health>0)
    {
        FInsectMotor M;
        if(Bridge->ReadMotor(A->AgentId,M)) { A->MoveFromBrain(M,Dt); Ecology(A,Dt); Active=true; }
        else { A->Speed=0; A->Intent=TEXT("Waiting for brain"); }
    }
    if(!Active) return;
    Elapsed+=Dt;
    for(auto& F:Food)
    {
        if(!bDrought) F.Amount=FMath::Min(75.f,F.Amount+Dt*1.4f);
        const float S=.15f+.7f*F.Amount/75.f; F.Visual->SetWorldScale3D(FVector(S,S,S*.65f));
    }
    for(int32 I=Eggs.Num()-1;I>=0;--I)
    {
        auto& E=Eggs[I]; E.Remaining-=Dt;
        if(E.Remaining<=0)
        {
            const auto Copy=E; E.Visual->DestroyComponent(); Eggs.RemoveAt(I);
            if(SpawnInsect(Copy.Colony,Copy.Form,Copy.Position+FVector(0,0,20),Copy.Generation))
            { ++Births; Record(TEXT("Egg hatched: a new independent brain joins the colony")); }
        }
    }
    for(int32 I=Agents.Num()-1;I>=0;--I) if(!IsValid(Agents[I])||Agents[I]->Health<=0)
    {
        if(IsValid(Agents[I])) { Record(FString::Printf(TEXT("%s #%d died (%s)"),*Agents[I]->Backend(),Agents[I]->AgentId,Agents[I]->Energy<=0 ? TEXT("starvation") : TEXT("combat"))); Agents[I]->Destroy(); }
        Agents.RemoveAt(I); ++Deaths;
    }
    if(PlayerHealth<=0)
    {
        if(auto* P=UGameplayStatics::GetPlayerPawn(this,0)) P->SetActorLocation(FVector(-1250,1250,110));
        PlayerHealth=100; Record(TEXT("Player recovered at the observation deck"));
    }
}
FString AInsectLab::SnapshotJson() const
{
    if(bExpandedBiome) return BiomeSnapshot();
    auto Root=MakeShared<FJsonObject>();
    Root->SetNumberField(TEXT("elapsed"),Elapsed); Root->SetNumberField(TEXT("alive"),LivingCount()); Root->SetNumberField(TEXT("eggs"),Eggs.Num());
    Root->SetNumberField(TEXT("meals"),Meals); Root->SetNumberField(TEXT("fights"),Fights); Root->SetNumberField(TEXT("player_hits"),PlayerHits);
    Root->SetNumberField(TEXT("births"),Births); Root->SetNumberField(TEXT("deaths"),Deaths); Root->SetNumberField(TEXT("eggs_laid"),EggsLaid);
    Root->SetNumberField(TEXT("player_health"),PlayerHealth); Root->SetNumberField(TEXT("batch_ms"),Bridge->BatchMilliseconds);
    Root->SetNumberField(TEXT("batches"),Bridge->CompletedBatches); Root->SetBoolField(TEXT("ablation"),Bridge->bAblated);
    Root->SetStringField(TEXT("status"),Bridge->Status);
    TArray<TSharedPtr<FJsonValue>> Rows;
    for(AInsectAgent* A:Agents) if(IsValid(A))
    {
        auto R=MakeShared<FJsonObject>(); const auto P=A->GetActorLocation();
        R->SetNumberField(TEXT("id"),A->AgentId); R->SetStringField(TEXT("backend"),A->Backend()); R->SetStringField(TEXT("intent"),A->Intent);
        R->SetNumberField(TEXT("energy"),A->Energy); R->SetNumberField(TEXT("health"),A->Health); R->SetNumberField(TEXT("generation"),A->Generation);
        R->SetNumberField(TEXT("x"),P.X); R->SetNumberField(TEXT("y"),P.Y); R->SetNumberField(TEXT("turn"),A->Motor.Turn); R->SetNumberField(TEXT("drive"),A->Motor.Drive);
        R->SetNumberField(TEXT("left_hz"),A->Motor.LeftHz); R->SetNumberField(TEXT("right_hz"),A->Motor.RightHz); R->SetNumberField(TEXT("forward_hz"),A->Motor.ForwardHz);
        Rows.Add(MakeShared<FJsonValueObject>(R));
    }
    Root->SetArrayField(TEXT("agents"),Rows); FString Out; auto Writer=TJsonWriterFactory<>::Create(&Out); FJsonSerializer::Serialize(Root,Writer); return Out;
}
