#include "IRGameMode.h"
#include "IceRiot.h"
#include "IRRoster.h"
#include "IRRink.h"
#include "IRCamera.h"
#include "IRAudio.h"
#include "IRFX.h"
#include "IRArena.h"
#include "IRHUD.h"
#include "IRAssets.h"
#include "IRAnimInstance.h"
#include "IRPlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/CommandLine.h"
#include "Misc/ConfigCacheIni.h"
#include "HAL/PlatformMisc.h"
#include "Engine/Engine.h"
#include "GameFramework/GameUserSettings.h"
#include "UnrealClient.h"
#include "HighResScreenshot.h"

using namespace IRRink;

static const FLinearColor GHumanColors[IR_MAX_HUMANS] = {
	FLinearColor(0.1f, 0.45f, 1.f),   // P1 blue
	FLinearColor(1.f, 0.85f, 0.05f),  // P2 yellow
	FLinearColor(1.f, 0.12f, 0.1f),   // P3 red
	FLinearColor(0.15f, 0.95f, 0.2f), // P4 green
	FLinearColor(1.f, 0.45f, 0.05f),  // P5 orange
	FLinearColor(0.75f, 0.25f, 1.f),  // P6 purple
	FLinearColor(0.1f, 0.95f, 0.95f), // P7 cyan
	FLinearColor(1.f, 0.35f, 0.75f),  // P8 pink
};

AIRGameMode::AIRGameMode()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bTickEvenWhenPaused = true;
	PlayerControllerClass = AIRPlayerController::StaticClass();
	HUDClass = AIRHUD::StaticClass();
	DefaultPawnClass = nullptr;
}

TArray<AIRPlayer*> AIRGameMode::AllPlayers() const
{
	TArray<AIRPlayer*> Out;
	for (int32 t = 0; t < 2; ++t)
	{
		for (AIRPlayer* P : Skaters[t]) { if (P) { Out.Add(P); } }
		if (Goalies[t]) { Out.Add(Goalies[t]); }
	}
	if (Referee) { Out.Add(Referee); }
	return Out;
}

TArray<AIRPlayer*> AIRGameMode::TeamSkaters(int32 InTeam) const
{
	TArray<AIRPlayer*> Out;
	for (AIRPlayer* P : Skaters[InTeam]) { if (P) { Out.Add(P); } }
	return Out;
}

int32 AIRGameMode::AttackSign(int32 InTeam) const
{
	// home team attacks +X in periods 1 and 3 (and overtime), teams switch ends every period
	const bool bSwap = (Period % 2) == 0;
	const int32 HomeSign = bSwap ? -1 : 1;
	return InTeam == 0 ? HomeSign : -HomeSign;
}

// ------------------------------------------------------------------------------------------------ options

void AIRGameMode::LoadOptions()
{
	const TCHAR* S = TEXT("IceRiot");
	const FString& Ini = GGameUserSettingsIni;
	GConfig->GetInt(S, TEXT("PeriodSeconds"), Opt.PeriodSeconds, Ini);
	GConfig->GetInt(S, TEXT("TeamSize"), Opt.TeamSize, Ini);
	int32 Rules = 0; GConfig->GetInt(S, TEXT("Rules"), Rules, Ini); Opt.Rules = EIRRules(FMath::Clamp(Rules, 0, 1));
	GConfig->GetInt(S, TEXT("Difficulty"), Opt.Difficulty, Ini);
	GConfig->GetBool(S, TEXT("Fighting"), Opt.bFighting, Ini);
	GConfig->GetBool(S, TEXT("PuckStreak"), Opt.bPuckStreak, Ini);
	GConfig->GetBool(S, TEXT("CatchUp"), Opt.bCatchUp, Ini);
	GConfig->GetBool(S, TEXT("AutoSwitch"), Opt.bAutoSwitch, Ini);
	GConfig->GetBool(S, TEXT("Replays"), Opt.bReplays, Ini);
	int32 CamIdx = 0; GConfig->GetInt(S, TEXT("Camera"), CamIdx, Ini); Opt.Camera = EIRCameraMode(FMath::Clamp(CamIdx, 0, int32(EIRCameraMode::Count) - 1));
	GConfig->GetFloat(S, TEXT("MasterVol"), Opt.MasterVol, Ini);
	GConfig->GetFloat(S, TEXT("MusicVol"), Opt.MusicVol, Ini);
	GConfig->GetFloat(S, TEXT("SfxVol"), Opt.SfxVol, Ini);
	GConfig->GetFloat(S, TEXT("CrowdVol"), Opt.CrowdVol, Ini);
	GConfig->GetFloat(S, TEXT("VoiceVol"), Opt.VoiceVol, Ini);
	GConfig->GetInt(S, TEXT("Quality"), Opt.Quality, Ini);
	GConfig->GetBool(S, TEXT("ShowFps"), Opt.bShowFps, Ini);
	Opt.PeriodSeconds = FMath::Clamp(Opt.PeriodSeconds, 30, 600);
	Opt.TeamSize = FMath::Clamp(Opt.TeamSize, 3, 4);
	Opt.Difficulty = FMath::Clamp(Opt.Difficulty, 0, 4);
	Opt.Quality = FMath::Clamp(Opt.Quality, 0, 3);
}

void AIRGameMode::SaveOptions()
{
	const TCHAR* S = TEXT("IceRiot");
	const FString& Ini = GGameUserSettingsIni;
	GConfig->SetInt(S, TEXT("PeriodSeconds"), Opt.PeriodSeconds, Ini);
	GConfig->SetInt(S, TEXT("TeamSize"), Opt.TeamSize, Ini);
	GConfig->SetInt(S, TEXT("Rules"), int32(Opt.Rules), Ini);
	GConfig->SetInt(S, TEXT("Difficulty"), Opt.Difficulty, Ini);
	GConfig->SetBool(S, TEXT("Fighting"), Opt.bFighting, Ini);
	GConfig->SetBool(S, TEXT("PuckStreak"), Opt.bPuckStreak, Ini);
	GConfig->SetBool(S, TEXT("CatchUp"), Opt.bCatchUp, Ini);
	GConfig->SetBool(S, TEXT("AutoSwitch"), Opt.bAutoSwitch, Ini);
	GConfig->SetBool(S, TEXT("Replays"), Opt.bReplays, Ini);
	GConfig->SetInt(S, TEXT("Camera"), int32(Opt.Camera), Ini);
	GConfig->SetFloat(S, TEXT("MasterVol"), Opt.MasterVol, Ini);
	GConfig->SetFloat(S, TEXT("MusicVol"), Opt.MusicVol, Ini);
	GConfig->SetFloat(S, TEXT("SfxVol"), Opt.SfxVol, Ini);
	GConfig->SetFloat(S, TEXT("CrowdVol"), Opt.CrowdVol, Ini);
	GConfig->SetFloat(S, TEXT("VoiceVol"), Opt.VoiceVol, Ini);
	GConfig->SetInt(S, TEXT("Quality"), Opt.Quality, Ini);
	GConfig->SetBool(S, TEXT("ShowFps"), Opt.bShowFps, Ini);
	GConfig->Flush(false, Ini);
}

void AIRGameMode::ApplyOptionsLive()
{
	if (Arena) { Arena->ApplyQuality(Opt.Quality); }
	if (FX) { FX->Quality = Opt.Quality == 0 ? 0.5f : 1.f; }
	if (GEngine)
	{
		// scalability: performance .. ultra
		const int32 Q = Opt.Quality;
		static const TCHAR* Cmds[4][6] = {
			{ TEXT("sg.ShadowQuality 0"), TEXT("sg.PostProcessQuality 0"), TEXT("sg.EffectsQuality 0"), TEXT("r.ScreenPercentage 70"), TEXT("sg.GlobalIlluminationQuality 0"), TEXT("sg.ReflectionQuality 0") },
			{ TEXT("sg.ShadowQuality 1"), TEXT("sg.PostProcessQuality 1"), TEXT("sg.EffectsQuality 1"), TEXT("r.ScreenPercentage 85"), TEXT("sg.GlobalIlluminationQuality 1"), TEXT("sg.ReflectionQuality 1") },
			{ TEXT("sg.ShadowQuality 2"), TEXT("sg.PostProcessQuality 2"), TEXT("sg.EffectsQuality 2"), TEXT("r.ScreenPercentage 100"), TEXT("sg.GlobalIlluminationQuality 2"), TEXT("sg.ReflectionQuality 2") },
			{ TEXT("sg.ShadowQuality 3"), TEXT("sg.PostProcessQuality 3"), TEXT("sg.EffectsQuality 3"), TEXT("r.ScreenPercentage 100"), TEXT("sg.GlobalIlluminationQuality 3"), TEXT("sg.ReflectionQuality 3") },
		};
#if !PLATFORM_WASM
		for (const TCHAR* C : Cmds[Q])
		{
			GEngine->Exec(GetWorld(), C);
		}
#endif
	}
}

