#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Interfaces/IHttpRequest.h"
#include "InsectBrain.h"
#include "InsectBrainBridge.generated.h"

UCLASS(ClassGroup=AI, meta=(BlueprintSpawnableComponent))
class RPGPROTOTYPE_API UInsectBrainBridge : public UActorComponent, public IInsectBrain
{
    GENERATED_BODY()
public:
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void SubmitSenses(const TArray<FInsectSenses>& Senses) override;
    virtual bool ReadMotor(int32 AgentId, FInsectMotor& Out) const override;
    void Reset(bool Ablate);
    bool IsPending() const { return bPending; }
    const FString& SessionId() const { return Session; }
    UPROPERTY(BlueprintReadOnly) FString Status = TEXT("Connecting to local brain service...");
    UPROPERTY(BlueprintReadOnly) float BatchMilliseconds = 0;
    UPROPERTY(BlueprintReadOnly) int32 CompletedBatches = 0;
    UPROPERTY(BlueprintReadOnly) bool bAblated = false;
    int32 NeuralWindowMs=40;
    int32 Seed=1701;
    bool bLearnedReadout=false;
    FString MotorController=TEXT("connectome");
private:
    TMap<int32, FInsectMotor> Motors;
    TSharedPtr<IHttpRequest, ESPMode::ThreadSafe> Request;
    FString Session = FGuid::NewGuid().ToString(EGuidFormats::Digits);
    double LastResponse = -1.e9;
    bool bPending = false;
};
