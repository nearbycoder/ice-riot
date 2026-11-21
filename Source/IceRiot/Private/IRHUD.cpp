#include "IRHUD.h"
#include "IRGameMode.h"
#include "IRDraw.h"
#include "IRAssets.h"
#include "IRRoster.h"
#include "IRRink.h"
#include "IRInput.h"
#include "Engine/Canvas.h"
#include "CanvasItem.h"
#include "TextureResource.h"
#include "Engine/Texture2D.h"
#include "Kismet/GameplayStatics.h"

using namespace IRDraw;

namespace
{
	const FLinearColor Ice(0.35f, 0.85f, 1.f);
	const FLinearColor Hot(1.f, 0.42f, 0.05f);
	const FLinearColor Gold(1.f, 0.8f, 0.15f);
	const FLinearColor Ink(0.012f, 0.016f, 0.035f);
	const FLinearColor Dim(0.6f, 0.68f, 0.8f);
	FLinearColor WithA(FLinearColor C, float A) { C.A = A; return C; }
	float EaseOutBack(float X) { const float C1 = 1.70158f, C3 = C1 + 1.f; return 1.f + C3 * FMath::Pow(X - 1.f, 3.f) + C1 * FMath::Pow(X - 1.f, 2.f); }
	FString ClockStr(float Secs) { const int32 S = FMath::CeilToInt(FMath::Max(0.f, Secs)); return FString::Printf(TEXT("%d:%02d"), S / 60, S % 60); }
	FString SourceName(const FIRBinding& B, int32 PadIndex)
	{
		switch (B.Source)
		{
		case EIRSource::KeyboardFull: return TEXT("KEYBOARD");
		case EIRSource::KeyboardA: return TEXT("KEYBOARD WASD");
		case EIRSource::KeyboardB: return TEXT("KEYBOARD ARROWS");
		case EIRSource::Gamepad: return FString::Printf(TEXT("GAMEPAD %d"), PadIndex + 1);
		case EIRSource::Autopilot: return TEXT("AUTOPILOT");
		default: return TEXT("");
		}
	}
}

FString AIRHUD::CameraName(EIRCameraMode M)
{
	switch (M)
	{
	case EIRCameraMode::Broadcast: return TEXT("BROADCAST");
	case EIRCameraMode::HighBroadcast: return TEXT("HIGH BROADCAST");
	case EIRCameraMode::Overhead: return TEXT("OVERHEAD");
	case EIRCameraMode::EndZone: return TEXT("END ZONE");
	case EIRCameraMode::Close: return TEXT("CLOSE ACTION");
	case EIRCameraMode::Blimp: return TEXT("BLIMP");
	default: return TEXT("?");
	}
}

AIRGameMode* AIRHUD::G() const
{
	return Cast<AIRGameMode>(UGameplayStatics::GetGameMode(this));
}

void AIRHUD::DrawHUD()
{
	Super::DrawHUD();
	AIRGameMode* Game = G();
	if (!Game || !Canvas)
	{
		return;
	}
	W = Canvas->ClipX;
	H = Canvas->ClipY;
	S = FMath::Min(H / 1080.f, W / 1920.f);
	const float Now = GetWorld()->GetRealTimeSeconds();
	const float Dt = FMath::Clamp(Now - LastRealTime, 0.f, 0.25f);
	LastRealTime = Now;
	T += Dt;
	FpsAccum += Dt; FpsFrames++;
	if (FpsAccum > 0.5f) { FpsShown = FpsFrames / FpsAccum; MsShown = FpsAccum / FpsFrames * 1000.f; FpsAccum = 0.f; FpsFrames = 0; }

	switch (Game->Screen)
	{
	case EIRScreen::Title: DrawTitle(Game); break;
	case EIRScreen::MainMenu: DrawMainMenu(Game); break;
	case EIRScreen::Join: DrawJoin(Game); break;
	case EIRScreen::TeamSelect: DrawTeamSelect(Game); break;
	case EIRScreen::Options: if (Game->Mode != EIRMode::Attract) { DrawGameplay(Game); } DrawOptions(Game); break;
	case EIRScreen::Controls: DrawControls(Game); break;
	case EIRScreen::Credits: DrawCredits(Game); break;
	case EIRScreen::Playing: DrawGameplay(Game); break;
	case EIRScreen::Pause: DrawGameplay(Game); DrawPause(Game); break;
	case EIRScreen::Intermission: DrawIntermission(Game, false); break;
	case EIRScreen::Results: DrawIntermission(Game, true); break;
	default: break;
	}
	if (Game->CheatToastTime > 0.f)
	{
		const float A = FMath::Clamp(Game->CheatToastTime, 0.f, 1.f);
		Slant(Canvas, W * 0.5f - 260 * S, H - 190 * S, 520 * S, 64 * S, 18 * S, WithA(Hot, 0.9f * A));
		Text(Canvas, Game->CheatToast, W * 0.5f, H - 182 * S, 46 * S, WithA(FLinearColor::White, A), Center, true, 3 * S);
	}
	if (Game->Opt.bShowFps) { DrawFps(Game); }
}

// ------------------------------------------------------------------------------------------------ shared pieces

void AIRHUD::DrawPanel(float X, float Y, float PW, float PH, float Alpha)
{
	Box(Canvas, X, Y, PW, PH, WithA(Ink, Alpha));
	Box(Canvas, X, Y, PW, 3 * S, WithA(Ice, 0.9f * Alpha));
	Box(Canvas, X, Y + PH - 2 * S, PW, 2 * S, WithA(Ice, 0.25f * Alpha));
}

void AIRHUD::DrawLogo(float CX, float Y, float Scale, float Alpha)
{
	if (UTexture2D* Tex = UIRAssets::Get()->Texture(TEXT("T_LogoIceRiot")))
	{
		const float LW = 900.f * S * Scale;
		const float LH = LW * Tex->GetSizeY() / FMath::Max(1, Tex->GetSizeX());
		Image(Canvas, Tex, CX - LW * 0.5f, Y, LW, LH, WithA(FLinearColor::White, Alpha));
		return;
	}
	// typographic fallback logo: ICE (ice blue) RIOT (hot orange) with a slanted underline
	const float Sz = 190.f * S * Scale;
	const FVector2D A = Measure(TEXT("ICE "), Sz), B = Measure(TEXT("RIOT"), Sz);
	const float X0 = CX - (A.X + B.X) * 0.5f;
	Slant(Canvas, X0 - 30 * S * Scale, Y + Sz * 0.98f, A.X + B.X + 60 * S * Scale, 16 * S * Scale, -14 * S * Scale, WithA(Hot, Alpha));
	Text(Canvas, TEXT("ICE "), X0, Y, Sz, WithA(Ice, Alpha), Left, true, 0.f, WithA(Ink, Alpha), 6 * S * Scale);
	Text(Canvas, TEXT("RIOT"), X0 + A.X, Y, Sz, WithA(Hot, Alpha), Left, true, 0.f, WithA(Ink, Alpha), 6 * S * Scale);
}

void AIRHUD::DrawTeamBadge(const FIRTeamInfo& Team, float CX, float CY, float Size, float Alpha)
{
	if (UTexture2D* Tex = UIRAssets::Get()->Texture(*FString::Printf(TEXT("T_Logo_%s"), *Team.Id)))
	{
		Image(Canvas, Tex, CX - Size * 0.5f, CY - Size * 0.5f, Size, Size, WithA(FLinearColor::White, Alpha));
		return;
	}
	Circle(Canvas, CX, CY, Size * 0.5f, WithA(Team.Secondary, Alpha), 36);
	Circle(Canvas, CX, CY, Size * 0.44f, WithA(Team.Primary, Alpha), 36);
	Text(Canvas, Team.Abbrev, CX, CY - Size * 0.2f, Size * 0.36f, WithA(Team.Trim, Alpha), Center, true, 2 * S);
}

void AIRHUD::DrawFooter(const FString& Str)
{
	Box(Canvas, 0, H - 56 * S, W, 56 * S, WithA(Ink, 0.85f));
	Box(Canvas, 0, H - 56 * S, W, 2 * S, WithA(Ice, 0.6f));
	Text(Canvas, Str, W * 0.5f, H - 44 * S, 26 * S, Dim, Center, false);
}

