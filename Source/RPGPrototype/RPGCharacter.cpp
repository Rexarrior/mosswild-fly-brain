#include "RPGCharacter.h"
#include "InsectLab.h"
#include "InsectBrainBridge.h"
#include "Kismet/GameplayStatics.h"
#include "InputCoreTypes.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

ARPGCharacter::ARPGCharacter()
{
    PrimaryActorTick.bCanEverTick = true;
    GetCapsuleComponent()->InitCapsuleSize(32.f, 86.f);
    bUseControllerRotationYaw = false;
    GetCharacterMovement()->bOrientRotationToMovement = true;
    GetCharacterMovement()->RotationRate = FRotator(0, 640, 0);
    GetCharacterMovement()->MaxWalkSpeed = 420.f;
    GetCharacterMovement()->MaxAcceleration = 1800.f;
    GetCharacterMovement()->BrakingDecelerationWalking = 1800.f;
    GetCharacterMovement()->JumpZVelocity = 520.f;
    GetCharacterMovement()->GravityScale = 1.5f;
    GetCharacterMovement()->AirControl = 0.45f;
    GetCharacterMovement()->MaxStepHeight = 40.f;

    CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
    CameraBoom->SetupAttachment(RootComponent);
    CameraBoom->SetUsingAbsoluteRotation(true);
    CameraBoom->SetRelativeRotation(FRotator(-48.f, -45.f, 0));
    CameraBoom->TargetArmLength = ZoomTarget;
    CameraBoom->TargetOffset = FVector(0, 0, 40);
    CameraBoom->bDoCollisionTest = false;
    CameraBoom->bEnableCameraLag = true;
    CameraBoom->CameraLagSpeed = 7.f;
    CameraBoom->CameraLagMaxDistance = 100.f;
    UCameraComponent* Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
    Camera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
    Camera->FieldOfView = 55.f;

    VisualRoot = CreateDefaultSubobject<USceneComponent>(TEXT("VisualRoot"));
    VisualRoot->SetupAttachment(RootComponent);
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    auto Part = [&](const TCHAR* Name, UStaticMesh* Mesh, FVector Position, FVector Scale, const TCHAR* Material)
    {
        auto* C = CreateDefaultSubobject<UStaticMeshComponent>(Name);
        C->SetupAttachment(VisualRoot);
        C->SetStaticMesh(Mesh);
        C->SetRelativeLocation(Position);
        C->SetRelativeScale3D(Scale);
        C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        C->ComponentTags.Add(FName(Material));
        return C;
    };
    Part(TEXT("Body"), Cube.Object, FVector(0,0,0), FVector(.43,.52,.58), TEXT("Pale"));
    Part(TEXT("Head"), Sphere.Object, FVector(0,0,48), FVector(.45,.43,.48), TEXT("Pale"));
    Part(TEXT("Visor"), Cube.Object, FVector(20,0,49), FVector(.12,.38,.17), TEXT("Cyan"));
    LeftLeg = Part(TEXT("LeftLeg"), Cube.Object, FVector(0,-15,-57), FVector(.27,.22,.52), TEXT("Dark"));
    RightLeg = Part(TEXT("RightLeg"), Cube.Object, FVector(0,15,-57), FVector(.27,.22,.52), TEXT("Dark"));
    LeftArm = Part(TEXT("LeftArm"), Cube.Object, FVector(0,-35,-1), FVector(.25,.19,.52), TEXT("Pale"));
    RightArm = Part(TEXT("RightArm"), Cube.Object, FVector(0,35,-1), FVector(.25,.19,.52), TEXT("Pale"));
}

void ARPGCharacter::BeginPlay()
{
    Super::BeginPlay();
    SpawnPoint = GetActorLocation();
    if(auto* Lab=AInsectLab::Find(GetWorld())) ZoomTarget=Lab->bExpandedBiome?10000:3900;
    TArray<UStaticMeshComponent*> Parts;
    GetComponents(Parts);
    for (auto* Part : Parts)
    {
        if (Part->ComponentTags.IsEmpty()) continue;
        const FString Name = Part->ComponentTags[0].ToString();
        const FString Path = FString::Printf(TEXT("/Game/BrainLab/M_%s.M_%s"), *Name, *Name);
        if (auto* Material = LoadObject<UMaterialInterface>(nullptr, *Path)) Part->SetMaterial(0, Material);
    }
}