// ------------------------------------------------------------------------------------------------ startup

void AIRGameMode::StartPlay()
{
	Super::StartPlay();
	LoadOptions();
	const TCHAR* Cmd = FCommandLine::Get();
	bAutoplay = FParse::Param(Cmd, TEXT("irwatch"));
	bAutopilot = FParse::Param(Cmd, TEXT("irautopilot"));
	FParse::Value(Cmd, TEXT("irspeed="), SimSpeed);
	bSimExit = FParse::Param(Cmd, TEXT("irsimexit"));
	int32 PeriodOverride = 0;
	if (FParse::Value(Cmd, TEXT("irperiod="), PeriodOverride)) { Opt.PeriodSeconds = PeriodOverride; }
	FParse::Value(Cmd, TEXT("irteamsize="), Opt.TeamSize);
	FParse::Value(Cmd, TEXT("irdiff="), Opt.Difficulty);
	if (FParse::Param(Cmd, TEXT("irbighead"))) { Opt.bBigHeads = true; }
	if (FParse::Param(Cmd, TEXT("irfrenzy"))) { Opt.bFightFrenzy = true; }
	if (FParse::Param(Cmd, TEXT("irpro"))) { Opt.Rules = EIRRules::Pro; }
	bTestPowerShots = FParse::Param(Cmd, TEXT("irpowershots"));
	if (FParse::Param(Cmd, TEXT("irarcade"))) { Opt.Rules = EIRRules::Arcade; }
	int32 CamMode = -1;
	if (FParse::Value(Cmd, TEXT("ircam="), CamMode)) { Opt.Camera = EIRCameraMode(FMath::Clamp(CamMode, 0, 5)); }

	UWorld* W = GetWorld();
	FActorSpawnParameters SP;
	SP.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	Arena = W->SpawnActor<AIRArena>(SP);
	Arena->Build(this);
	Cam = W->SpawnActor<AIRCamera>(SP);
	Cam->Init(this);
	Puck = W->SpawnActor<AIRPuck>(SP);
	UIRAssets* AS = UIRAssets::Get();
	if (UStaticMesh* PM = AS->Mesh(TEXT("SM_Puck")))
	{
		Puck->Mesh->SetStaticMesh(PM);
		Puck->Mesh->SetRelativeScale3D(FVector(1.5f, 1.5f, 1.4f));   // arcade readability: drawn bigger than its physics radius
	}
	else
	{
		Puck->Mesh->SetStaticMesh(AS->EngineShape(TEXT("Cylinder")));
		Puck->Mesh->SetRelativeScale3D(FVector(0.076f, 0.076f, 0.0254f));
		UMaterialInstanceDynamic* M = UMaterialInstanceDynamic::Create(AS->BasicMaterial(), Puck);
		M->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.01f, 0.01f, 0.01f));
		Puck->Mesh->SetMaterial(0, M);
	}
	if (UMaterialInterface* GM = AS->FXMaterial(TEXT("M_FX_Ring")))
	{
		// a crisp locator ring under the puck that reads on white ice
		Puck->Marker->SetStaticMesh(AS->EngineShape(TEXT("Plane")));
		Puck->MarkerMID = UMaterialInstanceDynamic::Create(GM, Puck);
		Puck->MarkerMID->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.f, 0.75f, 1.f));
		Puck->MarkerMID->SetScalarParameterValue(TEXT("Turbo"), 0.f);
		Puck->Marker->SetMaterial(0, Puck->MarkerMID);
		Puck->Marker->SetWorldScale3D(FVector(0.42f, 0.42f, 1.f));
		Puck->Marker->SetTranslucentSortPriority(6);
	}
	else
	{
		Puck->Marker->SetVisibility(false);
	}
	Audio = NewObject<UIRAudio>(this);
	Audio->Init(W, &Opt);
	FX = NewObject<UIRFX>(this);
	FX->Init(Arena);
	ApplyOptionsLive();

	if (APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0))
	{
		PC->SetViewTarget(Cam);
	}

	// screenshots for automated checks: -autoshot=<dir> -autoshotint=<sec> -autoshotdur=<sec>
	if (FParse::Value(Cmd, TEXT("autoshot="), AutoshotDir))
	{
		FParse::Value(Cmd, TEXT("autoshotint="), AutoshotInterval);
		FParse::Value(Cmd, TEXT("autoshotdur="), AutoshotEnd);
		if (AutoshotInterval <= 0.f) { AutoshotInterval = 2.f; }
		if (AutoshotEnd <= 0.f) { AutoshotEnd = 30.f; }
		NextAutoshot = 3.f;
	}

	FString StartMode;
	if (bAutoplay || bSimExit)
	{
		StartAttract();
		GoToScreen(EIRScreen::Playing);
		Mode = EIRMode::Exhibition;
		SetPhase(EIRMatchPhase::Intro);
	}
	else if (bAutopilot)
	{
		Humans.Reset();
		FIRHuman H;
		H.Bind = { EIRSource::Autopilot, -1 };
		H.Team = 0;
		H.bActive = true;
		H.Color = GHumanColors[0];
		Humans.Add(H);
		StartMatch(EIRMode::Exhibition);
	}
	else if (FParse::Value(Cmd, TEXT("irstart="), StartMode))
	{
		Humans.Reset();
		FIRHuman H;
		H.Bind = { EIRSource::KeyboardFull, -1 };
		H.bActive = true;
		H.Color = GHumanColors[0];
		Humans.Add(H);
		StartMatch(StartMode == TEXT("practice") ? EIRMode::Practice : EIRMode::Exhibition);
	}
	else
	{
		StartAttract();
		GoToScreen(EIRScreen::Title);
		// test hook: open a menu screen directly (-irscreen=menu|join|teams|options|controls|credits|pause)
		FString ScreenName;
		if (FParse::Value(Cmd, TEXT("irscreen="), ScreenName))
		{
			auto AddHuman = [this](EIRSource Src, int32 Team)
			{
				FIRHuman H; H.Bind = { Src, -1 }; H.Team = Team; H.bActive = true; H.Color = GHumanColors[Humans.Num()]; Humans.Add(H);
			};
			if (ScreenName == TEXT("menu")) { GoToScreen(EIRScreen::MainMenu); MenuIndex = 0; }
			else if (ScreenName == TEXT("join")) { PendingMode = EIRMode::Exhibition; AddHuman(EIRSource::KeyboardA, 0); AddHuman(EIRSource::KeyboardB, 1); AddHuman(EIRSource::Autopilot, 0); GoToScreen(EIRScreen::Join); }
			else if (ScreenName == TEXT("teams")) { PendingMode = EIRMode::Exhibition; AddHuman(EIRSource::KeyboardFull, 0); SelectCursor[0] = 5; SelectCursor[1] = 2; bSideLocked[0] = true; GoToScreen(EIRScreen::TeamSelect); }
			else if (ScreenName == TEXT("options")) { PauseReturn = EIRScreen::MainMenu; GoToScreen(EIRScreen::Options); MenuIndex = 4; }
			else if (ScreenName == TEXT("controls")) { GoToScreen(EIRScreen::Controls); }
			else if (ScreenName == TEXT("credits")) { GoToScreen(EIRScreen::Credits); }
		}
	}
}