void AIRHUD::DrawMenuItem(const FString& Label, float X, float Y, float Width, bool bSel, const FString& Value, bool bEnabled)
{
	const float HH = 58 * S;
	if (bSel)
	{
		const float Pulse = 0.85f + 0.15f * FMath::Sin(T * 6.f);
		Slant(Canvas, X - 10 * S, Y, Width, HH, 16 * S, WithA(Hot, 0.95f * Pulse));
		Slant(Canvas, X - 10 * S + Width + 6 * S, Y, 10 * S, HH, 16 * S, WithA(Gold, 0.9f));
	}
	else
	{
		Slant(Canvas, X - 10 * S, Y, Width, HH, 16 * S, WithA(Ink, 0.7f));
	}
	const FLinearColor C = !bEnabled ? FLinearColor(0.4f, 0.4f, 0.45f) : (bSel ? FLinearColor::White : FLinearColor(0.85f, 0.9f, 1.f));
	Text(Canvas, Label, X + 18 * S, Y + 6 * S, 44 * S, C, Left, true, bSel ? 3 * S : 0.f);
	if (!Value.IsEmpty())
	{
		const FString V = bSel ? FString::Printf(TEXT("<  %s  >"), *Value) : Value;
		Text(Canvas, V, X + Width - 30 * S, Y + 10 * S, 36 * S, bSel ? FLinearColor::White : Gold, Right, true);
	}
}

void AIRHUD::DrawFps(AIRGameMode* Game)
{
	const FString Str = FString::Printf(TEXT("%.0f FPS  %.1f ms"), FpsShown, MsShown);
	Box(Canvas, W - 250 * S, 10 * S, 240 * S, 40 * S, WithA(Ink, 0.7f));
	Text(Canvas, Str, W - 20 * S, 16 * S, 26 * S, MsShown < 8.6f ? FLinearColor(0.3f, 1.f, 0.4f) : (MsShown < 16.9f ? Gold : FLinearColor::Red), Right, false);
}

// ------------------------------------------------------------------------------------------------ gameplay HUD

void AIRHUD::DrawGameplay(AIRGameMode* Game)
{
	const bool bAttractBg = Game->Mode == EIRMode::Attract && Game->Screen != EIRScreen::Playing;
	if (bAttractBg)
	{
		return;
	}
	if (Game->Phase == EIRMatchPhase::Replay)
	{
		DrawReplay(Game);
		DrawCallouts(Game);
		return;
	}
	if (Game->Phase == EIRMatchPhase::Intro)
	{
		// team intro cards
		const float U = Game->PhaseTime;
		for (int32 t = 0; t < 2; ++t)
		{
			const float Start = t == 1 ? 1.8f : 3.4f;
			const float A = FMath::Clamp((U - Start) / 0.35f, 0.f, 1.f) * FMath::Clamp((6.4f - U) / 0.3f, 0.f, 1.f);
			if (A <= 0.f) { continue; }
			const FIRTeamInfo& TI = Game->TeamInfo[t];
			const float Slide = (1.f - EaseOutBack(FMath::Clamp((U - Start) / 0.45f, 0.f, 1.f))) * W * (t == 0 ? -0.5f : 0.5f);
			const float CX = (t == 0 ? W * 0.27f : W * 0.73f) + Slide;
			const float Y = H * 0.56f;
			Slant(Canvas, CX - 360 * S, Y, 720 * S, 190 * S, 30 * S, WithA(TI.Primary, 0.92f * A));
			Slant(Canvas, CX - 360 * S, Y + 190 * S, 720 * S, 12 * S, 30 * S, WithA(TI.Secondary, A));
			DrawTeamBadge(TI, CX - 250 * S, Y + 95 * S, 160 * S, A);
			Text(Canvas, TI.City.ToUpper(), CX - 150 * S, Y + 26 * S, 40 * S, WithA(TI.Trim, A), Left, true, 2 * S);
			Text(Canvas, TI.Name.ToUpper(), CX - 150 * S, Y + 66 * S, 86 * S, WithA(FLinearColor::White, A), Left, true, 4 * S);
			Text(Canvas, t == 0 ? TEXT("HOME") : TEXT("AWAY"), CX + 330 * S, Y - 40 * S, 34 * S, WithA(Gold, A), Right, true, 2 * S);
		}
		DrawLogo(W * 0.5f, H * 0.08f, 0.55f, FMath::Clamp(U / 0.6f, 0.f, 1.f) * FMath::Clamp((6.2f - U) / 0.4f, 0.f, 1.f));
		if (U > 1.f) { Text(Canvas, TEXT("PRESS ENTER / A TO SKIP"), W * 0.5f, H - 60 * S, 24 * S, WithA(Dim, 0.6f + 0.4f * FMath::Sin(T * 4.f)), Center, false); }
		return;
	}
	if (Game->Phase != EIRMatchPhase::Fight) { DrawPlayerMarkers(Game); }
	DrawScoreboard(Game);
	if (Game->Phase == EIRMatchPhase::Fight) { DrawFight(Game); }
	DrawFaceoffHint(Game);
	DrawAmbulance(Game);
	DrawCallouts(Game);
}

void AIRHUD::DrawScoreboard(AIRGameMode* Game)
{
	const float CW = 820 * S, CH = 70 * S;
	const float X = W * 0.5f - CW * 0.5f, Y = 22 * S;
	if (Game->Mode == EIRMode::Practice)
	{
		DrawPanel(W * 0.5f - 300 * S, Y, 600 * S, CH);
		Text(Canvas, TEXT("PRACTICE  ·  SHOOTING"), W * 0.5f, Y + 12 * S, 40 * S, FLinearColor::White, Center, true);
		Text(Canvas, FString::Printf(TEXT("GOALS %d   SHOTS %d"), Game->Score[0], Game->TStats[0].Shots), W * 0.5f, Y + CH + 6 * S, 28 * S, Gold, Center, true, 2 * S);
		return;
	}
	// home / away plates
	for (int32 t = 0; t < 2; ++t)
	{
		const FIRTeamInfo& TI = Game->TeamInfo[t];
		const float PX = t == 0 ? X : X + CW * 0.5f + 110 * S;
		const float PW = CW * 0.5f - 110 * S;
		Slant(Canvas, PX, Y, PW, CH, t == 0 ? 18 * S : -18 * S, WithA(TI.Primary, 0.95f));
		Box(Canvas, PX + (t == 0 ? 0 : PW - 8 * S), Y, 8 * S, CH, TI.Secondary);
		DrawTeamBadge(TI, t == 0 ? PX + 50 * S : PX + PW - 50 * S, Y + CH * 0.5f, 62 * S);
		Text(Canvas, TI.Abbrev, t == 0 ? PX + 95 * S : PX + PW - 95 * S, Y + 10 * S, 48 * S, FLinearColor::White, t == 0 ? Left : Right, true, 2 * S);
		// score box
		const float SX = t == 0 ? PX + PW - 90 * S : PX + 10 * S;
		Box(Canvas, SX, Y + 6 * S, 80 * S, CH - 12 * S, WithA(Ink, 0.85f));
		const bool bJust = Game->LastGoalTeam == t && Game->Phase == EIRMatchPhase::Goal;
		const float Pop = bJust ? 1.f + 0.25f * FMath::Max(0.f, 1.f - Game->PhaseTime * 2.f) : 1.f;
		Text(Canvas, FString::FromInt(Game->Score[t]), SX + 40 * S, Y + CH * 0.5f - 30 * S * Pop, 60 * S * Pop, bJust ? Gold : FLinearColor::White, Center, true);
	}
	// center: clock + period
	const float CX = W * 0.5f;
	Box(Canvas, CX - 110 * S, Y - 4 * S, 220 * S, CH + 8 * S, WithA(Ink, 0.92f));
	Box(Canvas, CX - 110 * S, Y - 4 * S, 220 * S, 3 * S, Ice);
	const bool bLow = Game->Clock < 10.f && Game->Phase == EIRMatchPhase::Live;
	Text(Canvas, ClockStr(Game->Clock), CX, Y + 2 * S, 44 * S, bLow && FMath::Fmod(T, 0.5f) < 0.25f ? FLinearColor::Red : FLinearColor::White, Center, true);
	const FString Per = Game->bOvertime ? TEXT("OVERTIME") : FString::Printf(TEXT("PERIOD %d"), Game->Period);
	Text(Canvas, Per, CX, Y + 46 * S, 20 * S, Gold, Center, false);

	// penalty timers (Pro rules)
	for (int32 t = 0; t < 2; ++t)
	{
		for (int32 i = 0; i < Game->Penalties[t].Num(); ++i)
		{
			const FIRPenalty& Pen = Game->Penalties[t][i];
			const float PX = t == 0 ? X + 20 * S : X + CW - 250 * S;
			Box(Canvas, PX, Y + CH + 36 * S + i * 34 * S, 230 * S, 30 * S, WithA(Ink, 0.85f));
			Text(Canvas, FString::Printf(TEXT("PENALTY  %s"), *ClockStr(Pen.Time)), PX + 10 * S, Y + CH + 38 * S + i * 34 * S, 24 * S, Gold, Left, true);
		}
		if (Game->Penalties[1 - t].Num() > 0 && Game->Penalties[t].Num() == 0)
		{
			const float PX = t == 0 ? X + 20 * S : X + CW - 250 * S;
			Slant(Canvas, PX, Y + CH + 36 * S, 230 * S, 30 * S, 8 * S, WithA(Hot, 0.9f));
			Text(Canvas, TEXT("POWER PLAY"), PX + 115 * S, Y + CH + 38 * S, 24 * S, FLinearColor::White, Center, true);
		}
	}
	// hot streak / rage badges under the plates
	for (int32 t = 0; t < 2; ++t)
	{
		for (AIRPlayer* P : Game->TeamSkaters(t))
		{
			if (P->bBlazing)
			{
				const float BX = t == 0 ? X + 30 * S : X + CW - 30 * S;
				Text(Canvas, FString::Printf(TEXT("BLAZING: %s"), *P->Info.Last.ToUpper()), BX, Y + CH + 8 * S, 22 * S, Hot, t == 0 ? Left : Right, true, 2 * S);
			}
		}
	}
}

