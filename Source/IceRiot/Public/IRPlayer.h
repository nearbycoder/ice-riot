#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "IRTypes.h"
#include "IRPlayer.generated.h"

class AIRGameMode;
class UIRAnimInstance;
class USkeletalMeshComponent;
class UStaticMeshComponent;
class UMaterialInstanceDynamic;
class UAnimSequence;

/** What a controller (human or AI) wants this frame. MoveWorld is in world XY, magnitude 0..1. */
struct FIRIntent
{
	FVector2D MoveWorld = FVector2D::ZeroVector;
	bool bTurbo = false;
	bool bShoot = false, bShootPressed = false, bShootReleased = false;
	bool bPass = false, bPassPressed = false;
	bool bSwitchPressed = false;
	bool bHook = false, bHookPressed = false;
	/** AI: face this point instead of the move direction (skating backward / facing the play). */
	bool bFaceTarget = false;
	FVector2D FaceTarget = FVector2D::ZeroVector;
	/** AI: explicit pass target and shot aim. */
	class AIRPlayer* PassTo = nullptr;
	float ShotCharge = -1.f;   // AI: hold the shot this long before releasing (<0 = human control)
};

enum class EIRAction : uint8
{
	None,
	ShotCharge,     // holding the slap windup
	Shot,           // wrist / slap / power release animation
	OneTimerWindup, // waiting for a pass to arrive
	Pass,
	Check,
	Poke,
	Hook,
	Dive,
	Stop,
	Spin,           // deke spin-o-rama
	Down,           // lying on the ice
	GetUp,
	Flying,         // launched by a power check
	Celebrate,
	Dejected,
	FaceoffReady,
	FaceoffWin,
	FightIdle,
	FightAttack,
	FightHit,
	FightBlock,
	FightKO,
	GoalieSave,
	GoalieCover,
	GoaliePoke,
	RefDrop,
	Scripted,       // driven by the game (intro/replay)
};

UCLASS()
class ICERIOT_API AIRPlayer : public AActor
{
	GENERATED_BODY()
public:
	AIRPlayer();

	void Setup(AIRGameMode* InGame, int32 InTeam, int32 InTeamIndex, EIRRole InRole, const FIRPlayerInfo& InInfo, const struct FIRTeamInfo* TeamInfo);
	void SetInfo(const FIRPlayerInfo& InInfo);   // line change after a fight (new face/number)

	/** Gameplay step (deterministic order, called by the game mode). */
	void Simulate(float Dt, const FIRIntent& In);
	/** Visual step: animation choice, ring, lean, FX. */
	void UpdateVisuals(float Dt);

	// --- queries
	FVector2D Pos2() const { return Pos; }
	FVector GetPos3() const { return FVector(Pos.X, Pos.Y, Z); }
	FVector2D Forward() const { return FVector2D(FMath::Cos(Yaw), FMath::Sin(Yaw)); }
	FVector2D Right() const { return FVector2D(-FMath::Sin(Yaw), FMath::Cos(Yaw)); }
	float Speed() const { return Vel.Size(); }
	float MaxSpeed() const;
	bool IsGoalie() const { return Role == EIRRole::Goalie; }
	bool IsReferee() const { return Role == EIRRole::Referee; }
	bool IsHuman() const { return HumanIndex >= 0; }
	bool CanAct() const;           // free to start an action
	bool CanPlayPuck() const;      // allowed to pick up / control the puck
	bool IsDown() const { return Action == EIRAction::Down || Action == EIRAction::Flying || Action == EIRAction::GetUp || Action == EIRAction::Dive || Action == EIRAction::FightKO; }
	bool IsInFight() const { return Action >= EIRAction::FightIdle && Action <= EIRAction::FightKO; }
	bool HasPuck() const;
	/** Where the puck sits when carried (blade contact point on the ice). */
	FVector BladePos() const;
	FVector HeadPos() const;
	FVector2D StickReachPoint() const;

	// --- events from the game
	void TakeHit(AIRPlayer* From, float Power, bool bPowerCheck, FVector2D Dir);
	void Trip(AIRPlayer* From);
	void StartCelebrate(int32 Variant);
	void StartDejected();
	void PlayGoalieSave(const FVector& LocalTarget, bool bCatch);
	void PlayGoalieCover();
	void BeginFaceoff(FVector2D Spot, float FaceYaw);
	void FaceoffWin();
	void EnterFight(AIRPlayer* Opponent);
	void FightTakeHit(float Damage, bool bUppercut);
	void FightKO();
	void LeaveFight();
	void ResetForFaceoff();
	void SetScripted(bool bOn);
	void Teleport(FVector2D P, float InYaw);
	void PlayOneShot(UAnimSequence* Seq, float Rate = 1.f, float Blend = 0.12f);
	void ArmOneTimer(float Window);
	void StartAction(EIRAction A, float Duration);

