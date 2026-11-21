#include "IRFX.h"
#include "IRAssets.h"
#include "IRPlayer.h"
#include "IRRink.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "GameFramework/Actor.h"
#include "Engine/StaticMesh.h"

void UIRFX::Init(AActor* Owner)
{
	UIRAssets* AS = UIRAssets::Get();
	auto Make = [&](const TCHAR* MatName, UStaticMesh* Mesh) -> UInstancedStaticMeshComponent*
	{
		UInstancedStaticMeshComponent* C = NewObject<UInstancedStaticMeshComponent>(Owner);
		C->SetStaticMesh(Mesh);
		C->SetMobility(EComponentMobility::Movable);
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->CastShadow = false;
		C->NumCustomDataFloats = 4;
		C->SetupAttachment(Owner->GetRootComponent());
		C->SetUsingAbsoluteLocation(true);
		C->SetUsingAbsoluteRotation(true);
		C->SetUsingAbsoluteScale(true);
		C->RegisterComponent();
		if (UMaterialInterface* M = AS->FXMaterial(MatName))
		{
			C->SetMaterial(0, M);
		}
		C->SetBoundsScale(1000.f);
		return C;
	};
	UStaticMesh* Plane = AS->EngineShape(TEXT("Plane"));
	AddISM = Make(TEXT("M_FX_Additive"), Plane);
	AlphaISM = Make(TEXT("M_FX_Translucent"), Plane);
	UStaticMesh* Hat = AS->Mesh(TEXT("SM_Hat"));
	if (!Hat) { Hat = AS->Mesh(TEXT("SM_Hat1")); }
	HatISM = Make(TEXT("M_FX_Opaque"), Hat ? Hat : AS->EngineShape(TEXT("Cone")));
	if (Hat) { HatISM->EmptyOverrideMaterials(); }
	HatISM->CastShadow = true;
	bEnabled = AS->FXMaterial(TEXT("M_FX_Additive")) != nullptr;
}

void UIRFX::Clear()
{
	Parts.Reset();
}

void UIRFX::Add(const FPart& P)
{
	if (!bEnabled && P.Kind != KHat)
	{
		return;
	}
	if (Parts.Num() > 2600)
	{
		return;
	}
	Parts.Add(P);
}

static UIRFX* GFX = nullptr;

void UIRFX::Tick(float Dt, const FVector& CamLoc)
{
	for (int32 i = Parts.Num() - 1; i >= 0; --i)
	{
		FPart& P = Parts[i];
		P.Life -= Dt;
		if (P.Life <= 0.f)
		{
			Parts.RemoveAtSwap(i, EAllowShrinking::No);
			continue;
		}
		P.V.Z -= P.Gravity * Dt;
		P.V *= FMath::Max(0.f, 1.f - P.Drag * Dt);
		P.P += P.V * Dt;
		P.Rot += P.RotV * Dt;
		if (P.bGround && P.P.Z < 1.f)
		{
			P.P.Z = 1.f;
			P.V.Z = -P.V.Z * 0.2f;
			P.V.X *= 0.6f; P.V.Y *= 0.6f;
			P.RotV *= 0.5f;
		}
	}

	auto Fill = [&](UInstancedStaticMeshComponent* ISM, EKind Kind)
	{
		if (!ISM)
		{
			return;
		}
		TArray<FTransform> Xf;
		TArray<float> Custom;
		for (const FPart& P : Parts)
		{
			if (P.Kind != Kind)
			{
				continue;
			}
			const float T = 1.f - P.Life / P.MaxLife;
			const float Size = FMath::Lerp(P.Size0, P.Size1, T);
			FTransform X;
			X.SetLocation(P.P);
			if (Kind == KHat)
			{
				X.SetRotation(FRotator(P.Rot * 0.5f, P.Rot, P.Rot * 0.3f).Quaternion());
				X.SetScale3D(FVector(Size));
			}
			else if (P.bFlat)
			{
				X.SetRotation(FRotator(0.f, P.Rot, 0.f).Quaternion());
				X.SetScale3D(FVector(Size / 100.f, Size / 100.f, 1.f));
			}
			else
			{
				// camera-facing quad: the engine plane faces +Z, so point +Z at the camera
				FVector ToCam = (CamLoc - P.P).GetSafeNormal();
				if (ToCam.IsNearlyZero()) { ToCam = FVector::UpVector; }
				FQuat Q = FRotationMatrix::MakeFromZ(ToCam).ToQuat();
				Q = Q * FQuat(FVector::UpVector, FMath::DegreesToRadians(P.Rot));
				FVector S(Size / 100.f, Size / 100.f, 1.f);
				if (P.bStretch)
				{
					const float Sp = P.V.Size();
					if (Sp > 50.f)
					{
						const FVector Dir = P.V / Sp;
						const FVector Side = FVector::CrossProduct(Dir, ToCam).GetSafeNormal();
						if (!Side.IsNearlyZero())
						{
							const FVector Fwd = FVector::CrossProduct(ToCam, Side).GetSafeNormal();
							Q = FMatrix(Fwd, Side, ToCam, FVector::ZeroVector).ToQuat();
							S.X *= 1.f + FMath::Min(Sp / 400.f, 6.f);
						}
					}
				}
				Q.Normalize();
				if (Q.ContainsNaN()) { Q = FQuat::Identity; }
				X.SetRotation(Q);
				X.SetScale3D(S);
			}
			Xf.Add(X);
			const float Fade = FMath::Min(1.f, P.Life / FMath::Max(0.05f, P.MaxLife * 0.35f)) * FMath::Min(1.f, (P.MaxLife - P.Life) / 0.04f + 0.3f);
			Custom.Add(P.C.R);
			Custom.Add(P.C.G);
			Custom.Add(P.C.B);
			Custom.Add(P.C.A * Fade);
		}
		const int32 N = Xf.Num();
		if (ISM->GetInstanceCount() != N)
		{
			ISM->ClearInstances();
			if (N > 0)
			{
				ISM->AddInstances(Xf, false, true);
			}
		}
		else if (N > 0)
		{
			ISM->BatchUpdateInstancesTransforms(0, Xf, true, false, true);
		}
		for (int32 i = 0; i < N; ++i)
		{
			ISM->SetCustomData(i, TArrayView<const float>(&Custom[i * 4], 4), false);
		}
		ISM->MarkRenderInstancesDirty();
		ISM->SetVisibility(N > 0);
	};
	Fill(AddISM, KAdd);
	Fill(AlphaISM, KAlpha);
	Fill(HatISM, KHat);
}