void AIRHUD::DrawPlayerMarkers(AIRGameMode* Game)
{
	APlayerController* PC = GetOwningPlayerController();
	if (!PC)
	{
		return;
	}
	for (int32 h = 0; h < Game->Humans.Num(); ++h)
	{
		const FIRHuman& Hu = Game->Humans[h];
		AIRPlayer* P = Hu.Controlled.Get();
		if (!Hu.bActive || !P) { continue; }
		FVector2D Scr;
		const FVector Head = FVector(P->Pos.X, P->Pos.Y, P->Z + 230.f * (P->HeadScale > 1.5f ? 1.35f : 1.f));
		const bool bOn = PC->ProjectWorldLocationToScreen(Head, Scr, true);
		const FLinearColor C = Hu.Color;
		const FString Tag = FString::Printf(TEXT("P%d"), h + 1);
		if (bOn && Scr.X > 0 && Scr.X < W && Scr.Y > 0 && Scr.Y < H)
		{
			// colored tag with a pointer
			const float TW = 58 * S, TH = 34 * S;
			const float Bob = FMath::Sin(T * 5.f + h) * 3 * S;
			Box(Canvas, Scr.X - TW * 0.5f, Scr.Y - TH - 12 * S + Bob, TW, TH, WithA(Ink, 0.75f));
			Box(Canvas, Scr.X - TW * 0.5f, Scr.Y - 14 * S + Bob, TW, 3 * S, C);
			Text(Canvas, Tag, Scr.X, Scr.Y - TH - 10 * S + Bob, 28 * S, C, Center, true);
			FCanvasTriangleItem Tri(FVector2D(Scr.X - 9 * S, Scr.Y - 11 * S + Bob), FVector2D(Scr.X + 9 * S, Scr.Y - 11 * S + Bob), FVector2D(Scr.X, Scr.Y + Bob), GWhiteTexture);
			Tri.SetColor(C);
			Canvas->DrawItem(Tri);
			// anger meter when steaming
			if (P->Anger > 0.45f && Game->Opt.bFighting)
			{
				const float AW = 70 * S;
				Box(Canvas, Scr.X - AW * 0.5f, Scr.Y - TH - 24 * S + Bob, AW, 8 * S, WithA(Ink, 0.8f));
				Box(Canvas, Scr.X - AW * 0.5f, Scr.Y - TH - 24 * S + Bob, AW * FMath::Clamp(P->Anger, 0.f, 1.f), 8 * S, FLinearColor::LerpUsingHSV(Gold, FLinearColor::Red, P->Anger));
			}
			// slap-shot charge meter
			if (P->Action == EIRAction::ShotCharge && P->PendingShot != EIRShotKind::Power)
			{
				const float Ch = FMath::Clamp((P->ShotChargeTime - 0.1f) / 0.65f, 0.f, 1.f);
				const float MW = 90 * S;
				Box(Canvas, Scr.X + 40 * S, Scr.Y - 8 * S, 12 * S, MW, WithA(Ink, 0.8f));
				Box(Canvas, Scr.X + 40 * S, Scr.Y - 8 * S + MW * (1.f - Ch), 12 * S, MW * Ch, FLinearColor::LerpUsingHSV(Ice, Hot, Ch));
			}
		}
		else
		{
			// off-screen arrow at the edge
			FVector2D Dir = Scr - FVector2D(W * 0.5f, H * 0.5f);
			if (!bOn) { Dir = -Dir; }
			Dir.Normalize();
			const FVector2D E(FMath::Clamp(W * 0.5f + Dir.X * W, 40 * S, W - 40 * S), FMath::Clamp(H * 0.5f + Dir.Y * H, 120 * S, H - 40 * S));
			Circle(Canvas, E.X, E.Y, 26 * S, WithA(Ink, 0.8f), 20);
			Text(Canvas, Tag, E.X, E.Y - 15 * S, 24 * S, C, Center, true);
		}
	}
	// small name tag over the puck carrier
	if (AIRPlayer* Cr = Game->PuckCarrier())
	{
		if (!Cr->IsGoalie())
		{
			FVector2D Scr;
			if (PC->ProjectWorldLocationToScreen(FVector(Cr->Pos.X, Cr->Pos.Y, -30.f), Scr, true) && Cr->HumanIndex < 0)
			{
				Text(Canvas, FString::Printf(TEXT("%d %s"), Cr->Info.Number, *Cr->Info.Last.ToUpper()), Scr.X, Scr.Y + 6 * S, 20 * S, WithA(FLinearColor::White, 0.85f), Center, false, 2 * S);
			}
		}
	}
}