void AIRGameMode::GoToScreen(EIRScreen S)
{
	Screen = S;
	ScreenTime = 0.f;
	MenuIndex = 0;
	if (!Audio)
	{
		return;
	}
	switch (S)
	{
	case EIRScreen::Title:
		Audio->PlayMusic(TEXT("Music_Title"), 1.5f);
		if (Cam) { Cam->SetShot(EIRShot::Title, 1.5f); }
		break;
	case EIRScreen::MainMenu:
	case EIRScreen::Join:
	case EIRScreen::TeamSelect:
	case EIRScreen::Options:
	case EIRScreen::Controls:
	case EIRScreen::Credits:
		if (Mode == EIRMode::Attract) { Audio->PlayMusic(TEXT("Music_Menu"), 1.5f); }
		break;
	case EIRScreen::Intermission:
		Audio->PlayMusic(TEXT("Music_Intermission"), 1.f);
		if (Cam) { Cam->SetShot(EIRShot::Title, 1.2f); }
		break;
	case EIRScreen::Results:
		Audio->PlayMusic(TEXT("Music_Victory"), 0.3f);
		break;
	default:
		break;
	}
}

void AIRGameMode::ClearTeams()
{
	for (AIRPlayer* P : AllPlayers())
	{
		if (P) { P->Destroy(); }
	}
	for (int32 t = 0; t < 2; ++t)
	{
		for (FIRPenalty& Pen : Penalties[t]) { if (AIRPlayer* P = Pen.P.Get()) { P->Destroy(); } }
		Penalties[t].Reset();
		Skaters[t].Reset();
		Goalies[t] = nullptr;
	}
	Referee = nullptr;
	if (Puck) { Puck->SetCarried(nullptr); Puck->LastTouch = nullptr; Puck->LastShooter = nullptr; Puck->PrevTouch = nullptr; }
}

void AIRGameMode::SpawnTeams()
{
	ClearTeams();
	const TArray<FIRTeamInfo>& All = IRRoster::Teams();
	int32 HumansPerTeam[2] = { 0, 0 };
	for (const FIRHuman& H : Humans) { if (H.bActive) { HumansPerTeam[H.Team]++; } }
	int32 Size = Opt.TeamSize;
	if (FMath::Max(HumansPerTeam[0], HumansPerTeam[1]) > 3) { Size = 4; }
	if (Mode == EIRMode::Practice) { Size = 1; }
	for (int32 t = 0; t < 2; ++t)
	{
		TeamInfo[t] = All[FMath::Clamp(TeamIdx[t], 0, All.Num() - 1)];
		BenchNext[t] = Size;
	}
	FActorSpawnParameters SP;
	SP.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	UWorld* W = GetWorld();
	for (int32 t = 0; t < 2; ++t)
	{
		const int32 N = (Mode == EIRMode::Practice && t == 1) ? 0 : Size;
		for (int32 i = 0; i < N; ++i)
		{
			AIRPlayer* P = W->SpawnActor<AIRPlayer>(SP);
			P->Setup(this, t, i, EIRRole::Skater, TeamInfo[t].Skaters[i], &TeamInfo[t]);
			P->RingColor = TeamInfo[t].Primary;
			Skaters[t].Add(P);
		}
		AIRPlayer* G = W->SpawnActor<AIRPlayer>(SP);
		G->Setup(this, t, 9, EIRRole::Goalie, TeamInfo[t].Goalie, &TeamInfo[t]);
		Goalies[t] = G;
	}
	Referee = W->SpawnActor<AIRPlayer>(SP);
	FIRPlayerInfo RefInfo;
	RefInfo.First = TEXT("Ref");
	RefInfo.Last = TEXT("Stripes");
	RefInfo.Number = 0;
	RefInfo.Skin = FLinearColor(0.7f, 0.5f, 0.38f);
	Referee->Setup(this, 0, 0, EIRRole::Referee, RefInfo, nullptr);
	AssignHumans();
}

void AIRGameMode::AssignHumans()
{
	for (AIRPlayer* P : AllPlayers()) { P->HumanIndex = -1; }
	for (int32 h = 0; h < Humans.Num(); ++h)
	{
		FIRHuman& H = Humans[h];
		H.Controlled = nullptr;
		if (!H.bActive) { continue; }
		H.Color = GHumanColors[h % IR_MAX_HUMANS];
		for (AIRPlayer* P : Skaters[H.Team])
		{
			if (P->HumanIndex < 0)
			{
				P->HumanIndex = h;
				P->LastHumanIndex = h;
				P->RingColor = H.Color;
				H.Controlled = P;
				break;
			}
		}
	}
}

void AIRGameMode::StartAttract()
{
	Mode = EIRMode::Attract;
	Humans.Reset();
	TeamIdx[0] = FMath::RandRange(0, 7);
	TeamIdx[1] = (TeamIdx[0] + FMath::RandRange(1, 7)) % 8;
	Score[0] = Score[1] = 0;
	Period = 1;
	bOvertime = false;
	Clock = Opt.PeriodSeconds;
	SpawnTeams();
	SetupFaceoff(FVector2D::ZeroVector);
	SetPhase(EIRMatchPhase::FaceoffSetup);
}

void AIRGameMode::StartMatch(EIRMode InMode)
{
	Mode = InMode;
	Score[0] = Score[1] = 0;
	TStats[0] = TStats[1] = FIRTeamStats();
	Period = 1;
	bOvertime = false;
	Clock = Opt.PeriodSeconds;
	ScoringStreak = 0;
	ScoringStreakTeam = -1;
	bTwoMinuteCalled = bLastMinuteCalled = false;
	ReplayBuf.Reset();
	Callouts.Reset();
	if (FX) { FX->Clear(); }
	for (FIRHuman& H : Humans) { H.Stats = FIRStats(); }
	if (Mode == EIRMode::Tournament && TournamentOrder.Num() > 0)
	{
		TeamIdx[1] = TournamentOrder[FMath::Clamp(TournamentStage, 0, TournamentOrder.Num() - 1)];
	}
	SpawnTeams();
	GoToScreen(EIRScreen::Playing);
	if (Mode == EIRMode::Practice)
	{
		SetupFaceoff(FVector2D(0.f, 0.f));
		SetPhase(EIRMatchPhase::Live);
		if (Audio) { Audio->PlayMusic(TEXT("Music_Menu"), 1.f); }
		return;
	}
	SetPhase(EIRMatchPhase::Intro);
}

void AIRGameMode::QuitToMenu()
{
	if (Audio) { Audio->StopAll(); }
	StartAttract();
	GoToScreen(EIRScreen::MainMenu);
}

// ------------------------------------------------------------------------------------------------ phases

void AIRGameMode::SetPhase(EIRMatchPhase P)
{
	Phase = P;
	PhaseTime = 0.f;
	const bool bAttract = Mode == EIRMode::Attract && Screen != EIRScreen::Playing;
	switch (P)
	{
	case EIRMatchPhase::Intro:
		if (Cam) { Cam->SetShot(EIRShot::Intro, 0.f); }
		if (Arena) { Arena->SetIntroLights(true); }
		SetupFaceoff(FVector2D::ZeroVector);
		for (AIRPlayer* Pl : AllPlayers()) { Pl->SetScripted(false); }
		if (Audio && !bAttract)
		{
			Audio->PlayMusic(TEXT("Music_Title"), 0.5f);
			Audio->Announce(TEXT("VO_Welcome"), 2.f);
			Audio->SetExcitement(0.9f);
		}
		break;
	case EIRMatchPhase::FaceoffSetup:
		if (Cam && !bAttract) { Cam->SetShot(EIRShot::Game, 0.8f); }
		if (Arena) { Arena->SetIntroLights(false); }
		if (Audio && !bAttract) { Audio->SetMusicDuck(0.55f); }
		break;
	case EIRMatchPhase::Faceoff:
		bFaceoffDropped = false;
		FaceoffDropTime = FMath::FRandRange(0.9f, 1.6f);
		if (Referee)
		{
			Referee->StartAction(EIRAction::RefDrop, 2.f);
		}
		break;
	case EIRMatchPhase::Live:
		if (Cam && !bAttract && Cam->Shot != EIRShot::Game) { Cam->SetShot(EIRShot::Game, 0.6f); }
		break;
	case EIRMatchPhase::Goal:
		if (Cam && !bAttract) { Cam->SetShot(EIRShot::Goal, 0.5f); }
		break;
	case EIRMatchPhase::Replay:
		StartReplay();
		break;
	case EIRMatchPhase::Fight:
		if (Cam && !bAttract) { Cam->SetShot(EIRShot::Fight, 0.5f); }
		break;
	case EIRMatchPhase::PeriodEnd:
		if (Audio) { Sfx(TEXT("Sfx/Period_Buzzer"), FVector::ZeroVector, 1.f); Audio->Announce(TEXT("VO_EndPeriod"), 2.f); }
		break;
	default:
		break;
	}
}

