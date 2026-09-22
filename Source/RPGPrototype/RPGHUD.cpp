#include "RPGHUD.h"
#include "RPGCharacter.h"
#include "InsectLab.h"
#include "InsectAgent.h"
#include "InsectBrainBridge.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "GameFramework/PlayerController.h"

namespace
{
const FLinearColor Ink(.026f,.047f,.050f,.94f);
const FLinearColor Gold(.88f,.69f,.35f,1.f);
const FLinearColor Paper(.88f,.90f,.79f,1.f);
const FLinearColor Muted(.51f,.65f,.61f,1.f);
}

void ARPGHUD::DrawHUD()
{
    Super::DrawHUD();
    if (!Canvas || !PlayerOwner) return;
    if (auto* Lab = AInsectLab::Find(GetWorld())) DrawInsectLab(Lab);
}

void ARPGHUD::DrawInsectLab(AInsectLab* Lab)
{
    const float W=Canvas->ClipX,H=Canvas->ClipY;
    const FLinearColor Cyan(.16f,.84f,.78f),Amber(1.f,.56f,.18f),Red(1.f,.35f,.29f);
    auto Text=[&](const FString& S,float X,float Y,FLinearColor C=Paper,float Scale=.9f) { DrawText(S,C,X,Y,GEngine->GetSmallFont(),Scale); };
    DrawRect(Ink,22,22,420,177); DrawRect(Cyan,22,22,3,177);
    DrawText(Lab->bExpandedBiome?TEXT("M O S S W I L D"):TEXT("I N S E C T A R I U M"),Paper,42,35,GEngine->GetLargeFont(),.96f);
    Text(Lab->bExpandedBiome?TEXT("THE LIVING GROVE / COLONY ECOLOGY"):TEXT("CONNECTOME ECOLOGY  /  EXPERIMENT 01"),43,71,Muted,.78f);
    Text(TEXT("CYAN   SiliconFly   139,255 neurons"),43,99,Cyan);
    Text(TEXT("AMBER  FlyBrainEngine   138,639 neurons"),43,121,Amber);
    Text(Lab->bExpandedBiome?FString::Printf(TEXT("Nest %.0f/%.0f | %.0f/%.0f    Care %.0f%% / %.0f%%"),Lab->ColonyReserve(0),Lab->ColonyDemand(0),Lab->ColonyReserve(1),Lab->ColonyDemand(1),Lab->NestCare(0)*100,Lab->NestCare(1)*100):TEXT("Both: 15,091,983 edges / independent NPC state"),43,147,Muted,.8f);
    Text(Lab->bExpandedBiome?(Lab->bSensoryCompetition?TEXT("N  Sensory competition / no goal planner"):TEXT("N  Goal planner / H social steering")):TEXT("Neural motors + authored ecological rules"),43,173,Muted,.8f);
    const float PX=FMath::Max(454.f,W-324.f);
    DrawRect(Ink,PX,22,302,177);
    Text(FString::Printf(TEXT("COLONY CENSUS  /  %.0f s"),Lab->Elapsed),PX+18,37,Gold);
    Text(FString::Printf(TEXT("%d alive     %d eggs     %d births"),Lab->LivingCount(),Lab->EggCount(),Lab->Births),PX+18,66);
    Text(FString::Printf(TEXT("%d clashes   %d deaths"),Lab->Fights,Lab->Deaths),PX+18,91);
    Text(Lab->bDrought ? TEXT("DROUGHT / regrowth stopped") : TEXT("FOOD / finite reserves, slow regrowth"),PX+18,119,Lab->bDrought?Red:Muted,.8f);
    Text(FString::Printf(TEXT("PLAYER  %.0f / 100    [F] strike"),Lab->PlayerHealth),PX+18,147);
    DrawRect(FLinearColor(.2,.24,.23),PX+18,175,264,5);
    DrawRect(Lab->PlayerHealth<40?Red:Cyan,PX+18,175,264*FMath::Clamp(Lab->PlayerHealth/100,0.f,1.f),5);
    for(const AInsectAgent* A:Lab->Agents) if(IsValid(A))
    {
        const FVector Screen=Project(A->GetActorLocation()+FVector(0,0,115));
        const FVector2D P(Screen.X,Screen.Y);
        if(P.X<0||P.X>W||P.Y<210||P.Y>H-158) continue;
        const auto C=A->Colony==0?Cyan:Amber;
        Text(FString::Printf(TEXT("%s #%d  %s"),A->Colony==0?TEXT("S"):TEXT("F"),A->AgentId,*A->Intent),P.X-55,P.Y-22,C,.72f);
        DrawRect(Ink,P.X-40,P.Y,80,9);
        DrawRect(C,P.X-39,P.Y+1,78*FMath::Clamp(A->Energy/120,0.f,1.f),3);
        DrawRect(Red,P.X-39,P.Y+5,78*FMath::Clamp(A->Health/60,0.f,1.f),2);
        if(Lab->bExpandedBiome) DrawRect(FLinearColor(.25,.65,1),P.X-39,P.Y+9,78*FMath::Clamp(A->Hydration/100,0.f,1.f),2);
    }
    DrawRect(Ink,22,H-153,W-44,131);
    Text(Lab->bPaused?TEXT("PAUSED / P to resume"):Lab->Bridge->Status,40,H-140,Lab->Bridge->bAblated?Red:Cyan,.88f);
    Text(FString::Printf(TEXT("%d ms neural windows   |   batch %.0f ms   |   %d responses   |   B: synapse ablation"),Lab->Bridge->NeuralWindowMs,Lab->Bridge->BatchMilliseconds,Lab->Bridge->CompletedBatches),40,H-117,Muted,.8f);
    Text(Lab->LastEvent,40,H-94,Gold,.86f);
    Text(Lab->bExpandedBiome?TEXT("WASD move   F strike   M map   N brain goals (resets)   H social   G drought   B ablation   R reset   P pause   O camera   1/2 colonies"):TEXT("WASD move   F strike   G drought/rain   B ablation   R reset   P pause   O camera   1/2 colonies   L biome"),40,H-64,Paper,.84f);
    Text(Lab->bExpandedBiome?TEXT("Green: food  |  Blue: water  |  Glowing trails: recruitment  |  Enter nest rings to challenge a colony."):TEXT("Enter a coloured ring to challenge its colony. Green = food; small coloured pods = eggs."),40,H-42,Muted,.78f);
    if(Lab->bExpandedBiome)
    {
        const auto* Hero=Cast<ARPGCharacter>(PlayerOwner->GetPawn());
        if(Hero&&Hero->IsMapOpen())
        {
            DrawRect(FLinearColor(.01,.02,.025,.85),0,0,W,H);
            const float S=FMath::Min(H-160,W-200); DrawBiomeMap(Lab,(W-S)*.5f,(H-S)*.5f,S,true);
        }
        else DrawBiomeMap(Lab,W-258,215,230,false);
    }
}