void AIRHUD::DrawCallouts(AIRGameMode* Game)
{
	int32 Ticker = 0;
	for (const FIRCallout& C : Game->Callouts)
	{
		const float U = C.Time;
		const float Out = FMath::Clamp((C.Duration - U) / 0.3f, 0.f, 1.f);
		if (C.Style == 0)
		{
			// big slam-in text
			const float In = FMath::Clamp(U / 0.25f, 0.f, 1.f);
			const float Sc = (U < 0.25f ? FMath::Lerp(2.4f, 1.f, EaseOutBack(In)) : 1.f + 0.03f * FMath::Sin(U * 8.f)) * C.Scale;
			const float Sz = 150.f * S * Sc;
			const float CY = H * 0.26f;
			const float Y = CY - Sz * 0.55f;
			Slant(Canvas, 0, CY - Sz * 0.42f, W, Sz * 0.84f, 0, WithA(Ink, 0.32f * Out * In));
			Slant(Canvas, W * 0.5f - 600 * S, CY + Sz * 0.42f, 1200 * S, 8 * S, 20 * S, WithA(C.Color, Out));
			Text(Canvas, C.Text, W * 0.5f, Y, Sz, WithA(FLinearColor::White, Out), Center, true, 0.f, WithA(C.Color, Out), 7 * S * Sc);
			if (!C.Sub.IsEmpty())
			{
				Text(Canvas, C.Sub, W * 0.5f, CY + Sz * 0.42f + 16 * S, 40 * S, WithA(FLinearColor::White, Out * FMath::Clamp((U - 0.2f) / 0.2f, 0.f, 1.f)), Center, true, 3 * S);
			}
		}
		else if (C.Style == 1)
		{
			// side ticker (bottom left)
			const float In = FMath::Clamp(U / 0.18f, 0.f, 1.f);
			const float X = FMath::Lerp(-420 * S, 30 * S, EaseOutBack(In));
			const float Y = H - 200 * S - Ticker * 66 * S;
			Slant(Canvas, X, Y, 380 * S, 56 * S, 14 * S, WithA(Ink, 0.85f * Out));
			Box(Canvas, X, Y, 8 * S, 56 * S, WithA(C.Color, Out));
			Text(Canvas, C.Text, X + 26 * S, Y + 4 * S, 34 * S, WithA(C.Color, Out), Left, true);
			if (!C.Sub.IsEmpty()) { Text(Canvas, C.Sub, X + 26 * S, Y + 36 * S, 16 * S, WithA(FLinearColor::White, Out * 0.85f), Left, false); }
			Ticker++;
		}
		else
		{
			// top banner
			const float In = FMath::Clamp(U / 0.3f, 0.f, 1.f);
			const float Y = 120 * S;
			const float BW = 900 * S * EaseOutBack(In);
			Slant(Canvas, W * 0.5f - BW * 0.5f, Y, BW, 92 * S, 26 * S, WithA(Ink, 0.88f * Out));
			Box(Canvas, W * 0.5f - BW * 0.5f, Y + 88 * S, BW, 4 * S, WithA(C.Color, Out));
			Text(Canvas, C.Text, W * 0.5f, Y + 6 * S, 64 * S, WithA(C.Color, Out * In), Center, true, 3 * S);
			if (!C.Sub.IsEmpty()) { Text(Canvas, C.Sub, W * 0.5f, Y + 100 * S, 30 * S, WithA(FLinearColor::White, Out * In), Center, true, 2 * S); }
		}
	}
}

void AIRHUD::DrawFight(AIRGameMode* Game)
{
	AIRPlayer* A = Game->Fight.A.Get();
	AIRPlayer* B = Game->Fight.B.Get();
	if (!A || !B)
	{
		return;
	}
	for (int32 i = 0; i < 2; ++i)
	{
		AIRPlayer* P = i == 0 ? A : B;
		const FIRTeamInfo& TI = Game->TeamInfo[P->Team];
		const float BW = 620 * S, BH = 34 * S;
		const float X = i == 0 ? 60 * S : W - 60 * S - BW;
		const float Y = H - 170 * S;
		Text(Canvas, FString::Printf(TEXT("#%d %s"), P->Info.Number, *P->Info.Last.ToUpper()), i == 0 ? X : X + BW, Y - 50 * S, 42 * S, FLinearColor::White, i == 0 ? Left : Right, true, 3 * S);
		if (P->HumanIndex >= 0 && Game->Humans.IsValidIndex(P->HumanIndex))
		{
			Text(Canvas, FString::Printf(TEXT("P%d"), P->HumanIndex + 1), i == 0 ? X + BW : X, Y - 46 * S, 36 * S, Game->Humans[P->HumanIndex].Color, i == 0 ? Right : Left, true, 2 * S);
		}
		Slant(Canvas, X, Y, BW, BH, 12 * S, WithA(Ink, 0.9f));
		const float Hp = FMath::Clamp(P->FightHealth, 0.f, 1.f);
		const float FX = i == 0 ? X : X + BW * (1.f - Hp);
		Slant(Canvas, FX, Y + 4 * S, BW * Hp, BH - 8 * S, 10 * S, FLinearColor::LerpUsingHSV(FLinearColor::Red, TI.Primary.GetLuminance() > 0.05f ? TI.Primary : Gold, Hp));
		// stamina
		Box(Canvas, X, Y + BH + 6 * S, BW * FMath::Clamp(P->Stamina, 0.f, 1.f), 6 * S, WithA(Gold, 0.85f));
	}
	if (!Game->Fight.bOver)
	{
		Text(Canvas, TEXT("SHOOT = PUNCH   PASS = JAB   HOOK = GRAB   TURBO+SHOOT = UPPERCUT   SWITCH = BLOCK"), W * 0.5f, H - 70 * S, 24 * S, Dim, Center, false, 2 * S);
	}
}

void AIRHUD::DrawAmbulance(AIRGameMode* Game)
{
	const float U = Game->GameTime - Game->AmbulanceTime;
	if (U < 0.f || U > 3.2f)
	{
		return;
	}
	// a cartoon ambulance races across the top of the screen
	const float X = FMath::Lerp(-300 * S, W + 300 * S, U / 3.2f);
	const float Y = 120 * S + FMath::Abs(FMath::Sin(U * 18.f)) * 4 * S;
	const float Sc = 1.f * S;
	Box(Canvas, X - 130 * Sc, Y, 190 * Sc, 80 * Sc, FLinearColor(0.95f, 0.95f, 0.95f));
	Box(Canvas, X + 60 * Sc, Y + 22 * Sc, 70 * Sc, 58 * Sc, FLinearColor(0.95f, 0.95f, 0.95f));
	Box(Canvas, X + 72 * Sc, Y + 30 * Sc, 46 * Sc, 22 * Sc, FLinearColor(0.3f, 0.6f, 0.9f));
	Box(Canvas, X - 130 * Sc, Y + 50 * Sc, 260 * Sc, 10 * Sc, FLinearColor(0.85f, 0.05f, 0.05f));
	Text(Canvas, TEXT("MEDIC"), X - 35 * Sc, Y + 8 * Sc, 34 * Sc, FLinearColor(0.85f, 0.05f, 0.05f), Center, true);
	const bool bFlash = FMath::Fmod(U, 0.3f) < 0.15f;
	Box(Canvas, X - 40 * Sc, Y - 16 * Sc, 30 * Sc, 16 * Sc, bFlash ? FLinearColor::Red : FLinearColor(0.2f, 0.4f, 1.f));
	Circle(Canvas, X - 80 * Sc, Y + 82 * Sc, 18 * Sc, FLinearColor(0.05f, 0.05f, 0.05f), 16);
	Circle(Canvas, X + 90 * Sc, Y + 82 * Sc, 18 * Sc, FLinearColor(0.05f, 0.05f, 0.05f), 16);
	// speed lines
	for (int32 i = 0; i < 4; ++i)
	{
		Box(Canvas, X - 230 * Sc - i * 30 * Sc, Y + (12 + i * 18) * Sc, 80 * Sc, 4 * Sc, WithA(FLinearColor::White, 0.6f));
	}
}

void AIRHUD::DrawReplay(AIRGameMode* Game)
{
	// letterbox + blinking REPLAY bug
	Box(Canvas, 0, 0, W, 80 * S, FLinearColor(0, 0, 0, 0.9f));
	Box(Canvas, 0, H - 80 * S, W, 80 * S, FLinearColor(0, 0, 0, 0.9f));
	if (FMath::Fmod(T, 1.f) < 0.6f) { Circle(Canvas, 60 * S, 40 * S, 12 * S, FLinearColor::Red, 16); }
	Text(Canvas, TEXT("REPLAY"), 84 * S, 18 * S, 44 * S, FLinearColor::White, Left, true);
	if (AIRPlayer* Sc = Game->LastScorer.Get())
	{
		const FString Line = FString::Printf(TEXT("GOAL: #%d %s"), Sc->Info.Number, *Sc->Info.Last.ToUpper()) + (Game->LastAssist.IsValid() ? FString::Printf(TEXT("   ASSIST: %s"), *Game->LastAssist->Info.Last.ToUpper()) : FString());
		Text(Canvas, Line, W - 40 * S, 22 * S, 32 * S, Gold, Right, true);
	}
	Text(Canvas, TEXT("PRESS SHOOT TO SKIP"), W * 0.5f, H - 56 * S, 24 * S, Dim, Center, false);
}

