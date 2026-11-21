#include "IRCamera.h"
#include "IRGameMode.h"
#include "IRPlayer.h"
#include "IRPuck.h"
#include "IRRink.h"
#include "Camera/CameraComponent.h"

AIRCamera::AIRCamera()
{
	PrimaryActorTick.bCanEverTick = false;
	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
	RootComponent = Camera;
	Camera->SetFieldOfView(52.f);
	Camera->bConstrainAspectRatio = false;
	Camera->PostProcessSettings.bOverride_MotionBlurAmount = true;
	Camera->PostProcessSettings.MotionBlurAmount = 0.f;
}

void AIRCamera::Init(AIRGameMode* InGame)
{
	Game = InGame;
}

void AIRCamera::SetShot(EIRShot S, float BlendTime)
{
	if (S == Shot && BlendTime > 0.f)
	{
		return;
	}
	Shot = S;
	ShotTime = 0.f;
	Blend = BlendTime > 0.f ? 0.f : 1.f;
	BlendSpeed = BlendTime > 0.f ? 1.f / BlendTime : 100.f;
	if (S == EIRShot::Replay)
	{
		ReplayAngle = (ReplayAngle + 1) % 3;
	}
}

void AIRCamera::Cut()
{
	Blend = 1.f;
	FVector L; FRotator R; float F;
	if (Shot == EIRShot::Game) { ComputeGame(0.f, L, R, F); }
	else { ComputeShot(0.f, L, R, F); }
	CurLoc = L; CurRot = R; CurFov = F;
}

FVector AIRCamera::GetCamLocation() const
{
	return Camera ? Camera->GetComponentLocation() : CurLoc;
}

FVector2D AIRCamera::ScreenToWorld(const FVector2D& Stick) const
{
	const FRotator R = Camera ? Camera->GetComponentRotation() : CurRot;
	FVector2D F(FMath::Cos(FMath::DegreesToRadians(R.Yaw)), FMath::Sin(FMath::DegreesToRadians(R.Yaw)));
	const FVector2D Rt(-F.Y, F.X);
	return Rt * Stick.X + F * Stick.Y;
}

static FVector2D PuckFocus(AIRGameMode* G)
{
	if (!G || !G->Puck)
	{
		return FVector2D::ZeroVector;
	}
	FVector2D P(G->Puck->Pos.X, G->Puck->Pos.Y);
	if (AIRPlayer* C = G->PuckCarrier())
	{
		P = C->Pos + C->Vel * 0.35f;
	}
	else
	{
		P += FVector2D(G->Puck->Vel.X, G->Puck->Vel.Y) * 0.18f;
	}
	return P;
}

