#include "IRArena.h"
#include "IRGameMode.h"
#include "IRAssets.h"
#include "IRDraw.h"
#include "IRRink.h"
#include "IRAudio.h"
#include "Components/StaticMeshComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/SpotLightComponent.h"
#include "Components/PostProcessComponent.h"
#include "Engine/CanvasRenderTarget2D.h"
#include "Engine/Canvas.h"
#include "Engine/StaticMesh.h"
#include "Engine/Texture2D.h"
#include "Materials/MaterialInstanceDynamic.h"

using namespace IRRink;

AIRArena::AIRArena()
{
	PrimaryActorTick.bCanEverTick = false;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
}

UStaticMeshComponent* AIRArena::AddMesh(UStaticMesh* M, const FTransform& X, bool bShadow)
{
	if (!M)
	{
		return nullptr;
	}
	UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
	C->SetStaticMesh(M);
	C->SetupAttachment(RootComponent);
	C->SetRelativeTransform(X);
	C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	C->CastShadow = bShadow;
	C->RegisterComponent();
	Parts.Add(C);
	return C;
}

void AIRArena::Build(AIRGameMode* InGame)
{
	Game = InGame;
	UIRAssets* AS = UIRAssets::Get();

	// ---------------------------------------------------------------- lighting
	Sun = NewObject<UDirectionalLightComponent>(this);
	Sun->SetupAttachment(RootComponent);
	Sun->SetRelativeRotation(FRotator(-62.f, 35.f, 0.f));
	Sun->SetIntensity(4.2f);
	Sun->SetLightColor(FLinearColor(1.f, 0.97f, 0.93f));
	Sun->SetCastShadows(true);
	Sun->LightSourceAngle = 6.f;
	Sun->SetDynamicShadowCascades(3);
	Sun->SetDynamicShadowDistanceMovableLight(9000.f);
	Sun->RegisterComponent();

	Sky = NewObject<USkyLightComponent>(this);
	Sky->SetupAttachment(RootComponent);
	Sky->SourceType = ESkyLightSourceType::SLS_CapturedScene;
	Sky->SetIntensity(1.6f);
	Sky->bRealTimeCapture = false;
	Sky->SetLowerHemisphereColor(FLinearColor(0.35f, 0.4f, 0.48f));
	Sky->bLowerHemisphereIsBlack = false;
	Sky->RegisterComponent();

	// arena light banks over the ice (give the glossy ice its long highlights)
	for (int32 i = 0; i < 6; ++i)
	{
		USpotLightComponent* S = NewObject<USpotLightComponent>(this);
		S->SetupAttachment(RootComponent);
		const float X = (i % 3 - 1) * 1500.f;
		const float Y = (i < 3 ? -1.f : 1.f) * 500.f;
		S->SetRelativeLocation(FVector(X, Y, 2400.f));
		S->SetRelativeRotation(FRotator(-90.f, 0.f, 0.f));
		S->SetIntensityUnits(ELightUnits::Candelas);
		S->SetIntensity(5200.f);
		S->SetAttenuationRadius(5000.f);
		S->SetOuterConeAngle(42.f);
		S->SetInnerConeAngle(20.f);
		S->SetCastShadows(false);
		S->SetLightColor(FLinearColor(1.f, 0.98f, 0.95f));
		S->RegisterComponent();
		Spots.Add(S);
	}
	// intro / goal sweeping spotlights
	for (int32 i = 0; i < 4; ++i)
	{
		USpotLightComponent* S = NewObject<USpotLightComponent>(this);
		S->SetupAttachment(RootComponent);
		S->SetRelativeLocation(FVector((i - 1.5f) * 900.f, -2200.f, 2100.f));
		S->SetIntensityUnits(ELightUnits::Candelas);
		S->SetIntensity(0.f);
		S->SetAttenuationRadius(6000.f);
		S->SetOuterConeAngle(9.f);
		S->SetInnerConeAngle(5.f);
		S->SetCastShadows(false);
		S->SetLightColor(i % 2 ? FLinearColor(0.6f, 0.8f, 1.f) : FLinearColor(1.f, 0.85f, 0.6f));
		S->RegisterComponent();
		IntroSpots.Add(S);
	}

	Post = NewObject<UPostProcessComponent>(this);
	Post->SetupAttachment(RootComponent);
	Post->bUnbound = true;
	FPostProcessSettings& PP = Post->Settings;
	PP.bOverride_AutoExposureMethod = true;
	PP.AutoExposureMethod = EAutoExposureMethod::AEM_Manual;
	PP.bOverride_AutoExposureBias = true;
	PP.AutoExposureBias = 9.6f;
	PP.bOverride_BloomIntensity = true;
	PP.BloomIntensity = 0.55f;
	PP.bOverride_BloomThreshold = true;
	PP.BloomThreshold = 1.2f;
	PP.bOverride_VignetteIntensity = true;
	PP.VignetteIntensity = 0.32f;
	PP.bOverride_ColorSaturation = true;
	PP.ColorSaturation = FVector4(1.12f, 1.12f, 1.12f, 1.f);
	PP.bOverride_ColorContrast = true;
	PP.ColorContrast = FVector4(1.06f, 1.06f, 1.06f, 1.f);
	PP.bOverride_SceneFringeIntensity = true;
	PP.SceneFringeIntensity = 0.f;
	PP.bOverride_MotionBlurAmount = true;
	PP.MotionBlurAmount = 0.f;
	PP.bOverride_AmbientOcclusionIntensity = true;
	PP.AmbientOcclusionIntensity = 0.5f;
	Post->RegisterComponent();

	// ---------------------------------------------------------------- geometry
	UStaticMesh* IceMesh = AS->Mesh(TEXT("SM_Ice"));
	bHasArt = IceMesh != nullptr;
	if (!bHasArt)
	{
		BuildPlaceholder();
	}
	else
	{
		Ice = AddMesh(IceMesh, FTransform::Identity, false);
		if (Ice && Ice->GetMaterial(0))
		{
			IceMID = UMaterialInstanceDynamic::Create(Ice->GetMaterial(0), this);
			Ice->SetMaterial(0, IceMID);
		}
		AddMesh(AS->Mesh(TEXT("SM_Boards")), FTransform::Identity);
		Glass = AddMesh(AS->Mesh(TEXT("SM_Glass")), FTransform::Identity, false);
		AddMesh(AS->Mesh(TEXT("SM_Arena")), FTransform::Identity);
		Crowd = AddMesh(AS->Mesh(TEXT("SM_Crowd")), FTransform::Identity, false);
		if (Crowd && Crowd->GetMaterial(0))
		{
			CrowdMID = UMaterialInstanceDynamic::Create(Crowd->GetMaterial(0), this);
			for (int32 i = 0; i < Crowd->GetNumMaterials(); ++i)
			{
				Crowd->SetMaterial(i, CrowdMID);
			}
		}
		Jumbo = AddMesh(AS->Mesh(TEXT("SM_Jumbotron")), FTransform::Identity);
	}
	// nets (+X mesh; mirrored for -X)
	UStaticMesh* NetMesh = AS->Mesh(TEXT("SM_Net"));
	for (int32 i = 0; i < 2; ++i)
	{
		const float Sign = i == 0 ? 1.f : -1.f;
		FTransform X(FRotator(0.f, i == 0 ? 0.f : 180.f, 0.f), FVector::ZeroVector);
		if (NetMesh)
		{
			Nets[i] = AddMesh(NetMesh, X);
		}
		else
		{
			// placeholder net: posts + crossbar + back
			auto Box = [&](FVector C, FVector E, FLinearColor Col)
			{
				UStaticMeshComponent* B = AddMesh(AS->EngineShape(TEXT("Cube")), FTransform(FRotator::ZeroRotator, C, E / 50.f));
				UMaterialInstanceDynamic* M = UMaterialInstanceDynamic::Create(AS->BasicMaterial(), this);
				M->SetVectorParameterValue(TEXT("Color"), Col);
				B->SetMaterial(0, M);
			};
			const FLinearColor Red(0.8f, 0.02f, 0.02f), White(0.9f, 0.9f, 0.9f);
			Box(FVector(GoalLineX * Sign, NetHalfWidth + 3.f, 61.f), FVector(3.f, 3.f, 61.f), Red);
			Box(FVector(GoalLineX * Sign, -NetHalfWidth - 3.f, 61.f), FVector(3.f, 3.f, 61.f), Red);
			Box(FVector(GoalLineX * Sign, 0.f, 125.f), FVector(3.f, NetHalfWidth + 6.f, 3.f), Red);
			Box(FVector((GoalLineX + NetDepth) * Sign, 0.f, 40.f), FVector(2.f, NetHalfWidth, 40.f), White);
		}
		if (UStaticMesh* GL = AS->Mesh(TEXT("SM_GoalLight")))
		{
			GoalLights[i] = AddMesh(GL, X);
			if (GoalLights[i] && GoalLights[i]->GetMaterial(0))
			{
				GoalLightMID[i] = UMaterialInstanceDynamic::Create(GoalLights[i]->GetMaterial(0), this);
				GoalLights[i]->SetMaterial(0, GoalLightMID[i]);
			}
		}
	}

	// jumbotron screen render target
	if (Jumbo)
	{
		JumboRT = UCanvasRenderTarget2D::CreateCanvasRenderTarget2D(this, UCanvasRenderTarget2D::StaticClass(), 1024, 512);
		if (JumboRT)
		{
			JumboRT->OnCanvasRenderTargetUpdate.AddDynamic(this, &AIRArena::DrawJumbo);
			JumboRT->ClearColor = FLinearColor::Black;
			for (int32 i = 0; i < Jumbo->GetNumMaterials(); ++i)
			{
				UMaterialInterface* M = Jumbo->GetMaterial(i);
				if (M && M->GetName().Contains(TEXT("Jumbo")))
				{
					JumboMID = UMaterialInstanceDynamic::Create(M, this);
					JumboMID->SetTextureParameterValue(TEXT("Screen"), JumboRT);
					Jumbo->SetMaterial(i, JumboMID);
				}
			}
		}
	}
	if (Sky)
	{
		Sky->RecaptureSky();
	}
}