void AIRHUD::DrawFaceoffHint(AIRGameMode* Game)
{
	if (Game->Phase != EIRMatchPhase::Faceoff && Game->Phase != EIRMatchPhase::FaceoffSetup)
	{
		return;
	}
	bool bHumanCenter = false;
	for (const FIRHuman& Hu : Game->Humans)
	{
		if (Hu.Controlled.IsValid() && Game->Skaters[Hu.Team].Num() && Hu.Controlled.Get() == Game->Skaters[Hu.Team][0]) { bHumanCenter = true; }
	}
	Slant(Canvas, W * 0.5f - 210 * S, H * 0.78f, 420 * S, 60 * S, 16 * S, WithA(Ink, 0.8f));
	Text(Canvas, Game->bFaceoffDropped ? TEXT("GO!") : TEXT("FACE-OFF"), W * 0.5f, H * 0.78f + 6 * S, 46 * S, Game->bFaceoffDropped ? Gold : FLinearColor::White, Center, true);
	if (bHumanCenter)
	{
		Text(Canvas, TEXT("hit SHOOT or PASS the instant the puck drops · aim with the stick"), W * 0.5f, H * 0.78f + 70 * S, 24 * S, Dim, Center, false, 2 * S);
	}
}

// ------------------------------------------------------------------------------------------------ menus

void AIRHUD::DrawTitle(AIRGameMode* Game)
{
	Gradient(Canvas, 0, H * 0.45f, W, H * 0.55f, FLinearColor(0, 0, 0, 0.f), FLinearColor(0.f, 0.01f, 0.03f, 0.85f));
	Gradient(Canvas, 0, 0, W, H * 0.3f, FLinearColor(0.f, 0.01f, 0.03f, 0.7f), FLinearColor(0, 0, 0, 0.f));
	const float In = FMath::Clamp(Game->ScreenTime / 0.5f, 0.f, 1.f);
	DrawLogo(W * 0.5f, H * 0.16f - (1.f - EaseOutBack(In)) * 200 * S, 1.f, In);
	Text(Canvas, TEXT("ARCADE HOCKEY · UP TO 8 PLAYERS"), W * 0.5f, H * 0.47f, 34 * S, WithA(FLinearColor::White, In), Center, true, 3 * S);
	const float Blink = 0.55f + 0.45f * FMath::Sin(T * 4.f);
	Slant(Canvas, W * 0.5f - 260 * S, H * 0.7f, 520 * S, 74 * S, 20 * S, WithA(Hot, 0.9f * Blink));
	Text(Canvas, TEXT("PRESS START"), W * 0.5f, H * 0.7f + 10 * S, 56 * S, FLinearColor::White, Center, true, 3 * S);
	Text(Canvas, TEXT("ENTER / SPACE / ANY GAMEPAD BUTTON"), W * 0.5f, H * 0.7f + 90 * S, 22 * S, Dim, Center, false);
	Text(Canvas, TEXT("© ICE RIOT CONTRIBUTORS · OPEN SOURCE · MADE WITH BLENDER + UNREAL ENGINE"), W * 0.5f, H - 40 * S, 18 * S, WithA(Dim, 0.7f), Center, false);
}

void AIRHUD::DrawMainMenu(AIRGameMode* Game)
{
	Gradient(Canvas, 0, 0, W * 0.55f, H, FLinearColor(0.f, 0.01f, 0.03f, 0.88f), FLinearColor(0.f, 0.01f, 0.03f, 0.7f));
	DrawLogo(W * 0.27f, 70 * S, 0.62f);
#if PLATFORM_WASM
	static const TCHAR* Items[] = { TEXT("EXHIBITION"), TEXT("TOURNAMENT"), TEXT("PRACTICE"), TEXT("OPTIONS"), TEXT("CONTROLS"), TEXT("CREDITS") };
	const int32 N = 6;
#else
	static const TCHAR* Items[] = { TEXT("EXHIBITION"), TEXT("TOURNAMENT"), TEXT("PRACTICE"), TEXT("OPTIONS"), TEXT("CONTROLS"), TEXT("CREDITS"), TEXT("QUIT") };
	const int32 N = 7;
#endif
	static const TCHAR* Desc[] = {
		TEXT("1-8 players. Any teams, any sides. Drop the gloves."),
		TEXT("Beat every team in the league to lift the cup."),
		TEXT("You, a bucket of pucks and a goalie. Work on that snipe."),
		TEXT("Period length, team size, rules, difficulty, audio, video."),
		TEXT("Keyboard and gamepad layouts, combos and secret moves."),
		TEXT("Who made this thing."),
		TEXT("Hang up the skates."),
	};
	const float X0 = 130 * S, Y0 = H * 0.36f;
	for (int32 i = 0; i < N; ++i)
	{
		const float In = FMath::Clamp((Game->ScreenTime - i * 0.04f) / 0.25f, 0.f, 1.f);
		DrawMenuItem(Items[i], X0 - (1.f - EaseOutBack(In)) * 400 * S, Y0 + i * 70 * S, 560 * S, Game->MenuIndex == i);
	}
	Text(Canvas, Desc[FMath::Clamp(Game->MenuIndex, 0, N - 1)], X0, Y0 + N * 70 * S + 20 * S, 26 * S, Dim, Left, false);
	DrawFooter(TEXT("UP/DOWN select · ENTER / A confirm · ESC / B back"));
}

void AIRHUD::DrawJoin(AIRGameMode* Game)
{
	Box(Canvas, 0, 0, W, H, WithA(Ink, 0.82f));
	const FString Title = Game->PendingMode == EIRMode::Tournament ? TEXT("TOURNAMENT") : Game->PendingMode == EIRMode::Practice ? TEXT("PRACTICE") : TEXT("EXHIBITION");
	Text(Canvas, Title, W * 0.5f, 40 * S, 80 * S, FLinearColor::White, Center, true, 4 * S);
	Text(Canvas, TEXT("JOIN IN: press SHOOT (gamepad A · keyboard J/Space · arrows-side , )"), W * 0.5f, 140 * S, 28 * S, Gold, Center, false);
	const float ColW = 700 * S;
	for (int32 Side = 0; Side < 2; ++Side)
	{
		if (Game->PendingMode != EIRMode::Exhibition && Side == 1) { continue; }
		const float CX = Game->PendingMode != EIRMode::Exhibition ? W * 0.5f : (Side == 0 ? W * 0.28f : W * 0.72f);
		DrawPanel(CX - ColW * 0.5f, 210 * S, ColW, 640 * S);
		Text(Canvas, Side == 0 ? TEXT("HOME") : TEXT("AWAY"), CX, 226 * S, 56 * S, Side == 0 ? Ice : Hot, Center, true, 3 * S);
		int32 Row = 0;
		for (int32 h = 0; h < Game->Humans.Num(); ++h)
		{
			const FIRHuman& Hu = Game->Humans[h];
			if (Hu.Team != Side) { continue; }
			const float Y = 310 * S + Row * 128 * S;
			Slant(Canvas, CX - ColW * 0.44f, Y, ColW * 0.88f, 108 * S, 14 * S, WithA(Hu.Color, 0.9f));
			Text(Canvas, FString::Printf(TEXT("P%d"), h + 1), CX - ColW * 0.38f, Y + 14 * S, 72 * S, Ink, Left, true);
			const int32 PadIdx = Game->Humans[h].Bind.Source == EIRSource::Gamepad ? FIRInput::Get().KnownPads().IndexOfByKey(Hu.Bind.DeviceId) : 0;
			Text(Canvas, SourceName(Hu.Bind, PadIdx), CX - ColW * 0.18f, Y + 34 * S, 36 * S, Ink, Left, true);
			if (Game->PendingMode == EIRMode::Exhibition)
			{
				Text(Canvas, Side == 0 ? TEXT("→") : TEXT("←"), CX + ColW * 0.38f, Y + 30 * S, 40 * S, WithA(Ink, 0.7f), Center, false);
			}
			Row++;
		}
		if (Row < 4 && Game->Humans.Num() < IR_MAX_HUMANS)
		{
			const float Y = 310 * S + Row * 128 * S;
			const float A = 0.35f + 0.25f * FMath::Sin(T * 3.f);
			Slant(Canvas, CX - ColW * 0.44f, Y, ColW * 0.88f, 108 * S, 14 * S, WithA(FLinearColor::White, A * 0.25f));
			Text(Canvas, TEXT("PRESS SHOOT TO JOIN"), CX, Y + 34 * S, 34 * S, WithA(FLinearColor::White, A + 0.3f), Center, true);
		}
	}
	const int32 Pads = FIRInput::Get().KnownPads().Num();
	Text(Canvas, FString::Printf(TEXT("%d gamepad%s detected · up to 8 players · 7-8 players play 4-on-4"), Pads, Pads == 1 ? TEXT("") : TEXT("s")), W * 0.5f, 880 * S, 24 * S, Dim, Center, false);
	DrawFooter(Game->Humans.Num() > 0 ? TEXT("LEFT/RIGHT pick a side · ENTER / START continue · ESC / B leave") : TEXT("Waiting for players... · ESC / B back"));
}

