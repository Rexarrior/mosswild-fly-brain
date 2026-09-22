#include "InsectLab.h"
#include "InsectAgent.h"
#include "InsectBrainBridge.h"
#include "Components/StaticMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Materials/MaterialInterface.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"
#include "Serialization/JsonSerializer.h"

namespace
{
// Authored ecological goals. The optional audit control replaces the neural motor only.
enum EGoal { Scout=0,Forage=1,Deliver=2,Drink=3,Recover=4,Defend=5,Rest=6,Patrol=7 };
float Distance(const FVector& A,const FVector& B) { return FVector::Dist2D(A,B); }
FVector Flat(FVector V) { V.Z=0; return V.GetSafeNormal(); }
FString JsonString(const TSharedPtr<FJsonObject>& O)
{ FString S; auto W=TJsonWriterFactory<TCHAR,TCondensedJsonPrintPolicy<TCHAR>>::Create(&S); FJsonSerializer::Serialize(O.ToSharedRef(),W); return S; }
}

bool AInsectLab::LoadBiome()
{
    FString Text;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectConfigDir()/TEXT("BrainBiome.json")))) return false;
    TSharedPtr<FJsonObject> O;
    if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),O)||!O.IsValid()) return false;
    const TArray<TSharedPtr<FJsonValue>>* Points; const TArray<TSharedPtr<FJsonValue>>* HomesJson;
    if(!O->TryGetArrayField(TEXT("points"),Points)||Points->IsEmpty()||!O->TryGetArrayField(TEXT("homes"),HomesJson)||HomesJson->Num()!=2) return false;
    for(const auto& H:*HomesJson) if(H->Type!=EJson::Array||H->AsArray().Num()!=2) return false;
    int FoodCount=0,WaterCount=0;
    for(const auto& P:*Points)
    {
        if(P->Type!=EJson::Object) return false;
        const auto F=P->AsObject(); double Capacity,Kind;
        if(!F->TryGetNumberField(TEXT("capacity"),Capacity)||Capacity<=0||!F->TryGetNumberField(TEXT("kind"),Kind)) return false;
        if(Kind==0) ++FoodCount; else if(Kind==1) ++WaterCount; else return false;
    }
    if(!FoodCount||!WaterCount) return false;
    HalfWidth=O->GetNumberField(TEXT("half_width")); HalfHeight=O->GetNumberField(TEXT("half_height"));
    const auto& H=O->GetArrayField(TEXT("homes"));
    for(int C=0;C<2;++C) Homes[C]=FVector(H[C]->AsArray()[0]->AsNumber(),H[C]->AsArray()[1]->AsNumber(),55);
    for(const auto& Entry:O->GetArrayField(TEXT("points")))
    {
        const auto P=Entry->AsObject(); FInsectFood F;
        F.Name=P->GetStringField(TEXT("name")); F.Kind=P->GetIntegerField(TEXT("kind"));
        F.Position=FVector(P->GetNumberField(TEXT("x")),P->GetNumberField(TEXT("y")),35);
        F.Capacity=P->GetNumberField(TEXT("capacity")); F.Amount=F.Capacity;
        F.Regrowth=P->GetNumberField(TEXT("regrowth")); F.Phase=P->GetNumberField(TEXT("phase"));
        if(F.Kind==0) F.Visual=Orb(FString::Printf(TEXT("BiomeFood%d"),Food.Num()),F.Position,FVector(1.3,1.3,.75),TEXT("Green"));
        Food.Add(F);
    }
    for(const auto& Entry:O->GetArrayField(TEXT("obstacles")))
    {
        const auto P=Entry->AsObject(); FBiomeObstacle B;
        B.Position=FVector(P->GetNumberField(TEXT("x")),P->GetNumberField(TEXT("y")),55);
        B.Radius=P->GetNumberField(TEXT("radius")); Obstacles.Add(B);
    }
    const TSharedPtr<FJsonObject>* Economy=nullptr;
    if(O->TryGetObjectField(TEXT("economy"),Economy))
    {
        (*Economy)->TryGetBoolField(TEXT("enabled"),bContinuousEconomy);
        auto ReadCost=[&](const TCHAR* Key,float& Value,float Max)
        { double N; if((*Economy)->TryGetNumberField(Key,N)&&FMath::IsFinite(N)) Value=FMath::Clamp(float(N),0.f,Max); };
        ReadCost(TEXT("upkeep_per_adult"),UpkeepPerAdult,1);
        ReadCost(TEXT("reserve_per_adult"),ReservePerAdult,100);
        ReadCost(TEXT("reserve_base"),ReserveBase,300);
        ReadCost(TEXT("spoilage_rate"),SpoilageRate,.01f);
        ReadCost(TEXT("cargo_timeout"),CargoTimeout,120);
    }
    ImprovementStage=O->GetIntegerField(TEXT("default_stage"));
    O->TryGetBoolField(TEXT("predict_senses"),bPredictiveSenses);
    double NeuralMs; if(O->TryGetNumberField(TEXT("neural_ms"),NeuralMs)) NeuralMilliseconds=FMath::Clamp(int32(NeuralMs),10,100);
    const auto Params=O->GetObjectField(TEXT("default_parameters"));
    double Limit; if(Params->TryGetNumberField(TEXT("colony_limit"),Limit)) ColonyLimit=FMath::Clamp(int32(Limit),4,6);
    SenseRadius=Params->GetNumberField(TEXT("sense_radius")); SeparationWeight=Params->GetNumberField(TEXT("separation"));
    AlignmentWeight=Params->GetNumberField(TEXT("alignment")); CohesionWeight=Params->GetNumberField(TEXT("cohesion"));
    HungerThreshold=Params->GetNumberField(TEXT("hunger")); ThirstThreshold=Params->GetNumberField(TEXT("thirst"));
    MemorySeconds=Params->GetNumberField(TEXT("memory_seconds")); TrailLifetime=Params->GetNumberField(TEXT("trail_lifetime"));
    BroodCost=Params->GetNumberField(TEXT("brood_cost")); RegrowthMultiplier=Params->GetNumberField(TEXT("regrowth"));
    TurnGain=Params->GetNumberField(TEXT("turn_gain")); MotorSmoothing=Params->GetNumberField(TEXT("motor_smoothing"));
    for(int C=0;C<2;++C)
    {
        auto* Cloud=NewObject<UInstancedStaticMeshComponent>(this,C==0?TEXT("CyanPheromones"):TEXT("AmberPheromones"));
        AddInstanceComponent(Cloud); Cloud->SetupAttachment(RootComponent);
        Cloud->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Sphere.Sphere")));
        Cloud->SetMaterial(0,LoadObject<UMaterialInterface>(nullptr,C==0?TEXT("/Game/BrainLab/M_Cyan.M_Cyan"):TEXT("/Game/BrainLab/M_Amber.M_Amber")));
        Cloud->SetCollisionEnabled(ECollisionEnabled::NoCollision); Cloud->SetCastShadow(false); Cloud->RegisterComponent();
        if(C==0) CyanTrails=Cloud; else AmberTrails=Cloud;
    }
    return true;
}