void AIRGameMode::SetupFaceoff(FVector2D Spot)
{
	FaceoffSpot = Spot;
	if (Arena) { Arena->SetGoalLight(1, false); Arena->SetGoalLight(-1, false); }
	if (Audio) { Audio->StopLoop(TEXT("NetFire")); }
	if (Puck)
	{
		Puck->SetCarried(nullptr);
		Puck->bFrozen = true;
		Puck->bOnFire = false;
		Puck->PlaceAt(FVector(Spot.X, Spot.Y, 95.f));
		Puck->bFrozen = true;
	}
	const bool bCenter = Spot.SizeSquared() < 1.f;
	for (int32 t = 0; t < 2; ++t)
	{
		const int32 A = AttackSign(t);
		const float FaceYaw = A > 0 ? 0.f : PI;
		TArray<AIRPlayer*> S = TeamSkaters(t);
		const FVector2D Positions[5] = {
			FVector2D(-A * 58.f, 0.f),                           // center
			FVector2D(-A * 120.f, bCenter ? 480.f : 420.f),      // wing
			FVector2D(-A * 120.f, bCenter ? -480.f : -420.f),    // wing
			FVector2D(-A * 650.f, 260.f),                        // D
			FVector2D(-A * 650.f, -260.f),                       // D
		};
		for (int32 i = 0; i < S.Num(); ++i)
		{
			FVector2D P = Spot + Positions[FMath::Min(i, 4)];
			FVector2D N;
			ClampInside(P, SkaterRadius + 10.f, N);
			S[i]->BeginFaceoff(P, i == 0 ? FaceYaw : FaceYaw);
			if (i != 0) { S[i]->Action = EIRAction::None; }
			S[i]->Turbo = FMath::Max(S[i]->Turbo, 0.6f);
		}
		if (Goalies[t])
		{
			const int32 Def = -A;
			Goalies[t]->ResetForFaceoff();
			Goalies[t]->GoalieHome = FVector2D((GoalLineX - 70.f) * Def, 0.f);
			Goalies[t]->Teleport(Goalies[t]->GoalieHome, Def > 0 ? PI : 0.f);
		}
	}
	if (Referee)
	{
		Referee->ResetForFaceoff();
		Referee->Teleport(Spot + FVector2D(0.f, 110.f), -PI * 0.5f);
	}
	for (FIRHuman& H : Humans)
	{
		// humans take the center at face-offs if their team's center is free
		if (H.bActive && Skaters[H.Team].Num() > 0)
		{
			AIRPlayer* C = Skaters[H.Team][0];
			if (C->HumanIndex < 0)
			{
				if (AIRPlayer* Old = H.Controlled.Get()) { Old->HumanIndex = -1; }
				C->HumanIndex = int32(&H - Humans.GetData());
				C->LastHumanIndex = C->HumanIndex;
				C->RingColor = H.Color;
				H.Controlled = C;
			}
		}
	}
	for (AIRPlayer* P : AllPlayers())
	{
		if (P->HumanIndex < 0 && !P->IsReferee() && !P->IsGoalie())
		{
			P->RingColor = TeamInfo[P->Team].Primary;
		}
	}
	if (Cam) { Cam->FocusSmoothed = FVector(Spot, 0.f); Cam->FocusVel = FVector2D::ZeroVector; }
}

void AIRGameMode::StartPeriod()
{
	Clock = bOvertime ? FMath::Max(60.f, Opt.PeriodSeconds * 0.75f) : float(Opt.PeriodSeconds);
	bTwoMinuteCalled = bLastMinuteCalled = false;
	SetupFaceoff(FVector2D::ZeroVector);
	SetPhase(EIRMatchPhase::FaceoffSetup);
	if (Audio)
	{
		Audio->PlayMusic(bOvertime ? TEXT("Music_Overtime") : TEXT("Music_Title"), 1.f);
		Audio->Announce(bOvertime ? TEXT("VO_Overtime") : FString::Printf(TEXT("VO_Period%d"), FMath::Clamp(Period, 1, 3)), 2.f);
	}
	Callout(bOvertime ? TEXT("OVERTIME") : FString::Printf(TEXT("PERIOD %d"), Period), bOvertime ? TEXT("SUDDEN DEATH") : FString(), FLinearColor(1.f, 0.85f, 0.2f), 2.2f, 2);
}

void AIRGameMode::EndPeriod()
{
	SetPhase(EIRMatchPhase::PeriodEnd);
	if (Puck) { Puck->SetCarried(nullptr); Puck->bFrozen = true; }
}

void AIRGameMode::FinishGame()
{
	SetPhase(EIRMatchPhase::GameOver);
	if (Mode == EIRMode::Attract)
	{
		StartAttract();
		return;
	}
	const int32 Winner = Score[0] > Score[1] ? 0 : 1;
	if (Audio)
	{
		Audio->Announce(TEXT("VO_FinalBuzzer"), 3.f);
		Audio->Announce(FString::Printf(TEXT("VO_Team_%s"), *TeamInfo[Winner].Id), 2.f);
		Audio->Announce(TEXT("VO_Wins"), 2.f);
		Audio->CrowdReaction(TEXT("Crowd_Cheer_Big"), 1.f);
	}
	if (Cam) { Cam->SetShot(EIRShot::Results, 1.5f); }
	for (AIRPlayer* P : AllPlayers())
	{
		if (P->IsReferee()) { continue; }
		if (P->Team == Winner) { P->StartCelebrate(FMath::RandRange(0, 2)); }
		else { P->StartDejected(); }
	}
	if (Mode == EIRMode::Tournament)
	{
		const bool bHumanWon = Winner == 0;
		if (bHumanWon) { TournamentStage++; }
	}
	GoToScreen(EIRScreen::Results);
	if (bSimExit)
	{
		extern int32 GIRDbg[6];
		UE_LOG(LogIceRiot, Display, TEXT("IR_SIM_RESULT DBG preroll=%d ontarget=%d saverolls=%d goals=%d early=%d"), GIRDbg[1], GIRDbg[2], GIRDbg[3], GIRDbg[4], GIRDbg[5]);
		UE_LOG(LogIceRiot, Display, TEXT("IR_SIM_RESULT %s %d - %d %s | shots %d-%d saves %d-%d hits %d-%d fights %d"), *TeamInfo[0].Abbrev, Score[0], Score[1], *TeamInfo[1].Abbrev,
			TStats[0].Shots, TStats[1].Shots, TStats[0].Saves, TStats[1].Saves, TStats[0].Hits, TStats[1].Hits, TStats[0].Fights + TStats[1].Fights);
		FPlatformMisc::RequestExit(false);
	}
}

// ------------------------------------------------------------------------------------------------ tick

void AIRGameMode::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	const float RealDt = FMath::Min(DeltaSeconds, 0.1f);
	WallTime += RealDt;
	ScreenTime += RealDt;
	FIRInput::Get().BeginFrame(RealDt);

	TickCheats();
	TickMenus(RealDt);

	const bool bPaused = Screen == EIRScreen::Pause || (Screen == EIRScreen::Options && PauseReturn == EIRScreen::Pause && Mode != EIRMode::Attract);
	float Dt = bPaused ? 0.f : RealDt * SimSpeed;
	if (SlowMoTime > 0.f)
	{
		SlowMoTime -= RealDt;
		Dt *= SlowMo;
	}
	if (HitStop > 0.f)
	{
		HitStop -= RealDt;
		Dt *= 0.08f;
	}
	if (Dt > 0.f)
	{
		// big sim speeds (automated tests) run in several fixed steps
		const int32 Steps = FMath::Clamp(FMath::CeilToInt(Dt / 0.034f), 1, 64);
		for (int32 i = 0; i < Steps; ++i)
		{
			TickMatch(Dt / Steps);
		}
	}
	// visuals (once per frame)
	if (!bReplaying)
	{
		for (AIRPlayer* P : AllPlayers()) { P->UpdateVisuals(FMath::Max(Dt, 1e-4f)); }
	}
	if (Puck) { Puck->UpdateVisuals(FMath::Max(Dt, 1e-4f)); }
	if (Cam) { Cam->Tick2(bPaused ? 0.f : RealDt); }
	if (Arena) { Arena->Tick2(RealDt); }
	if (FX && Cam) { FX->Tick(Dt, Cam->GetCamLocation()); }
	if (Audio) { Audio->Tick(RealDt); }
	UpdateCallouts(RealDt);
	// a net that took a power-shot goal keeps burning for a few seconds
	for (int32 i = 0; i < 2; ++i)
	{
		const float Age = GameTime - NetFireTime[i];
		if (Age >= 0.f && Age < 4.f && FX && Dt > 0.f && FMath::FRand() < Dt * 14.f)
		{
			const float Sign = i == 0 ? 1.f : -1.f;
			FX->FireBurst(FVector((IRRink::GoalLineX + 55.f) * Sign, FMath::FRandRange(-80.f, 80.f), 60.f), 0.45f);
			if (Audio && Age < 0.1f) { Audio->StartLoop(TEXT("NetFire"), TEXT("Sfx/Fire_Loop"), 0.6f); }
		}
	}
	Autoshot(RealDt);
}

