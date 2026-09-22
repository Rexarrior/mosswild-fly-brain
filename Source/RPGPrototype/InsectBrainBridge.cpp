#include "InsectBrainBridge.h"
#include "HttpModule.h"
#include "Interfaces/IHttpResponse.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"

void UInsectBrainBridge::Reset(bool Ablate)
{
    if(Request) { Request->OnProcessRequestComplete().Unbind(); Request->CancelRequest(); Request.Reset(); }
    Session = FGuid::NewGuid().ToString(EGuidFormats::Digits);
    bAblated = Ablate; bPending = false; Motors.Empty(); LastResponse = -1.e9;
    CompletedBatches = 0; Status = TEXT("Warming up full connectomes...");
}
void UInsectBrainBridge::EndPlay(const EEndPlayReason::Type Reason)
{
    if(Request) { Request->OnProcessRequestComplete().Unbind(); Request->CancelRequest(); Request.Reset(); }
    Super::EndPlay(Reason);
}
bool UInsectBrainBridge::ReadMotor(int32 Id, FInsectMotor& Out) const
{
    if(FPlatformTime::Seconds() - LastResponse > 3.) return false;
    if(const auto* M = Motors.Find(Id)) { Out = *M; return true; }
    return false;
}
void UInsectBrainBridge::SubmitSenses(const TArray<FInsectSenses>& Senses)
{
    if(bPending || Senses.IsEmpty()) return;
    auto Root = MakeShared<FJsonObject>();
    Root->SetStringField(TEXT("session"), Session);
    Root->SetBoolField(TEXT("ablate"), bAblated);
    Root->SetNumberField(TEXT("neural_ms"),NeuralWindowMs);
    Root->SetNumberField(TEXT("seed"),Seed);
    Root->SetBoolField(TEXT("learned"),bLearnedReadout);
    Root->SetStringField(TEXT("motor_controller"),MotorController);
    TArray<TSharedPtr<FJsonValue>> List;
    for(const auto& S : Senses)
    {
        auto O = MakeShared<FJsonObject>();
        O->SetNumberField(TEXT("id"),S.AgentId); O->SetStringField(TEXT("backend"),S.Backend);
        O->SetNumberField(TEXT("turn"),S.Bearing); O->SetNumberField(TEXT("drive"),S.Drive); O->SetNumberField(TEXT("threat"),S.Threat);
        if(!S.Channels.IsEmpty())
        {
            TArray<TSharedPtr<FJsonValue>> Channels;
            for(float V:S.Channels) Channels.Add(MakeShared<FJsonValueNumber>(V));
            O->SetArrayField(TEXT("channels"),Channels);
        }
        List.Add(MakeShared<FJsonValueObject>(O));
    }
    Root->SetArrayField(TEXT("agents"), List);
    FString Body; auto Writer = TJsonWriterFactory<>::Create(&Body); FJsonSerializer::Serialize(Root, Writer);
    Request = FHttpModule::Get().CreateRequest();
    Request->SetURL(TEXT("http://127.0.0.1:18765/step"));
    Request->SetVerb(TEXT("POST")); Request->SetHeader(TEXT("Content-Type"),TEXT("application/json"));
    Request->SetHeader(TEXT("X-BrainLab"),TEXT("1"));
    Request->SetContentAsString(Body); Request->SetTimeout(30.f);
    bPending = true;
    Request->OnProcessRequestComplete().BindWeakLambda(this, [this](FHttpRequestPtr, FHttpResponsePtr Response, bool Success)
    {
        bPending = false;
        TSharedPtr<FJsonObject> Object;
        if(!Success || !Response.IsValid() || Response->GetResponseCode() != 200 ||
           !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Response->GetContentAsString()),Object) || !Object.IsValid())
        { Status = TEXT("OFFLINE - run Scripts/BrainLab/lab.py start; ecology paused"); Motors.Empty(); return; }
        const TArray<TSharedPtr<FJsonValue>>* Entries;
        double Duration = 0;
        if(!Object->TryGetArrayField(TEXT("agents"),Entries) || !Object->TryGetNumberField(TEXT("wall_ms"),Duration))
        { Status = TEXT("Invalid brain response; ecology paused"); Motors.Empty(); return; }
        TMap<int32, FInsectMotor> Next;
        for(const auto& Entry : *Entries)
        {
            const auto O = Entry->AsObject();
            double Id,Turn,Drive,Escape,Left,Right,Forward;
            if(!O.IsValid() || !O->TryGetNumberField(TEXT("id"),Id) || !O->TryGetNumberField(TEXT("turn"),Turn) ||
               !O->TryGetNumberField(TEXT("drive"),Drive) || !O->TryGetNumberField(TEXT("escape"),Escape) ||
               !O->TryGetNumberField(TEXT("left_hz"),Left) || !O->TryGetNumberField(TEXT("right_hz"),Right) ||
               !O->TryGetNumberField(TEXT("forward_hz"),Forward) || !FMath::IsFinite(Turn) || !FMath::IsFinite(Drive)) continue;
            FInsectMotor M; M.Turn=FMath::Clamp(float(Turn),-1.f,1.f); M.Drive=FMath::Clamp(float(Drive),0.f,1.f);
            M.Escape=Escape; M.LeftHz=Left; M.RightHz=Right; M.ForwardHz=Forward;
            Next.Add(int32(Id), M);
        }
        Motors = MoveTemp(Next); LastResponse=FPlatformTime::Seconds(); BatchMilliseconds=Duration; ++CompletedBatches;
        Status = MotorController==TEXT("reactive-v1") ? TEXT("CONTROL: reactive sensory controller / CPU") :
            (bAblated ? TEXT("ABLATION: recurrent synapses disabled") : TEXT("LIVE: SiliconFly + FlyBrainEngine / Metal"));
    });
    if(!Request->ProcessRequest()) { bPending=false; Status=TEXT("Cannot reach local brain service"); }
}