void AInsectLab::ResetBiome()
{
    FoodDelivered=Polarization=SwarmFraction=0; ResourceVisits=StarvationDeaths=DehydrationDeaths=CombatDeaths=GoalChanges=0;
    StuckSeconds=AgentSeconds=AlignmentSum=AlignmentSamples=SwarmSamples=SocialSamples=0;
    Trails.Empty(); ConsumedBatch=0; TelemetryTimer=0; MotorTimeCredit=SensoryLookahead=0; AuditStarted=FPlatformTime::Seconds();
    if(CyanTrails) CyanTrails->ClearInstances();
    if(AmberTrails) AmberTrails->ClearInstances();
    ResourceOwners.Init(INDEX_NONE,Food.Num()); ResourceClaims.Init(0,Food.Num());
    Bridge->Seed=RunSeed; Bridge->NeuralWindowMs=NeuralMilliseconds; Bridge->bLearnedReadout=ImprovementStage>=9;
    Random.Initialize(RunSeed);
    for(int32 C=0;C<2;++C)
    {
        Stores[C]=60; NestCondition[C]=1; MaintenanceSpent[C]=SpoiledFood[C]=DeliveredByColony[C]=0;
        UnfundedSeconds[C]=0; DeliveryTrips[C]=0;
        Pheromones[C].Init(0,Food.Num()); ColonyAmounts[C].Init(0,Food.Num()); ColonyKnowledge[C].Empty();
        VisitedResources[C].Empty(); VisitedCells[C].Empty(); LastDamage[C]=-100;
        for(int32 F=0;F<3;++F)
        {
            auto* A=SpawnInsect(C,F,Home(C)+FVector(0,(F-1)*160,0),0);
            A->ScoutIndex=(F+C*3)%Food.Num(); A->ProbePosition=A->GetActorLocation(); A->Energy=85;
        }
    }
    for(auto& F:Food) F.Amount=F.Capacity;
    if(bSynchronousExperiment)
    {
        const FString Folder=FPaths::ProjectSavedDir()/TEXT("BrainLab/iterations")/AuditName;
        IFileManager::Get().MakeDirectory(*Folder,true);
        FFileHelper::SaveStringToFile(TEXT(""),*(Folder/TEXT("trace.jsonl")));
    }
    TelemetryFolder=FPaths::ProjectSavedDir()/TEXT("BrainLab/sessions")/
        (FDateTime::UtcNow().ToString(TEXT("%Y%m%d-%H%M%S"))+TEXT("-")+Bridge->SessionId());
    IFileManager::Get().MakeDirectory(*TelemetryFolder,true); NextLiveSample=0;
    FString Configuration; FFileHelper::LoadFileToString(Configuration,*(FPaths::ProjectConfigDir()/TEXT("BrainBiome.json")));
    FFileHelper::SaveStringToFile(Configuration,*(TelemetryFolder/TEXT("biome-config.json")));
    Record(FString::Printf(TEXT("Mosswild / stage %d / seed %d"),ImprovementStage,RunSeed));
    WriteBiomeTelemetry();
}

void AInsectLab::ConfigureBiomeExperiment(const FString& Json)
{
    TSharedPtr<FJsonObject> O;
    if(!bExpandedBiome||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json),O)) return;
    FString MotorController=TEXT("connectome"), ContactGate=TEXT("neural");
    O->TryGetStringField(TEXT("motor_controller"),MotorController);
    O->TryGetStringField(TEXT("contact_gate"),ContactGate);
    bool Sensory=false; O->TryGetBoolField(TEXT("sensory_competition"),Sensory);
    if((MotorController!=TEXT("connectome")&&MotorController!=TEXT("reactive-v1"))||
       (ContactGate!=TEXT("neural")&&ContactGate!=TEXT("contact"))||
       (MotorController==TEXT("reactive-v1")&&(!Sensory||ContactGate!=TEXT("contact"))))
    { UE_LOG(LogTemp,Error,TEXT("Invalid motor/contact control experiment configuration")); return; }
    // Finalize with the old run's metadata, before applying the next configuration.
    FinishBiomeRecording(TEXT("reconfigure"));
    Bridge->MotorController=MotorController;
    bMatchedContactGate=ContactGate==TEXT("contact");
    auto Read=[&](const TCHAR* Name,float& Value) { double N; if(O->TryGetNumberField(Name,N)&&FMath::IsFinite(N)) Value=float(N); };
    double N;
    if(O->TryGetNumberField(TEXT("stage"),N)) ImprovementStage=FMath::Clamp(int(N),1,10);
    if(O->TryGetNumberField(TEXT("seed"),N)) RunSeed=int(N);
    if(O->TryGetNumberField(TEXT("neural_ms"),N)) NeuralMilliseconds=FMath::Clamp(int32(N),10,100);
    if(O->TryGetNumberField(TEXT("colony_limit"),N)) ColonyLimit=FMath::Clamp(int32(N),4,6);
    O->TryGetBoolField(TEXT("synchronous"),bSynchronousExperiment);
    O->TryGetBoolField(TEXT("swarm"),bSwarmEnabled);
    O->TryGetBoolField(TEXT("predict_senses"),bPredictiveSenses);
    O->TryGetBoolField(TEXT("continuous_economy"),bContinuousEconomy);
    O->TryGetBoolField(TEXT("sensory_competition"),bSensoryCompetition);
    O->TryGetBoolField(TEXT("contact_reflexes"),bContactReflexes);
    Read(TEXT("upkeep_per_adult"),UpkeepPerAdult); Read(TEXT("spoilage_rate"),SpoilageRate);
    Read(TEXT("reserve_base"),ReserveBase); Read(TEXT("reserve_per_adult"),ReservePerAdult);
    UpkeepPerAdult=FMath::Clamp(UpkeepPerAdult,0.f,1.f); SpoilageRate=FMath::Clamp(SpoilageRate,0.f,.01f);
    FString Name; if(O->TryGetStringField(TEXT("name"),Name)) AuditName=FPaths::MakeValidFileName(Name);
    Read(TEXT("duration"),AuditDuration); Read(TEXT("step"),ExperimentStep);
    ExperimentStep=FMath::Clamp(ExperimentStep,.1f,.5f); AuditDuration=FMath::Clamp(AuditDuration,10.f,3600.f);
    Read(TEXT("sense_radius"),SenseRadius); Read(TEXT("separation"),SeparationWeight);
    Read(TEXT("alignment"),AlignmentWeight); Read(TEXT("cohesion"),CohesionWeight);
    Read(TEXT("hunger"),HungerThreshold); Read(TEXT("thirst"),ThirstThreshold);
    Read(TEXT("memory_seconds"),MemorySeconds); Read(TEXT("trail_lifetime"),TrailLifetime);
    Read(TEXT("brood_cost"),BroodCost); Read(TEXT("regrowth"),RegrowthMultiplier);
    Read(TEXT("turn_gain"),TurnGain); Read(TEXT("motor_smoothing"),MotorSmoothing);
    bool Ablate=false; O->TryGetBoolField(TEXT("ablate"),Ablate);
    ResetExperiment(Ablate);
    if(bSynchronousExperiment) FFileHelper::SaveStringToFile(Json,*(FPaths::ProjectSavedDir()/TEXT("BrainLab/iterations")/AuditName/TEXT("config.json")));
}

void AInsectLab::SetSwarmEnabled(bool Enabled) { bSwarmEnabled=Enabled; Record(Enabled?TEXT("Social recruitment enabled"):TEXT("Social recruitment disabled")); }

