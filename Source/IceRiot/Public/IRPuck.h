#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "IRTypes.h"
#include "IRPuck.generated.h"

class AIRPlayer;
class UStaticMeshComponent;
class UMaterialInstanceDynamic;

/** Collision events the game reacts to (sounds, FX, rules). */
enum class EIRPuckEvent : uint8 { None, Boards, Glass, Post, Crossbar, NetOutside, NetInside, Ice, OutOfPlay, Goal };

struct FIRPuckHit
{
	EIRPuckEvent Type = EIRPuckEvent::None;
	FVector Location = FVector::ZeroVector;
	float Speed = 0.f;
	int32 GoalSign = 0;   // for Goal: which net (+1 = +X)
};

UCLASS()
class ICERIOT_API AIRPuck : public AActor
{
	GENERATED_BODY()
public:
	AIRPuck();

	/** Free-flight physics step. Appends collision events. */
	void Simulate(float Dt, TArray<FIRPuckHit>& OutHits);
	void UpdateVisuals(float Dt);

	void SetCarried(AIRPlayer* Carrier);
	void Release(const FVector& Velocity, EIRShotKind Kind, AIRPlayer* By);
	void PlaceAt(const FVector& P);
	bool IsFree() const { return Carrier == nullptr && !bFrozen; }

	FVector Pos = FVector(0, 0, 1.27f);
	FVector Vel = FVector::ZeroVector;
	FRotator Spin = FRotator::ZeroRotator;
	float SpinRate = 0.f;

	UPROPERTY() TObjectPtr<AIRPlayer> Carrier;
	UPROPERTY() TObjectPtr<AIRPlayer> LastTouch;
	UPROPERTY() TObjectPtr<AIRPlayer> LastShooter;
	UPROPERTY() TObjectPtr<AIRPlayer> PrevTouch;     // for assists (different team-mate)
	EIRShotKind Kind = EIRShotKind::None;
	float FlightTime = 0.f;
	bool bFrozen = false;          // held by a goalie / dead
	bool bInNet = false;
	int32 InNetSign = 0;
	bool bOnFire = false;          // power shot / blazing
	float FireTime = 0.f;
	float TrailTime = 0.f;

	/** Pre-rolled goalie outcome for the current shot (the game decides at release). */
	TWeakObjectPtr<AIRPlayer> SaveGoalie;
	bool bSaveCatch = false;
	bool bShotOnTarget = false;
	int32 ShotSign = 0;

	UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> Mesh;
	UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> Marker;   // glow disc so the puck is always readable
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> MarkerMID;

private:
	void CollideNets(FVector& P, FVector& V, TArray<FIRPuckHit>& OutHits);
	void CollideNet(int32 Sign, FVector& P, FVector& V, TArray<FIRPuckHit>& OutHits);
};