void AIRGameMode::TickMatch(float Dt)
{
	GameTime += Dt;
	PhaseTime += Dt;
	if (Cam && Cam->Shot != EIRShot::Game) { /* camera follows its shot */ }
	switch (Phase)
	{
	case EIRMatchPhase::Intro:
	{
		const bool bSkip = Mode == EIRMode::Attract || (PhaseTime > 1.f && FIRInput::Get().AnyState().bConfirm);
		if (PhaseTime > 6.5f || bSkip)
		{
			if (Arena) { Arena->SetIntroLights(false); }
			StartPeriod();
		}
		else if (Audio && PhaseTime > 2.2f && PhaseTime - Dt <= 2.2f)
		{
			Audio->Announce(FString::Printf(TEXT("VO_Team_%s"), *TeamInfo[1].Id), 1.5f);
		}
		else if (Audio && PhaseTime > 3.8f && PhaseTime - Dt <= 3.8f)
		{
			Audio->Announce(FString::Printf(TEXT("VO_Team_%s"), *TeamInfo[0].Id), 1.5f);
		}
		break;
	}
	case EIRMatchPhase::FaceoffSetup:
		if (PhaseTime > 0.7f)
		{
			SetPhase(EIRMatchPhase::Faceoff);
		}
		break;
	case EIRMatchPhase::Faceoff:
		TickFaceoff(Dt);
		break;
	case EIRMatchPhase::Live:
		TickLive(Dt);
		break;
	case EIRMatchPhase::Goal:
	{
		// players keep celebrating; puck rests in the net
		for (AIRPlayer* P : AllPlayers())
		{
			FIRIntent In;
			if (P->Action == EIRAction::Celebrate && LastScorer.IsValid() && P != LastScorer.Get() && P->Team == LastScorer->Team)
			{
				In.MoveWorld = (LastScorer->Pos - P->Pos).GetSafeNormal() * FMath::Clamp((LastScorer->Pos - P->Pos).Size() / 400.f - 0.3f, 0.f, 1.f);
			}
			P->Simulate(Dt, In);
		}
		ResolveCollisions(Dt);
		TArray<FIRPuckHit> Hits;
		if (Puck) { Puck->Simulate(Dt, Hits); }
		RecordReplay();
		if (PhaseTime > 3.4f)
		{
			if (bOvertime)
			{
				FinishGame();
			}
			else if (Opt.bReplays && Mode != EIRMode::Attract && Mode != EIRMode::Practice)
			{
				SetPhase(EIRMatchPhase::Replay);
			}
			else
			{
				SetupFaceoff(FVector2D::ZeroVector);
				SetPhase(EIRMatchPhase::FaceoffSetup);
			}
		}
		break;
	}
	case EIRMatchPhase::Replay:
		TickReplay(Dt);
		break;
	case EIRMatchPhase::Fight:
		TickFight(Dt);
		break;
	case EIRMatchPhase::Whistle:
		for (AIRPlayer* P : AllPlayers())
		{
			FIRIntent In;
			P->Simulate(Dt, In);
		}
		ResolveCollisions(Dt);
		if (PhaseTime > 1.2f)
		{
			SetupFaceoff(PendingFaceoff);
			SetPhase(EIRMatchPhase::FaceoffSetup);
		}
		break;
	case EIRMatchPhase::PeriodEnd:
		for (AIRPlayer* P : AllPlayers())
		{
			FIRIntent In;
			P->Simulate(Dt, In);
		}
		if (PhaseTime > 2.5f)
		{
			const bool bTied = Score[0] == Score[1];
			if ((Period >= 3 && !bTied) || (Mode == EIRMode::Attract && Period >= 3 && (!bTied || Period >= 4)))
			{
				FinishGame();
			}
			else if (Mode == EIRMode::Attract)
			{
				Period++;
				StartPeriod();
			}
			else
			{
				SetPhase(EIRMatchPhase::Intermission);
				GoToScreen(EIRScreen::Intermission);
			}
		}
		break;
	case EIRMatchPhase::Intermission:
		if (bAutoplay || bSimExit || bAutopilot)
		{
			if (PhaseTime > 1.f)
			{
				if (Period >= 3) { bOvertime = true; }
				Period++;
				GoToScreen(EIRScreen::Playing);
				StartPeriod();
			}
		}
		break;
	case EIRMatchPhase::GameOver:
		for (AIRPlayer* P : AllPlayers())
		{
			FIRIntent In;
			P->Simulate(Dt, In);
		}
		ResolveCollisions(Dt);
		if ((bAutoplay) && PhaseTime > 6.f)
		{
			StartAttract();
			GoToScreen(EIRScreen::Playing);
			Mode = EIRMode::Exhibition;
			SetPhase(EIRMatchPhase::Intro);
		}
		break;
	default:
		break;
	}
}

void AIRGameMode::TickFaceoff(float Dt)
{
	// everyone holds position; humans may press early (false start)
	HandleHumans(Dt);
	for (AIRPlayer* P : AllPlayers())
	{
		FIRIntent In;
		if (P->IsGoalie()) { In = ThinkGoalie(P, Dt); }
		P->Simulate(Dt, In);
	}
	if (!bFaceoffDropped && PhaseTime >= FaceoffDropTime)
	{
		bFaceoffDropped = true;
		if (Puck)
		{
			Puck->bFrozen = false;
			Puck->PlaceAt(FVector(FaceoffSpot.X, FaceoffSpot.Y, 70.f));
			Puck->Vel = FVector(0, 0, -200.f);
		}
		Sfx(TEXT("Sfx/Faceoff_Drop"), FVector(FaceoffSpot, 0.f), 0.8f);
		OnFaceoffDrop();
	}
	if (bFaceoffDropped)
	{
		TArray<FIRPuckHit> Hits;
		if (Puck) { Puck->Simulate(Dt, Hits); }
		if (PhaseTime > FaceoffDropTime + 0.15f || (Puck && Puck->Pos.Z < 3.f))
		{
			OnFaceoffDrop();
		}
	}
}

// ------------------------------------------------------------------------------------------------ humans

FIRIntent AIRGameMode::HumanIntent(FIRHuman& H, AIRPlayer* P, const FIRPadState& S)
{
	FIRIntent In;
	In.MoveWorld = Cam ? Cam->ScreenToWorld(S.Move) : FVector2D(S.Move.X, -S.Move.Y);
	In.bTurbo = S.bTurbo;
	In.bShoot = S.bShoot;
	In.bShootPressed = S.bShootPressed;
	In.bShootReleased = S.bShootReleased;
	In.bPass = S.bPass;
	In.bPassPressed = S.bPassPressed;
	In.bSwitchPressed = S.bSwitchPressed;
	In.bHook = S.bHook;
	In.bHookPressed = S.bHookPressed;
	return In;
}