void AIRArena::BuildPlaceholder()
{
	UIRAssets* AS = UIRAssets::Get();
	auto Box = [&](FVector C, FVector E, FLinearColor Col, bool bShadow = true)
	{
		UStaticMeshComponent* B = AddMesh(AS->EngineShape(TEXT("Cube")), FTransform(FRotator::ZeroRotator, C, E / 50.f), bShadow);
		UMaterialInstanceDynamic* M = UMaterialInstanceDynamic::Create(AS->BasicMaterial(), this);
		M->SetVectorParameterValue(TEXT("Color"), Col);
		B->SetMaterial(0, M);
		return B;
	};
	// ice slab
	Ice = Box(FVector(0, 0, -5.f), FVector(HalfLength, HalfWidth, 5.f), FLinearColor(0.85f, 0.9f, 0.95f), false);
	// lines
	const FLinearColor Red(0.7f, 0.02f, 0.02f), Blue(0.02f, 0.1f, 0.6f);
	Box(FVector(0, 0, 0.2f), FVector(15.f, HalfWidth - 40.f, 0.2f), Red, false);
	Box(FVector(BlueLineX, 0, 0.2f), FVector(15.f, HalfWidth - 10.f, 0.2f), Blue, false);
	Box(FVector(-BlueLineX, 0, 0.2f), FVector(15.f, HalfWidth - 10.f, 0.2f), Blue, false);
	Box(FVector(GoalLineX, 0, 0.2f), FVector(2.5f, HalfWidth - 300.f, 0.2f), Red, false);
	Box(FVector(-GoalLineX, 0, 0.2f), FVector(2.5f, HalfWidth - 300.f, 0.2f), Red, false);
	// boards (straight sections; corners approximated with angled boxes)
	const FLinearColor W(0.9f, 0.9f, 0.9f);
	Box(FVector(0, HalfWidth + 8.f, 53.f), FVector(HalfLength - CornerRadius, 8.f, 53.f), W);
	Box(FVector(0, -HalfWidth - 8.f, 53.f), FVector(HalfLength - CornerRadius, 8.f, 53.f), W);
	Box(FVector(HalfLength + 8.f, 0, 53.f), FVector(8.f, HalfWidth - CornerRadius, 53.f), W);
	Box(FVector(-HalfLength - 8.f, 0, 53.f), FVector(8.f, HalfWidth - CornerRadius, 53.f), W);
	for (int32 sx = -1; sx <= 1; sx += 2)
	{
		for (int32 sy = -1; sy <= 1; sy += 2)
		{
			for (int32 k = 0; k < 6; ++k)
			{
				const float A = (k + 0.5f) / 6.f * PI * 0.5f;
				const FVector C((HalfLength - CornerRadius + FMath::Sin(A) * (CornerRadius + 8.f)) * sx, (HalfWidth - CornerRadius + FMath::Cos(A) * (CornerRadius + 8.f)) * sy, 53.f);
				UStaticMeshComponent* B = Box(C, FVector(8.f, CornerRadius * 0.14f, 53.f), W);
				B->SetRelativeRotation(FRotator(0.f, FMath::RadiansToDegrees(PI * 0.5f - A) * sx * sy + 90.f, 0.f));
			}
		}
	}
	// a dark floor around the rink
	Box(FVector(0, 0, -30.f), FVector(6000.f, 6000.f, 10.f), FLinearColor(0.03f, 0.03f, 0.04f), false);
}