void AInsectLab::PlanBiome(AInsectAgent* A)
{
    const FVector P=A->GetActorLocation(); const int C=A->Colony;
    for(int I=0;I<Food.Num();++I) if(Distance(P,Food[I].Position)<SenseRadius)
    {
        A->ResourceMemory.Add(I,Elapsed);
        A->ResourceAmounts.Add(I,Food[I].Amount); ColonyAmounts[C][I]=Food[I].Amount;
        if(Food[I].Amount>8) ColonyKnowledge[C].Add(I,Elapsed);
    }
    if(A->Health<25) A->bRetreating=true;
    if(A->Health>49) A->bRetreating=false;
    A->Rival=nullptr; A->bPlayerTarget=false;
    int Kind=Scout,Index=INDEX_NONE; FVector Goal=P;
    auto Nearest=[&](int Type)
    {
        int Best=INDEX_NONE; float D=1.e9;
        for(int I=0;I<Food.Num();++I) if(Food[I].Kind==Type)
        { float X=Distance(P,Food[I].Position); if(X<D) { D=X; Best=I; } }
        return Best;
    };
    auto* Player=UGameplayStatics::GetPlayerPawn(this,0);
    bool PlayerInTerritory=Player&&Distance(Player->GetActorLocation(),A->Nest)<1150;
    if(Player&&ImprovementStage>=8)
        for(int I=0;I<Food.Num();++I)
            if(ResourceOwners[I]==C&&ResourceClaims[I]>2&&Distance(Player->GetActorLocation(),Food[I].Position)<500) PlayerInTerritory=true;
    const bool Critical=A->Energy<30 || (ImprovementStage>=2&&A->Hydration<25);
    const bool PartialLoad=ImprovementStage>=8&&A->Cargo>=10&&A->CargoSource>=0&&
        Distance(P,Food[A->CargoSource].Position)<SenseRadius&&Food[A->CargoSource].Amount<8;
    const bool CargoExpired=bContinuousEconomy&&A->Cargo>2&&Elapsed-A->CargoSince>CargoTimeout;
    const bool SupplyDuty=bContinuousEconomy?A->bProvisioning:Stores[C]<160;
    if(ImprovementStage>=2 && (ImprovementStage<3||A->Energy>25||A->Hydration<15) && (A->Hydration<ThirstThreshold || (A->GoalKind==Drink&&A->Hydration<95)))
    { Kind=Drink; Index=Nearest(1); Goal=Food[Index].Position; }
    else if(A->bRetreating&&!Critical)
    { Kind=Recover; Goal=A->Nest+FVector(C==0?-400:400,180,0); }
    else if(ImprovementStage>=3 && (A->Cargo>=24 || PartialLoad || CargoExpired || (A->GoalKind==Deliver&&A->Cargo>0)))
    { Kind=Deliver; Goal=A->Nest; }
    else
    {
        if(PlayerInTerritory&&Distance(P,Player->GetActorLocation())<1600&&!Critical)
        { Kind=Defend; A->bPlayerTarget=true; Goal=Player->GetActorLocation(); LastDamage[C]=Elapsed; Alarm[C]=Goal; }
        else
        {
            float Best=ImprovementStage>=8?430:550;
            bool AtClaim=false;
            if(ImprovementStage>=8)
                for(int I=0;I<Food.Num();++I)
                    if(ResourceOwners[I]==C&&ResourceClaims[I]>2&&Distance(P,Food[I].Position)<650) AtClaim=true;
            int Allies=0,Enemies=0;
            for(AInsectAgent* B:Agents) if(IsValid(B)&&B!=A&&B->Health>0)
            {
                const float D=Distance(P,B->GetActorLocation());
                if(D<650) { if(B->Colony==C) ++Allies; else ++Enemies; }
                if(B->Colony!=C && D<Best && (Distance(B->GetActorLocation(),A->Nest)<1800||AtClaim))
                { Best=D; A->Rival=B; }
            }
            if(A->Rival.IsValid()&&!Critical)
            {
                if(ImprovementStage>=8 && (Enemies>Allies+1 || A->Health<35))
                { Kind=Recover; Goal=A->Nest; A->Rival=nullptr; }
                else { Kind=Defend; Goal=A->Rival->GetActorLocation(); LastDamage[C]=Elapsed; Alarm[C]=Goal; }
            }
        }
        if(Kind==Scout)
        {
            // Hysteresis prevents reversing a decision after each noisy motor window.
            if(ImprovementStage>=8&&bSwarmEnabled&&!Critical&&A->Cargo<1&&Elapsed-LastDamage[C]<8&&Distance(P,Alarm[C])<1800)
            { Kind=Defend; Goal=Alarm[C]; }
            const bool Committed=Elapsed<A->GoalUntil||ImprovementStage>=4;
            const bool Keep=A->GoalKind==Forage&&A->GoalIndex>=0&&Committed&&(Distance(P,Food[A->GoalIndex].Position)>SenseRadius||Food[A->GoalIndex].Amount>2)&&(A->Energy<112||(SupplyDuty&&A->Cargo<24));
            if(Kind==Scout&&Keep) { Kind=Forage; Index=A->GoalIndex; Goal=Food[Index].Position; }
            else if(Kind==Scout&&(A->Energy<HungerThreshold || (ImprovementStage>=4&&A->GoalKind==Forage&&A->Energy<112) || (ImprovementStage>=3&&SupplyDuty&&A->Cargo<24)))
            {
                float Best=1.e9;
                for(int I=0;I<Food.Num();++I) if(Food[I].Kind==0)
                {
                    const bool Seen=A->ResourceMemory.Contains(I)&&Elapsed-A->ResourceMemory[I]<MemorySeconds;
                    const bool Shared=ImprovementStage>=5&&bSwarmEnabled&&ColonyKnowledge[C].Contains(I)&&Elapsed-ColonyKnowledge[C][I]<MemorySeconds;
                    if(ImprovementStage>=4&&!Seen&&!Shared) continue;
                    const float Available=ImprovementStage<4?Food[I].Amount:(Shared?ColonyAmounts[C][I]:A->ResourceAmounts.FindRef(I));
                    const float MinimumMeal=ImprovementStage>=8&&A->Energy>=25?FMath::Clamp(112-A->Energy,8.f,35.f):4.f;
                    if(Available<MinimumMeal) continue;
                    float Score=Distance(P,Food[I].Position)/160-Available*.035f;
                    if(bContinuousEconomy&&SupplyDuty)
                        Score=(Distance(P,Food[I].Position)+Distance(Food[I].Position,A->Nest)*.6f)/160-FMath::Min(Available,140.f)*.06f;
                    if(ImprovementStage>=5&&bSwarmEnabled) Score-=Pheromones[C][I]*7;
                    if(ImprovementStage>=6)
                    {
                        for(const AInsectAgent* B:Agents) if(B!=A&&B->GoalKind==Forage&&B->GoalIndex==I) Score+=3.2f;
                    }
                    if(Score<Best) { Best=Score; Index=I; }
                }
                if(Index!=INDEX_NONE) { Kind=Forage; Goal=Food[Index].Position; }
            }
            else if(Kind==Scout&&A->Energy>=HungerThreshold)
            { Kind=Rest; Goal=A->Nest+FVector(FMath::Cos(A->AgentId*2.4f)*220,FMath::Sin(A->AgentId*2.4f)*220,0); }
        }
    }
    if(Kind==Scout)
    {
        float Best=1.e9;
        for(int I=0;I<Food.Num();++I) if(Food[I].Kind==0)
        {
            const float Seen=A->ResourceMemory.Contains(I)?A->ResourceMemory[I]:-1000;
            const float Score=Distance(P,Food[I].Position)+FMath::Max(0.f,MemorySeconds-(Elapsed-Seen))*60;
            if(Score<Best) { Best=Score; Index=I; }
        }
        Goal=Food[Index].Position;
    }
    if(ImprovementStage>=8&&Kind==Rest)
    {
        // One fed adult keeps a useful remote patch occupied between meals.
        // Hunger, thirst, wounds and deliveries retain their earlier priorities.
        const AInsectAgent* Guard=nullptr;
        for(const AInsectAgent* B:Agents)
            if(B->Colony==C&&B->Energy>HungerThreshold+12&&B->Hydration>65&&B->Health>45&&B->Age>25&&B->Cargo<1&&!B->bRetreating)
                if(!Guard||B->AgentId<Guard->AgentId) Guard=B;
        if(Guard==A)
        {
            float Best=1.e9;
            for(int I=0;I<Food.Num();++I)
                if(ResourceOwners[I]==C&&ResourceClaims[I]>2&&Food[I].Amount>8&&Distance(Food[I].Position,A->Nest)>1200)
                {
                    const float BorderDistance=FMath::Abs(Distance(Food[I].Position,Homes[0])-Distance(Food[I].Position,Homes[1]));
                    const float Score=Distance(P,Food[I].Position)+BorderDistance*.6f;
                    if(Score<Best) { Best=Score; Index=I; }
                }
            if(Index!=INDEX_NONE)
            {
                Kind=Patrol; const float Angle=Elapsed*.025f+A->AgentId;
                Goal=Food[Index].Position+FVector(260*FMath::Cos(Angle),260*FMath::Sin(Angle),0);
            }
        }
    }
    if(ImprovementStage>=7&&bSwarmEnabled&&Kind==Forage&&!Critical&&A->Cargo<1)
    {
        AInsectAgent* Leader=nullptr;
        for(AInsectAgent* B:Agents) if(B->Colony==C&&B->AgentId<A->AgentId&&B->AgentId%2==A->AgentId%2&&B->GoalKind==Forage&&B->GoalIndex>=0&&Distance(P,B->GetActorLocation())<1500)
            if(!Leader||B->AgentId<Leader->AgentId) Leader=B;
        if(Leader&&(ImprovementStage<8||Distance(P,Food[Leader->GoalIndex].Position)>SenseRadius||Food[Leader->GoalIndex].Amount>=35))
        { Index=Leader->GoalIndex; Goal=Food[Index].Position; }
    }
    if(Kind!=A->GoalKind||Index!=A->GoalIndex) { ++GoalChanges; A->GoalUntil=Elapsed+8; }
    A->GoalKind=Kind; A->GoalIndex=Index; A->FoodTarget=Kind==Forage?Index:INDEX_NONE;
    A->Target=Goal;
    const TCHAR* Names[]={TEXT("Scout"),TEXT("Forage"),TEXT("Carry home"),TEXT("Drink"),TEXT("Recover"),TEXT("Defend"),TEXT("Nest"),TEXT("Patrol")};
    A->Intent=Names[Kind];
}