void ARPGCharacter::SetupPlayerInputComponent(UInputComponent* Input)
{
    Super::SetupPlayerInputComponent(Input);
    Input->BindAxis(TEXT("MoveForward"), this, &ARPGCharacter::MoveForward);
    Input->BindAxis(TEXT("MoveRight"), this, &ARPGCharacter::MoveRight);
    Input->BindAxis(TEXT("Zoom"), this, &ARPGCharacter::Zoom);
    Input->BindAction(TEXT("Sprint"), IE_Pressed, this, &ARPGCharacter::SprintStart);
    Input->BindAction(TEXT("Sprint"), IE_Released, this, &ARPGCharacter::SprintStop);
    Input->BindAction(TEXT("Jump"), IE_Pressed, this, &ARPGCharacter::JumpPressed);
    Input->BindAction(TEXT("Jump"), IE_Released, this, &ACharacter::StopJumping);
    Input->BindAction(TEXT("Map"), IE_Pressed, this, &ARPGCharacter::ToggleMap);
    Input->BindAction(TEXT("ZoomIn"), IE_Pressed, this, &ARPGCharacter::ZoomIn);
    Input->BindAction(TEXT("ZoomOut"), IE_Pressed, this, &ARPGCharacter::ZoomOut);
    Input->BindKey(EKeys::L, IE_Pressed, this, &ARPGCharacter::ToggleInsectLab);
    Input->BindKey(EKeys::F, IE_Pressed, this, &ARPGCharacter::LabStrike);
    Input->BindKey(EKeys::R, IE_Pressed, this, &ARPGCharacter::LabReset);
    Input->BindKey(EKeys::B, IE_Pressed, this, &ARPGCharacter::LabAblation);
    Input->BindKey(EKeys::G, IE_Pressed, this, &ARPGCharacter::LabDrought);
    Input->BindKey(EKeys::P, IE_Pressed, this, &ARPGCharacter::LabPause);
    Input->BindKey(EKeys::O, IE_Pressed, this, &ARPGCharacter::LabOverview);
    Input->BindKey(EKeys::One, IE_Pressed, this, &ARPGCharacter::FocusCyan);
    Input->BindKey(EKeys::Two, IE_Pressed, this, &ARPGCharacter::FocusAmber);
    Input->BindKey(EKeys::H, IE_Pressed, this, &ARPGCharacter::LabSwarm);
    Input->BindKey(EKeys::N, IE_Pressed, this, &ARPGCharacter::LabSensory);
}

void ARPGCharacter::ToggleInsectLab() { UGameplayStatics::OpenLevel(this,AInsectLab::Find(GetWorld()) && AInsectLab::Find(GetWorld())->bExpandedBiome ? TEXT("Insectarium") : TEXT("Mosswild")); }
void ARPGCharacter::LabOverview()
{
    LabFocus=INDEX_NONE;
    bLabOverview=!bLabOverview;
    if(auto* Lab=AInsectLab::Find(GetWorld())) ZoomTarget=bLabOverview?(Lab->bExpandedBiome?10000:3900):2600;
}
void ARPGCharacter::FocusInsectColony(int32 Colony)
{
    if(AInsectLab::Find(GetWorld()))
    { LabFocus=FMath::Clamp(Colony,0,1); bLabOverview=true; ZoomTarget=2300; }
}
void ARPGCharacter::LabSwarm() { if(auto* Lab=AInsectLab::Find(GetWorld())) Lab->SetSwarmEnabled(!Lab->bSwarmEnabled); }
void ARPGCharacter::LabSensory() { if(auto* Lab=AInsectLab::Find(GetWorld())) Lab->SetSensoryCompetition(!Lab->bSensoryCompetition); }
void ARPGCharacter::LabStrike() { if(auto* L=AInsectLab::Find(GetWorld())) L->PlayerStrike(); }
void ARPGCharacter::LabReset() { if(auto* L=AInsectLab::Find(GetWorld())) L->ResetExperiment(false); }
void ARPGCharacter::LabAblation() { if(auto* L=AInsectLab::Find(GetWorld())) L->ResetExperiment(!L->Bridge->bAblated); }
void ARPGCharacter::LabDrought() { if(auto* L=AInsectLab::Find(GetWorld())) L->SetDrought(!L->bDrought); }
void ARPGCharacter::LabPause() { if(auto* L=AInsectLab::Find(GetWorld())) L->TogglePause(); }