static FVector RandCone(const FVector& Dir, float HalfAngleDeg)
{
	return FMath::VRandCone(Dir, FMath::DegreesToRadians(HalfAngleDeg));
}

void UIRFX::IceSpray(const FVector& P, const FVector2D& Dir, float Amount)
{
	const int32 N = FMath::Clamp(int32(6 * Amount * Quality), 2, 24);
	const FVector D3 = FVector(Dir.X, Dir.Y, 0.35f).GetSafeNormal();
	for (int32 i = 0; i < N; ++i)
	{
		FPart X;
		X.P = P + FVector(FMath::FRandRange(-10.f, 10.f), FMath::FRandRange(-10.f, 10.f), 4.f);
		X.V = RandCone(D3, 38.f) * FMath::FRandRange(250.f, 620.f) * FMath::Sqrt(Amount);
		X.Life = X.MaxLife = FMath::FRandRange(0.35f, 0.75f);
		X.Size0 = FMath::FRandRange(8.f, 16.f);
		X.Size1 = X.Size0 * 2.4f;
		X.C = FLinearColor(0.9f, 0.95f, 1.f, 0.8f);
		X.Drag = 2.5f;
		X.Gravity = 900.f;
		X.Rot = FMath::FRandRange(0.f, 360.f);
		X.RotV = FMath::FRandRange(-90.f, 90.f);
		X.Kind = KAlpha;
		X.bFlat = false; X.bStretch = false; X.bGround = true;
		Add(X);
	}
}

void UIRFX::Sparks(const FVector& P, const FLinearColor& C, int32 Count, float Speed)
{
	for (int32 i = 0; i < int32(Count * Quality); ++i)
	{
		FPart X;
		X.P = P;
		X.V = FMath::VRand() * FMath::FRandRange(0.3f, 1.f) * Speed + FVector(0, 0, Speed * 0.3f);
		X.Life = X.MaxLife = FMath::FRandRange(0.25f, 0.6f);
		X.Size0 = FMath::FRandRange(3.f, 6.f);
		X.Size1 = 1.f;
		X.C = C;
		X.Drag = 1.5f;
		X.Gravity = 980.f;
		X.Rot = 0.f; X.RotV = 0.f;
		X.Kind = KAlpha;
		X.bFlat = false; X.bStretch = true; X.bGround = true;
		Add(X);
	}
}

