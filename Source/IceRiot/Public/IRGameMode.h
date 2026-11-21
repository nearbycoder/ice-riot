#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "IRTypes.h"
#include "IRInput.h"
#include "IRPlayer.h"
#include "IRPuck.h"
#include "IRGameMode.generated.h"

class AIRCamera;
class UIRAudio;
class UIRFX;
class AIRArena;
class UAnimSequence;

/** Screens (menus) layered over the arena. */
enum class EIRScreen : uint8 { Title, MainMenu, Join, TeamSelect, Options, Controls, Playing, Pause, Intermission, Results, Tournament, Credits };

enum class EIRMode : uint8 { Exhibition, Tournament, Practice, Attract };

struct FIRHuman
{
	FIRBinding Bind;
	int32 Team = 0;              // 0 home, 1 away
	bool bActive = false;
	bool bReady = false;
	TWeakObjectPtr<AIRPlayer> Controlled;
	FLinearColor Color = FLinearColor::White;
	FIRStats Stats;
	float SwitchCooldown = 0.f;
	FIRIntent LastIntent;
};

/** A callout on screen ("GOAL!", "POWER SHOT!", ...). */
struct FIRCallout
{
	FString Text;
	FString Sub;
	FLinearColor Color = FLinearColor::White;
	float Time = 0.f;
	float Duration = 2.f;
	float Scale = 1.f;
	int32 Style = 0;     // 0 = big center, 1 = side ticker, 2 = top banner
};

/** Replay frame for one player. */
struct FIRReplayActor
{
	FVector Pos;
	float Yaw;
	UAnimSequence* Seq;
	float Time;
	UAnimSequence* UpperSeq;
	float UpperTime;
	float UpperW;
	float StickScale;
};

struct FIRReplayFrame
{
	float T = 0.f;
	TArray<FIRReplayActor> Actors;
	FVector Puck;
	bool bPuckFire = false;
};

struct FIRPenalty
{
	TWeakObjectPtr<AIRPlayer> P;
	float Time = 0.f;
	FString Reason;
};

struct FIRFightState
{
	TWeakObjectPtr<AIRPlayer> A, B;
	float Time = 0.f;
	bool bOver = false;
	float OverTime = 0.f;
	TWeakObjectPtr<AIRPlayer> Winner;
};

UCLASS()
class ICERIOT_API AIRGameMode : public AGameModeBase
{
	GENERATED_BODY()
public:
	AIRGameMode();

	virtual void StartPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	// ---------------------------------------------------------------- setup / flow
	void GoToScreen(EIRScreen S);
	void StartMatch(EIRMode Mode);
	void StartAttract();
	void SpawnTeams();
	void ClearTeams();
	void AssignHumans();
	void SetupFaceoff(FVector2D Spot);
	void SetPhase(EIRMatchPhase P);
	void EndPeriod();
	void QuitToMenu();
	void ApplyOptionsLive();
	void LoadOptions();
	void SaveOptions();

	// ---------------------------------------------------------------- gameplay hooks used by players
	void OnShotReleased(AIRPlayer* Shooter, EIRShotKind Kind, float Power);
	void OnPassReleased(AIRPlayer* Passer, AIRPlayer* Target, bool bDrop);
	void OnCheck(AIRPlayer* Attacker, bool bPower);
	void OnPoke(AIRPlayer* Attacker);
	void OnHook(AIRPlayer* Attacker, bool bTrip);
	void OnSpin(AIRPlayer* Carrier);
	void CallPenalty(AIRPlayer* P, const FString& Reason);
	void ReleasePenalty(int32 InTeam);
	void TickPenalties(float Dt);
	void TickProRules(float Dt);
	void OnPlayerHitBoards(AIRPlayer* P, float Speed);
	void OnFaceoffDrop();
	void OnGoalieCleared(AIRPlayer* Goalie);
	void StartFight(AIRPlayer* A, AIRPlayer* B);
	void FightPunch(AIRPlayer* Attacker, int32 Kind);   // 0 jab, 1 punch, 2 uppercut, 3 grab
	AIRPlayer* PuckCarrier() const { return Puck ? Puck->Carrier.Get() : nullptr; }
	int32 AttackSign(int32 InTeam) const;               // which net (+1/-1) the team shoots at this period
	AIRPlayer* Goalie(int32 InTeam) const { return Goalies[InTeam]; }
	AIRPlayer* ChooseShotTarget(AIRPlayer* P) const;
	AIRPlayer* ChoosePassTarget(AIRPlayer* Passer, FVector2D StickDir, bool bStrict) const;
	bool IsLive() const { return Phase == EIRMatchPhase::Live; }
	float Difficulty01() const { return Opt.Difficulty / 4.f; }