void ARPGCharacter::MoveForward(float Value)
{
    if (!bMapOpen) AddMovementInput(FRotator(0,-45,0).Vector(), Value);
}
void ARPGCharacter::MoveRight(float Value)
{
    if (!bMapOpen) AddMovementInput(FRotator(0,45,0).Vector(), Value);
}
void ARPGCharacter::SetSprinting(bool Enabled)
{
    bSprinting = Enabled;
    GetCharacterMovement()->MaxWalkSpeed = Enabled ? 680.f : 420.f;
}
void ARPGCharacter::JumpPressed() { if (!bMapOpen) Jump(); }
void ARPGCharacter::ToggleMap()
{
    if(auto* Lab=AInsectLab::Find(GetWorld())) if(!Lab->bExpandedBiome) return;
    bMapOpen = !bMapOpen;
    if (bMapOpen)
    {
        ConsumeMovementInputVector();
        GetCharacterMovement()->StopMovementImmediately();
        StopJumping();
    }
}
void ARPGCharacter::Zoom(float Value)
{
    const auto* Lab=AInsectLab::Find(GetWorld());
    ZoomTarget = FMath::Clamp(ZoomTarget - Value * 180.f, 1100.f, Lab?(Lab->bExpandedBiome?14000.f:4800.f):3000.f);
}
float ARPGCharacter::GetZoomDistance() const { return CameraBoom->TargetArmLength; }

void ARPGCharacter::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if(AInsectLab::Find(GetWorld())&&bLabOverview)
    {
        const auto P=GetActorLocation();
        const auto Anchor=LabFocus>=0?AInsectLab::Find(GetWorld())->Home(LabFocus):FVector::ZeroVector;
        CameraBoom->TargetOffset=FVector(Anchor.X-P.X,Anchor.Y-P.Y,60);
        CameraBoom->SetRelativeRotation(FRotator(-55,-45,0));
    }
    else
    {
        CameraBoom->TargetOffset=FVector(0,0,40); CameraBoom->SetRelativeRotation(FRotator(-48,-45,0));
    }
    CameraBoom->TargetArmLength = FMath::FInterpTo(CameraBoom->TargetArmLength, ZoomTarget, DeltaSeconds, 8.f);
    const float Speed = GetVelocity().Size2D();
    const float Amount = FMath::Clamp(Speed / 420.f, 0.f, 1.3f);
    AnimationTime += DeltaSeconds * (3.f + Speed * .024f);
    const float Step = FMath::Sin(AnimationTime) * Amount;
    const bool Falling = GetCharacterMovement()->IsFalling();
    VisualRoot->SetRelativeLocation(FVector(0,0,Falling ? 4.f : FMath::Abs(Step)*3.f));
    LeftLeg->SetRelativeRotation(FRotator(Falling ? -22.f : Step*30.f,0,0));
    RightLeg->SetRelativeRotation(FRotator(Falling ? 22.f : -Step*30.f,0,0));
    LeftArm->SetRelativeRotation(FRotator(-Step*24.f,0,Falling ? -25.f : -6.f));
    RightArm->SetRelativeRotation(FRotator(Step*24.f,0,Falling ? 25.f : 6.f));
    if (GetActorLocation().Z < -500.f)
    {
        GetCharacterMovement()->StopMovementImmediately();
        SetActorLocation(SpawnPoint, false, nullptr, ETeleportType::TeleportPhysics);
    }
}