void AIRGameMode::SwitchHuman(FIRHuman& H, bool bForceNearest)
{
	const int32 HI = int32(&H - Humans.GetData());
	AIRPlayer* Cur = H.Controlled.Get();
	const FVector2D Target = Puck ? FVector2D(Puck->Pos.X, Puck->Pos.Y) : FVector2D::ZeroVector;
	AIRPlayer* Best = nullptr;
	float BestD = 1e12f;
	for (AIRPlayer* P : Skaters[H.Team])
	{
		if (P == Cur || (P->HumanIndex >= 0 && P->HumanIndex != HI) || P->IsInFight())
		{
			continue;
		}
		// prefer players between the puck and our own net
		const float D = FVector2D::DistSquared(P->Pos, Target) * (P->IsDown() ? 4.f : 1.f);
		if (D < BestD) { BestD = D; Best = P; }
	}
	if (!Best)
	{
		return;
	}
	if (Cur && !bForceNearest && FVector2D::DistSquared(Cur->Pos, Target) < BestD * 0.8f && Cur->HumanIndex == HI)
	{
		// current player is already the closest: still switch (the button means "give me someone else")
	}
	if (Cur && Cur->HumanIndex == HI)
	{
		Cur->HumanIndex = -1;
		Cur->RingColor = TeamInfo[Cur->Team].Primary;
	}
	Best->HumanIndex = HI;
	Best->LastHumanIndex = HI;
	Best->RingColor = H.Color;
	H.Controlled = Best;
	H.SwitchCooldown = 0.25f;
}

void AIRGameMode::HandleHumans(float Dt)
{
	for (int32 h = 0; h < Humans.Num(); ++h)
	{
		FIRHuman& H = Humans[h];
		if (!H.bActive)
		{
			continue;
		}
		H.SwitchCooldown -= Dt;
		AIRPlayer* P = H.Controlled.Get();
		if (!P || P->HumanIndex != h)
		{
			SwitchHuman(H, true);
			P = H.Controlled.Get();
		}
		if (!P)
		{
			continue;
		}
		FIRPadState S;
		if (H.Bind.Source == EIRSource::Autopilot)
		{
			// test hook: drive the human slot with the AI through the human input path
			const FIRIntent AI = ThinkAI(P, Dt);
			H.LastIntent = AI;
			continue;
		}
		S = FIRInput::Get().State(H.Bind);
		if (S.bCameraPressed)
		{
			Opt.Camera = EIRCameraMode((int32(Opt.Camera) + 1) % int32(EIRCameraMode::Count));
			Callout(FString::Printf(TEXT("CAMERA: %s"), *AIRHUD::CameraName(Opt.Camera)), FString(), FLinearColor::White, 1.2f, 1);
		}
		if (S.bPausePressed && Phase != EIRMatchPhase::Intro)
		{
			PauseReturn = Screen;
			GoToScreen(EIRScreen::Pause);
			if (Audio) { Audio->Ui(TEXT("UI_Select")); }
			return;
		}
		const bool bHasPuck = P->HasPuck();
		const bool bTeamHasPuck = PuckCarrier() && PuckCarrier()->Team == H.Team;
		if (S.bSwitchPressed && !bHasPuck && !bTeamHasPuck && H.SwitchCooldown <= 0.f && !P->IsInFight() && Phase == EIRMatchPhase::Live)
		{
			SwitchHuman(H, true);
			P = H.Controlled.Get();
			if (Audio) { Audio->Ui(TEXT("UI_Move"), 0.5f); }
			FIRIntent In = HumanIntent(H, P, S);
			In.bSwitchPressed = false;
			H.LastIntent = In;
			continue;
		}
		// when your team has the puck but a CPU teammate carries it: Pass = "give it to me", Shoot = "shoot it"
		if (bTeamHasPuck && !bHasPuck && PuckCarrier()->HumanIndex < 0)
		{
			if (S.bPassPressed)
			{
				// the CPU carrier sees PassComboTimer in its next think and feeds this player
				P->PassComboTimer = 0.6f;
				FIRIntent In = HumanIntent(H, P, S);
				In.bPassPressed = false;
				H.LastIntent = In;
				continue;
			}
			if (S.bShootPressed && PuckCarrier()->CanAct())
			{
				PuckCarrier()->ShootComboTimer = 0.5f;
			}
		}
		H.LastIntent = HumanIntent(H, P, S);
		if (S.bShoot || S.bPass || S.bTurbo || S.Move.SizeSquared() > 0.04f)
		{
			// any human activity
		}
	}
}

// ------------------------------------------------------------------------------------------------ menus

