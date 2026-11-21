#pragma once

#include "CoreMinimal.h"

/** ICE RIOT shared types. Units: Unreal centimeters, seconds. Rink: X along the length, Y across, Z up. */

constexpr int32 IR_MAX_HUMANS = 8;
constexpr int32 IR_NUM_TEAMS = 8;
constexpr int32 IR_ROSTER_SKATERS = 6;   // skaters per roster (on-ice 3 or 4, the rest replace fight losers)

enum class EIRRole : uint8 { Skater, Goalie, Referee };

enum class EIRRules : uint8 { Arcade, Pro };

enum class EIRCameraMode : uint8 { Broadcast, HighBroadcast, Overhead, EndZone, Close, Blimp, Count };

enum class EIRMatchPhase : uint8
{
	None,
	Intro,          // arena flyover + team intros
	FaceoffSetup,   // players gliding to their spots
	Faceoff,        // ref holding the puck, waiting for the drop
	Live,
	Goal,           // celebration
	Replay,
	Fight,
	Whistle,        // short stoppage before a face-off (freeze, out of play, icing...)
	PeriodEnd,
	Intermission,
	GameOver,
};

enum class EIRShotKind : uint8 { None, Wrist, Slap, OneTimer, Power, Pass, Dump, Clear };

/** Per-frame input for one human. */
struct FIRPadState
{
	FVector2D Move = FVector2D::ZeroVector;   // x = screen right, y = screen up, magnitude 0..1
	bool bShoot = false, bShootPressed = false, bShootReleased = false;
	bool bPass = false, bPassPressed = false, bPassReleased = false;
	bool bTurbo = false, bTurboPressed = false;
	bool bSwitch = false, bSwitchPressed = false;
	bool bHook = false, bHookPressed = false;
	bool bPausePressed = false;
	bool bStartPressed = false;      // Enter / gamepad Start (begins a game from the join screen)
	bool bCameraPressed = false;
	// menu navigation (edge-triggered, with auto-repeat)
	bool bUp = false, bDown = false, bLeft = false, bRight = false;
	bool bConfirm = false, bBack = false;
	bool bAnyPressed = false;
};

/** Ratings 1..10. */
struct FIRRatings
{
	uint8 Speed = 6, Shot = 6, Accuracy = 6, Pass = 6, Check = 6, Hands = 6, Fight = 6, Goalie = 6;
};

struct FIRPlayerInfo
{
	FString First;
	FString Last;
	int32 Number = 9;
	FIRRatings R;
	FLinearColor Skin = FLinearColor(0.8f, 0.55f, 0.4f);
	float Height = 1.f;     // scale 0.94..1.06
	float Bulk = 1.f;       // width scale
	bool bLefty = false;
};

struct FIRTeamInfo
{
	FString Id;          // NAR...
	FString City;
	FString Name;
	FString Abbrev;      // 3 letters
	FLinearColor Primary, Secondary, Trim;
	FIRPlayerInfo Skaters[IR_ROSTER_SKATERS];
	FIRPlayerInfo Goalie;
	int32 Stars = 3;     // overall 1..5 shown in team select
	bool bSecret = false;
};

/** Per-player game stats. */
struct FIRStats
{
	int32 Goals = 0, Assists = 0, Shots = 0, Hits = 0, Saves = 0, FightsWon = 0, Steals = 0;
	int32 Points() const { return Goals + Assists; }
};

struct FIRTeamStats
{
	int32 Shots = 0, Hits = 0, Faceoffs = 0, PowerShots = 0, Fights = 0, Saves = 0;
	int32 GoalsByPeriod[4] = { 0, 0, 0, 0 };
};

/** Game options (persisted in Saved/Config via GConfig). */
struct FIRGameOptions
{
	int32 PeriodSeconds = 120;  // 90/120/150/180
	int32 TeamSize = 3;         // skaters per side (3 or 4)
	EIRRules Rules = EIRRules::Arcade;
	int32 Difficulty = 2;       // 0..4 (Very Easy..Very Hard)
	bool bFighting = true;
	bool bPuckStreak = true;
	bool bCatchUp = true;
	bool bAutoSwitch = true;
	bool bReplays = true;
	bool bBigHeads = false;
	bool bTinyPlayers = false;
	bool bFightFrenzy = false;
	bool bSuperTeams = false;
	EIRCameraMode Camera = EIRCameraMode::Broadcast;
	// audio
	float MasterVol = 1.f, MusicVol = 0.7f, SfxVol = 1.f, CrowdVol = 0.9f, VoiceVol = 1.f;
	// video
	int32 Quality = 2;          // 0 perf,1 balanced,2 high,3 ultra
	bool bShowFps = false;
};
