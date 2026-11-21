#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "IRArena.generated.h"

class UStaticMeshComponent;
class UCanvasRenderTarget2D;
class UCanvas;
class UMaterialInstanceDynamic;
class UDirectionalLightComponent;
class USkyLightComponent;
class UPostProcessComponent;
class USpotLightComponent;
class AIRGameMode;

UCLASS()
class ICERIOT_API AIRArena : public AActor
{
	GENERATED_BODY()
public:
	AIRArena();
	void Build(AIRGameMode* InGame);
	void Tick2(float Dt);
	void ApplyQuality(int32 Q);
	void SetGoalLight(int32 Sign, bool bOn);
	void SetIntroLights(bool bOn);
	void FlashGlass(float Amount) { GlassShake = FMath::Min(1.f, GlassShake + Amount); }

	UPROPERTY() TObjectPtr<AIRGameMode> Game;
	UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> Parts;
	UPROPERTY() TObjectPtr<UStaticMeshComponent> Crowd;
	UPROPERTY() TObjectPtr<UStaticMeshComponent> Jumbo;
	UPROPERTY() TObjectPtr<UStaticMeshComponent> Glass;
	UPROPERTY() TObjectPtr<UStaticMeshComponent> Ice;
	UPROPERTY() TObjectPtr<UStaticMeshComponent> Ambulance;
	UPROPERTY() TObjectPtr<UStaticMeshComponent> Resurfacer;
	float ResurfaceT = 0.f;
	UPROPERTY() TObjectPtr<UStaticMeshComponent> Nets[2];
	UPROPERTY() TObjectPtr<UStaticMeshComponent> GoalLights[2];
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> GoalLightMID[2];
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> CrowdMID;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> IceMID;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> JumboMID;
	UPROPERTY() TObjectPtr<UCanvasRenderTarget2D> JumboRT;
	UPROPERTY() TObjectPtr<UDirectionalLightComponent> Sun;
	UPROPERTY() TObjectPtr<USkyLightComponent> Sky;
	UPROPERTY() TObjectPtr<UPostProcessComponent> Post;
	UPROPERTY() TArray<TObjectPtr<USpotLightComponent>> Spots;
	UPROPERTY() TArray<TObjectPtr<USpotLightComponent>> IntroSpots;
	bool bHasArt = false;
	float JumboTimer = 0.f;
	float GlassShake = 0.f;
	float T = 0.f;
	bool bIntro = false;

	UFUNCTION() void DrawJumbo(UCanvas* Canvas, int32 Width, int32 Height);

private:
	UStaticMeshComponent* AddMesh(UStaticMesh* M, const FTransform& X, bool bShadow = true);
	void BuildPlaceholder();
};