void UIRFX::Impact(const FVector& P, float Scale, const FLinearColor& C)
{
	FPart R;
	R.P = FVector(P.X, P.Y, 2.f);
	R.V = FVector::ZeroVector;
	R.Life = R.MaxLife = 0.45f;
	R.Size0 = 40.f * Scale;
	R.Size1 = 420.f * Scale;
	R.C = C;
	R.Drag = 0.f; R.Gravity = 0.f; R.Rot = 0.f; R.RotV = 0.f;
	R.Kind = KAdd; R.bFlat = true; R.bStretch = false; R.bGround = false;
	Add(R);
	FPart F = R;
	F.P = P;
	F.bFlat = false;
	F.Life = F.MaxLife = 0.18f;
	F.Size0 = 160.f * Scale;
	F.Size1 = 60.f * Scale;
	F.C = FLinearColor(1.f, 0.95f, 0.8f, 1.f);
	Add(F);
	Sparks(P, C, int32(18 * Scale), 700.f * Scale);
}

void UIRFX::FireBurst(const FVector& P, float Scale)
{
	const int32 N = int32(26 * Scale * Quality);
	for (int32 i = 0; i < N; ++i)
	{
		FPart X;
		X.P = P + FVector(FMath::FRandRange(-60.f, 60.f) * Scale, FMath::FRandRange(-90.f, 90.f) * Scale, FMath::FRandRange(0.f, 80.f) * Scale);
		X.V = FVector(FMath::FRandRange(-60.f, 60.f), FMath::FRandRange(-60.f, 60.f), FMath::FRandRange(120.f, 380.f)) * Scale;
		X.Life = X.MaxLife = FMath::FRandRange(0.4f, 0.9f);
		X.Size0 = FMath::FRandRange(40.f, 80.f) * Scale;
		X.Size1 = 10.f;
		const float H = FMath::FRand();
		X.C = FLinearColor(1.f, FMath::Lerp(0.25f, 0.75f, H), FMath::Lerp(0.02f, 0.15f, H), 1.f) * 2.f;
		X.C.A = 1.f;
		X.Drag = 1.f; X.Gravity = -150.f;
		X.Rot = FMath::FRandRange(0.f, 360.f); X.RotV = FMath::FRandRange(-120.f, 120.f);
		X.Kind = KAlpha; X.bFlat = false; X.bStretch = false; X.bGround = false;
		Add(X);
	}
	Smoke(P + FVector(0, 0, 120.f * Scale), Scale * 0.6f);
}

void UIRFX::FireTrail(const FVector& P, const FVector& Vel)
{
	for (int32 i = 0; i < 2; ++i)
	{
		FPart X;
		X.P = P + FMath::VRand() * 4.f;
		X.V = -Vel * 0.05f + FVector(0, 0, FMath::FRandRange(40.f, 140.f));
		X.Life = X.MaxLife = FMath::FRandRange(0.18f, 0.4f);
		X.Size0 = FMath::FRandRange(18.f, 32.f);
		X.Size1 = 4.f;
		X.C = FLinearColor(1.f, FMath::FRandRange(0.3f, 0.7f), 0.05f, 1.f) * 2.2f;
		X.C.A = 1.f;
		X.Drag = 3.f; X.Gravity = -200.f; X.Rot = FMath::FRandRange(0.f, 360.f); X.RotV = 200.f;
		X.Kind = KAlpha; X.bFlat = false; X.bStretch = false; X.bGround = false;
		Add(X);
	}
}

void UIRFX::Streak(const FVector& P, const FLinearColor& C, float Size)
{
	FPart X;
	X.P = P;
	X.V = FVector::ZeroVector;
	X.Life = X.MaxLife = 0.22f;
	X.Size0 = Size;
	X.Size1 = Size * 0.2f;
	X.C = C;
	X.Drag = 0.f; X.Gravity = 0.f; X.Rot = 0.f; X.RotV = 0.f;
	X.Kind = KAlpha; X.bFlat = false; X.bStretch = false; X.bGround = false;
	Add(X);
}

void UIRFX::Glow(const FVector& P, const FLinearColor& C, float Size, float Life)
{
	FPart X;
	X.P = P;
	X.V = FVector::ZeroVector;
	X.Life = X.MaxLife = Life;
	X.Size0 = Size; X.Size1 = Size * 1.2f;
	X.C = C;
	X.Drag = 0.f; X.Gravity = 0.f; X.Rot = 0.f; X.RotV = 0.f;
	X.Kind = KAdd; X.bFlat = false; X.bStretch = false; X.bGround = false;
	Add(X);
}

void UIRFX::PowerCharge(AIRPlayer* P)
{
	if (!P)
	{
		return;
	}
	const FVector B = P->BladePos() + FVector(0, 0, 10.f);
	for (int32 i = 0; i < 14; ++i)
	{
		FPart X;
		const FVector Off = FMath::VRand() * 90.f;
		X.P = B + Off;
		X.V = -Off * 4.f;
		X.Life = X.MaxLife = 0.25f;
		X.Size0 = 10.f; X.Size1 = 3.f;
		X.C = FLinearColor(1.f, 0.55f, 0.1f, 1.f) * 2.f;
		X.C.A = 1.f;
		X.Drag = 0.f; X.Gravity = 0.f; X.Rot = 0.f; X.RotV = 0.f;
		X.Kind = KAlpha; X.bFlat = false; X.bStretch = true; X.bGround = false;
		Add(X);
	}
	Glow(B, FLinearColor(1.f, 0.5f, 0.1f, 1.f), 90.f, 0.3f);
}