void AIRGameMode::TickMenus(float Dt)
{
	const FIRPadState& Any = FIRInput::Get().AnyState();
	auto Beep = [this](const TCHAR* N) { if (Audio) { Audio->Ui(N); } };

	switch (Screen)
	{
	case EIRScreen::Title:
		AttractTimer += Dt;
		if (ScreenTime > 0.6f && (Any.bConfirm || Any.bAnyPressed))
		{
			Beep(TEXT("UI_Start"));
			if (Audio) { Audio->Announce(TEXT("VO_Title"), 2.f); }
			GoToScreen(EIRScreen::MainMenu);
		}
		break;
	case EIRScreen::MainMenu:
	{
#if PLATFORM_WASM
		const int32 N = 6;
#else
		const int32 N = 7;
#endif
		if (Any.bUp) { MenuIndex = (MenuIndex + N - 1) % N; Beep(TEXT("UI_Move")); }
		if (Any.bDown) { MenuIndex = (MenuIndex + 1) % N; Beep(TEXT("UI_Move")); }
		if (Any.bBack) { Beep(TEXT("UI_Back")); GoToScreen(EIRScreen::Title); break; }
		if (Any.bConfirm && ScreenTime > 0.15f)
		{
			Beep(TEXT("UI_Select"));
			switch (MenuIndex)
			{
			case 0: PendingMode = EIRMode::Exhibition; Humans.Reset(); GoToScreen(EIRScreen::Join); break;
			case 1: PendingMode = EIRMode::Tournament; Humans.Reset(); GoToScreen(EIRScreen::Join); break;
			case 2: PendingMode = EIRMode::Practice; Humans.Reset(); GoToScreen(EIRScreen::Join); break;
			case 3: PauseReturn = EIRScreen::MainMenu; GoToScreen(EIRScreen::Options); break;
			case 4: GoToScreen(EIRScreen::Controls); break;
			case 5: GoToScreen(EIRScreen::Credits); break;
			case 6: SaveOptions(); FPlatformMisc::RequestExit(false); break;
			}
		}
		break;
	}
	case EIRScreen::Join:
	{
		const int32 MaxHumans = PendingMode == EIRMode::Exhibition ? IR_MAX_HUMANS : (PendingMode == EIRMode::Practice ? 1 : 4);
		FIRInput& In = FIRInput::Get();
		// new joins: gamepads by any face button, keyboard halves by their shoot key
		TArray<FIRBinding> Cands;
		for (int32 Id : In.KnownPads()) { Cands.Add({ EIRSource::Gamepad, Id }); }
		Cands.Add({ EIRSource::KeyboardA, -1 });
		Cands.Add({ EIRSource::KeyboardB, -1 });
		for (const FIRBinding& B : Cands)
		{
			const FIRPadState& S = In.State(B);
			bool bJoined = false;
			for (FIRHuman& H : Humans)
			{
				if (H.Bind == B || (B.Source == EIRSource::KeyboardA && H.Bind.Source == EIRSource::KeyboardFull)) { bJoined = true; }
			}
			if (bJoined || Humans.Num() >= MaxHumans || ScreenTime < 0.2f)
			{
				continue;
			}
			const bool bPress = B.Source == EIRSource::Gamepad ? (S.bShootPressed || S.bPassPressed || S.bConfirm) : S.bShootPressed;
			if (bPress)
			{
				FIRHuman H;
				H.Bind = B;
				// a lone keyboard player uses the whole keyboard
				if (B.Source == EIRSource::KeyboardA) { H.Bind.Source = EIRSource::KeyboardFull; }
				if (B.Source == EIRSource::KeyboardB)
				{
					for (FIRHuman& O : Humans) { if (O.Bind.Source == EIRSource::KeyboardFull) { O.Bind.Source = EIRSource::KeyboardA; } }
				}
				int32 Home = 0, Away = 0;
				for (const FIRHuman& O : Humans) { (O.Team == 0 ? Home : Away)++; }
				// like the N64 original: P2 joins P1, P3+P4 pair up against them
				H.Team = PendingMode == EIRMode::Exhibition && Humans.Num() >= 2 && Away < Home ? 1 : 0;
				H.bActive = true;
				H.Color = GHumanColors[Humans.Num()];
				Humans.Add(H);
				Beep(TEXT("UI_Join"));
			}
		}
		// joined players pick a side, the first player starts
		for (int32 h = 0; h < Humans.Num(); ++h)
		{
			FIRHuman& H = Humans[h];
			FIRBinding Read = H.Bind;
			const FIRPadState& S = In.State(Read);
			if (PendingMode == EIRMode::Exhibition && (S.bLeft || S.bRight))
			{
				H.Team = S.bLeft ? 0 : 1;
				Beep(TEXT("UI_Move"));
			}
			if (S.bBack && ScreenTime > 0.3f)
			{
				if (h == 0)
				{
					Humans.Reset();
					Beep(TEXT("UI_Back"));
					GoToScreen(EIRScreen::MainMenu);
					return;
				}
				Humans.RemoveAt(h);
				Beep(TEXT("UI_Back"));
				break;
			}
		}
		const bool bStart = ScreenTime > 0.4f && Any.bStartPressed;
		if (bStart && Humans.Num() > 0)
		{
			Beep(TEXT("UI_Select"));
			int32 Home = 0, Away = 0;
			for (const FIRHuman& O : Humans) { (O.Team == 0 ? Home : Away)++; }
			if (Home == 0)
			{
				for (FIRHuman& O : Humans) { O.Team = 0; }   // nobody on the home side: flip everyone so the menu flow stays simple
			}
			SelectCursor[0] = TeamIdx[0];
			SelectCursor[1] = TeamIdx[1];
			bSideLocked[0] = bSideLocked[1] = false;
			GoToScreen(EIRScreen::TeamSelect);
		}
		break;
	}
	case EIRScreen::TeamSelect:
	{
		const int32 NumTeams = IRRoster::NumSelectable(Opt.bSuperTeams);
		bool bSideHuman[2] = { false, false };
		for (const FIRHuman& H : Humans) { bSideHuman[H.Team] = true; }
		for (int32 h = 0; h < Humans.Num(); ++h)
		{
			const FIRPadState& S = FIRInput::Get().State(Humans[h].Bind);
			// humans steer their side; with no human on a side, player 1 also picks the opponent after locking
			int32 Side = Humans[h].Team;
			if (bSideLocked[Side] && !bSideHuman[1 - Side] && h == 0) { Side = 1 - Side; }
			if (S.bBack && ScreenTime > 0.2f)
			{
				if (bSideLocked[Side] ) { bSideLocked[Side] = false; Beep(TEXT("UI_Back")); }
				else if (bSideLocked[1 - Side] && !bSideHuman[1 - Side]) { bSideLocked[1 - Side] = false; Beep(TEXT("UI_Back")); }
				else if (h == 0) { Beep(TEXT("UI_Back")); GoToScreen(EIRScreen::Join); return; }
				continue;
			}
			if (bSideLocked[Side]) { continue; }
			if (S.bLeft) { SelectCursor[Side] = (SelectCursor[Side] + NumTeams - 1) % NumTeams; Beep(TEXT("UI_Move")); }
			if (S.bRight) { SelectCursor[Side] = (SelectCursor[Side] + 1) % NumTeams; Beep(TEXT("UI_Move")); }
			if ((S.bConfirm || S.bShootPressed) && ScreenTime > 0.25f)
			{
				bSideLocked[Side] = true;
				Beep(TEXT("UI_Select"));
				if (Audio) { Audio->Announce(FString::Printf(TEXT("VO_Team_%s"), *IRRoster::Teams()[SelectCursor[Side]].Id), 2.f); }
			}
		}
		if (PendingMode != EIRMode::Exhibition && bSideLocked[0])
		{
			bSideLocked[1] = true;
		}
		if (bSideLocked[0] && bSideLocked[1] && ScreenTime > 0.4f)
		{
			TeamIdx[0] = SelectCursor[0];
			TeamIdx[1] = SelectCursor[1];
			if (PendingMode == EIRMode::Tournament)
			{
				TournamentOrder.Reset();
				for (int32 i = 0; i < 8; ++i) { if (i != TeamIdx[0]) { TournamentOrder.Add(i); } }
				// easiest opponents first
				TournamentOrder.Sort([](int32 A, int32 B) { return IRRoster::Teams()[A].Stars < IRRoster::Teams()[B].Stars; });
				TournamentStage = 0;
			}
			if (TeamIdx[1] == TeamIdx[0] && PendingMode == EIRMode::Exhibition)
			{
				// mirror match is allowed; nothing to do
			}
			StartMatch(PendingMode);
		}
		break;
	}
	case EIRScreen::Options:
	{
		const int32 Rows = OptionsTab == 0 ? 10 : (OptionsTab == 1 ? 5 : 2);
		if (Any.bUp) { MenuIndex = (MenuIndex + Rows) % (Rows + 1); Beep(TEXT("UI_Move")); }
		if (Any.bDown) { MenuIndex = (MenuIndex + 1) % (Rows + 1); Beep(TEXT("UI_Move")); }
		bool bTabSwitch = false;
		for (FIRBinding B : { FIRBinding{ EIRSource::KeyboardFull, -1 } })
		{
			(void)B;
		}
		const int32 Dir = Any.bLeft ? -1 : (Any.bRight ? 1 : 0);
		if (MenuIndex == 0 && Dir != 0)
		{
			OptionsTab = (OptionsTab + 3 + Dir) % 3;
			bTabSwitch = true;
			Beep(TEXT("UI_Move"));
		}
		if (Dir != 0 && MenuIndex > 0 && !bTabSwitch)
		{
			Beep(TEXT("UI_Move"));
			const int32 R = MenuIndex - 1;
			const bool bInMatch = Mode != EIRMode::Attract;
			if (OptionsTab == 0)
			{
				switch (R)
				{
				case 0: if (!bInMatch) { static const int32 L[] = { 60, 90, 120, 150, 180, 300 }; int32 I = 0; for (int32 k = 0; k < 6; ++k) { if (L[k] == Opt.PeriodSeconds) { I = k; } } Opt.PeriodSeconds = L[(I + 6 + Dir) % 6]; } break;
				case 1: if (!bInMatch) { Opt.TeamSize = Opt.TeamSize == 3 ? 4 : 3; } break;
				case 2: if (!bInMatch) { Opt.Rules = Opt.Rules == EIRRules::Arcade ? EIRRules::Pro : EIRRules::Arcade; } break;
				case 3: Opt.Difficulty = FMath::Clamp(Opt.Difficulty + Dir, 0, 4); break;
				case 4: Opt.bFighting = !Opt.bFighting; break;
				case 5: Opt.bPuckStreak = !Opt.bPuckStreak; break;
				case 6: Opt.bCatchUp = !Opt.bCatchUp; break;
				case 7: Opt.bAutoSwitch = !Opt.bAutoSwitch; break;
				case 8: Opt.bReplays = !Opt.bReplays; break;
				case 9: Opt.Camera = EIRCameraMode((int32(Opt.Camera) + int32(EIRCameraMode::Count) + Dir) % int32(EIRCameraMode::Count)); break;
				}
			}
			else if (OptionsTab == 1)
			{
				float* V[] = { &Opt.MasterVol, &Opt.MusicVol, &Opt.SfxVol, &Opt.CrowdVol, &Opt.VoiceVol };
				*V[R] = FMath::Clamp(FMath::RoundToFloat((*V[R] + Dir * 0.1f) * 10.f) / 10.f, 0.f, 1.f);
				if (Audio) { Audio->Ui(TEXT("UI_Tick")); }
			}
			else
			{
				if (R == 0) { Opt.Quality = FMath::Clamp(Opt.Quality + Dir, 0, 3); ApplyOptionsLive(); }
				if (R == 1) { Opt.bShowFps = !Opt.bShowFps; }
			}
		}
		if (Any.bBack || (Any.bConfirm && MenuIndex == 0 && ScreenTime > 0.2f))
		{
			SaveOptions();
			ApplyOptionsLive();
			Beep(TEXT("UI_Back"));
			GoToScreen(PauseReturn == EIRScreen::Pause ? EIRScreen::Pause : EIRScreen::MainMenu);
		}
		break;
	}
	case EIRScreen::Controls:
	case EIRScreen::Credits:
		if ((Any.bBack || Any.bConfirm) && ScreenTime > 0.2f)
		{
			Beep(TEXT("UI_Back"));
			GoToScreen(EIRScreen::MainMenu);
		}
		break;
	case EIRScreen::Playing:
		if (Mode == EIRMode::Attract && !bAutoplay && !bSimExit)
		{
			// attract mode behind the title: any key goes back to the menu
			if (ScreenTime > 1.f && Any.bAnyPressed) { GoToScreen(EIRScreen::Title); }
		}
		break;
	case EIRScreen::Pause:
	{
		const int32 N = 5;
		bool bResume = false;
		if (Any.bUp) { MenuIndex = (MenuIndex + N - 1) % N; Beep(TEXT("UI_Move")); }
		if (Any.bDown) { MenuIndex = (MenuIndex + 1) % N; Beep(TEXT("UI_Move")); }
		if (Any.bPausePressed && ScreenTime > 0.2f) { bResume = true; }
		if (Any.bBack && ScreenTime > 0.2f) { bResume = true; }
		if (Any.bConfirm && ScreenTime > 0.2f)
		{
			Beep(TEXT("UI_Select"));
			switch (MenuIndex)
			{
			case 0: bResume = true; break;
			case 1: Opt.Camera = EIRCameraMode((int32(Opt.Camera) + 1) % int32(EIRCameraMode::Count)); break;
			case 2: PauseReturn = EIRScreen::Pause; GoToScreen(EIRScreen::Options); return;
			case 3: StartMatch(Mode); return;
			case 4: QuitToMenu(); return;
			}
		}
		if (bResume)
		{
			GoToScreen(EIRScreen::Playing);
			PauseReturn = EIRScreen::Playing;
		}
		break;
	}
	case EIRScreen::Intermission:
		if ((Any.bConfirm && ScreenTime > 1.f) || ScreenTime > 12.f)
		{
			Beep(TEXT("UI_Select"));
			if (Period >= 3) { bOvertime = true; }
			Period++;
			GoToScreen(EIRScreen::Playing);
			StartPeriod();
		}
		break;
	case EIRScreen::Results:
		if (Any.bConfirm && ScreenTime > 2.f)
		{
			Beep(TEXT("UI_Select"));
			if (Mode == EIRMode::Tournament && Score[0] > Score[1] && TournamentStage < TournamentOrder.Num())
			{
				StartMatch(EIRMode::Tournament);
			}
			else if (Mode == EIRMode::Tournament && Score[0] < Score[1])
			{
				StartMatch(EIRMode::Tournament);   // rematch the same team
			}
			else
			{
				QuitToMenu();
			}
		}
		break;
	default:
		break;
	}
}

