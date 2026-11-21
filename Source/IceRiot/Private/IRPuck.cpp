#include "IRPuck.h"
#include "IRRink.h"
#include "IRAssets.h"
#include "IRPlayer.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"

using namespace IRRink;

AIRPuck::AIRPuck()
{
	PrimaryActorTick.bCanEverTick = false;
	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	RootComponent = Mesh;
	Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Mesh->SetMobility(EComponentMobility::Movable);
	Mesh->CastShadow = true;
	Marker = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Marker"));
	Marker->SetupAttachment(Mesh);
	Marker->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Marker->CastShadow = false;
	Marker->SetUsingAbsoluteRotation(true);
}

void AIRPuck::SetCarried(AIRPlayer* InCarrier)
{
	if (InCarrier && LastTouch != InCarrier)
	{
		if (LastTouch && LastTouch->Team == InCarrier->Team)
		{
			PrevTouch = LastTouch;
		}
		else
		{
			PrevTouch = nullptr;
		}
	}
	Carrier = InCarrier;
	if (InCarrier)
	{
		LastTouch = InCarrier;
		Kind = EIRShotKind::None;
		bFrozen = false;
		SaveGoalie = nullptr;
		bShotOnTarget = false;
		bBeatGoalie = false;
		if (!InCarrier->bBlazing)
		{
			bOnFire = false;
		}
	}
}

void AIRPuck::Release(const FVector& Velocity, EIRShotKind InKind, AIRPlayer* By)
{
	Carrier = nullptr;
	bFrozen = false;
	Vel = Velocity;
	Kind = InKind;
	FlightTime = 0.f;
	bBeatGoalie = false;
	if (By)
	{
		LastTouch = By;
		if (InKind != EIRShotKind::Pass && InKind != EIRShotKind::None)
		{
			LastShooter = By;
		}
	}
	SpinRate = FMath::Clamp(Velocity.Size2D() * 0.6f, 200.f, 2400.f) * (FMath::RandBool() ? 1.f : -1.f);
}

void AIRPuck::PlaceAt(const FVector& P)
{
	Pos = P;
	Pos.Z = FMath::Max(Pos.Z, PuckHalfHeight);
	Vel = FVector::ZeroVector;
	bInNet = false;
	InNetSign = 0;
	Kind = EIRShotKind::None;
	SaveGoalie = nullptr;
	bShotOnTarget = false;
	SetActorLocation(Pos);
}

void AIRPuck::Simulate(float Dt, TArray<FIRPuckHit>& OutHits)
{
	FireTime = FMath::Max(0.f, FireTime - Dt);
	if (Carrier || bFrozen)
	{
		return;
	}
	FlightTime += Dt;
	const float Travel = Vel.Size() * Dt;
	const int32 Steps = FMath::Clamp(FMath::CeilToInt(Travel / 6.f), 1, 24);
	const float H = Dt / Steps;
	for (int32 s = 0; s < Steps; ++s)
	{
		FVector P = Pos;
		FVector V = Vel;
		const bool bOnIce = P.Z <= PuckHalfHeight + 0.2f && V.Z <= 1.f;
		if (!bOnIce)
		{
			V.Z -= 980.f * H;
		}
		else
		{
			// ice friction: arcade pucks glide far but settle
			FVector2D V2(V.X, V.Y);
			const float Sp = V2.Size();
			if (Sp > 0.f)
			{
				const float Dec = (55.f + 0.16f * Sp) * H;
				V2 *= FMath::Max(0.f, Sp - Dec) / Sp;
				V.X = V2.X; V.Y = V2.Y;
			}
		}
		const FVector Prev = P;
		P += V * H;

		// ice
		if (P.Z < PuckHalfHeight)
		{
			P.Z = PuckHalfHeight;
			if (V.Z < -120.f)
			{
				if (V.Z < -260.f)
				{
					OutHits.Add({ EIRPuckEvent::Ice, P, -V.Z, 0 });
				}
				V.Z = -V.Z * 0.28f;
				V.X *= 0.92f; V.Y *= 0.92f;
			}
			else
			{
				V.Z = 0.f;
			}
		}

		// boards / glass
		if (!bInNet)
		{
			FVector2D P2(P.X, P.Y);
			FVector2D N;
			const float D = BoardDistance(P2, N);
			if (D < PuckRadius)
			{
				if (P.Z > GlassHeight)
				{
					OutHits.Add({ EIRPuckEvent::OutOfPlay, P, V.Size(), 0 });
					bFrozen = true;
					Pos = P;
					Vel = FVector::ZeroVector;
					return;
				}
				const bool bGlass = P.Z > BoardHeight;
				P2 += N * (PuckRadius - D);
				FVector2D V2(V.X, V.Y);
				const float Vn = FVector2D::DotProduct(V2, N);
				if (Vn < 0.f)
				{
					const float E = bGlass ? 0.42f : 0.62f;
					const FVector2D Vt = V2 - N * Vn;
					V2 = Vt * 0.9f - N * Vn * E;
					if (-Vn > 120.f)
					{
						OutHits.Add({ bGlass ? EIRPuckEvent::Glass : EIRPuckEvent::Boards, P, -Vn, 0 });
					}
					if (bGlass) { V.Z *= 0.5f; }
				}
				P.X = P2.X; P.Y = P2.Y;
				V.X = V2.X; V.Y = V2.Y;
			}
		}
		Pos = Prev;
		CollideNets(P, V, OutHits);
		Pos = P;
		Vel = V;
	}
	// settle tiny speeds
	if (Pos.Z <= PuckHalfHeight + 0.1f && FVector2D(Vel.X, Vel.Y).SizeSquared() < 4.f)
	{
		Vel = FVector::ZeroVector;
	}
}

