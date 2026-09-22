#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "RPGCharacter.generated.h"

class USpringArmComponent;
class UStaticMeshComponent;

UCLASS()
class RPGPROTOTYPE_API ARPGCharacter : public ACharacter
{
    GENERATED_BODY()
public:
    ARPGCharacter();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void SetupPlayerInputComponent(UInputComponent* Input) override;

    UFUNCTION(BlueprintCallable) void MoveForward(float Value);
    UFUNCTION(BlueprintCallable) void MoveRight(float Value);
    UFUNCTION(BlueprintCallable) void SetSprinting(bool Enabled);
    UFUNCTION(BlueprintCallable) void ToggleMap();
    UFUNCTION(BlueprintCallable) void Zoom(float Value);
    UFUNCTION(BlueprintCallable) void ToggleInsectLab();
    UFUNCTION(BlueprintCallable) void FocusInsectColony(int32 Colony);
    UFUNCTION(BlueprintPure) bool IsMapOpen() const { return bMapOpen; }
    UFUNCTION(BlueprintPure) float GetZoomDistance() const;

private:
    UPROPERTY(VisibleAnywhere) TObjectPtr<USpringArmComponent> CameraBoom;
    UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> VisualRoot;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> LeftLeg;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> RightLeg;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> LeftArm;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> RightArm;
    bool bMapOpen = false;
    bool bSprinting = false;
    bool bLabOverview = true;
    int32 LabFocus=INDEX_NONE;
    float AnimationTime = 0.f;
    float ZoomTarget = 2600.f;
    FVector SpawnPoint;
    void SprintStart() { SetSprinting(true); }
    void SprintStop() { SetSprinting(false); }
    void JumpPressed();
    void ZoomIn() { Zoom(1.f); }
    void ZoomOut() { Zoom(-1.f); }
    void LabStrike();
    void LabReset();
    void LabAblation();
    void LabDrought();
    void LabPause();
    void LabOverview();
    void LabSwarm();
    void LabSensory();
    void FocusCyan() { FocusInsectColony(0); }
    void FocusAmber() { FocusInsectColony(1); }
};