void AIRHUD::DrawTeamSelect(AIRGameMode* Game)
{
	Box(Canvas, 0, 0, W, H, WithA(Ink, 0.7f));
	Text(Canvas, TEXT("CHOOSE YOUR TEAMS"), W * 0.5f, 34 * S, 70 * S, FLinearColor::White, Center, true, 4 * S);
	const TArray<FIRTeamInfo>& Teams = IRRoster::Teams();
	for (int32 Side = 0; Side < 2; ++Side)
	{
		const FIRTeamInfo& TI = Teams[FMath::Clamp(Game->SelectCursor[Side], 0, Teams.Num() - 1)];
		const float CX = Side == 0 ? W * 0.27f : W * 0.73f;
		const float PW = 760 * S, PY = 140 * S, PH = 760 * S;
		Box(Canvas, CX - PW * 0.5f, PY, PW, PH, WithA(TI.Primary, 0.88f));
		Gradient(Canvas, CX - PW * 0.5f, PY + PH * 0.45f, PW, PH * 0.55f, WithA(Ink, 0.f), WithA(Ink, 0.9f));
		Box(Canvas, CX - PW * 0.5f, PY, PW, 10 * S, TI.Secondary);
		Text(Canvas, Side == 0 ? TEXT("HOME") : TEXT("AWAY"), CX - PW * 0.5f + 20 * S, PY + 20 * S, 32 * S, TI.Trim, Left, true, 2 * S);
		DrawTeamBadge(TI, CX, PY + 200 * S, 250 * S);
		Text(Canvas, TI.City.ToUpper(), CX, PY + 340 * S, 40 * S, FLinearColor::White, Center, true, 0.f, Ink, 2 * S);
		Text(Canvas, TI.Name.ToUpper(), CX, PY + 380 * S, 86 * S, FLinearColor::White, Center, true, 4 * S);
		for (int32 i = 0; i < 5; ++i)
		{
			Star(Canvas, CX + (i - 2) * 44 * S, PY + 500 * S, 18 * S, i < FMath::Min(TI.Stars, 5) ? Gold : WithA(Ink, 0.6f));
		}
		Text(Canvas, FString::Printf(TEXT("STARS: %s #%d · %s #%d"), *TI.Skaters[0].Last.ToUpper(), TI.Skaters[0].Number, *TI.Skaters[1].Last.ToUpper(), TI.Skaters[1].Number), CX, PY + 528 * S, 22 * S, FLinearColor::White, Center, false, 2 * S);
		// team ratings averaged over the roster
		float Avg[5] = { 0, 0, 0, 0, 0 };
		for (const FIRPlayerInfo& P : TI.Skaters)
		{
			Avg[0] += P.R.Speed; Avg[1] += P.R.Shot; Avg[2] += P.R.Check; Avg[3] += P.R.Hands;
		}
		for (int32 i = 0; i < 4; ++i) { Avg[i] /= IR_ROSTER_SKATERS; }
		Avg[4] = TI.Goalie.R.Goalie;
		static const TCHAR* Lbl[] = { TEXT("SPEED"), TEXT("SHOOTING"), TEXT("CHECKING"), TEXT("HANDS"), TEXT("GOALIE") };
		for (int32 i = 0; i < 5; ++i)
		{
			const float Y = PY + 568 * S + i * 36 * S;
			Text(Canvas, Lbl[i], CX - 300 * S, Y, 26 * S, Dim, Left, false);
			Box(Canvas, CX - 120 * S, Y + 8 * S, 400 * S, 16 * S, WithA(Ink, 0.8f));
			Box(Canvas, CX - 120 * S, Y + 8 * S, 400 * S * Avg[i] / 10.f, 16 * S, FLinearColor::LerpUsingHSV(Ice, Hot, Avg[i] / 10.f));
		}
		if (Game->bSideLocked[Side])
		{
			Slant(Canvas, CX - 170 * S, PY + PH + 20 * S, 340 * S, 60 * S, 16 * S, Gold);
			Text(Canvas, TEXT("READY!"), CX, PY + PH + 26 * S, 46 * S, Ink, Center, true);
		}
		else
		{
			Text(Canvas, TEXT("<"), CX - PW * 0.5f - 40 * S, PY + 330 * S, 90 * S, WithA(FLinearColor::White, 0.6f + 0.4f * FMath::Sin(T * 5.f)), Center, true);
			Text(Canvas, TEXT(">"), CX + PW * 0.5f + 40 * S, PY + 330 * S, 90 * S, WithA(FLinearColor::White, 0.6f + 0.4f * FMath::Sin(T * 5.f)), Center, true);
		}
		// who is on this side
		FString Who;
		for (int32 h = 0; h < Game->Humans.Num(); ++h) { if (Game->Humans[h].Team == Side) { Who += FString::Printf(TEXT("P%d "), h + 1); } }
		Text(Canvas, Who.IsEmpty() ? TEXT("CPU") : Who, CX + PW * 0.5f - 20 * S, PY + 20 * S, 32 * S, FLinearColor::White, Right, true, 2 * S);
	}
	Text(Canvas, TEXT("VS"), W * 0.5f, H * 0.42f, 120 * S, Hot, Center, true, 0.f, Ink, 6 * S);
	DrawFooter(TEXT("LEFT/RIGHT change team · SHOOT / ENTER lock in · ESC / B back"));
}

