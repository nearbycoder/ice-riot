#pragma once

#include "CoreMinimal.h"
#include "UObject/Object.h"
#include "IRAssets.generated.h"

class UAnimSequence;
class USkeletalMesh;
class UStaticMesh;
class UMaterialInterface;
class USoundBase;
class UFont;
class UTexture2D;

/**
 * Loads every runtime asset by its contract path (Docs/ASSET_SPEC.md, Docs/AUDIO_SPEC.md) and keeps it alive.
 * Every getter is null-safe: missing art falls back to engine shapes so the game always runs.
 */
UCLASS()
class ICERIOT_API UIRAssets : public UObject
{
	GENERATED_BODY()
public:
	static UIRAssets* Get();

	UAnimSequence* Anim(const TCHAR* Name);
	USkeletalMesh* Skel(const TCHAR* Name);
	UStaticMesh* Mesh(const TCHAR* Name);
	UStaticMesh* EngineShape(const TCHAR* Name);   // Cube, Sphere, Cylinder, Plane, Cone
	UMaterialInterface* Material(const TCHAR* Name);
	UMaterialInterface* BasicMaterial();            // engine material with a "Color" vector param
	UTexture2D* Texture(const TCHAR* Name);
	USoundBase* Sound(const FString& CategoryAndName);  // e.g. "Sfx/Shot_Slap_01"
	/** Random variation: tries Name_01.._NN. */
	USoundBase* SoundVar(const FString& CategoryAndBase);
	UFont* Font(bool bDisplay);

	/** Material from the game's own FX set (/Game/IceRiot/FX/). */
	UMaterialInterface* FXMaterial(const TCHAR* Name);

private:
	UPROPERTY()
	TMap<FName, TObjectPtr<UObject>> Cache;
	TSet<FName> Missing;
	TMap<FString, int32> VarCount;

	UObject* LoadPath(const FString& Path, UClass* Class);
};
