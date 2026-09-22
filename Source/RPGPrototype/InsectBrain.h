#pragma once
#include "CoreMinimal.h"
#include "UObject/Interface.h"
#include "InsectBrain.generated.h"

// The game supplies intent OR simultaneous sensory populations; the brain returns motors.
USTRUCT(BlueprintType)
struct FInsectSenses
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadWrite) int32 AgentId = 0;
    UPROPERTY(BlueprintReadWrite) FString Backend;
    UPROPERTY(BlueprintReadWrite) float Bearing = 0;
    UPROPERTY(BlueprintReadWrite) float Drive = 0;
    UPROPERTY(BlueprintReadWrite) float Threat = 0;
    // Empty: legacy intent. Eight values: food L/R, water L/R, home L/R, arousal, threat.
    UPROPERTY(BlueprintReadWrite) TArray<float> Channels;
};

USTRUCT(BlueprintType)
struct FInsectMotor
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly) float Turn = 0;
    UPROPERTY(BlueprintReadOnly) float Drive = 0;
    UPROPERTY(BlueprintReadOnly) float Escape = 0;
    UPROPERTY(BlueprintReadOnly) float LeftHz = 0;
    UPROPERTY(BlueprintReadOnly) float RightHz = 0;
    UPROPERTY(BlueprintReadOnly) float ForwardHz = 0;
};

UINTERFACE(MinimalAPI, BlueprintType)
class UInsectBrain : public UInterface { GENERATED_BODY() };
class RPGPROTOTYPE_API IInsectBrain
{
    GENERATED_BODY()
public:
    virtual void SubmitSenses(const TArray<FInsectSenses>& Senses) = 0;
    virtual bool ReadMotor(int32 AgentId, FInsectMotor& Out) const = 0;
};