void AIRArena::ApplyQuality(int32 Q)
{
	if (Sun)
	{
		Sun->SetCastShadows(Q >= 1);
		Sun->SetDynamicShadowCascades(Q >= 2 ? 3 : 1);
	}
	if (Post)
	{
		Post->Settings.AmbientOcclusionIntensity = Q >= 2 ? 0.5f : 0.f;
		Post->Settings.BloomIntensity = Q >= 1 ? 0.55f : 0.f;
	}
}

void AIRArena::SetGoalLight(int32 Sign, bool bOn)
{
	const int32 I = Sign > 0 ? 0 : 1;
	if (GoalLightMID[I])
	{
		GoalLightMID[I]->SetScalarParameterValue(TEXT("On"), bOn ? 1.f : 0.f);
	}
}

void AIRArena::SetIntroLights(bool bOn)
{
	bIntro = bOn;
}

void AIRArena::Tick2(float Dt)
{
	T += Dt;
	GlassShake = FMath::Max(0.f, GlassShake - Dt * 2.f);
	if (CrowdMID && Game && Game->Audio)
	{
		CrowdMID->SetScalarParameterValue(TEXT("Excitement"), FMath::Clamp(0.15f + Game->Audio->Excite, 0.f, 1.f));
	}
	if (Glass && GlassShake > 0.01f)
	{
		Glass->SetRelativeLocation(FVector(FMath::Sin(T * 90.f) * 1.5f * GlassShake, FMath::Cos(T * 77.f) * 1.5f * GlassShake, 0.f));
	}
	else if (Glass)
	{
		Glass->SetRelativeLocation(FVector::ZeroVector);
	}
	// sweeping spotlights during the intro and after goals
	const bool bSweep = bIntro || (Game && Game->Phase == EIRMatchPhase::Goal);
	for (int32 i = 0; i < IntroSpots.Num(); ++i)
	{
		USpotLightComponent* S = IntroSpots[i];
		const float Target = bSweep ? 80000.f : 0.f;
		S->SetIntensity(FMath::FInterpTo(S->Intensity, Target, Dt, 3.f));
		const FVector Aim(FMath::Sin(T * (0.6f + i * 0.13f) + i) * 1600.f, FMath::Cos(T * (0.5f + i * 0.11f) + i * 2.f) * 700.f, 0.f);
		S->SetWorldRotation((Aim - S->GetComponentLocation()).Rotation());
	}
	if (Spots.Num() && Game)
	{
		const float Dim = bIntro ? 0.25f : 1.f;
		for (USpotLightComponent* S : Spots)
		{
			S->SetIntensity(FMath::FInterpTo(S->Intensity, 5200.f * Dim, Dt, 2.f));
		}
		if (Sun) { Sun->SetIntensity(FMath::FInterpTo(Sun->Intensity, 4.2f * (bIntro ? 0.35f : 1.f), Dt, 2.f)); }
	}
	if (IceMID && Game)
	{
		IceMID->SetScalarParameterValue(TEXT("Wear"), FMath::Clamp((Game->Period - 1) * 0.3f + (1.f - Game->Clock / FMath::Max(1.f, float(Game->Opt.PeriodSeconds))) * 0.3f, 0.f, 1.f));
	}
	JumboTimer -= Dt;
	if (JumboRT && JumboTimer <= 0.f)
	{
		JumboTimer = 0.1f;
		JumboRT->UpdateResource();
	}
}

