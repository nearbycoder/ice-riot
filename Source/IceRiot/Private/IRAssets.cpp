#include "IRAssets.h"
#include "Animation/AnimSequence.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/Texture2D.h"
#include "Engine/Font.h"
#include "Materials/MaterialInterface.h"
#include "Sound/SoundBase.h"
#include "UObject/UObjectGlobals.h"
#include "UObject/Package.h"

static TObjectPtr<UIRAssets> GIRAssets;

UIRAssets* UIRAssets::Get()
{
	if (!GIRAssets)
	{
		GIRAssets = NewObject<UIRAssets>(GetTransientPackage(), TEXT("IRAssets"));
		GIRAssets->AddToRoot();
	}
	return GIRAssets;
}

UObject* UIRAssets::LoadPath(const FString& Path, UClass* Class)
{
	const FName Key(*Path);
	if (TObjectPtr<UObject>* Found = Cache.Find(Key))
	{
		return *Found;
	}
	if (Missing.Contains(Key))
	{
		return nullptr;
	}
	UObject* Obj = StaticLoadObject(Class, nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet);
	if (Obj)
	{
		Cache.Add(Key, Obj);
	}
	else
	{
		Missing.Add(Key);
	}
	return Obj;
}

static FString ObjPath(const TCHAR* Folder, const TCHAR* Name)
{
	return FString::Printf(TEXT("/Game/IceRiot/%s/%s.%s"), Folder, Name, Name);
}

UAnimSequence* UIRAssets::Anim(const TCHAR* Name)
{
	return Cast<UAnimSequence>(LoadPath(ObjPath(TEXT("Anims"), Name), UAnimSequence::StaticClass()));
}

USkeletalMesh* UIRAssets::Skel(const TCHAR* Name)
{
	return Cast<USkeletalMesh>(LoadPath(ObjPath(TEXT("Meshes"), Name), USkeletalMesh::StaticClass()));
}

UStaticMesh* UIRAssets::Mesh(const TCHAR* Name)
{
	return Cast<UStaticMesh>(LoadPath(ObjPath(TEXT("Meshes"), Name), UStaticMesh::StaticClass()));
}

UStaticMesh* UIRAssets::EngineShape(const TCHAR* Name)
{
	return Cast<UStaticMesh>(LoadPath(FString::Printf(TEXT("/Engine/BasicShapes/%s.%s"), Name, Name), UStaticMesh::StaticClass()));
}

UMaterialInterface* UIRAssets::Material(const TCHAR* Name)
{
	return Cast<UMaterialInterface>(LoadPath(ObjPath(TEXT("Materials"), Name), UMaterialInterface::StaticClass()));
}

UMaterialInterface* UIRAssets::FXMaterial(const TCHAR* Name)
{
	return Cast<UMaterialInterface>(LoadPath(ObjPath(TEXT("FX"), Name), UMaterialInterface::StaticClass()));
}

UMaterialInterface* UIRAssets::BasicMaterial()
{
	return Cast<UMaterialInterface>(LoadPath(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"), UMaterialInterface::StaticClass()));
}

UTexture2D* UIRAssets::Texture(const TCHAR* Name)
{
	return Cast<UTexture2D>(LoadPath(ObjPath(TEXT("Textures"), Name), UTexture2D::StaticClass()));
}

USoundBase* UIRAssets::Sound(const FString& CategoryAndName)
{
	FString Folder, Name;
	if (!CategoryAndName.Split(TEXT("/"), &Folder, &Name))
	{
		return nullptr;
	}
	return Cast<USoundBase>(LoadPath(FString::Printf(TEXT("/Game/IceRiot/Audio/%s/%s.%s"), *Folder, *Name, *Name), USoundBase::StaticClass()));
}

USoundBase* UIRAssets::SoundVar(const FString& CategoryAndBase)
{
	int32* Count = VarCount.Find(CategoryAndBase);
	if (!Count)
	{
		int32 N = 0;
		while (N < 12 && Sound(FString::Printf(TEXT("%s_%02d"), *CategoryAndBase, N + 1)))
		{
			++N;
		}
		Count = &VarCount.Add(CategoryAndBase, N);
	}
	if (*Count == 0)
	{
		return Sound(CategoryAndBase);
	}
	return Sound(FString::Printf(TEXT("%s_%02d"), *CategoryAndBase, FMath::RandRange(1, *Count)));
}

UFont* UIRAssets::Font(bool bDisplay)
{
	UFont* F = Cast<UFont>(LoadPath(bDisplay ? TEXT("/Game/IceRiot/UI/F_Display.F_Display") : TEXT("/Game/IceRiot/UI/F_Body.F_Body"), UFont::StaticClass()));
	if (!F)
	{
		F = Cast<UFont>(LoadPath(TEXT("/Engine/EngineFonts/Roboto.Roboto"), UFont::StaticClass()));
	}
	return F;
}