	// ---------------------------------------------------------------- AI (IRAI.cpp)
	FIRIntent ThinkAI(AIRPlayer* P, float Dt);
	FIRIntent ThinkGoalie(AIRPlayer* P, float Dt);
	FIRIntent ThinkFighter(AIRPlayer* P, float Dt);
	FIRIntent ThinkFaceoff(AIRPlayer* P, float Dt);
	FVector2D SupportSpot(AIRPlayer* P, int32 Slot) const;
	float LaneOpen(FVector2D From, FVector2D To, int32 DefTeam, float Width = 90.f) const;
	float ShotQuality(AIRPlayer* P) const;
	float Pressure(AIRPlayer* P) const;

	// ---------------------------------------------------------------- feedback
	void Callout(const FString& Text, const FString& Sub, FLinearColor Color, float Duration = 2.f, int32 Style = 0, float Scale = 1.f);
	void Announce(const FString& Line, float Priority = 1.f);
	void Sfx(const FString& Name, const FVector& Where, float Volume = 1.f, float Pitch = 1.f);
	void Shake(float Amount);
	void RumbleFor(AIRPlayer* P, float Strength, float Duration);
	void Crowd(float Excite, const FString& Reaction = FString());

	// ---------------------------------------------------------------- state
	FIRGameOptions Opt;
	EIRMode Mode = EIRMode::Attract;
	EIRScreen Screen = EIRScreen::Title;
	EIRMatchPhase Phase = EIRMatchPhase::None;
	float PhaseTime = 0.f;
	float ScreenTime = 0.f;
	int32 TeamIdx[2] = { 0, 1 };
	FIRTeamInfo TeamInfo[2];
	int32 Score[2] = { 0, 0 };
	FIRTeamStats TStats[2];
	int32 Period = 1;
	float Clock = 120.f;
	bool bOvertime = false;
	int32 ScoringStreakTeam = -1;
	int32 ScoringStreak = 0;
	int32 BenchNext[2] = { 0, 0 };
	float SlowMo = 1.f;
	float SlowMoTime = 0.f;
	float HitStop = 0.f;
	int32 GoalSignLast = 0;
	int32 LastGoalTeam = -1;
	TWeakObjectPtr<AIRPlayer> LastScorer;
	TWeakObjectPtr<AIRPlayer> LastAssist;
	bool bLastGoalPower = false;
	float LastShotTime = -100.f;
	float PrevShotTime = -100.f;
	float LastFightTime = -100.f;
	float FaceoffDropTime = 0.f;
	bool bFaceoffDropped = false;
	FVector2D FaceoffSpot = FVector2D::ZeroVector;
	FVector2D PendingFaceoff = FVector2D::ZeroVector;
	float LooseTime = 0.f;
	float CatchupBoost[2] = { 0.f, 0.f };
	float AmbulanceTime = -10.f;
	float HatRainTime = -10.f;
	float GoalLightTime[2] = { -10.f, -10.f };
	float NetFireTime[2] = { -10.f, -10.f };
	bool bTwoMinuteCalled = false, bLastMinuteCalled = false;
	int32 TournamentStage = 0;
	TArray<int32> TournamentOrder;
	int32 PracticeKind = 0;
	FIRFightState Fight;
	TArray<FIRCallout> Callouts;
	FString Ticker;
	float WallTime = 0.f;
	float GameTime = 0.f;       // scaled match time
	FString AutoshotDir;

