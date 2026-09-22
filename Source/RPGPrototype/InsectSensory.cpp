#include "InsectLab.h"
#include "InsectAgent.h"
#include "InsectBrainBridge.h"
#include "Kismet/GameplayStatics.h"

void AInsectLab::SetSensoryCompetition(bool Enabled)
{
    if(!bExpandedBiome) return;
    FinishBiomeRecording(TEXT("controller_switch"));
    bSensoryCompetition=Enabled;
    Bridge->MotorController=TEXT("connectome");
    bMatchedContactGate=false;
    ResetExperiment(false);
}

FInsectSenses AInsectLab::SenseBiome(AInsectAgent* A)
{
    FInsectSenses S; S.AgentId=A->AgentId; S.Backend=A->Backend(); S.Channels.Init(0,8);
    FVector P=A->GetActorLocation(); float Yaw=A->GetActorRotation().Yaw;
    FInsectMotor Current;
    if(SensoryLookahead>0&&Bridge->ReadMotor(A->AgentId,Current))
        A->PredictMotion(Current,SensoryLookahead,MotorSmoothing,P,Yaw);
    auto Unit=[](float V) { return FMath::Clamp(V,0.f,1.f); };
    const float Hunger=Unit((120-A->Energy)/100), Thirst=Unit((100-A->Hydration)/80);
    const float Deficit=Unit((ColonyDemand(A->Colony)-Stores[A->Colony])/FMath::Max(1.f,ColonyDemand(A->Colony)));
    const float Load=Unit(A->Cargo/30), Injury=Unit((60-A->Health)/45);
    const float FoodNeed=Unit(Hunger*1.5f+Deficit*.6f)*(1-.92f*Load);
    const float WaterNeed=Thirst*Thirst*1.4f;
    const float HomeNeed=Unit(Load*1.3f+Injury*.7f+Unit((A->Energy-108)/12)*.15f);
    A->SensoryNeeds={Hunger,Thirst,Deficit,Load,Injury};
    float Contact=0, NearHazard=0;
    // Every source contributes to its own modality's two receptor populations.
    // No resource ranking, chosen goal, averaged bearing or motor command here.
    auto Smell=[&](FVector Source,int Modality,float Strength,float Radius)
    {
        const float D=FVector::Dist2D(P,Source);
        const float Concentration=Strength*FMath::Square(Unit(1-D/Radius));
        const float Angle=FMath::FindDeltaAngleDegrees(Yaw,(Source-P).Rotation().Yaw);
        const float Lateral=Unit(FMath::Abs(Angle)/65.f);
        S.Channels[Modality*2+(Angle>=0?0:1)]+=Concentration*Lateral;
        if(D<155) Contact+=Concentration;
    };
    for(const auto& F:Food)
        Smell(F.Position,F.Kind==1?1:0,(F.Kind==1?WaterNeed:FoodNeed)*Unit(F.Amount/40),SenseRadius*2);
    Smell(A->Nest,2,HomeNeed,6000);
    // Touch and looming are receptors too: left contact excites right partners.
    // This never changes the actor yaw/position or supplies a waypoint.
    auto Loom=[&](FVector Source,float Range,float Strength)
    {
        const float D=FVector::Dist2D(P,Source);
        const float Angle=FMath::FindDeltaAngleDegrees(Yaw,(Source-P).Rotation().Yaw);
        const float Level=Strength*Unit(1-D/Range)*Unit(1-FMath::Abs(Angle)/110);
        NearHazard+=Level;
        for(int M=0;M<3;++M) S.Channels[M*2+(Angle>=0?1:0)]+=Level*.65f;
    };
    for(const auto& B:Obstacles) Loom(B.Position,B.Radius+240,1.4f);
    Loom(FVector(HalfWidth,P.Y,P.Z),280,1.4f); Loom(FVector(-HalfWidth,P.Y,P.Z),280,1.4f);
    Loom(FVector(P.X,HalfHeight,P.Z),280,1.4f); Loom(FVector(P.X,-HalfHeight,P.Z),280,1.4f);
    for(const AInsectAgent* B:Agents) if(B!=A&&IsValid(B)&&B->Health>0)
        Loom(B->GetActorLocation(),B->Colony==A->Colony?200:550,B->Colony==A->Colony?.5f:.4f+Injury);
    // Arousal carries combined needs, not the bearing of a winning source.
    S.Channels[6]=Unit(.22f+.55f*FoodNeed+.5f*WaterNeed+.45f*HomeNeed)/(1+2*Contact+NearHazard);
    S.Channels[7]=Unit(NearHazard*.15f+Injury*.1f);
    for(float& V:S.Channels) V=Unit(V);
    A->SensoryChannels=S.Channels;
    A->GoalKind=INDEX_NONE; A->GoalIndex=INDEX_NONE; A->FoodTarget=INDEX_NONE;
    A->bProvisioning=false; A->bRetreating=false;
    A->Target=A->GetActorLocation(); // Telemetry: no navigation target exists in this mode.
    A->Intent=TEXT("Sensing");
    return S;
}

void AInsectLab::SenseContactThreats(AInsectAgent* A)
{
    A->Rival=nullptr; A->bPlayerTarget=false;
    const FVector P=A->GetActorLocation();
    auto InTerritory=[&](FVector Point)
    {
        if(FVector::Dist2D(Point,A->Nest)<900) return true;
        for(int I=0;I<Food.Num();++I)
            if(ResourceOwners[I]==A->Colony&&ResourceClaims[I]>2&&FVector::Dist2D(Point,Food[I].Position)<500) return true;
        return false;
    };
    if(!InTerritory(P)) return;
    float Nearest=160;
    for(AInsectAgent* B:Agents) if(B!=A&&B->Colony!=A->Colony&&B->Health>0)
    {
        const float D=FVector::Dist2D(P,B->GetActorLocation());
        if(D<Nearest) { A->Rival=B; Nearest=D; }
    }
    auto* Player=UGameplayStatics::GetPlayerPawn(this,0);
    A->bPlayerTarget=!A->Rival.IsValid()&&Player&&FVector::Dist2D(P,Player->GetActorLocation())<170;
}
