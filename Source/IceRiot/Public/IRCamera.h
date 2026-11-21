#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "IRTypes.h"
#include "IRCamera.generated.h"

class UCameraComponent;
class AIRGameMode;

enum class EIRShot : uint8 { Game, Intro, Goal, Fight, Replay, Faceoff, Title, Results, Menu };

UCLASS()
class ICERIOT_API AIRCamera : public AActor
{
	GENERATED_BODY()
public:
	AIRCamera();
	void Init(AIRGameMode* InGame);
	void Tick2(float Dt);
	void SetShot(EIRShot S, float BlendTime = 0.6f);
	void Cut();
	void AddShake(float A) { ShakeAmt = FMath::Min(2.f, ShakeAmt + A); }
	/** Screen-space stick (x right, y up) to a world XY direction for the current view. */
	FVector2D ScreenToWorld(const FVector2D& Stick) const;
	FVector GetCamLocation() const;

	UPROPERTY(VisibleAnywhere) TObjectPtr<UCameraComponent> Camera;
	UPROPERTY() TObjectPtr<AIRGameMode> Game;
	EIRShot Shot = EIRShot::Title;
	float ShotTime = 0.f;
	FVector FocusSmoothed = FVector::ZeroVector;
	FVector2D FocusVel = FVector2D::ZeroVector;
	float ZoomSmoothed = 1.f;
	FVector CurLoc = FVector(0, 2600, 1400);
	FRotator CurRot = FRotator(-28, -90, 0);
	float CurFov = 52.f;
	float Blend = 1.f, BlendSpeed = 2.f;
	float ShakeAmt = 0.f;
	float ShakeT = 0.f;
	FVector ReplayCamPos = FVector::ZeroVector;
	int32 ReplayAngle = 0;

private:
	void ComputeGame(float Dt, FVector& OutLoc, FRotator& OutRot, float& OutFov);
	void ComputeShot(float Dt, FVector& OutLoc, FRotator& OutRot, float& OutFov);
};