void AIRCamera::ComputeGame(float Dt, FVector& OutLoc, FRotator& OutRot, float& OutFov)
{
	const FVector2D Target = PuckFocus(Game);
	// critically damped follow
	const float K = 3.2f;
	FVector2D Cur(FocusSmoothed.X, FocusSmoothed.Y);
	if (Dt > 0.f)
	{
		const FVector2D Acc = (Target - Cur) * K * K - FocusVel * 2.f * K;
		FocusVel += Acc * Dt;
		Cur += FocusVel * Dt;
	}
	else
	{
		Cur = Target;
		FocusVel = FVector2D::ZeroVector;
	}
	FocusSmoothed = FVector(Cur, 0.f);

	// zoom out when the action is spread
	float Spread = 0.f;
	if (Game)
	{
		for (AIRPlayer* P : Game->AllPlayers())
		{
			if (P && !P->IsGoalie() && !P->IsReferee())
			{
				Spread = FMath::Max(Spread, FMath::Abs(P->Pos.X - Cur.X));
			}
		}
	}
	const float WantZoom = FMath::GetMappedRangeValueClamped(FVector2D(900.f, 2200.f), FVector2D(0.92f, 1.12f), Spread);
	ZoomSmoothed = Dt > 0.f ? FMath::FInterpTo(ZoomSmoothed, WantZoom, Dt, 1.2f) : WantZoom;

	const EIRCameraMode Mode = Game ? Game->Opt.Camera : EIRCameraMode::Broadcast;
	const float Fx = FMath::Clamp(Cur.X * 0.88f, -1450.f, 1450.f);
	const float Fy = FMath::Clamp(Cur.Y, -800.f, 800.f);
	switch (Mode)
	{
	default:
	case EIRCameraMode::Broadcast:
	{
		const FVector Look(Fx, Fy * 0.45f - 60.f, 0.f);
		OutLoc = Look + FVector(0.f, 2080.f, 1150.f) * ZoomSmoothed;
		OutRot = (Look - OutLoc).Rotation();
		OutFov = 46.f;
		break;
	}
	case EIRCameraMode::HighBroadcast:
	{
		const FVector Look(Fx, Fy * 0.4f - 40.f, 0.f);
		OutLoc = Look + FVector(0.f, 1650.f, 1850.f) * ZoomSmoothed;
		OutRot = (Look - OutLoc).Rotation();
		OutFov = 52.f;
		break;
	}
	case EIRCameraMode::Overhead:
	{
		const FVector Look(FMath::Clamp(Cur.X, -1300.f, 1300.f), Fy * 0.3f, 0.f);
		OutLoc = Look + FVector(0.f, 650.f, 3000.f) * ZoomSmoothed;
		OutRot = (Look - OutLoc).Rotation();
		OutFov = 55.f;
		break;
	}
	case EIRCameraMode::EndZone:
	{
		// behind the first human's team, looking toward the net they attack
		int32 Sign = 1;
		if (Game && Game->Humans.Num() > 0) { Sign = Game->AttackSign(Game->Humans[0].Team); }
		const FVector Look(Cur.X + Sign * 500.f, Cur.Y * 0.7f, 0.f);
		OutLoc = FVector(Cur.X - Sign * 1500.f, Cur.Y * 0.5f, 900.f);
		OutRot = (Look - OutLoc).Rotation();
		OutFov = 62.f;
		break;
	}
	case EIRCameraMode::Close:
	{
		const FVector Look(Cur.X, Cur.Y * 0.8f, 0.f);
		OutLoc = Look + FVector(0.f, 1300.f, 760.f);
		OutRot = (Look - OutLoc).Rotation();
		OutFov = 50.f;
		break;
	}
	case EIRCameraMode::Blimp:
	{
		const FVector Look(Cur.X * 0.5f, 0.f, 0.f);
		OutLoc = Look + FVector(-200.f, 3400.f, 3300.f);
		OutRot = (Look - OutLoc).Rotation();
		OutFov = 48.f;
		break;
	}
	}
}

void AIRCamera::ComputeShot(float Dt, FVector& OutLoc, FRotator& OutRot, float& OutFov)
{
	const float T = ShotTime;
	switch (Shot)
	{
	case EIRShot::Title:
	case EIRShot::Menu:
	{
		// slow orbit high above the rink
		const float A = T * 0.05f + 0.6f;
		const FVector Look(0.f, 0.f, 150.f);
		OutLoc = FVector(FMath::Cos(A) * 2600.f, FMath::Sin(A) * 1900.f, 900.f + FMath::Sin(T * 0.11f) * 200.f);
		OutRot = (Look - OutLoc).Rotation();
		OutFov = 60.f;
		break;
	}
	case EIRShot::Intro:
	{
		// sweep from high over one end down to center ice
		const float U = FMath::Clamp(T / 6.f, 0.f, 1.f);
		const float E = U * U * (3.f - 2.f * U);
		const float A = FMath::Lerp(-2.2f, -PI * 0.5f, E);
		const float R = FMath::Lerp(3000.f, 2300.f, E);
		OutLoc = FVector(FMath::Cos(A) * R * 0.9f, -FMath::Sin(A) * R, FMath::Lerp(2600.f, 900.f, E));
		const FVector Look(0.f, 0.f, FMath::Lerp(400.f, 80.f, E));
		OutRot = (Look - OutLoc).Rotation();
		OutFov = FMath::Lerp(70.f, 45.f, E);
		break;
	}
	case EIRShot::Goal:
	{
		AIRPlayer* S = Game ? Game->LastScorer.Get() : nullptr;
		const FVector C = S ? FVector(S->Pos, 105.f) : (Game && Game->Puck ? Game->Puck->Pos : FVector::ZeroVector);
		// broadcast-side orbit around the scorer, pushing in slowly
		const float Push = FMath::Clamp(T / 3.f, 0.f, 1.f);
		const float Dist = FMath::Lerp(820.f, 600.f, Push);
		const float A = FMath::DegreesToRadians(FMath::Lerp(-28.f, 18.f, Push) + (C.X > 0.f ? 0.f : 0.f));
		OutLoc = C + FVector(FMath::Sin(A) * Dist, FMath::Cos(A) * Dist, FMath::Lerp(300.f, 190.f, Push));
		OutRot = (C - OutLoc).Rotation();
		OutFov = 42.f;
		break;
	}
	case EIRShot::Fight:
	{
		FVector C = FVector::ZeroVector;
		if (Game && Game->Fight.A.IsValid() && Game->Fight.B.IsValid())
		{
			C = FVector((Game->Fight.A->Pos + Game->Fight.B->Pos) * 0.5f, 110.f);
		}
		OutLoc = C + FVector(FMath::Sin(T * 0.25f) * 220.f, 560.f, 210.f);
		OutRot = (C - OutLoc).Rotation();
		OutFov = 44.f;
		break;
	}
	case EIRShot::Replay:
	{
		const FVector P = Game && Game->Puck ? Game->Puck->Pos : FVector::ZeroVector;
		const int32 Sign = Game ? (Game->GoalSignLast != 0 ? Game->GoalSignLast : 1) : 1;
		if (ReplayAngle == 0)
		{
			// behind the net, looking out at the shooter
			OutLoc = FVector((IRRink::GoalLineX + 420.f) * Sign, 120.f, 260.f);
			OutRot = (FVector(P.X, P.Y, 40.f) - OutLoc).Rotation();
			OutFov = FMath::Clamp(FVector::Dist(OutLoc, P) / 40.f, 22.f, 55.f);
		}
		else if (ReplayAngle == 1)
		{
			// low ice-level tracking from the side
			const FVector L(P.X - Sign * 380.f, P.Y + 520.f, 60.f);
			OutLoc = Dt > 0.f ? FMath::VInterpTo(CurLoc, L, Dt, 3.f) : L;
			OutRot = (P + FVector(0, 0, 30.f) - OutLoc).Rotation();
			OutFov = 50.f;
		}
		else
		{
			// high corner
			OutLoc = FVector((IRRink::GoalLineX - 600.f) * Sign, -1200.f, 900.f);
			OutRot = (FVector(P.X, P.Y, 0.f) - OutLoc).Rotation();
			OutFov = 40.f;
		}
		break;
	}
	case EIRShot::Faceoff:
	{
		const FVector C = Game ? FVector(Game->FaceoffSpot, 60.f) : FVector::ZeroVector;
		OutLoc = C + FVector(0.f, 1250.f, 700.f);
		OutRot = (C - OutLoc).Rotation();
		OutFov = 46.f;
		break;
	}
	case EIRShot::Results:
	{
		const float A = T * 0.08f;
		const FVector Look(0.f, 0.f, 200.f);
		OutLoc = FVector(FMath::Cos(A) * 1200.f, 900.f + FMath::Sin(A) * 300.f, 420.f);
		OutRot = (Look - OutLoc).Rotation();
		OutFov = 55.f;
		break;
	}
	default:
		ComputeGame(Dt, OutLoc, OutRot, OutFov);
		break;
	}
}