void UIRFX::Confetti(const FVector& Center, const FLinearColor& A, const FLinearColor& B, int32 Count)
{
	for (int32 i = 0; i < int32(Count * Quality); ++i)
	{
		FPart X;
		X.P = Center + FVector(FMath::FRandRange(-900.f, 900.f), FMath::FRandRange(-500.f, 500.f), FMath::FRandRange(700.f, 1300.f));
		X.V = FVector(FMath::FRandRange(-80.f, 80.f), FMath::FRandRange(-80.f, 80.f), FMath::FRandRange(-60.f, 0.f));
		X.Life = X.MaxLife = FMath::FRandRange(3.f, 5.f);
		X.Size0 = X.Size1 = FMath::FRandRange(5.f, 9.f);
		X.C = FMath::RandBool() ? A : B;
		X.C.A = 1.f;
		X.Drag = 1.6f; X.Gravity = 160.f;
		X.Rot = FMath::FRandRange(0.f, 360.f); X.RotV = FMath::FRandRange(-400.f, 400.f);
		X.Kind = KAlpha; X.bFlat = false; X.bStretch = false; X.bGround = true;
		Add(X);
	}
}

void UIRFX::Hats(int32 Count)
{
	for (int32 i = 0; i < Count; ++i)
	{
		FPart X;
		const float Side = FMath::RandBool() ? 1.f : -1.f;
		X.P = FVector(FMath::FRandRange(-1800.f, 1800.f), Side * FMath::FRandRange(1100.f, 1500.f), FMath::FRandRange(400.f, 700.f));
		X.V = FVector(FMath::FRandRange(-120.f, 120.f), -Side * FMath::FRandRange(300.f, 900.f), FMath::FRandRange(100.f, 400.f));
		X.Life = X.MaxLife = FMath::FRandRange(7.f, 10.f);
		X.Size0 = X.Size1 = FMath::FRandRange(0.9f, 1.2f);
		X.C = FLinearColor::White;
		X.Drag = 0.4f; X.Gravity = 700.f;
		X.Rot = FMath::FRandRange(0.f, 360.f); X.RotV = FMath::FRandRange(-300.f, 300.f);
		X.Kind = KHat; X.bFlat = false; X.bStretch = false; X.bGround = true;
		Parts.Add(X);
	}
}

void UIRFX::Smoke(const FVector& P, float Scale)
{
	for (int32 i = 0; i < int32(8 * Scale * Quality) + 1; ++i)
	{
		FPart X;
		X.P = P + FMath::VRand() * 30.f * Scale;
		X.V = FVector(FMath::FRandRange(-40.f, 40.f), FMath::FRandRange(-40.f, 40.f), FMath::FRandRange(60.f, 160.f));
		X.Life = X.MaxLife = FMath::FRandRange(1.f, 2.f);
		X.Size0 = 60.f * Scale; X.Size1 = 220.f * Scale;
		X.C = FLinearColor(0.15f, 0.15f, 0.17f, 0.45f);
		X.Drag = 0.8f; X.Gravity = -30.f; X.Rot = FMath::FRandRange(0.f, 360.f); X.RotV = FMath::FRandRange(-30.f, 30.f);
		X.Kind = KAlpha; X.bFlat = false; X.bStretch = false; X.bGround = false;
		Add(X);
	}
}

void UIRFX::Stars(const FVector& P)
{
	for (int32 i = 0; i < 6; ++i)
	{
		FPart X;
		const float A = i / 6.f * 2.f * PI;
		X.P = P + FVector(FMath::Cos(A) * 40.f, FMath::Sin(A) * 40.f, 0.f);
		X.V = FVector(-FMath::Sin(A) * 120.f, FMath::Cos(A) * 120.f, 20.f);
		X.Life = X.MaxLife = 1.2f;
		X.Size0 = 18.f; X.Size1 = 10.f;
		X.C = FLinearColor(1.f, 0.9f, 0.2f, 1.f) * 1.6f;
		X.C.A = 1.f;
		X.Drag = 0.f; X.Gravity = 0.f; X.Rot = 0.f; X.RotV = 180.f;
		X.Kind = KAlpha; X.bFlat = false; X.bStretch = false; X.bGround = false;
		Add(X);
	}
}
