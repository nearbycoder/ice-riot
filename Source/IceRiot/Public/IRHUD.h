#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "IRTypes.h"
#include "IRHUD.generated.h"

class AIRGameMode;
class AIRPlayer;

UCLASS()
class ICERIOT_API AIRHUD : public AHUD
{
	GENERATED_BODY()
public:
	virtual void DrawHUD() override;
	static FString CameraName(EIRCameraMode M);

private:
	AIRGameMode* G() const;
	float S = 1.f;          // UI scale (1 at 1080p)
	float W = 1920.f, H = 1080.f;
	float T = 0.f;
	float LastRealTime = 0.f;
	float FpsAccum = 0.f; int32 FpsFrames = 0; float FpsShown = 0.f; float MsShown = 0.f;

	void DrawGameplay(AIRGameMode* Game);
	void DrawScoreboard(AIRGameMode* Game);
	void DrawPlayerMarkers(AIRGameMode* Game);
	void DrawCallouts(AIRGameMode* Game);
	void DrawFight(AIRGameMode* Game);
	void DrawAmbulance(AIRGameMode* Game);
	void DrawReplay(AIRGameMode* Game);
	void DrawFaceoffHint(AIRGameMode* Game);
	void DrawTitle(AIRGameMode* Game);
	void DrawMainMenu(AIRGameMode* Game);
	void DrawJoin(AIRGameMode* Game);
	void DrawTeamSelect(AIRGameMode* Game);
	void DrawOptions(AIRGameMode* Game);
	void DrawControls(AIRGameMode* Game);
	void DrawPause(AIRGameMode* Game);
	void DrawIntermission(AIRGameMode* Game, bool bFinal);
	void DrawCredits(AIRGameMode* Game);
	void DrawLogo(float CX, float Y, float Scale, float Alpha = 1.f);
	void DrawTeamBadge(const FIRTeamInfo& Team, float CX, float CY, float Size, float Alpha = 1.f);
	void DrawFooter(const FString& Text);
	void DrawPanel(float X, float Y, float W, float H, float Alpha = 0.78f);
	void DrawMenuItem(const FString& Label, float X, float Y, float Width, bool bSel, const FString& Value = FString(), bool bEnabled = true);
	void DrawFps(AIRGameMode* Game);
};