	// --- state (public for the game mode / AI / HUD)
	UPROPERTY() TObjectPtr<AIRGameMode> Game;
	int32 Team = 0;
	int32 TeamIndex = 0;            // slot on the ice (0 = center, 1/2 = wings, 3 = D...)
	EIRRole Role = EIRRole::Skater;
	FIRPlayerInfo Info;
	int32 HumanIndex = -1;          // which human controls him (-1 = CPU)
	int32 LastHumanIndex = -1;      // last human who controlled him (CPU teammates of humans get a tinted ring)

	FVector2D Pos = FVector2D::ZeroVector;
	FVector2D Vel = FVector2D::ZeroVector;
	float Yaw = 0.f;                // radians
	float Z = 0.f;                  // height (flying)
	float VZ = 0.f;
	float SpinRate = 0.f;           // flying tumble / deke spin (rad/s)
	float Turbo = 1.f;
	float TurboDelay = 0.f;
	bool bTurboActive = false;
	float Anger = 0.f;              // 0..1
	float FightHealth = 1.f;
	float Stamina = 1.f;
	float Rage = 0.f;               // seconds of RAGE (free power shots) after winning a fight
	bool bBlazing = false;          // hat-trick fire
	int32 GoalsThisGame = 0;

	EIRAction Action = EIRAction::None;
	float ActionTime = 0.f;
	float ActionDuration = 0.f;
	bool bActionEvent = false;      // the action's gameplay event already fired
	EIRShotKind PendingShot = EIRShotKind::None;
	float ShotChargeTime = 0.f;
	float OneTimerWindow = 0.f;     // >0 while armed for a one-timer
	bool bAutoOneTimer = false;     // receive-and-fire (Shoot+Pass give-and-go)
	float NoPickupTime = 0.f;       // after shooting/passing/being stripped
	float StunTime = 0.f;
	float HookedTime = 0.f;
	float PassComboTimer = 0.f;     // shoot+pass chord detection
	float ShootComboTimer = 0.f;
	float LastHitTime = -100.f;
	TWeakObjectPtr<AIRPlayer> LastHitBy;
	TWeakObjectPtr<AIRPlayer> FightOpponent;
	FVector2D GoalieHome = FVector2D::ZeroVector;
	float GoalieGlow = 0.f;         // power save charge 0..1
	float StrideTimer = 0.f;
	float SprayTimer = 0.f;
	float FootstepPhase = 0.f;
	float LeanSmoothed = 0.f;
	float HitFlash = 0.f;
	float LastYaw = 0.f;
	float YawRate = 0.f;
	bool bStopping = false;
	bool bWasStopping = false;
	bool bBackward = false;
	FIRIntent LastIntent;
	FIRStats Stats;
	// AI memory
	float AITimer = 0.f;          // next discrete decision
	float PossessTime = 0.f;      // seconds with the puck
	float AIActTimer = 0.f;       // next defensive action allowed
	float AIWeave = 0.f;          // carry weave phase
	float AIChargeTarget = -1.f;
	bool bAIShooting = false;
	FVector2D AISpot = FVector2D::ZeroVector;

	// visuals
	UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> Root;
	UPROPERTY(VisibleAnywhere) TObjectPtr<USkeletalMeshComponent> Mesh;
	UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> Ring;
	UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> Shadow;
	UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> Placeholder;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> RingMID;
	UPROPERTY() TArray<TObjectPtr<UMaterialInstanceDynamic>> MIDs;
	UPROPERTY() TObjectPtr<UIRAnimInstance> AnimInst;
	bool bHasSkel = false;
	float HeadScale = 1.f;
	FLinearColor RingColor = FLinearColor::White;

	UAnimSequence* A(const TCHAR* Name) const;
	void ApplyTeamLook(const struct FIRTeamInfo* TeamInfo);

private:
	void SimulateSkater(float Dt, const FIRIntent& In);
	void SimulateGoalie(float Dt, const FIRIntent& In);
	void SimulateReferee(float Dt, const FIRIntent& In);
	void SimulateFight(float Dt, const FIRIntent& In);
	void HandleActions(float Dt, const FIRIntent& In);
	void Integrate(float Dt, const FIRIntent& In, float SpeedScale);
	void FireActionEvent();
	void SelectLocomotionAnim(float Dt);
	void BuildPlaceholder(const struct FIRTeamInfo* TeamInfo);
};
