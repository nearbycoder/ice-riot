using UnrealBuildTool;

public class IceRiot : ModuleRules
{
	public IceRiot(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "InputCore" });
		PrivateDependencyModuleNames.AddRange(new string[] { "Slate", "SlateCore", "AudioMixer", "ApplicationCore", "RenderCore", "RHI", "Json" });
	}
}