void AIRPuck::CollideNets(FVector& P, FVector& V, TArray<FIRPuckHit>& OutHits)
{
	if (FMath::Abs(P.X) < GoalLineX - 80.f)
	{
		return;
	}
	CollideNet(P.X > 0.f ? 1 : -1, P, V, OutHits);
}

void AIRPuck::CollideNet(int32 Sign, FVector& P, FVector& V, TArray<FIRPuckHit>& OutHits)
{
	const float Gx = GoalLineX * Sign;
	const float LocalX = (P.X - Gx) * Sign;        // depth into the net (>0 behind the goal line)
	const float PrevLocalX = (Pos.X - Gx) * Sign;

	if (bInNet && InNetSign == Sign)
	{
		// confined inside the netting
		bool bHit = false;
		const float Back = NetDepth - PuckRadius - 6.f;
		if (LocalX > Back) { P.X = Gx + Back * Sign; if (V.X * Sign > 0.f) { V.X = -V.X * 0.12f; bHit = true; } }
		if (LocalX < PuckRadius) { P.X = Gx + PuckRadius * Sign; if (V.X * Sign < 0.f) { V.X = -V.X * 0.1f; } }
		const float Side = NetHalfWidth - PuckRadius - 2.f;
		if (FMath::Abs(P.Y) > Side) { P.Y = FMath::Sign(P.Y) * Side; V.Y = -V.Y * 0.12f; bHit = true; }
		const float Top = NetHeight - PuckRadius - 4.f;
		if (P.Z > Top) { P.Z = Top; V.Z = -FMath::Abs(V.Z) * 0.1f; bHit = true; }
		V.X *= 0.97f; V.Y *= 0.97f;
		if (bHit && V.Size() > 150.f)
		{
			OutHits.Add({ EIRPuckEvent::NetInside, P, V.Size(), Sign });
		}
		return;
	}

	// posts (vertical cylinders)
	for (int32 S = -1; S <= 1; S += 2)
	{
		const FVector2D Post(Gx, NetHalfWidth * S + PostRadius * S);
		FVector2D D(P.X - Post.X, P.Y - Post.Y);
		const float Len = D.Size();
		const float R = PostRadius + PuckRadius;
		if (Len < R && P.Z < NetHeight + PostRadius)
		{
			const FVector2D N = Len > 1e-3f ? D / Len : FVector2D(-Sign, 0.f);
			P.X = Post.X + N.X * R; P.Y = Post.Y + N.Y * R;
			FVector2D V2(V.X, V.Y);
			const float Vn = FVector2D::DotProduct(V2, N);
			if (Vn < 0.f)
			{
				V2 -= N * Vn * 1.78f;
				V.X = V2.X; V.Y = V2.Y;
				if (-Vn > 200.f)
				{
					OutHits.Add({ EIRPuckEvent::Post, P, -Vn, Sign });
				}
			}
		}
	}
	// crossbar (horizontal cylinder along Y at the goal line, top of the net)
	if (FMath::Abs(P.Y) < NetHalfWidth + PostRadius)
	{
		const FVector2D Bar(Gx, NetHeight + PostRadius);
		FVector2D D(P.X - Bar.X, P.Z - Bar.Y);
		const float Len = D.Size();
		const float R = PostRadius + PuckRadius;
		if (Len < R)
		{
			const FVector2D N = Len > 1e-3f ? D / Len : FVector2D(-Sign, 0.f);
			P.X = Bar.X + N.X * R; P.Z = Bar.Y + N.Y * R;
			FVector2D V2(V.X, V.Z);
			const float Vn = FVector2D::DotProduct(V2, N);
			if (Vn < 0.f)
			{
				V2 -= N * Vn * 1.75f;
				V.X = V2.X; V.Z = V2.Y;
				if (-Vn > 200.f)
				{
					OutHits.Add({ EIRPuckEvent::Crossbar, P, -Vn, Sign });
				}
			}
		}
	}

	// net body: entering through the mouth = goal; anything else bounces off the frame/mesh
	const float LX = (P.X - Gx) * Sign;
	const bool bInsideBox = LX > -PuckRadius * 0.5f && LX < NetDepth + PuckRadius && FMath::Abs(P.Y) < NetHalfWidth + PostRadius + PuckRadius && P.Z < NetHeight + PuckRadius;
	if (!bInsideBox)
	{
		return;
	}
	const bool bFromFront = PrevLocalX <= 0.5f && FMath::Abs(P.Y) < NetHalfWidth - PuckRadius * 0.5f && P.Z < NetHeight - PuckRadius * 0.5f;
	if (bFromFront)
	{
		if (LX > 0.f)
		{
			bInNet = true;
			InNetSign = Sign;
			OutHits.Add({ EIRPuckEvent::Goal, P, V.Size(), Sign });
			OutHits.Add({ EIRPuckEvent::NetInside, P, V.Size(), Sign });
		}
		return;
	}
	// push out through the nearest outside face
	const float DSide = NetHalfWidth + PostRadius + PuckRadius - FMath::Abs(P.Y);
	const float DBack = NetDepth + PuckRadius - LX;
	const float DTop = NetHeight + PuckRadius - P.Z;
	const float DFront = LX + PuckRadius * 0.5f;
	const float M = FMath::Min(FMath::Min(DSide, DBack), FMath::Min(DTop, DFront));
	if (M == DSide) { P.Y = FMath::Sign(P.Y) * (NetHalfWidth + PostRadius + PuckRadius); if (V.Y * FMath::Sign(P.Y) < 0.f) { V.Y = -V.Y * 0.3f; } }
	else if (M == DBack) { P.X = Gx + (NetDepth + PuckRadius) * Sign; if (V.X * Sign < 0.f) { V.X = -V.X * 0.3f; } }
	else if (M == DTop) { P.Z = NetHeight + PuckRadius; if (V.Z < 0.f) { V.Z = -V.Z * 0.3f; } }
	else { P.X = Gx - PuckRadius * 0.5f * Sign; if (V.X * Sign > 0.f) { V.X = -V.X * 0.3f; } }
	if (V.Size() > 200.f)
	{
		OutHits.Add({ EIRPuckEvent::NetOutside, P, V.Size(), Sign });
	}
}

void AIRPuck::UpdateVisuals(float Dt)
{
	SetActorLocation(Pos);
	if (Carrier)
	{
		SpinRate = FMath::FInterpTo(SpinRate, 0.f, Dt, 4.f);
	}
	else
	{
		SpinRate *= FMath::Max(0.f, 1.f - Dt * 0.4f);
	}
	Spin.Yaw = FMath::Fmod(Spin.Yaw + SpinRate * Dt, 360.f);
	FRotator R = Spin;
	if (Pos.Z > PuckHalfHeight + 8.f)
	{
		R.Pitch = FMath::Sin(FlightTime * 9.f) * 25.f;   // wobble in the air
	}
	SetActorRotation(R);
	if (MarkerMID)
	{
		MarkerMID->SetScalarParameterValue(TEXT("Alpha"), Carrier ? 0.35f : 0.8f);
	}
	if (Marker)
	{
		// the glow disc stays on the ice under the puck
		Marker->SetWorldLocation(FVector(Pos.X, Pos.Y, 0.35f));
	}
}