FVector AInsectLab::RouteBiome(AInsectAgent* A,FVector Goal)
{
    const FVector P=A->GetActorLocation();
    if(ImprovementStage<4) return Goal;
    if(Elapsed<A->AvoidUntil&&Distance(P,A->AvoidPoint)>90) return A->AvoidPoint;
    const FVector Direction=Flat(Goal-P);
    for(const auto& B:Obstacles)
    {
        const float Along=FVector::DotProduct(B.Position-P,Direction);
        if(Along<-20||Along>FMath::Min(1000.f,Distance(P,Goal))) continue;
        const FVector Nearest=P+Direction*Along;
        if(Distance(Nearest,B.Position)<B.Radius+85)
        {
            FVector Side(-Direction.Y,Direction.X,0);
            if(FVector::DotProduct(P-B.Position,Side)<0) Side=-Side;
            if(Distance(P,B.Position)<B.Radius+100)
            {
                A->AvoidPoint=P+Flat(P-B.Position)*220+Side*80;
                A->AvoidUntil=Elapsed+3; return A->AvoidPoint;
            }
            A->AvoidPoint=B.Position+Side*(B.Radius+170)+Direction*130;
            A->AvoidUntil=Elapsed+7; return A->AvoidPoint;
        }
    }
    if(ImprovementStage>=6&&A->StuckTime>5)
    {
        const FVector Side(-Direction.Y,Direction.X,0);
        A->AvoidPoint=P+Side*(A->AgentId%2?300:-300)-Direction*150;
        A->AvoidUntil=Elapsed+4; A->StuckTime=0; return A->AvoidPoint;
    }
    return Goal;
}

FVector AInsectLab::SocialDirection(AInsectAgent* A,FVector Direction) const
{
    if(ImprovementStage<2) return Direction;
    const FVector P=A->GetActorLocation(); FVector Separation=FVector::ZeroVector,Alignment=FVector::ZeroVector,Center=FVector::ZeroVector;
    int N=0;
    for(const AInsectAgent* B:Agents) if(B!=A&&IsValid(B)&&B->Health>0)
    {
        const float D=Distance(P,B->GetActorLocation());
        if(D<180&&D>1) Separation+=Flat(P-B->GetActorLocation())*(1-D/180);
        if(ImprovementStage>=7&&bSwarmEnabled&&B->Colony==A->Colony&&D<800&&B->GoalKind==A->GoalKind&&B->GoalIndex==A->GoalIndex&&B->Speed>20)
        { Alignment+=B->GetActorForwardVector(); Center+=B->GetActorLocation(); ++N; }
    }
    FVector Result=Direction+Separation*SeparationWeight;
    if(N>0&&Distance(P,A->Target)>300)
        Result+=Flat(Alignment)*AlignmentWeight+Flat(Center/N-P)*CohesionWeight;
    return Flat(Result);
}

void AInsectLab::SubmitBiome()
{
    if(Bridge->IsPending()||LivingCount()==0) return;
    SensoryLookahead=0;
    if(!bSynchronousExperiment&&bPredictiveSenses)
    {
        const float Frame=FMath::Max(.001f,GetWorld()->GetDeltaSeconds());
        // Account for the body-delta clamp and delivery over the game thread.
        // The available command credit bounds prediction when the brain is slow.
        const float BodyRate=FMath::Min(.1f,Frame)/Frame;
        SensoryLookahead=FMath::Min(MotorTimeCredit,(Bridge->BatchMilliseconds*.001f+Frame*2)*BodyRate);
    }
    if(!bSensoryCompetition) AssignProvisioners();
    TArray<FInsectSenses> Senses;
    for(AInsectAgent* A:Agents) if(A->Health>0)
    {
        if(bSensoryCompetition) { Senses.Add(SenseBiome(A)); continue; }
        PlanBiome(A);
        FVector Guide=A->Target;
        if(ImprovementStage>=5&&bSwarmEnabled&&A->GoalKind==Forage)
        {
            float Best=Distance(A->GetActorLocation(),Guide);
            for(const auto& T:Trails) if(T.Colony==A->Colony&&T.Food==A->GoalIndex&&Distance(A->GetActorLocation(),T.Position)<800&&Distance(A->GetActorLocation(),T.Position)>140)
            {
                const float D=Distance(T.Position,A->Target);
                if(D<Best-100) { Best=D; Guide=T.Position; }
            }
        }
        FVector Goal=RouteBiome(A,Guide);
        FVector SensePosition=A->GetActorLocation(); float SenseYaw=A->GetActorRotation().Yaw;
        FInsectMotor Current;
        if(SensoryLookahead>0&&Bridge->ReadMotor(A->AgentId,Current))
            A->PredictMotion(Current,SensoryLookahead,ImprovementStage>=9?MotorSmoothing:0,SensePosition,SenseYaw);
        FVector Direction=SocialDirection(A,Flat(Goal-SensePosition));
        const float Bearing=FMath::FindDeltaAngleDegrees(SenseYaw,Direction.Rotation().Yaw);
        const float D=Distance(SensePosition,A->Target);
        FInsectSenses S; S.AgentId=A->AgentId; S.Backend=A->Backend();
        S.Bearing=FMath::Clamp(Bearing/65.f*TurnGain,-1.f,1.f);
        S.Drive=D<100?.08f:(FMath::Abs(Bearing)>70?.28f:1.f);
        if(ImprovementStage>=3&&D<155&&(A->GoalKind==Forage||A->GoalKind==Drink)) S.Drive=FMath::Max(S.Drive,.32f);
        if(ImprovementStage>=8&&D<190&&A->GoalKind==Defend) S.Drive=FMath::Max(S.Drive,.32f);
        // A common sensory cruise speed lets differently shaped bodies travel together.
        if(ImprovementStage>=7&&bSwarmEnabled&&D>350)
        {
            bool HasCompanion=false;
            for(const AInsectAgent* B:Agents)
                if(B!=A&&B->Colony==A->Colony&&B->GoalKind==A->GoalKind&&B->GoalIndex==A->GoalIndex&&Distance(A->GetActorLocation(),B->GetActorLocation())<850) HasCompanion=true;
            if(HasCompanion)
            {
                const float TopSpeed=A->Form==0?155.f:(A->Form==1?200.f:240.f);
                S.Drive=FMath::Min(S.Drive,150.f/TopSpeed);
            }
        }
        // Rest is a neutral sensory input, not a forced motor stop.
        if(bContinuousEconomy&&A->GoalKind==Rest&&D<150) { S.Drive=0; S.Bearing=0; }
        S.Threat=A->bRetreating?.12f:0;
        Senses.Add(S);
    }
    Bridge->SubmitSenses(Senses);
}

