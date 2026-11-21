#pragma once

#include "CoreMinimal.h"
#include "UObject/Object.h"
#include "IRFX.generated.h"

class UInstancedStaticMeshComponent;
class AIRPlayer;
class AActor;

/**
 * Lightweight CPU particle system. Every particle is one instance of a camera-facing quad (or a mesh for hats)
 * whose color/alpha go in per-instance custom data (materials in /Game/IceRiot/FX, built by Tools/ue_fx.py).
 */
UCLASS()
class ICERIOT_API UIRFX : public UObject
{
	GENERATED_BODY()
public:
	void Init(AActor* Owner);
	void Tick(float Dt, const FVector& CamLoc);
	void Clear();

	void IceSpray(const FVector& P, const FVector2D& Dir, float Amount);
	void Sparks(const FVector& P, const FLinearColor& C, int32 Count, float Speed = 600.f);
	void Impact(const FVector& P, float Scale, const FLinearColor& C);   // shockwave ring + flash
	void FireBurst(const FVector& P, float Scale);
	void FireTrail(const FVector& P, const FVector& Vel);
	void Streak(const FVector& P, const FLinearColor& C, float Size);
	void PowerCharge(AIRPlayer* P);
	void Confetti(const FVector& Center, const FLinearColor& A, const FLinearColor& B, int32 Count);
	void Hats(int32 Count);
	void Smoke(const FVector& P, float Scale);
	void Stars(const FVector& P);
	void Glow(const FVector& P, const FLinearColor& C, float Size, float Life);

	bool bEnabled = true;
	float Quality = 1.f;

private:
	enum EKind : uint8 { KAdd, KAlpha, KHat };
	struct FPart
	{
		FVector P, V;
		float Life, MaxLife;
		float Size0, Size1;
		FLinearColor C;
		float Drag;
		float Gravity;
		float Rot, RotV;
		EKind Kind;
		bool bFlat;       // lies on the ice instead of facing the camera
		bool bStretch;    // stretched along velocity
		bool bGround;     // collides with the ice
	};
	TArray<FPart> Parts;
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> AddISM;
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> AlphaISM;
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> HatISM;
	void Add(const FPart& P);
};
