#pragma once
#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "RPGHUD.generated.h"
class ARPGCharacter;
UCLASS()
class RPGPROTOTYPE_API ARPGHUD : public AHUD
{
    GENERATED_BODY()
public:
    virtual void DrawHUD() override;
private:
    void DrawInsectLab(class AInsectLab* Lab);
    void DrawBiomeMap(class AInsectLab* Lab,float X,float Y,float Size,bool Expanded);
};