// ------------------------------------------------------------------------------------------------ cheats

void AIRGameMode::TickCheats()
{
	if (Screen != EIRScreen::MainMenu && Screen != EIRScreen::Title && Screen != EIRScreen::Options && Screen != EIRScreen::TeamSelect)
	{
		return;
	}
	APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0);
	if (!PC)
	{
		return;
	}
	static const FKey Letters[] = { EKeys::A, EKeys::B, EKeys::C, EKeys::D, EKeys::E, EKeys::F, EKeys::G, EKeys::H, EKeys::I, EKeys::J, EKeys::K, EKeys::L, EKeys::M,
		EKeys::N, EKeys::O, EKeys::P, EKeys::Q, EKeys::R, EKeys::S, EKeys::T, EKeys::U, EKeys::V, EKeys::W, EKeys::X, EKeys::Y, EKeys::Z };
	for (int32 i = 0; i < 26; ++i)
	{
		if (PC->WasInputKeyJustPressed(Letters[i]))
		{
			CheatBuffer.AppendChar(TCHAR('A' + i));
			if (CheatBuffer.Len() > 16) { CheatBuffer.RightChopInline(CheatBuffer.Len() - 16); }
		}
	}
	auto Check = [this](const TCHAR* Word, bool& Flag, const TCHAR* Name)
	{
		if (CheatBuffer.EndsWith(Word))
		{
			Flag = !Flag;
			CheatBuffer.Reset();
			CheatToast = FString::Printf(TEXT("%s %s"), Name, Flag ? TEXT("ON") : TEXT("OFF"));
			CheatToastTime = 2.5f;
			if (Audio) { Audio->Ui(TEXT("UI_Impact")); }
		}
	};
	Check(TEXT("BIGHEAD"), Opt.bBigHeads, TEXT("BIG HEADS"));
	Check(TEXT("TINY"), Opt.bTinyPlayers, TEXT("TINY PLAYERS"));
	Check(TEXT("ALLSTAR"), Opt.bSuperTeams, TEXT("SUPER TEAMS"));
	Check(TEXT("FRENZY"), Opt.bFightFrenzy, TEXT("FIGHT FRENZY"));
}

// ------------------------------------------------------------------------------------------------ feedback helpers

void AIRGameMode::Callout(const FString& Text, const FString& Sub, FLinearColor Color, float Duration, int32 Style, float Scale)
{
	if (Mode == EIRMode::Attract && Screen != EIRScreen::Playing)
	{
		return;
	}
	if (Style == 0)
	{
		Callouts.RemoveAll([](const FIRCallout& C) { return C.Style == 0; });
	}
	FIRCallout C;
	C.Text = Text;
	C.Sub = Sub;
	C.Color = Color;
	C.Duration = Duration;
	C.Style = Style;
	C.Scale = Scale;
	Callouts.Add(C);
	if (Style == 0 && Audio) { Audio->Ui(TEXT("UI_Whoosh"), 0.6f); }
}

void AIRGameMode::UpdateCallouts(float Dt)
{
	for (FIRCallout& C : Callouts) { C.Time += Dt; }
	Callouts.RemoveAll([](const FIRCallout& C) { return C.Time > C.Duration; });
	CheatToastTime -= Dt;
}

void AIRGameMode::Announce(const FString& Line, float Priority)
{
	if (Audio && !(Mode == EIRMode::Attract && Screen != EIRScreen::Playing))
	{
		Audio->Announce(Line, Priority);
	}
}

void AIRGameMode::Sfx(const FString& Name, const FVector& Where, float Volume, float Pitch)
{
	if (Audio)
	{
		const float AttractMul = (Mode == EIRMode::Attract && Screen != EIRScreen::Playing) ? 0.35f : 1.f;
		Audio->Sfx(Name, Where, Volume * AttractMul, Pitch);
	}
}

void AIRGameMode::Shake(float Amount)
{
	if (Cam) { Cam->AddShake(Amount); }
}

void AIRGameMode::RumbleFor(AIRPlayer* P, float Strength, float Duration)
{
	if (P && P->HumanIndex >= 0 && Humans.IsValidIndex(P->HumanIndex))
	{
		FIRInput::Get().Rumble(Humans[P->HumanIndex].Bind, Strength, Duration);
	}
}

void AIRGameMode::Crowd(float Excite, const FString& Reaction)
{
	if (!Audio)
	{
		return;
	}
	Audio->Pulse(Excite);
	if (!Reaction.IsEmpty())
	{
		Audio->CrowdReaction(Reaction, 1.f);
	}
}

// ------------------------------------------------------------------------------------------------ autoshot

void AIRGameMode::Autoshot(float Dt)
{
	if (AutoshotDir.IsEmpty())
	{
		return;
	}
	if (WallTime > AutoshotEnd)
	{
		FPlatformMisc::RequestExit(false);
		AutoshotDir.Reset();
		return;
	}
	if (EventShotAt > 0.f && WallTime >= EventShotAt)
	{
		EventShotAt = -1.f;
		const FString File = FString::Printf(TEXT("%s/evt_%02d_%s.png"), *AutoshotDir, EventShotCount++, *EventShotTag);
		FScreenshotRequest::RequestScreenshot(File, false, false);
		UE_LOG(LogIceRiot, Display, TEXT("IR_AUTOSHOT %s"), *File);
	}
	if (WallTime >= NextAutoshot)
	{
		NextAutoshot = WallTime + AutoshotInterval;
		const FString File = FString::Printf(TEXT("%s/shot_%03d.png"), *AutoshotDir, AutoshotCount++);
		FScreenshotRequest::RequestScreenshot(File, false, false);
		UE_LOG(LogIceRiot, Display, TEXT("IR_AUTOSHOT %s phase=%d screen=%d score=%d-%d"), *File, int32(Phase), int32(Screen), Score[0], Score[1]);
	}
}

void AIRGameMode::EventShot(const TCHAR* Tag, float Delay)
{
	if (!AutoshotDir.IsEmpty() && EventShotAt < 0.f && EventShotCount < 40)
	{
		EventShotAt = WallTime + Delay;
		EventShotTag = Tag;
	}
}