	// menus
	int32 MenuIndex = 0;
	int32 OptionsTab = 0;
	TArray<FIRHuman> Humans;
	int32 SelectCursor[2] = { 0, 1 };    // team select (left/right side)
	bool bSideLocked[2] = { false, false };
	EIRMode PendingMode = EIRMode::Exhibition;
	FString CheatBuffer;
	FString CheatToast;
	float CheatToastTime = 0.f;
	EIRScreen PauseReturn = EIRScreen::Playing;

	// replay
	TArray<FIRReplayFrame> ReplayBuf;
	int32 ReplayHead = 0;
	float ReplayCursor = 0.f;
	float ReplayStart = 0.f, ReplayEnd = 0.f;
	bool bReplaying = false;

	TArray<TObjectPtr<AIRPlayer>> Skaters[2];
	TArray<FIRPenalty> Penalties[2];
	float PrevPuckX = 0.f;
	bool bIcingCandidate = false;
	int32 IcingTeam = -1;   // actors stay alive through the world
	UPROPERTY() TObjectPtr<AIRPlayer> Goalies[2];
	UPROPERTY() TObjectPtr<AIRPlayer> Referee;
	UPROPERTY() TObjectPtr<AIRPuck> Puck;
	UPROPERTY() TObjectPtr<AIRCamera> Cam;
	UPROPERTY() TObjectPtr<UIRAudio> Audio;
	UPROPERTY() TObjectPtr<UIRFX> FX;
	UPROPERTY() TObjectPtr<AIRArena> Arena;

	TArray<AIRPlayer*> AllPlayers() const;
	TArray<AIRPlayer*> TeamSkaters(int32 InTeam) const;

	// test hooks
	bool bAutoplay = false;      // -irwatch: CPU vs CPU
	bool bAutopilot = false;     // -irautopilot: human slot 0 driven by AI through the human path
	float SimSpeed = 1.f;
	bool bSimExit = false;

private:
	void TickMenus(float Dt);
	void TickMatch(float Dt);
	void TickLive(float Dt);
	void TickFaceoff(float Dt);
	void TickFight(float Dt);
	void TickReplay(float Dt);
	void UpdatePuckInteractions(float Dt);
	void ResolveCollisions(float Dt);
	void HandlePuckHits(const TArray<FIRPuckHit>& Hits);
	void HandleHumans(float Dt);
	FIRIntent HumanIntent(FIRHuman& H, AIRPlayer* P, const FIRPadState& S);
	void SwitchHuman(FIRHuman& H, bool bForceNearest);
	void OnGoal(int32 Sign);
	void OnSave(AIRPlayer* G, bool bCatch, bool bPower);
	void PreRollShot(AIRPlayer* Shooter, EIRShotKind Kind, float Power);
	void RecordReplay();
	void StartReplay();
	void EndReplay();
	void UpdateCallouts(float Dt);
	void TickCheats();
	void HandleWhistle(FVector2D Spot, const FString& Reason);
	void StartPeriod();
	void FinishGame();
	void UpdateCatchup();
	void Autoshot(float Dt);
public:
	void EventShot(const TCHAR* Tag, float Delay = 0.35f);
private:
	float EventShotAt = -1.f;
	FString EventShotTag;
	int32 EventShotCount = 0;
	float NextAutoshot = 0.f;
	int32 AutoshotCount = 0;
	FString AutoshotPrefix;
	float AutoshotInterval = 0.f;
	float AutoshotEnd = 0.f;
	float AttractTimer = 0.f;
};