void AIRCamera::Tick2(float Dt)
{
	ShotTime += Dt;
	FVector L; FRotator R; float F;
	if (Shot == EIRShot::Game)
	{
		ComputeGame(Dt, L, R, F);
	}
	else
	{
		ComputeShot(Dt, L, R, F);
		// keep the game focus warm so returning to gameplay doesn't snap
		FVector GL; FRotator GR; float GF;
		ComputeGame(Dt, GL, GR, GF);
	}
	Blend = FMath::Min(1.f, Blend + Dt * BlendSpeed);
	const float A = Blend * Blend * (3.f - 2.f * Blend);
	if (A >= 1.f)
	{
		CurLoc = L; CurRot = R; CurFov = F;
	}
	else
	{
		CurLoc = FMath::Lerp(CurLoc, L, A);
		CurRot = FMath::Lerp(CurRot, R, A);
		CurFov = FMath::Lerp(CurFov, F, A);
	}
	// shake
	ShakeT += Dt;
	ShakeAmt = FMath::Max(0.f, ShakeAmt - Dt * 2.2f);
	FVector ShakeOff = FVector::ZeroVector;
	FRotator ShakeRot = FRotator::ZeroRotator;
	if (ShakeAmt > 0.f)
	{
		const float S = ShakeAmt * ShakeAmt;
		ShakeOff = FVector(FMath::PerlinNoise1D(ShakeT * 23.f), FMath::PerlinNoise1D(ShakeT * 19.f + 3.f), FMath::PerlinNoise1D(ShakeT * 29.f + 7.f)) * 26.f * S;
		ShakeRot = FRotator(FMath::PerlinNoise1D(ShakeT * 17.f + 11.f) * 1.4f * S, FMath::PerlinNoise1D(ShakeT * 21.f + 13.f) * 1.4f * S, FMath::PerlinNoise1D(ShakeT * 25.f) * 1.0f * S);
	}
	SetActorLocationAndRotation(CurLoc + ShakeOff, CurRot + ShakeRot);
	Camera->SetFieldOfView(CurFov);
}