void ARPGHUD::DrawBiomeMap(AInsectLab* Lab,float X,float Y,float S,bool Expanded)
{
    DrawRect(Ink,X-10,Y-10,S+20,S+40);
    DrawRect(FLinearColor(.11,.20,.13),X,Y,S,S);
    auto Point=[=](FVector P) { return FVector2D(X+S*(.5+P.X/11200),Y+S*(.5-P.Y/10000)); };
    for(int I=0;I<Lab->Resources().Num();++I)
    {
        const auto& F=Lab->Resources()[I];
        const auto P=Point(F.Position); const auto C=F.Kind==1?FLinearColor(.3,.7,1):FLinearColor(.6,.8,.3);
        const int Owner=Lab->ResourceOwner(I);
        if(Owner!=INDEX_NONE) DrawRect(Owner==0?FLinearColor(.16,.84,.78):FLinearColor(1,.56,.18),P.X-5,P.Y-5,10,10);
        DrawRect(C,P.X-3,P.Y-3,6,6);
        if(Expanded) DrawText(F.Name,Paper,P.X+8,P.Y-5,GEngine->GetSmallFont(),.85f);
    }
    for(int C=0;C<2;++C)
    {
        const auto P=Point(Lab->Home(C)); const auto Color=C==0?FLinearColor(.16,.84,.78):FLinearColor(1,.56,.18);
        for(int I=0;I<32;++I)
        {
            const float A=I*2*PI/32,B=(I+1)*2*PI/32,R=S*1150/11200;
            DrawLine(P.X+R*FMath::Cos(A),P.Y+R*FMath::Sin(A),P.X+R*FMath::Cos(B),P.Y+R*FMath::Sin(B),Color,1);
        }
        DrawRect(Color,P.X-4,P.Y-4,8,8);
    }
    for(const AInsectAgent* A:Lab->Agents)
    {
        const auto P=Point(A->GetActorLocation());DrawRect(A->Colony==0?FLinearColor(.16,.84,.78):FLinearColor(1,.56,.18),P.X-2,P.Y-2,4,4);
    }
    if(const APawn* Hero=PlayerOwner->GetPawn()) { const auto P=Point(Hero->GetActorLocation()); DrawRect(Paper,P.X-3,P.Y-3,6,6); }
    DrawText(Expanded?TEXT("M  Return to the grove"):TEXT("M  MOSSWILD MAP"),Gold,X+4,Y+S+10,GEngine->GetSmallFont(),.8f);
}
