#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "InsectLab.generated.h"
class AInsectAgent;
class UInsectBrainBridge;
class UStaticMeshComponent;
class UInstancedStaticMeshComponent;
struct FInsectSenses;

USTRUCT()
struct FInsectFood
{
    GENERATED_BODY()
    FVector Position=FVector::ZeroVector;
    float Amount=75;
    float Capacity=75, Regrowth=1.4f, Phase=0;
    int32 Kind=0;
    FString Name;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> Visual;
};

struct FBiomeObstacle { FVector Position=FVector::ZeroVector; float Radius=150; };
struct FBiomeTrail { FVector Position=FVector::ZeroVector; int32 Colony=0, Food=0; float Strength=0, Age=0; };
USTRUCT()
struct FInsectEgg
{
    GENERATED_BODY()
    FVector Position=FVector::ZeroVector;
    int32 Colony=0, Form=0, Generation=1;
    float Remaining=8;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> Visual;
};

UCLASS()
class RPGPROTOTYPE_API AInsectLab : public AActor
{
    GENERATED_BODY()
public:
    AInsectLab();
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void Tick(float Dt) override;
    UFUNCTION(BlueprintCallable) void ResetExperiment(bool Ablate=false);
    UFUNCTION(BlueprintCallable) void SetDrought(bool Enabled);
    UFUNCTION(BlueprintCallable) void TogglePause() { bPaused=!bPaused; }
    UFUNCTION(BlueprintCallable) void PlayerStrike();
    UFUNCTION(BlueprintCallable) void ConfigureBiomeExperiment(const FString& Json);
    UFUNCTION(BlueprintCallable) void SetSwarmEnabled(bool Enabled);
    UFUNCTION(BlueprintCallable) void SetSensoryCompetition(bool Enabled);
    UFUNCTION(BlueprintPure) FString SnapshotJson() const;
    UFUNCTION(BlueprintPure) int32 LivingCount() const;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly) TObjectPtr<UInsectBrainBridge> Bridge;
    UPROPERTY(BlueprintReadOnly) TArray<TObjectPtr<AInsectAgent>> Agents;
    UPROPERTY(BlueprintReadOnly) bool bDrought=false;
    UPROPERTY(BlueprintReadOnly) bool bPaused=false;
    UPROPERTY(BlueprintReadOnly) float PlayerHealth=100;
    UPROPERTY(BlueprintReadOnly) float Elapsed=0;
    UPROPERTY(BlueprintReadOnly) int32 Meals=0;
    UPROPERTY(BlueprintReadOnly) int32 Fights=0;
    UPROPERTY(BlueprintReadOnly) int32 PlayerHits=0;
    UPROPERTY(BlueprintReadOnly) int32 Births=0;
    UPROPERTY(BlueprintReadOnly) int32 Deaths=0;
    UPROPERTY(BlueprintReadOnly) int32 EggsLaid=0;
    UPROPERTY(BlueprintReadOnly) FString LastEvent=TEXT("Two colonies share a finite food supply.");
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Biome") bool bExpandedBiome=false;
    UPROPERTY(BlueprintReadOnly) int32 ImprovementStage=10;
    UPROPERTY(BlueprintReadOnly) bool bSwarmEnabled=true;
    UPROPERTY(BlueprintReadOnly) bool bPredictiveSenses=true;
    UPROPERTY(BlueprintReadOnly) bool bSensoryCompetition=false;
    UPROPERTY(BlueprintReadOnly) float FoodDelivered=0;
    UPROPERTY(BlueprintReadOnly) float Polarization=0;
    UPROPERTY(BlueprintReadOnly) float SwarmFraction=0;
    UPROPERTY(BlueprintReadOnly) int32 ResourceVisits=0;
    UPROPERTY(BlueprintReadOnly) int32 StarvationDeaths=0;
    UPROPERTY(BlueprintReadOnly) int32 DehydrationDeaths=0;
    UPROPERTY(BlueprintReadOnly) int32 CombatDeaths=0;
    UPROPERTY(BlueprintReadOnly) int32 GoalChanges=0;
    UPROPERTY(BlueprintReadOnly) float StuckSeconds=0;
    UPROPERTY(BlueprintReadOnly) float AgentSeconds=0;
    static AInsectLab* Find(const UWorld* World);
    FVector Home(int32 Colony) const { return bExpandedBiome ? Homes[Colony] : FVector(Colony==0 ? -650 : 650,0,55); }
    float ColonyReserve(int32 Colony) const { return Stores[Colony]; }
    float ColonyDemand(int32 Colony) const;
    float NestCare(int32 Colony) const { return NestCondition[Colony]; }
    const TArray<FInsectFood>& Resources() const { return Food; }
    int32 ResourceOwner(int32 I) const { return ResourceOwners.IsValidIndex(I)?ResourceOwners[I]:INDEX_NONE; }
    int32 EggCount() const { return Eggs.Num(); }
