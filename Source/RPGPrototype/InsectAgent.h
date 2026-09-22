#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "InsectBrain.h"
#include "InsectAgent.generated.h"
class USphereComponent;
class UStaticMeshComponent;

UCLASS()
class RPGPROTOTYPE_API AInsectAgent : public AActor
{
    GENERATED_BODY()
public:
    AInsectAgent();
    virtual void Tick(float Dt) override;
    void Configure(int32 Id, int32 Colony, int32 Form, FVector Nest, int32 Generation);
    void MoveFromBrain(const FInsectMotor& Command, float Dt);
    void PredictMotion(const FInsectMotor& Command,float Duration,float Smoothing,FVector& Position,float& Yaw) const;
    UPROPERTY(BlueprintReadOnly) int32 AgentId=0;
    UPROPERTY(BlueprintReadOnly) int32 Colony=0;
    UPROPERTY(BlueprintReadOnly) int32 Form=0;
    UPROPERTY(BlueprintReadOnly) int32 Generation=0;
    UPROPERTY(BlueprintReadOnly) float Energy=72;
    UPROPERTY(BlueprintReadOnly) float Health=60;
    UPROPERTY(BlueprintReadOnly) float Age=0;
    UPROPERTY(BlueprintReadOnly) float Hydration=100;
    UPROPERTY(BlueprintReadOnly) float Cargo=0;
    UPROPERTY(BlueprintReadOnly) float AttackPulse=0;
    UPROPERTY(BlueprintReadOnly) float HurtPulse=0;
    UPROPERTY(BlueprintReadOnly) bool bFeeding=false;
    UPROPERTY(BlueprintReadOnly) bool bDrinking=false;
    UPROPERTY(BlueprintReadOnly) FString Intent=TEXT("Waking");
    UPROPERTY(BlueprintReadOnly) FInsectMotor Motor;
    FVector Nest, Target;
    float AttackCooldown=0, BirthCooldown=0, Speed=0;
    int32 FoodTarget=INDEX_NONE;
    TWeakObjectPtr<AInsectAgent> Rival;
    bool bPlayerTarget=false;
    bool bRetreating=false;
    bool bWasEating=false;
    int32 GoalKind=0, GoalIndex=INDEX_NONE, ScoutIndex=0;
    float GoalUntil=0, StuckTime=0, ProbeTime=0, TrailTimer=0, NeuralDrive=0, NeuralTurn=0;
    float DistanceTravelled=0, FoodConsumed=0, FoodDelivered=0, RestUntil=0;
    float FeedingMotionFactor=1;
    FVector ProbePosition=FVector::ZeroVector;
    FVector AvoidPoint=FVector::ZeroVector;
    float AvoidUntil=0;
    TMap<int32,float> ResourceMemory;
    TMap<int32,float> ResourceAmounts;
    int32 CargoSource=INDEX_NONE;
    bool bProvisioning=false;
    float CargoSince=0, LastDeliveryTime=-120;
    TArray<float> SensoryChannels, SensoryNeeds;
    int32 ContactResource=INDEX_NONE;
    FString Backend() const { return Colony==0 ? TEXT("siliconfly") : TEXT("flybrain"); }
private:
    UPROPERTY() TObjectPtr<USphereComponent> Body;
    UPROPERTY() TObjectPtr<USceneComponent> Visual;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> Abdomen;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> Head;
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> Legs;
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> Shins;
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> Feet;
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> Antennae;
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> Mandibles;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> CargoVisual;
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> Shells;
    float Phase=0;
};