void AIRArena::DrawJumbo(UCanvas* Canvas, int32 W, int32 H)
{
	if (!Game)
	{
		return;
	}
	IRDraw::Gradient(Canvas, 0, 0, W, H, FLinearColor(0.02f, 0.03f, 0.08f), FLinearColor(0.0f, 0.0f, 0.02f));
	const bool bGoal = Game->Phase == EIRMatchPhase::Goal;
	if (bGoal && FMath::Fmod(T, 0.5f) < 0.3f)
	{
		const FLinearColor C = Game->LastGoalTeam >= 0 ? Game->TeamInfo[Game->LastGoalTeam].Primary : FLinearColor::Red;
		IRDraw::Box(Canvas, 0, 0, W, H, C * 0.8f);
		IRDraw::Text(Canvas, TEXT("GOAL!"), W * 0.5f, H * 0.18f, 230.f, FLinearColor::White, IRDraw::Center, true, 6.f);
		return;
	}
	if (Game->Phase == EIRMatchPhase::Replay)
	{
		IRDraw::Text(Canvas, TEXT("REPLAY"), W * 0.5f, H * 0.3f, 150.f, FLinearColor(1.f, 0.85f, 0.2f), IRDraw::Center, true, 5.f);
		return;
	}
	if (Game->Phase == EIRMatchPhase::Fight)
	{
		IRDraw::Text(Canvas, TEXT("FIGHT!"), W * 0.5f, H * 0.25f, 190.f, FLinearColor(1.f, 0.2f, 0.1f), IRDraw::Center, true, 5.f);
		return;
	}
	if (Game->Screen == EIRScreen::Title || Game->Screen == EIRScreen::MainMenu || Game->Phase == EIRMatchPhase::None)
	{
		IRDraw::Text(Canvas, TEXT("ICE RIOT"), W * 0.5f, H * 0.22f, 200.f, FLinearColor(0.3f, 0.8f, 1.f), IRDraw::Center, true, 5.f);
		return;
	}
	for (int32 t = 0; t < 2; ++t)
	{
		const float X = t == 0 ? W * 0.25f : W * 0.75f;
		IRDraw::Box(Canvas, X - 230.f, 30.f, 460.f, 90.f, Game->TeamInfo[t].Primary);
		IRDraw::Text(Canvas, Game->TeamInfo[t].Abbrev, X, 34.f, 86.f, FLinearColor::White, IRDraw::Center, true, 3.f);
		IRDraw::Text(Canvas, FString::FromInt(Game->Score[t]), X, 140.f, 230.f, FLinearColor(1.f, 0.85f, 0.15f), IRDraw::Center, true, 5.f);
	}
	const int32 Secs = FMath::CeilToInt(FMath::Max(0.f, Game->Clock));
	const FString Clock = FString::Printf(TEXT("%d:%02d"), Secs / 60, Secs % 60);
	IRDraw::Text(Canvas, Clock, W * 0.5f, 380.f, 110.f, FLinearColor(1.f, 0.3f, 0.2f), IRDraw::Center, true, 4.f);
	IRDraw::Text(Canvas, Game->bOvertime ? TEXT("OT") : FString::Printf(TEXT("P%d"), Game->Period), W * 0.5f, 60.f, 90.f, FLinearColor::White, IRDraw::Center, true, 3.f);
}