private:
    UPROPERTY() TArray<FInsectFood> Food;
    UPROPERTY() TArray<FInsectEgg> Eggs;
    int32 NextId=1;
    float RequestTimer=0, PlayerAttackTimer=0;
    FRandomStream Random{1701};
    AInsectAgent* SpawnInsect(int32 Colony,int32 Form,FVector Position,int32 Generation);
    void Plan(AInsectAgent* Agent);
    void Ecology(AInsectAgent* Agent,float Dt);
    void Record(const FString& Event);
    UStaticMeshComponent* Orb(FString Name,FVector Position,FVector Scale,const TCHAR* Material);
    bool LoadBiome();
    void ResetBiome();
    void PlanBiome(AInsectAgent* A);
    void TickBiome(float Dt);
    void StepBiome(float Dt);
    void SubmitBiome();
    FInsectSenses SenseBiome(AInsectAgent* A);
    void SenseContactThreats(AInsectAgent* A);
    void AssignProvisioners();
    void WriteBiomeTelemetry(bool Final=false);
    void FinishBiomeRecording(const FString& Reason);
    FString BiomeSnapshot() const;
    FVector RouteBiome(AInsectAgent* A,FVector Goal);
    FVector SocialDirection(AInsectAgent* A,FVector Direction) const;
    FVector Homes[2]={FVector(-2800,-700,55),FVector(2800,700,55)};
    float Stores[2]={60,60};
    bool bContinuousEconomy=true;
    bool bContactReflexes=false;
    // Audit-only common contact rule: remove the neural activity gate in BOTH arms.
    bool bMatchedContactGate=false;
    float UpkeepPerAdult=.045f, ReservePerAdult=20, ReserveBase=60;
    float SpoilageRate=.0004f, CargoTimeout=35;
    float NestCondition[2]={1,1};
    double MaintenanceSpent[2]={0,0}, SpoiledFood[2]={0,0}, DeliveredByColony[2]={0,0};
    float UnfundedSeconds[2]={0,0};
    int DeliveryTrips[2]={0,0};
    FString TelemetryFolder;
    float NextLiveSample=0;
    float HalfWidth=5500,HalfHeight=4800;
    float SenseRadius=1500,SeparationWeight=1.8f,AlignmentWeight=.45f,CohesionWeight=.28f;
    float HungerThreshold=82,ThirstThreshold=60,MemorySeconds=70,TrailLifetime=100;
    float BroodCost=30,RegrowthMultiplier=1,TurnGain=1,MotorSmoothing=.35f;
    int32 RunSeed=1701,ConsumedBatch=0;
    int32 NeuralMilliseconds=20;
    int32 ColonyLimit=6;
    bool bSynchronousExperiment=false;
    float ExperimentStep=.4f,AuditDuration=600,TelemetryTimer=0;
    float MotorTimeCredit=0;
    float SensoryLookahead=0;
    double AuditStarted=0;
    FString AuditName=TEXT("interactive");
    TArray<FBiomeObstacle> Obstacles;
    TArray<FBiomeTrail> Trails;
    TArray<float> Pheromones[2];
    TArray<float> ColonyAmounts[2];
    TArray<int32> ResourceOwners;
    TArray<float> ResourceClaims;
    UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> CyanTrails;
    UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> AmberTrails;
    TMap<int32,float> ColonyKnowledge[2];
    TSet<int32> VisitedResources[2];
    TSet<int32> VisitedCells[2];
    float AlignmentSum=0,AlignmentSamples=0,SwarmSamples=0,SocialSamples=0;
    float LastDamage[2]={-100,-100};
    FVector Alarm[2];
};
