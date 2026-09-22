using UnrealBuildTool;
public class RPGPrototype : ModuleRules
{
    public RPGPrototype(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "InputCore", "HTTP", "Json" });
    }
}
