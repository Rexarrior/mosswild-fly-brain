using UnrealBuildTool;
public class RPGPrototypeEditorTarget : TargetRules
{
    public RPGPrototypeEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V7;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
        ExtraModuleNames.Add("RPGPrototype");
    }
}