void AInsectLab::StepBiome(float Dt)
{
    const bool Reflexes=bSensoryCompetition||bContactReflexes;
    bool Active=LivingCount()==0;
    for(AInsectAgent* A:Agents) if(IsValid(A)&&A->Health>0)
    {
        FInsectMotor M;
        if(!Bridge->ReadMotor(A->AgentId,M)) { A->Speed=0; continue; }
        const bool ContactAllowed=bMatchedContactGate||M.ForwardHz>4;
        Active=true; AgentSeconds+=Dt; A->Age+=Dt; A->AttackCooldown-=Dt; A->BirthCooldown-=Dt;
        const FVector Before=A->GetActorLocation();
        if(ImprovementStage>=9)
        {
            const float Alpha=1-FMath::Exp(-Dt/FMath::Max(.05f,MotorSmoothing));
            A->NeuralDrive=FMath::Lerp(A->NeuralDrive,M.Drive,Alpha); A->NeuralTurn=FMath::Lerp(A->NeuralTurn,M.Turn,Alpha);
            M.Drive=A->NeuralDrive; M.Turn=A->NeuralTurn;
        }
        A->MoveFromBrain(M,Dt);
        const FVector P=A->GetActorLocation(); A->DistanceTravelled+=Distance(Before,P);
        if(ImprovementStage>=2) A->Speed=Distance(Before,P)/FMath::Max(Dt,.001f);
        A->bFeeding=A->bDrinking=false;
        if(ImprovementStage>=3&&A->Energy<25&&A->Cargo>0&&ContactAllowed)
        {
            const float Eaten=FMath::Min(A->Cargo,Dt*18);
            A->Cargo-=Eaten; A->Energy+=Eaten; A->FoodConsumed+=Eaten; A->bFeeding=true;
        }
        A->Energy=FMath::Max(0.f,A->Energy-Dt*(.24f+M.Drive*.18f));
        if(ImprovementStage>=2) A->Hydration=FMath::Max(0.f,A->Hydration-Dt*(.12f+M.Drive*.07f));
        if(A->Energy<=0||A->Hydration<=0) A->Health-=Dt*3;
        if((Reflexes?A->Health<60:A->GoalKind==Recover)&&Distance(P,A->Nest)<850&&A->Energy>18)
        { A->Health=FMath::Min(60.f,A->Health+Dt*2); A->Energy-=Dt*.5f; }
        int ContactIndex=A->GoalIndex;
        if(Reflexes)
        {
            ContactIndex=INDEX_NONE; float ContactDistance=155;
            for(int I=0;I<Food.Num();++I)
            {
                const float D=Distance(P,Food[I].Position);
                if(D<ContactDistance) { ContactDistance=D; ContactIndex=I; }
            }
            if(bSensoryCompetition) A->Intent=TEXT("Sensing");
        }
        A->ContactResource=Food.IsValidIndex(ContactIndex)&&Distance(P,Food[ContactIndex].Position)<155?ContactIndex:INDEX_NONE;
        if(A->ContactResource!=INDEX_NONE&&ContactAllowed)
        {
            auto& F=Food[ContactIndex];
            if(F.Kind==1&&(Reflexes||A->GoalKind==Drink)) { A->Hydration=FMath::Min(100.f,A->Hydration+Dt*25); A->bDrinking=true; }
            if(F.Kind==0&&(Reflexes||A->GoalKind==Forage)&&F.Amount>0)
            {
                const float Eaten=FMath::Min3(F.Amount,Dt*18.f,120-A->Energy);
                F.Amount-=Eaten; A->Energy+=Eaten; A->FoodConsumed+=Eaten; A->bFeeding=Eaten>0;
                const float Pickup=Reflexes?FMath::Clamp((ColonyDemand(A->Colony)-Stores[A->Colony])/FMath::Max(1.f,ColonyDemand(A->Colony)),0.f,1.f):1.f;
                if(ImprovementStage>=3&&A->Energy>100&&(Reflexes||ImprovementStage<4||(bContinuousEconomy?A->bProvisioning:Stores[A->Colony]<160)||A->Cargo>0))
                { const float Picked=FMath::Min3(F.Amount,Dt*16.f*Pickup,30-A->Cargo); F.Amount-=Picked; if(Picked>0&&A->Cargo<=0) A->CargoSince=Elapsed; A->Cargo+=Picked; A->bFeeding|=Picked>0; if(Picked>0) A->CargoSource=ContactIndex; }
                if(A->bFeeding&&!A->bWasEating) { ++Meals; ++ResourceVisits; }
                if(A->bFeeding)
                {
                    VisitedResources[A->Colony].Add(ContactIndex); A->Health=FMath::Min(60.f,A->Health+Dt);
                    if(ImprovementStage>=8)
                    {
                        auto& Owner=ResourceOwners[ContactIndex]; auto& Claim=ResourceClaims[ContactIndex]; const float BeforeClaim=Claim;
                        if(Owner==INDEX_NONE) Owner=A->Colony;
                        Claim+=Dt*(Owner==A->Colony?2.f:-3.f);
                        if(Claim<0) { Owner=A->Colony; Claim=-Claim; }
                        Claim=FMath::Min(Claim,20.f);
                        if(BeforeClaim<=2&&Claim>2)
                            Record(FString::Printf(TEXT("%s colony claimed %s"),Owner==0?TEXT("Cyan"):TEXT("Amber"),*F.Name));
                    }
                }
                if(ImprovementStage>=5&&bSwarmEnabled&&F.Amount>10) Pheromones[A->Colony][ContactIndex]=1;
            }
        }
        A->bWasEating=A->bFeeding;
        if(bSensoryCompetition)
        {
            if(A->bFeeding) A->Intent=TEXT("Eating at contact");
            if(A->bDrinking) A->Intent=TEXT("Drinking at contact");
        }
        if(ImprovementStage>=3&&A->Cargo>0&&Distance(P,A->Nest)<220)
        {
            Stores[A->Colony]+=A->Cargo; FoodDelivered+=A->Cargo; A->FoodDelivered+=A->Cargo;
            if(A->Cargo>=1) Record(FString::Printf(TEXT("%s #%d delivered %.0f nectar"),A->Colony==0?TEXT("Cyan"):TEXT("Amber"),A->AgentId,A->Cargo));
            DeliveredByColony[A->Colony]+=A->Cargo; ++DeliveryTrips[A->Colony];
            A->Cargo=0; A->bProvisioning=false; A->LastDeliveryTime=Elapsed;
        }
        if(ImprovementStage>=5&&bSwarmEnabled&&A->Cargo>0&&A->CargoSource>=0)
        {
            A->TrailTimer-=Dt;
            if(A->TrailTimer<=0)
            { FBiomeTrail T; T.Position=P; T.Colony=A->Colony; T.Food=A->CargoSource; T.Strength=1; Trails.Add(T); A->TrailTimer=2; }
        }
        if(Reflexes) SenseContactThreats(A);
        if(A->AttackCooldown<=0&&ContactAllowed&&(Reflexes||A->GoalKind==Defend))
        {
            if(A->Rival.IsValid()&&Distance(P,A->Rival->GetActorLocation())<160)
            {
                A->Rival->Health-=8; A->Rival->HurtPulse=1; A->AttackPulse=1; A->Energy=FMath::Max(0.f,A->Energy-1.5f);
                A->AttackCooldown=1.7f; ++Fights;
                if(Fights%5==1) Record(FString::Printf(TEXT("Territory clash: %s #%d hit #%d"),A->Colony==0?TEXT("Cyan"):TEXT("Amber"),A->AgentId,A->Rival->AgentId));
            }
            if(A->bPlayerTarget)
            {
                auto* Player=UGameplayStatics::GetPlayerPawn(this,0);
                if(Player&&Distance(P,Player->GetActorLocation())<170)
                { PlayerHealth-=7; ++PlayerHits; A->AttackPulse=1; A->AttackCooldown=1.7f; Record(TEXT("Player bitten inside a colony territory")); }
            }
        }
        int ColonySize=0; for(const AInsectAgent* B:Agents) if(B->Colony==A->Colony) ++ColonySize;
        for(const auto& E:Eggs) if(E.Colony==A->Colony) ++ColonySize;
        const bool Brood=ImprovementStage<3 || (Stores[A->Colony]>=BroodCost&&(!bContinuousEconomy||NestCondition[A->Colony]>.55f));
        if(A->Energy>=108&&A->Hydration>50&&A->Health>=42&&A->Age>25&&A->BirthCooldown<=0&&ColonySize<ColonyLimit&&LivingCount()+Eggs.Num()<ColonyLimit*2&&Distance(P,A->Nest)<500&&Brood)
        {
            FInsectEgg E; E.Colony=A->Colony; E.Form=A->Form; E.Generation=A->Generation+1;
            E.Position=A->Nest+FVector(Random.FRandRange(-170,170),Random.FRandRange(-170,170),-20);
            E.Visual=Orb(FString::Printf(TEXT("BiomeEgg%d"),++EggsLaid),E.Position,FVector(.38,.32,.5),A->Colony==0?TEXT("Cyan"):TEXT("Amber"));
            Eggs.Add(E); A->Energy-=40; A->BirthCooldown=60; if(ImprovementStage>=3) Stores[A->Colony]-=BroodCost;
        }
        A->ProbeTime+=Dt;
        if(A->ProbeTime>=2)
        {
            if(Distance(P,A->ProbePosition)<35&&(bSensoryCompetition?!(A->bFeeding||A->bDrinking):Distance(P,A->Target)>300)&&M.Drive>.1f)
            { A->StuckTime+=A->ProbeTime; StuckSeconds+=A->ProbeTime; }
            else A->StuckTime=0;
            A->ProbeTime=0; A->ProbePosition=P;
        }
        const int CellX=FMath::FloorToInt((P.X+HalfWidth)/700),CellY=FMath::FloorToInt((P.Y+HalfHeight)/700);
        VisitedCells[A->Colony].Add(CellY*100+CellX);
    }
    if(!Active) return;
    Elapsed+=Dt;
    if(bContinuousEconomy)
    {
        for(int C=0;C<2;++C)
        {
            int Adults=0,Pods=0;
            for(const AInsectAgent* A:Agents) if(A->Colony==C&&A->Health>0) ++Adults;
            for(const auto& E:Eggs) if(E.Colony==C) ++Pods;
            const float Needed=Dt*(Adults?(.06f+Adults*UpkeepPerAdult+Pods*.02f):0.f);
            const float Paid=FMath::Min(Stores[C],Needed); Stores[C]-=Paid; MaintenanceSpent[C]+=Paid;
            const bool Funded=Paid+UE_SMALL_NUMBER>=Needed;
            if(!Funded) UnfundedSeconds[C]+=Dt;
            NestCondition[C]=FMath::Clamp(NestCondition[C]+Dt*(Funded?.004f:-.006f),0.f,1.f);
            const float Spoiled=FMath::Min(Stores[C],Stores[C]*SpoilageRate*Dt);
            Stores[C]-=Spoiled; SpoiledFood[C]+=Spoiled;
        }
    }
    for(int I=0;I<ResourceClaims.Num();++I)
    {
        ResourceClaims[I]=FMath::Max(0.f,ResourceClaims[I]-Dt*.04f);
        if(ResourceClaims[I]<=0) ResourceOwners[I]=INDEX_NONE;
    }
    for(auto& F:Food)
    {
        const float Seasonal=ImprovementStage>=4?.25f+.75f*FMath::Max(0.f,FMath::Sin(Elapsed/45+F.Phase)):1.f;
        if(!bDrought) F.Amount=FMath::Min(F.Capacity,F.Amount+Dt*F.Regrowth*RegrowthMultiplier*Seasonal);
        if(F.Visual) { float Scale=.18f+1.2f*F.Amount/F.Capacity; F.Visual->SetWorldScale3D(FVector(Scale,Scale,Scale*.65f)); }
    }
    for(int C=0;C<2;++C)
    {
        for(float& V:Pheromones[C]) V*=FMath::Exp(-Dt/FMath::Max(5.f,TrailLifetime));
        FVector Sum=FVector::ZeroVector; int Moving=0,Grouped=0;
        for(const AInsectAgent* A:Agents) if(A->Colony==C&&A->Speed>30)
        {
            Sum+=A->GetActorForwardVector(); ++Moving; int Neighbours=0; FVector Local=A->GetActorForwardVector();
            for(const AInsectAgent* B:Agents) if(A!=B&&B->Colony==C&&B->Speed>30&&Distance(A->GetActorLocation(),B->GetActorLocation())<850)
            { ++Neighbours; Local+=B->GetActorForwardVector(); }
            if(Neighbours>=2&&Local.Size()/(Neighbours+1)>.65f) ++Grouped;
        }
        if(Moving>=3)
        { Polarization=Sum.Size()/Moving; AlignmentSum+=Polarization*Dt; AlignmentSamples+=Dt; SwarmSamples+=float(Grouped)/Moving*Dt; SocialSamples+=Dt; }
    }
    SwarmFraction=SocialSamples>0?SwarmSamples/SocialSamples:0;
    for(int I=Trails.Num()-1;I>=0;--I) { Trails[I].Age+=Dt; if(Trails[I].Age>TrailLifetime) Trails.RemoveAt(I); }
    if(Trails.Num()>256) Trails.RemoveAt(0,Trails.Num()-256);
    if(FMath::FloorToInt(Elapsed)!=FMath::FloorToInt(Elapsed-Dt)&&CyanTrails&&AmberTrails)
    {
        CyanTrails->ClearInstances(); AmberTrails->ClearInstances();
        for(int I=0;I<Food.Num();++I) if(ResourceOwners[I]!=INDEX_NONE&&ResourceClaims[I]>2)
        {
            UInstancedStaticMeshComponent* Cloud=ResourceOwners[I]==0?CyanTrails:AmberTrails;
            for(int J=0;J<12;++J)
            {
                const float Angle=J*2*PI/12;
                const FVector P=Food[I].Position+FVector(500*FMath::Cos(Angle),500*FMath::Sin(Angle),-26);
                Cloud->AddInstance(FTransform(FQuat::Identity,P,FVector(.10f,.10f,.025f)));
            }
        }
        for(const auto& T:Trails)
        {
            const float S=.03f+.07f*(1-T.Age/TrailLifetime);
            (T.Colony==0?CyanTrails:AmberTrails)->AddInstance(FTransform(FQuat::Identity,FVector(T.Position.X,T.Position.Y,9),FVector(S,S,.025f)));
        }
    }
    for(int I=Eggs.Num()-1;I>=0;--I)
    {
        auto& E=Eggs[I]; E.Remaining-=Dt*(bContinuousEconomy?FMath::Lerp(.4f,1.f,NestCondition[E.Colony]):1.f);
        if(E.Remaining<=0)
        {
            const auto Copy=E; E.Visual->DestroyComponent(); Eggs.RemoveAt(I);
            auto* A=SpawnInsect(Copy.Colony,Copy.Form,Copy.Position+FVector(0,0,20),Copy.Generation);
            if(A)
            {
                ++Births; A->ProbePosition=A->GetActorLocation();
                Record(FString::Printf(TEXT("%s hatchling #%d / generation %d"),A->Colony==0?TEXT("Cyan"):TEXT("Amber"),A->AgentId,A->Generation));
            }
        }
    }
    for(int I=Agents.Num()-1;I>=0;--I) if(Agents[I]->Health<=0)
    {
        const auto A=Agents[I];
        if(A->Energy<=0) ++StarvationDeaths; else if(A->Hydration<=0) ++DehydrationDeaths; else ++CombatDeaths;
        Record(FString::Printf(TEXT("%s #%d died / %s"),A->Colony==0?TEXT("Cyan"):TEXT("Amber"),A->AgentId,A->Energy<=0?TEXT("hunger"):(A->Hydration<=0?TEXT("thirst"):TEXT("combat"))));
        A->Destroy(); Agents.RemoveAt(I); ++Deaths;
    }
    if(PlayerHealth<=0)
    { if(auto* Player=UGameplayStatics::GetPlayerPawn(this,0)) Player->SetActorLocation(FVector(-4200,3200,110)); PlayerHealth=100; }
}