void AIRHUD::DrawOptions(AIRGameMode* Game)
{
	Box(Canvas, 0, 0, W, H, WithA(Ink, 0.86f));
	Text(Canvas, TEXT("OPTIONS"), W * 0.5f, 40 * S, 80 * S, FLinearColor::White, Center, true, 4 * S);
	const FIRGameOptions& O = Game->Opt;
	static const TCHAR* Tabs[] = { TEXT("GAME"), TEXT("AUDIO"), TEXT("VIDEO") };
	const float X0 = W * 0.5f - 520 * S;
	for (int32 i = 0; i < 3; ++i)
	{
		const bool bSel = Game->OptionsTab == i;
		Slant(Canvas, X0 + i * 360 * S, 150 * S, 330 * S, 56 * S, 14 * S, bSel ? WithA(Hot, Game->MenuIndex == 0 ? 1.f : 0.75f) : WithA(Ink, 0.8f));
		Text(Canvas, Tabs[i], X0 + i * 360 * S + 165 * S, 156 * S, 42 * S, FLinearColor::White, Center, true);
	}
	if (Game->MenuIndex == 0) { Text(Canvas, TEXT("< LEFT / RIGHT >"), W * 0.5f, 214 * S, 22 * S, Gold, Center, false); }
	auto OnOff = [](bool b) { return FString(b ? TEXT("ON") : TEXT("OFF")); };
	TArray<TPair<FString, FString>> Rows;
	const bool bInMatch = Game->Mode != EIRMode::Attract;
	if (Game->OptionsTab == 0)
	{
		static const TCHAR* Diff[] = { TEXT("VERY EASY"), TEXT("EASY"), TEXT("MEDIUM"), TEXT("HARD"), TEXT("VERY HARD") };
		Rows.Add({ TEXT("PERIOD LENGTH"), ClockStr(O.PeriodSeconds) });
		Rows.Add({ TEXT("TEAM SIZE"), FString::Printf(TEXT("%d ON %d"), O.TeamSize, O.TeamSize) });
		Rows.Add({ TEXT("RULES"), O.Rules == EIRRules::Arcade ? TEXT("ARCADE (NO RULES)") : TEXT("PRO") });
		Rows.Add({ TEXT("DIFFICULTY"), Diff[O.Difficulty] });
		Rows.Add({ TEXT("FIGHTING"), OnOff(O.bFighting) });
		Rows.Add({ TEXT("PUCK STREAK"), OnOff(O.bPuckStreak) });
		Rows.Add({ TEXT("CATCH-UP"), OnOff(O.bCatchUp) });
		Rows.Add({ TEXT("AUTO SWITCH"), OnOff(O.bAutoSwitch) });
		Rows.Add({ TEXT("GOAL REPLAYS"), OnOff(O.bReplays) });
		Rows.Add({ TEXT("CAMERA"), CameraName(O.Camera) });
	}
	else if (Game->OptionsTab == 1)
	{
		auto Pct = [](float V) { return FString::Printf(TEXT("%d%%"), FMath::RoundToInt(V * 100.f)); };
		Rows.Add({ TEXT("MASTER"), Pct(O.MasterVol) });
		Rows.Add({ TEXT("MUSIC"), Pct(O.MusicVol) });
		Rows.Add({ TEXT("EFFECTS"), Pct(O.SfxVol) });
		Rows.Add({ TEXT("CROWD"), Pct(O.CrowdVol) });
		Rows.Add({ TEXT("ANNOUNCER"), Pct(O.VoiceVol) });
	}
	else
	{
		static const TCHAR* Q[] = { TEXT("PERFORMANCE"), TEXT("BALANCED"), TEXT("HIGH"), TEXT("ULTRA") };
		Rows.Add({ TEXT("QUALITY"), Q[O.Quality] });
		Rows.Add({ TEXT("FPS METER"), OnOff(O.bShowFps) });
	}
	for (int32 i = 0; i < Rows.Num(); ++i)
	{
		const bool bLockedRow = bInMatch && Game->OptionsTab == 0 && i <= 2;
		DrawMenuItem(Rows[i].Key, W * 0.5f - 520 * S, 250 * S + i * 66 * S, 1040 * S, Game->MenuIndex == i + 1, Rows[i].Value, !bLockedRow);
	}
	if (Game->OptionsTab == 1)
	{
		for (int32 i = 0; i < 5; ++i)
		{
			const float* V[] = { &O.MasterVol, &O.MusicVol, &O.SfxVol, &O.CrowdVol, &O.VoiceVol };
			Box(Canvas, W * 0.5f - 40 * S, 250 * S + i * 66 * S + 44 * S, 300 * S * *V[i], 5 * S, Ice);
		}
	}
	Text(Canvas, TEXT("secret codes work on the menus... try typing a few words"), W * 0.5f, H - 110 * S, 22 * S, WithA(Dim, 0.5f), Center, false);
	DrawFooter(TEXT("UP/DOWN select · LEFT/RIGHT change · ESC / B save and back"));
}

void AIRHUD::DrawControls(AIRGameMode* Game)
{
	Box(Canvas, 0, 0, W, H, WithA(Ink, 0.88f));
	Text(Canvas, TEXT("CONTROLS"), W * 0.5f, 34 * S, 80 * S, FLinearColor::White, Center, true, 4 * S);
	struct FRow { const TCHAR* Action; const TCHAR* Pad; const TCHAR* K1; const TCHAR* K2; };
	static const FRow Rows[] = {
		{ TEXT("SKATE"), TEXT("LEFT STICK / D-PAD"), TEXT("W A S D"), TEXT("ARROWS") },
		{ TEXT("SHOOT (tap wrist / hold slap) · CHECK"), TEXT("A"), TEXT("J / SPACE"), TEXT(",") },
		{ TEXT("PASS · POKE CHECK"), TEXT("X"), TEXT("K"), TEXT(".") },
		{ TEXT("TURBO"), TEXT("RT / RB / LT"), TEXT("L / L-SHIFT"), TEXT("/ · R-SHIFT") },
		{ TEXT("SWITCH PLAYER · DEKE SPIN"), TEXT("B"), TEXT("I"), TEXT(";") },
		{ TEXT("HOOK · DROP PASS"), TEXT("Y / LB"), TEXT("U"), TEXT("'") },
		{ TEXT("CAMERA"), TEXT("BACK / VIEW"), TEXT("C"), TEXT("-") },
		{ TEXT("PAUSE"), TEXT("START"), TEXT("ESC"), TEXT("P") },
	};
	const float X0 = W * 0.5f - 820 * S;
	const float Cols[] = { 0.f, 720.f, 1060.f, 1360.f };
	static const TCHAR* Head[] = { TEXT("ACTION"), TEXT("GAMEPAD"), TEXT("KEYBOARD P1"), TEXT("KEYBOARD P2") };
	for (int32 c = 0; c < 4; ++c) { Text(Canvas, Head[c], X0 + Cols[c] * S, 150 * S, 30 * S, Gold, Left, true); }
	for (int32 r = 0; r < UE_ARRAY_COUNT(Rows); ++r)
	{
		const float Y = 200 * S + r * 56 * S;
		Box(Canvas, X0 - 20 * S, Y - 6 * S, 1680 * S, 50 * S, WithA(r % 2 ? Ink : FLinearColor(0.05f, 0.07f, 0.12f), 0.8f));
		Text(Canvas, Rows[r].Action, X0 + Cols[0] * S, Y, 28 * S, FLinearColor::White, Left, false);
		Text(Canvas, Rows[r].Pad, X0 + Cols[1] * S, Y, 28 * S, Ice, Left, false);
		Text(Canvas, Rows[r].K1, X0 + Cols[2] * S, Y, 28 * S, Ice, Left, false);
		Text(Canvas, Rows[r].K2, X0 + Cols[3] * S, Y, 28 * S, Ice, Left, false);
	}
	static const TCHAR* Combos[] = {
		TEXT("POWER SHOT: SHOOT + TURBO (half a turbo meter) - the puck catches fire"),
		TEXT("ONE-TIMER: hold SHOOT while a pass is on its way · GIVE-AND-GO: SHOOT + PASS together"),
		TEXT("POWER CHECK: TURBO + SHOOT on defense · DIVE: TURBO + PASS · TRIP: TURBO + HOOK"),
		TEXT("CPU teammate has the puck? PASS calls for it, SHOOT tells him to fire"),
		TEXT("FIGHTS: SHOOT punch · PASS jab · HOOK grab · TURBO+SHOOT uppercut · SWITCH block"),
	};
	for (int32 i = 0; i < 5; ++i) { Text(Canvas, Combos[i], W * 0.5f, 690 * S + i * 46 * S, 26 * S, i == 0 ? Hot : Dim, Center, false); }
	DrawFooter(TEXT("ESC / B back"));
}

void AIRHUD::DrawPause(AIRGameMode* Game)
{
	Box(Canvas, 0, 0, W, H, WithA(Ink, 0.6f));
	DrawPanel(W * 0.5f - 380 * S, H * 0.2f, 760 * S, 600 * S, 0.92f);
	Text(Canvas, TEXT("PAUSED"), W * 0.5f, H * 0.2f + 26 * S, 80 * S, FLinearColor::White, Center, true, 4 * S);
	const FString Items[] = { TEXT("RESUME"), FString::Printf(TEXT("CAMERA: %s"), *CameraName(Game->Opt.Camera)), TEXT("OPTIONS"), TEXT("RESTART MATCH"), TEXT("QUIT TO MENU") };
	for (int32 i = 0; i < 5; ++i)
	{
		DrawMenuItem(Items[i], W * 0.5f - 300 * S, H * 0.2f + 150 * S + i * 72 * S, 600 * S, Game->MenuIndex == i);
	}
	Text(Canvas, FString::Printf(TEXT("%s %d - %d %s   ·   %s   ·   %s"), *Game->TeamInfo[0].Abbrev, Game->Score[0], Game->Score[1], *Game->TeamInfo[1].Abbrev,
		Game->bOvertime ? TEXT("OT") : *FString::Printf(TEXT("P%d"), Game->Period), *ClockStr(Game->Clock)), W * 0.5f, H * 0.2f + 540 * S, 30 * S, Gold, Center, true);
}