void AInsectLab::TickBiome(float Dt)
{
    if(bPaused) { for(AInsectAgent* A:Agents) A->Speed=0; return; }
    RequestTimer-=Dt;
    if(bSynchronousExperiment)
    {
        if(Bridge->CompletedBatches>ConsumedBatch||LivingCount()==0)
        {
            ConsumedBatch=Bridge->CompletedBatches;
            const int Steps=FMath::CeilToInt(ExperimentStep/.05f);
            for(int I=0;I<Steps;++I) StepBiome(ExperimentStep/Steps);
            if(Elapsed>=TelemetryTimer)
            {
                const FString Folder=FPaths::ProjectSavedDir()/TEXT("BrainLab/iterations")/AuditName;
                const FString Snapshot=BiomeSnapshot();
                FFileHelper::SaveStringToFile(Snapshot+TEXT("\n"),*(Folder/TEXT("trace.jsonl")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,&IFileManager::Get(),FILEWRITE_Append);
                FFileHelper::SaveStringToFile(Snapshot,*(Folder/TEXT("latest.json")));
                TelemetryTimer=Elapsed+1;
            }
            if(Elapsed>=AuditDuration)
            {
                bPaused=true;
                FFileHelper::SaveStringToFile(BiomeSnapshot(),*(FPaths::ProjectSavedDir()/TEXT("BrainLab/iterations")/AuditName/TEXT("complete.json")));
                return;
            }
        }
        if(!Bridge->IsPending()&&RequestTimer<=0) { SubmitBiome(); RequestTimer=.02f; }
    }
    else
    {
        // Bound each answer's lifetime in the body clock. Slow full-brain batches
        // slow ecology instead of driving indefinitely on an obsolete turn.
        if(Bridge->CompletedBatches>ConsumedBatch)
        { ConsumedBatch=Bridge->CompletedBatches; MotorTimeCredit=ExperimentStep; }
        if(RequestTimer<=0&&!Bridge->IsPending()) { SubmitBiome(); RequestTimer=.3f; }
        const float Step=LivingCount()==0?Dt:FMath::Min(Dt,MotorTimeCredit);
        if(Step>0) { StepBiome(Step); MotorTimeCredit=FMath::Max(0.f,MotorTimeCredit-Step); }
        else for(AInsectAgent* A:Agents) A->Speed=0;
    }
    if(Elapsed>=NextLiveSample) WriteBiomeTelemetry();
}

FString AInsectLab::BiomeSnapshot() const
{
    auto O=MakeShared<FJsonObject>();
    O->SetNumberField(TEXT("elapsed"),Elapsed); O->SetNumberField(TEXT("wall_seconds"),FPlatformTime::Seconds()-AuditStarted);
    O->SetNumberField(TEXT("stage"),ImprovementStage); O->SetNumberField(TEXT("seed"),RunSeed); O->SetBoolField(TEXT("swarm"),bSwarmEnabled);
    O->SetNumberField(TEXT("alive"),LivingCount()); O->SetNumberField(TEXT("eggs"),Eggs.Num()); O->SetNumberField(TEXT("births"),Births);
    O->SetNumberField(TEXT("deaths"),Deaths); O->SetNumberField(TEXT("starvation_deaths"),StarvationDeaths); O->SetNumberField(TEXT("dehydration_deaths"),DehydrationDeaths); O->SetNumberField(TEXT("combat_deaths"),CombatDeaths);
    O->SetNumberField(TEXT("meals"),Meals); O->SetNumberField(TEXT("fights"),Fights); O->SetNumberField(TEXT("player_hits"),PlayerHits); O->SetNumberField(TEXT("player_health"),PlayerHealth);
    O->SetNumberField(TEXT("food_delivered"),FoodDelivered); O->SetNumberField(TEXT("cyan_store"),Stores[0]); O->SetNumberField(TEXT("amber_store"),Stores[1]);
    O->SetNumberField(TEXT("goal_changes"),GoalChanges); O->SetNumberField(TEXT("stuck_fraction"),AgentSeconds>0?StuckSeconds/AgentSeconds:0);
    O->SetNumberField(TEXT("polarization"),AlignmentSamples>0?AlignmentSum/AlignmentSamples:0); O->SetNumberField(TEXT("swarm_fraction"),SwarmFraction);
    O->SetNumberField(TEXT("social_seconds"),SocialSamples); O->SetNumberField(TEXT("coverage"),VisitedCells[0].Num()+VisitedCells[1].Num()); O->SetNumberField(TEXT("resource_visits"),VisitedResources[0].Num()+VisitedResources[1].Num());
    O->SetNumberField(TEXT("batch_ms"),Bridge->BatchMilliseconds); O->SetNumberField(TEXT("batches"),Bridge->CompletedBatches); O->SetStringField(TEXT("status"),Bridge->Status); O->SetBoolField(TEXT("ablation"),Bridge->bAblated);
    O->SetNumberField(TEXT("neural_ms"),Bridge->NeuralWindowMs);
    O->SetBoolField(TEXT("predict_senses"),!bSynchronousExperiment&&bPredictiveSenses);
    O->SetNumberField(TEXT("sensory_lookahead_ms"),SensoryLookahead*1000);
    O->SetNumberField(TEXT("colony_limit"),ColonyLimit);
    O->SetBoolField(TEXT("continuous_economy"),bContinuousEconomy);
    O->SetStringField(TEXT("controller"),bSensoryCompetition?TEXT("sensory-populations-v1"):TEXT("planner"));
    O->SetBoolField(TEXT("contact_reflexes"),bSensoryCompetition||bContactReflexes);
    O->SetStringField(TEXT("motor_controller"),Bridge->MotorController);
    O->SetStringField(TEXT("contact_gate"),bMatchedContactGate?TEXT("contact"):TEXT("neural"));
    O->SetBoolField(TEXT("social_steering"),bSwarmEnabled&&!bSensoryCompetition);
    O->SetStringField(TEXT("neural_session"),Bridge->SessionId());
    O->SetStringField(TEXT("telemetry_folder"),FPaths::ConvertRelativePathToFull(TelemetryFolder));
    O->SetNumberField(TEXT("maintenance_spent"),MaintenanceSpent[0]+MaintenanceSpent[1]);
    O->SetNumberField(TEXT("spoiled_food"),SpoiledFood[0]+SpoiledFood[1]);
    TArray<TSharedPtr<FJsonValue>> Colonies;
    for(int C=0;C<2;++C)
    {
        auto Row=MakeShared<FJsonObject>();
        Row->SetNumberField(TEXT("colony"),C); Row->SetNumberField(TEXT("store"),Stores[C]);
        Row->SetNumberField(TEXT("target"),ColonyDemand(C)); Row->SetNumberField(TEXT("condition"),NestCondition[C]);
        Row->SetNumberField(TEXT("upkeep"),MaintenanceSpent[C]); Row->SetNumberField(TEXT("spoilage"),SpoiledFood[C]);
        Row->SetNumberField(TEXT("unfunded_seconds"),UnfundedSeconds[C]);
        Row->SetNumberField(TEXT("delivered"),DeliveredByColony[C]); Row->SetNumberField(TEXT("trips"),DeliveryTrips[C]);
        Colonies.Add(MakeShared<FJsonValueObject>(Row));
    }
    O->SetArrayField(TEXT("colonies"),Colonies);
    TArray<TSharedPtr<FJsonValue>> Rows;
    for(const AInsectAgent* A:Agents)
    {
        auto R=MakeShared<FJsonObject>(); const auto P=A->GetActorLocation();
        R->SetNumberField(TEXT("id"),A->AgentId); R->SetStringField(TEXT("backend"),A->Backend()); R->SetStringField(TEXT("intent"),A->Intent); R->SetNumberField(TEXT("goal"),A->GoalKind); R->SetNumberField(TEXT("resource"),A->GoalIndex);
        R->SetBoolField(TEXT("provisioning"),A->bProvisioning); R->SetNumberField(TEXT("cargo_since"),A->CargoSince);
        R->SetNumberField(TEXT("contact_resource"),A->ContactResource);
        TArray<TSharedPtr<FJsonValue>> Channels,Needs;
        for(float V:A->SensoryChannels) Channels.Add(MakeShared<FJsonValueNumber>(V));
        for(float V:A->SensoryNeeds) Needs.Add(MakeShared<FJsonValueNumber>(V));
        R->SetArrayField(TEXT("sensory_channels"),Channels); R->SetArrayField(TEXT("sensory_needs"),Needs);
        R->SetNumberField(TEXT("energy"),A->Energy); R->SetNumberField(TEXT("hydration"),A->Hydration); R->SetNumberField(TEXT("cargo"),A->Cargo); R->SetNumberField(TEXT("health"),A->Health); R->SetNumberField(TEXT("generation"),A->Generation);
        R->SetNumberField(TEXT("x"),P.X); R->SetNumberField(TEXT("y"),P.Y); R->SetNumberField(TEXT("yaw"),A->GetActorRotation().Yaw); R->SetNumberField(TEXT("target_x"),A->Target.X); R->SetNumberField(TEXT("target_y"),A->Target.Y);
        R->SetNumberField(TEXT("drive"),A->Motor.Drive); R->SetNumberField(TEXT("turn"),A->Motor.Turn); R->SetNumberField(TEXT("forward_hz"),A->Motor.ForwardHz); R->SetNumberField(TEXT("left_hz"),A->Motor.LeftHz); R->SetNumberField(TEXT("right_hz"),A->Motor.RightHz);
        R->SetNumberField(TEXT("distance"),A->DistanceTravelled); R->SetNumberField(TEXT("consumed"),A->FoodConsumed); R->SetNumberField(TEXT("delivered"),A->FoodDelivered); R->SetNumberField(TEXT("speed"),A->Speed);
        Rows.Add(MakeShared<FJsonValueObject>(R));
    }
    O->SetArrayField(TEXT("agents"),Rows);
    TArray<TSharedPtr<FJsonValue>> Resources;
    for(int I=0;I<Food.Num();++I)
    {
        auto R=MakeShared<FJsonObject>(); R->SetNumberField(TEXT("index"),I);
        R->SetNumberField(TEXT("amount"),Food[I].Amount); R->SetNumberField(TEXT("owner"),ResourceOwners[I]);
        R->SetNumberField(TEXT("claim"),ResourceClaims[I]); Resources.Add(MakeShared<FJsonValueObject>(R));
    }
    O->SetArrayField(TEXT("resources"),Resources); return JsonString(O);
}


float AInsectLab::ColonyDemand(int32 Colony) const
{
    int Members=0; for(const AInsectAgent* A:Agents) if(A->Colony==Colony&&A->Health>0) ++Members;
    return ReserveBase+Members*ReservePerAdult;
}

void AInsectLab::AssignProvisioners()
{
    if(!bContinuousEconomy) return;
    for(int C=0;C<2;++C)
    {
        float Incoming=0; int Workers=0;
        for(AInsectAgent* A:Agents) if(A->Colony==C&&A->Health>0) Incoming+=A->Cargo;
        const bool Demand=Stores[C]+Incoming<ColonyDemand(C);
        const int Limit=Stores[C]<BroodCost?3:2;
        for(AInsectAgent* A:Agents) if(A->Colony==C&&A->Health>0)
        {
            if(A->Cargo<1&&(!Demand||A->bRetreating||A->Hydration<25)) A->bProvisioning=false;
            if(A->bProvisioning) ++Workers;
        }
        while(Demand&&Workers<Limit)
        {
            AInsectAgent* Best=nullptr; float Score=1.e9f;
            for(AInsectAgent* A:Agents) if(A->Colony==C&&A->Health>40&&!A->bProvisioning&&!A->bRetreating&&A->Energy>HungerThreshold-8&&A->Hydration>ThirstThreshold+8)
            {
                // Rotate delivery work; depleted/thirsty individuals keep their own needs first.
                const float Cost=A->LastDeliveryTime*.12f+Distance(A->GetActorLocation(),A->Nest)/1000-A->Energy*.03f;
                if(Cost<Score) { Score=Cost; Best=A; }
            }
            if(!Best) break;
            Best->bProvisioning=true; ++Workers;
        }
    }
}

void AInsectLab::WriteBiomeTelemetry(bool Final)
{
    if(TelemetryFolder.IsEmpty()) return;
    const FString Snapshot=BiomeSnapshot();
    FFileHelper::SaveStringToFile(Snapshot+TEXT("\n"),*(TelemetryFolder/TEXT("trace.jsonl")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,&IFileManager::Get(),FILEWRITE_Append);
    FFileHelper::SaveStringToFile(Snapshot,*(TelemetryFolder/(Final?TEXT("final.json"):TEXT("latest.json"))));
    NextLiveSample=Elapsed+2;
}

void AInsectLab::FinishBiomeRecording(const FString& Reason)
{
    if(TelemetryFolder.IsEmpty()) return;
    WriteBiomeTelemetry(true);
    FFileHelper::SaveStringToFile(Reason,*(TelemetryFolder/TEXT("end-reason.txt")));
    TelemetryFolder.Empty();
}