void AIRHUD::DrawIntermission(AIRGameMode* Game, bool bFinal)
{
	Box(Canvas, 0, 0, W, H, WithA(Ink, bFinal ? 0.55f : 0.8f));
	const int32 Win = Game->Score[0] > Game->Score[1] ? 0 : 1;
	if (bFinal && Game->Mode != EIRMode::Practice)
	{
		const FIRTeamInfo& WT = Game->TeamInfo[Win];
		const float In = EaseOutBack(FMath::Clamp(Game->ScreenTime / 0.5f, 0.f, 1.f));
		Slant(Canvas, W * 0.5f - 700 * S * In, 40 * S, 1400 * S * In, 140 * S, 30 * S, WithA(WT.Primary, 0.95f));
		Text(Canvas, FString::Printf(TEXT("%s WIN!"), *WT.Name.ToUpper()), W * 0.5f, 52 * S, 100 * S, FLinearColor::White, Center, true, 0.f, Ink, 5 * S);
	}
	else
	{
		Text(Canvas, FString::Printf(TEXT("END OF PERIOD %d"), Game->Period), W * 0.5f, 50 * S, 80 * S, FLinearColor::White, Center, true, 4 * S);
	}
	// big score
	const float Y = 220 * S;
	for (int32 t = 0; t < 2; ++t)
	{
		const FIRTeamInfo& TI = Game->TeamInfo[t];
		const float CX = t == 0 ? W * 0.3f : W * 0.7f;
		DrawTeamBadge(TI, CX, Y + 80 * S, 170 * S);
		Text(Canvas, TI.Name.ToUpper(), CX, Y + 180 * S, 44 * S, FLinearColor::White, Center, true, 2 * S);
		Text(Canvas, FString::FromInt(Game->Score[t]), t == 0 ? W * 0.43f : W * 0.57f, Y + 10 * S, 170 * S, t == Win && bFinal ? Gold : FLinearColor::White, Center, true, 0.f, Ink, 5 * S);
	}
	Text(Canvas, TEXT("-"), W * 0.5f, Y + 10 * S, 150 * S, Dim, Center, true);
	// stats table
	DrawPanel(W * 0.5f - 560 * S, 470 * S, 1120 * S, 330 * S);
	struct FStatRow { const TCHAR* Name; int32 A; int32 B; };
	const FStatRow Rows[] = {
		{ TEXT("SHOTS"), Game->TStats[0].Shots, Game->TStats[1].Shots },
		{ TEXT("HITS"), Game->TStats[0].Hits, Game->TStats[1].Hits },
		{ TEXT("FACE-OFFS WON"), Game->TStats[0].Faceoffs, Game->TStats[1].Faceoffs },
		{ TEXT("POWER SHOTS"), Game->TStats[0].PowerShots, Game->TStats[1].PowerShots },
		{ TEXT("SAVES"), Game->TStats[0].Saves, Game->TStats[1].Saves },
		{ TEXT("FIGHTS"), Game->TStats[0].Fights, Game->TStats[1].Fights },
	};
	for (int32 i = 0; i < UE_ARRAY_COUNT(Rows); ++i)
	{
		const float RY = 490 * S + i * 50 * S;
		Text(Canvas, FString::FromInt(Rows[i].A), W * 0.5f - 400 * S, RY, 36 * S, FLinearColor::White, Center, true);
		Text(Canvas, Rows[i].Name, W * 0.5f, RY + 4 * S, 28 * S, Dim, Center, false);
		Text(Canvas, FString::FromInt(Rows[i].B), W * 0.5f + 400 * S, RY, 36 * S, FLinearColor::White, Center, true);
	}
	// three stars
	TArray<AIRPlayer*> All;
	for (int32 t = 0; t < 2; ++t) { for (AIRPlayer* P : Game->TeamSkaters(t)) { All.Add(P); } if (Game->Goalies[t]) { All.Add(Game->Goalies[t]); } }
	All.Sort([](const AIRPlayer& A, const AIRPlayer& B)
	{
		auto Score = [](const AIRPlayer& P) { return P.Stats.Goals * 3.f + P.Stats.Assists * 2.f + P.Stats.Hits * 0.4f + P.Stats.Saves * 0.35f + P.Stats.FightsWon * 1.5f + P.Stats.Steals * 0.5f; };
		return Score(A) > Score(B);
	});
	Text(Canvas, bFinal ? TEXT("THREE STARS") : TEXT("TOP PERFORMERS"), W * 0.5f, 820 * S, 34 * S, Gold, Center, true, 2 * S);
	for (int32 i = 0; i < FMath::Min(3, All.Num()); ++i)
	{
		AIRPlayer* P = All[i];
		const float CX = W * (0.25f + i * 0.25f);
		const FString Line = P->IsGoalie() ? FString::Printf(TEXT("%d SAVES"), P->Stats.Saves) : FString::Printf(TEXT("%dG %dA  %d HITS"), P->Stats.Goals, P->Stats.Assists, P->Stats.Hits);
		for (int32 k = 0; k < 3 - i; ++k) { Star(Canvas, CX + (k - (2 - i) * 0.5f) * 30 * S, 852 * S, 12 * S, Gold); }
		Text(Canvas, FString::Printf(TEXT("#%d %s"), P->Info.Number, *P->Info.Last.ToUpper()), CX, 872 * S, 32 * S, Game->TeamInfo[P->Team].Primary.GetLuminance() > 0.06f ? Game->TeamInfo[P->Team].Primary : FLinearColor::White, Center, true, 2 * S);
		Text(Canvas, Line, CX, 908 * S, 24 * S, Dim, Center, false);
	}
	FString Footer = TEXT("ENTER / A continue");
	if (bFinal && Game->Mode == EIRMode::Tournament)
	{
		Footer = Game->Score[0] > Game->Score[1]
			? (Game->TournamentStage >= Game->TournamentOrder.Num() ? TEXT("CHAMPIONS! ENTER / A back to menu") : FString::Printf(TEXT("TOURNAMENT ROUND %d / %d CLEARED · ENTER / A next opponent"), Game->TournamentStage, Game->TournamentOrder.Num()))
			: FString(TEXT("You lost: rematch! ENTER / A play again"));
	}
	DrawFooter(Footer);
}

void AIRHUD::DrawCredits(AIRGameMode* Game)
{
	Box(Canvas, 0, 0, W, H, WithA(Ink, 0.86f));
	DrawLogo(W * 0.5f, 60 * S, 0.6f);
	static const TCHAR* Lines[] = {
		TEXT("AN ORIGINAL ARCADE HOCKEY GAME"),
		TEXT(""),
		TEXT("Inspired by the 3D arcade hockey cabinets of the mid-90s and their console ports"),
		TEXT("Every model, texture and animation generated procedurally in Blender"),
		TEXT("Every sound, song and announcer line synthesized from scratch"),
		TEXT("Gameplay in C++ on Unreal Engine · Web build via Unreal's WebAssembly/WebGPU export"),
		TEXT(""),
		TEXT("All teams, players, logos and sponsors are fictional"),
		TEXT("Open source on GitHub"),
	};
	for (int32 i = 0; i < UE_ARRAY_COUNT(Lines); ++i)
	{
		Text(Canvas, Lines[i], W * 0.5f, 380 * S + i * 52 * S, i == 0 ? 40 * S : 28 * S, i == 0 ? Gold : FLinearColor::White, Center, i == 0, 2 * S);
	}
	DrawFooter(TEXT("ESC / B back"));
}
