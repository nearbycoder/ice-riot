#include "IRPlayer.h"
#include "IRGameMode.h"
#include "IRAnimInstance.h"
#include "IRAssets.h"
#include "IRRink.h"
#include "IRFX.h"
#include "IRRoster.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Engine/SkeletalMesh.h"
#include "Animation/AnimSequence.h"
#include "Engine/Texture2D.h"

using namespace IRRink;

namespace
{
	// Animation clip timings (Docs/ASSET_SPEC.md): {length, event}
	constexpr float kWristLen = 0.55f, kWristEvt = 0.22f;
	constexpr float kSlapLen = 0.50f, kSlapEvt = 0.10f;
	constexpr float kOneTLen = 0.55f, kOneTEvt = 0.18f;
	constexpr float kPassLen = 0.45f, kPassEvt = 0.16f;
	constexpr float kCheckLen = 0.55f, kCheckEvt = 0.18f;
	constexpr float kPCheckLen = 0.70f, kPCheckEvt = 0.22f;
	constexpr float kPokeLen = 0.45f, kPokeEvt = 0.15f;
	constexpr float kHookLen = 0.60f, kHookEvt = 0.20f;
	constexpr float kDiveLen = 1.2f;
	constexpr float kFallLen = 1.1f;
	constexpr float kGetUpLen = 0.9f;
	constexpr float kSpinLen = 0.45f;

	float WrapPi(float A)
	{
		while (A > PI) { A -= 2.f * PI; }
		while (A < -PI) { A += 2.f * PI; }
		return A;
	}
	float YawOf(const FVector2D& D) { return FMath::Atan2(D.Y, D.X); }
}

AIRPlayer::AIRPlayer()
{
	PrimaryActorTick.bCanEverTick = false;
	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;
	Mesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("Mesh"));
	Mesh->SetupAttachment(Root);
	Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Mesh->SetRelativeRotation(FRotator(0.f, -90.f, 0.f));
	Mesh->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	Mesh->bCastDynamicShadow = true;
	Mesh->SetRenderCustomDepth(false);
	Ring = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Ring"));
	Ring->SetupAttachment(Root);
	Ring->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Ring->CastShadow = false;
	Ring->SetUsingAbsoluteRotation(true);
	Shadow = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Shadow"));
	Shadow->SetupAttachment(Root);
	Shadow->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Shadow->CastShadow = false;
	Shadow->SetVisibility(false);
}

UAnimSequence* AIRPlayer::A(const TCHAR* Name) const
{
	return bHasSkel ? UIRAssets::Get()->Anim(Name) : nullptr;
}

void AIRPlayer::Setup(AIRGameMode* InGame, int32 InTeam, int32 InTeamIndex, EIRRole InRole, const FIRPlayerInfo& InInfo, const FIRTeamInfo* TI)
{
	Game = InGame;
	Team = InTeam;
	TeamIndex = InTeamIndex;
	Role = InRole;
	Info = InInfo;
	UIRAssets* AS = UIRAssets::Get();

	USkeletalMesh* SK = AS->Skel(Role == EIRRole::Goalie ? TEXT("SK_Goalie") : TEXT("SK_Skater"));
	if (!SK && Role == EIRRole::Goalie)
	{
		SK = AS->Skel(TEXT("SK_Skater"));
	}
	bHasSkel = SK != nullptr;
	if (bHasSkel)
	{
		Mesh->SetSkeletalMesh(SK);
		Mesh->SetAnimInstanceClass(UIRAnimInstance::StaticClass());
		AnimInst = Cast<UIRAnimInstance>(Mesh->GetAnimInstance());
	}
	else
	{
		Mesh->SetVisibility(false);
		BuildPlaceholder(TI);
	}

	// player ring
	if (UMaterialInterface* RM = AS->FXMaterial(TEXT("M_FX_Ring")))
	{
		Ring->SetStaticMesh(AS->EngineShape(TEXT("Plane")));
		RingMID = UMaterialInstanceDynamic::Create(RM, this);
		Ring->SetMaterial(0, RingMID);
		Ring->SetRelativeScale3D(FVector(1.5f, 1.5f, 1.f));
		Ring->SetRelativeLocation(FVector(0, 0, 0.6f));
		Ring->SetTranslucentSortPriority(5);
	}
	else
	{
		Ring->SetStaticMesh(AS->EngineShape(TEXT("Cylinder")));
		RingMID = UMaterialInstanceDynamic::Create(AS->BasicMaterial(), this);
		Ring->SetMaterial(0, RingMID);
		Ring->SetRelativeScale3D(FVector(1.1f, 1.1f, 0.01f));
		Ring->SetRelativeLocation(FVector(0, 0, 0.5f));
	}
	if (UMaterialInterface* SM = AS->FXMaterial(TEXT("M_FX_Shadow")))
	{
		Shadow->SetStaticMesh(AS->EngineShape(TEXT("Plane")));
		Shadow->SetMaterial(0, SM);
		Shadow->SetRelativeScale3D(FVector(1.3f, 1.3f, 1.f));
		Shadow->SetRelativeLocation(FVector(0, 0, 0.3f));
		Shadow->SetVisibility(true);
	}
	ApplyTeamLook(TI);
	SetInfo(InInfo);
	if (Role == EIRRole::Referee)
	{
		Ring->SetVisibility(false);
	}
}

void AIRPlayer::SetInfo(const FIRPlayerInfo& InInfo)
{
	Info = InInfo;
	const float Tiny = (Game && Game->Opt.bTinyPlayers) ? 0.62f : 1.f;
	const float H = (Role == EIRRole::Goalie ? 1.04f : Info.Height) * Tiny;
	const float W = (Role == EIRRole::Goalie ? 1.06f : Info.Bulk) * Tiny;
	Mesh->SetRelativeScale3D(FVector(W, W, H));
	HeadScale = (Game && Game->Opt.bBigHeads) ? 2.1f : 1.f;
	for (UMaterialInstanceDynamic* M : MIDs)
	{
		if (!M) { continue; }
		const FString N = M->Parent ? M->Parent->GetName() : FString();
		if (N.Contains(TEXT("Skin")) || N.Contains(TEXT("Face")))
		{
			M->SetVectorParameterValue(TEXT("SkinColor"), Info.Skin);
			M->SetVectorParameterValue(TEXT("Color"), Info.Skin);
		}
		if (N.Contains(TEXT("Number")))
		{
			const int32 Num = FMath::Clamp(Info.Number, 0, 99);
			M->SetScalarParameterValue(TEXT("Tens"), Num >= 10 ? float(Num / 10) : -1.f);
			M->SetScalarParameterValue(TEXT("Ones"), float(Num % 10));
		}
	}
}

void AIRPlayer::ApplyTeamLook(const FIRTeamInfo* TI)
{
	if (!bHasSkel)
	{
		return;
	}
	UIRAssets* AS = UIRAssets::Get();
	const bool bRef = Role == EIRRole::Referee;
	FLinearColor Primary = bRef ? FLinearColor(0.85f, 0.85f, 0.85f) : (TI ? TI->Primary : FLinearColor::Gray);
	FLinearColor Secondary = bRef ? FLinearColor(0.02f, 0.02f, 0.02f) : (TI ? TI->Secondary : FLinearColor::Black);
	FLinearColor Trim = bRef ? FLinearColor(0.02f, 0.02f, 0.02f) : (TI ? TI->Trim : FLinearColor::White);
	const FLinearColor HelmetC = Secondary.GetLuminance() > 0.6f ? Primary : Secondary;
	if (!bRef && Team == 1)
	{
		// the away team wears white (like real hockey): every matchup reads at a glance
		const FLinearColor White(0.82f, 0.83f, 0.86f);
		Trim = Secondary.GetLuminance() > 0.6f ? Primary : Secondary;
		Secondary = Primary;
		Primary = White;
	}
	const float LumP = Primary.GetLuminance(), LumS = Secondary.GetLuminance();
	const FLinearColor Dark = LumP < LumS ? Primary : Secondary;
	MIDs.Reset();
	const TArray<FName> Slots = Mesh->GetMaterialSlotNames();
	for (int32 i = 0; i < Slots.Num(); ++i)
	{
		const FString S = Slots[i].ToString();
		UMaterialInterface* Base = Mesh->GetMaterial(i);
		if (bRef && (S == TEXT("MI_TeamPrimary") || S == TEXT("MI_TeamSecondary") || S == TEXT("MI_TeamTrim") || S == TEXT("MI_JerseyCrest")))
		{
			if (UMaterialInterface* RefMat = AS->Material(TEXT("MI_RefJersey")))
			{
				Mesh->SetMaterial(i, RefMat);
				continue;
			}
		}
		if (!Base)
		{
			continue;
		}
		UMaterialInstanceDynamic* M = UMaterialInstanceDynamic::Create(Base, this);
		Mesh->SetMaterial(i, M);
		MIDs.Add(M);
		FLinearColor C;
		bool bSet = true;
		if (S == TEXT("MI_TeamPrimary")) { C = Primary; }
		else if (S == TEXT("MI_TeamSecondary")) { C = Secondary; }
		else if (S == TEXT("MI_TeamTrim")) { C = Trim; }
		else if (S == TEXT("MI_Helmet")) { C = bRef ? FLinearColor(0.02f, 0.02f, 0.02f) : HelmetC; }
		else if (S == TEXT("MI_Pants")) { C = bRef ? FLinearColor(0.02f, 0.02f, 0.02f) : (Team == 1 ? Secondary * 0.6f : Dark); }
		else if (S == TEXT("MI_Gloves")) { C = bRef ? FLinearColor(0.02f, 0.02f, 0.02f) : HelmetC; }
		else if (S == TEXT("MI_JerseyCrest"))
		{
			if (TI) { if (UTexture2D* Crest = AS->Texture(*FString::Printf(TEXT("T_Logo_%s"), *TI->Id))) { M->SetTextureParameterValue(TEXT("BaseTexture"), Crest); } }
			bSet = false;
		}
		else if (S == TEXT("MI_GoaliePads")) { C = FLinearColor::LerpUsingHSV(FLinearColor(0.85f, 0.85f, 0.85f), Primary, 0.35f); }
		else if (S == TEXT("MI_GoalieMask")) { C = Primary; }
		else if (S == TEXT("MI_Number"))
		{
			C = bRef ? FLinearColor::Black : Trim;
			FLinearColor Out = Secondary;
			if (FMath::Abs(C.GetLuminance() - Primary.GetLuminance()) < 0.08f)
			{
				C = Secondary;
				Out = Trim;
			}
			M->SetVectorParameterValue(TEXT("OutlineColor"), Out);
		}
		else { bSet = false; }
		if (bSet)
		{
			M->SetVectorParameterValue(TEXT("Color"), C);
		}
	}
}

void AIRPlayer::BuildPlaceholder(const FIRTeamInfo* TI)
{
	UIRAssets* AS = UIRAssets::Get();
	auto Add = [&](const TCHAR* Shape, FVector Loc, FVector Scale, FLinearColor Color)
	{
		UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
		C->SetStaticMesh(AS->EngineShape(Shape));
		C->SetupAttachment(Root);
		C->SetRelativeLocation(Loc);
		C->SetRelativeScale3D(Scale);
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->RegisterComponent();
		UMaterialInstanceDynamic* M = UMaterialInstanceDynamic::Create(AS->BasicMaterial(), this);
		M->SetVectorParameterValue(TEXT("Color"), Color);
		C->SetMaterial(0, M);
		Placeholder.Add(C);
	};
	const FLinearColor P = Role == EIRRole::Referee ? FLinearColor(0.8f, 0.8f, 0.8f) : (TI ? TI->Primary : FLinearColor::Gray);
	const FLinearColor S = Role == EIRRole::Referee ? FLinearColor::Black : (TI ? TI->Secondary : FLinearColor::Black);
	const float W = Role == EIRRole::Goalie ? 0.95f : 0.7f;
	Add(TEXT("Cylinder"), FVector(0, 0, 95), FVector(W, W * 0.8f, 1.3f), P);
	Add(TEXT("Sphere"), FVector(0, 0, 178), FVector(0.42f), S);
	Add(TEXT("Cube"), FVector(55, 25, 40), FVector(1.3f, 0.06f, 0.06f), FLinearColor(0.1f, 0.1f, 0.1f));
	Add(TEXT("Cube"), FVector(110, 25, 4), FVector(0.3f, 0.12f, 0.06f), FLinearColor(0.02f, 0.02f, 0.02f));
}

float AIRPlayer::MaxSpeed() const
{
	float S = 720.f + Info.R.Speed * 26.f;
	if (Role == EIRRole::Goalie) { S = 560.f; }
	if (Role == EIRRole::Referee) { S = 800.f; }
	if (Game) { S *= 1.f + Game->CatchupBoost[Team] * 0.06f; }
	if (bBlazing) { S *= 1.05f; }
	return S;
}

bool AIRPlayer::HasPuck() const
{
	return Game && Game->Puck && Game->Puck->Carrier == this;
}

bool AIRPlayer::CanAct() const
{
	return Action == EIRAction::None || Action == EIRAction::Stop;
}

bool AIRPlayer::CanPlayPuck() const
{
	if (Role == EIRRole::Referee || NoPickupTime > 0.f)
	{
		return false;
	}
	switch (Action)
	{
	case EIRAction::Down: case EIRAction::Flying: case EIRAction::GetUp: case EIRAction::Celebrate: case EIRAction::Dejected:
	case EIRAction::FightIdle: case EIRAction::FightAttack: case EIRAction::FightHit: case EIRAction::FightBlock: case EIRAction::FightKO:
	case EIRAction::Scripted: case EIRAction::Spin:
		return false;
	default:
		return true;
	}
}

FVector AIRPlayer::BladePos() const
{
	if (bHasSkel && Mesh && Mesh->GetBoneIndex(TEXT("stick_blade")) != INDEX_NONE && Action != EIRAction::Scripted)
	{
		FVector B = Mesh->GetBoneLocation(TEXT("stick_blade"));
		// keep the puck on the ice and not too far from the body (animations can lift the blade)
		FVector2D Rel(B.X - Pos.X, B.Y - Pos.Y);
		const float Len = Rel.Size();
		if (Len > 150.f) { Rel *= 150.f / Len; }
		if (Len < 45.f) { Rel = Forward() * 60.f; }
		return FVector(Pos.X + Rel.X, Pos.Y + Rel.Y, PuckHalfHeight);
	}
	const float Side = Info.bLefty ? -1.f : 1.f;
	const FVector2D F = Forward(), R = Right();
	const float Handle = FMath::Sin(StrideTimer * 7.f) * 14.f;
	const FVector2D P = Pos + F * 72.f + R * (20.f * Side + Handle);
	return FVector(P.X, P.Y, PuckHalfHeight);
}

FVector AIRPlayer::HeadPos() const
{
	if (bHasSkel && Mesh && Mesh->GetBoneIndex(TEXT("head")) != INDEX_NONE)
	{
		return Mesh->GetBoneLocation(TEXT("head"));
	}
	return FVector(Pos.X, Pos.Y, Z + 180.f);
}

FVector2D AIRPlayer::StickReachPoint() const
{
	return Pos + Forward() * 80.f;
}

void AIRPlayer::Teleport(FVector2D P, float InYaw)
{
	Pos = P;
	Vel = FVector2D::ZeroVector;
	Yaw = InYaw;
	LastYaw = InYaw;
	Z = 0.f;
	VZ = 0.f;
	SetActorLocationAndRotation(FVector(P.X, P.Y, 0.f), FRotator(0.f, FMath::RadiansToDegrees(InYaw), 0.f));
}

void AIRPlayer::StartAction(EIRAction InA, float Duration)
{
	Action = InA;
	ActionTime = 0.f;
	ActionDuration = Duration;
	bActionEvent = false;
}

void AIRPlayer::PlayOneShot(UAnimSequence* Seq, float Rate, float Blend)
{
	if (AnimInst && Seq)
	{
		AnimInst->StopUpper(0.08f);
		AnimInst->Play(Seq, false, Rate, Blend, 0.f, true);
	}
}

void AIRPlayer::ArmOneTimer(float Window)
{
	OneTimerWindow = Window;
}

void AIRPlayer::ResetForFaceoff()
{
	Action = EIRAction::None;
	ActionTime = 0.f;
	PendingShot = EIRShotKind::None;
	OneTimerWindow = 0.f;
	bAutoOneTimer = false;
	NoPickupTime = 0.f;
	StunTime = 0.f;
	HookedTime = 0.f;
	Z = 0.f; VZ = 0.f; SpinRate = 0.f;
	bStopping = false;
	if (AnimInst)
	{
		AnimInst->StopUpper(0.05f);
		AnimInst->StickScale = 1.f;
	}
}

void AIRPlayer::SetScripted(bool bOn)
{
	if (bOn)
	{
		StartAction(EIRAction::Scripted, 1e6f);
	}
	else if (Action == EIRAction::Scripted)
	{
		Action = EIRAction::None;
	}
}

// ------------------------------------------------------------------------------------------------ simulation

void AIRPlayer::Simulate(float Dt, const FIRIntent& In)
{
	LastIntent = In;
	NoPickupTime = FMath::Max(0.f, NoPickupTime - Dt);
	StunTime = FMath::Max(0.f, StunTime - Dt);
	HookedTime = FMath::Max(0.f, HookedTime - Dt);
	OneTimerWindow = FMath::Max(0.f, OneTimerWindow - Dt);
	PassComboTimer = FMath::Max(0.f, PassComboTimer - Dt);
	ShootComboTimer = FMath::Max(0.f, ShootComboTimer - Dt);
	Rage = FMath::Max(0.f, Rage - Dt);
	GoalieGlow = FMath::Max(0.f, GoalieGlow - Dt * 0.02f);
	Anger = FMath::Max(0.f, Anger - Dt * 0.025f);
	ActionTime += Dt;
	PossessTime = HasPuck() ? PossessTime + Dt : 0.f;

	if (Action == EIRAction::Scripted)
	{
		return;
	}
	if (IsInFight())
	{
		SimulateFight(Dt, In);
		return;
	}
	switch (Role)
	{
	case EIRRole::Goalie: SimulateGoalie(Dt, In); break;
	case EIRRole::Referee: SimulateReferee(Dt, In); break;
	default: SimulateSkater(Dt, In); break;
	}
}

void AIRPlayer::Integrate(float Dt, const FIRIntent& In, float SpeedScale)
{
	const float Max = MaxSpeed() * SpeedScale;
	FVector2D Want = In.MoveWorld;
	if (Want.SizeSquared() > 1.f) { Want.Normalize(); }
	const float WantMag = Want.Size();
	const float Sp = Vel.Size();

	const bool bCanTurbo = Turbo > 0.02f && WantMag > 0.3f && In.bTurbo && Role == EIRRole::Skater;
	bTurboActive = bCanTurbo;
	if (bTurboActive)
	{
		Turbo = FMath::Max(0.f, Turbo - Dt * 0.40f);
		TurboDelay = 0.55f;
	}
	else
	{
		TurboDelay -= Dt;
		if (TurboDelay <= 0.f)
		{
			Turbo = FMath::Min(1.f, Turbo + Dt * 0.24f);
		}
	}
	const float TurboMul = bTurboActive ? 1.42f : 1.f;
	float Accel = (1350.f + Info.R.Speed * 70.f) * (bTurboActive ? 1.6f : 1.f);
	if (HookedTime > 0.f) { Accel *= 0.35f; }
	const float Target = Max * TurboMul * WantMag;

	bStopping = false;
	if (WantMag > 0.1f)
	{
		const FVector2D WantDir = Want / WantMag;
		if (Sp > 60.f)
		{
			const FVector2D Dir = Vel / Sp;
			const float Ang = FMath::Acos(FMath::Clamp(FVector2D::DotProduct(Dir, WantDir), -1.f, 1.f));
			if (Ang > FMath::DegreesToRadians(118.f) && Sp > 420.f)
			{
				// hockey stop: dig in, spray, then go the other way
				bStopping = true;
				const float NewSp = FMath::Max(0.f, Sp - 3300.f * Dt);
				Vel = Dir * NewSp;
			}
			else
			{
				const float Cross = Dir.X * WantDir.Y - Dir.Y * WantDir.X;
				const float SpeedFrac = FMath::Clamp(Sp / 1100.f, 0.f, 1.f);
				const float TurnRate = FMath::Lerp(8.5f, 3.6f, SpeedFrac) * (bTurboActive ? 1.1f : 1.f) * (HasPuck() ? 0.95f : 1.f);
				const float Step = FMath::Min(Ang, TurnRate * Dt) * FMath::Sign(Cross);
				const FVector2D NewDir = Dir.GetRotated(FMath::RadiansToDegrees(Step));
				float NewSp = Sp;
				if (Sp < Target) { NewSp = FMath::Min(Target, Sp + Accel * Dt); }
				else { NewSp = FMath::Max(Target, Sp - 900.f * Dt); }
				// a little edge bite: lose speed in very sharp turns
				NewSp *= 1.f - FMath::Clamp(FMath::Abs(Step) / Dt - 4.f, 0.f, 6.f) * 0.004f;
				Vel = NewDir * NewSp;
			}
		}
		else
		{
			Vel = WantDir * FMath::Min(Target, Sp + Accel * Dt);
		}
	}
	else
	{
		// coasting: ice is slick but players dig in to slow down
		const float NewSp = FMath::Max(0.f, Sp - 520.f * Dt);
		Vel = Sp > 0.f ? Vel / Sp * NewSp : FVector2D::ZeroVector;
	}

	// facing
	float WantYaw = Yaw;
	bBackward = false;
	if (In.bFaceTarget)
	{
		const FVector2D ToT = In.FaceTarget - Pos;
		if (ToT.SizeSquared() > 100.f)
		{
			WantYaw = YawOf(ToT);
			if (Vel.SizeSquared() > 150.f * 150.f && FVector2D::DotProduct(Vel.GetSafeNormal(), ToT.GetSafeNormal()) < -0.3f)
			{
				bBackward = true;
			}
		}
	}
	else if (bStopping)
	{
		WantYaw = YawOf(Vel) + (FMath::Sin(Yaw) > 0 ? 1.f : -1.f) * PI * 0.5f;
	}
	else if (Vel.SizeSquared() > 90.f * 90.f)
	{
		WantYaw = YawOf(Vel);
	}
	else if (WantMag > 0.1f)
	{
		WantYaw = YawOf(Want);
	}
	const float D = WrapPi(WantYaw - Yaw);
	Yaw = WrapPi(Yaw + FMath::Clamp(D, -14.f * Dt, 14.f * Dt));
	Pos += Vel * Dt;
}

void AIRPlayer::SimulateSkater(float Dt, const FIRIntent& In)
{
	// airborne (power-check victims)
	if (Action == EIRAction::Flying)
	{
		VZ -= 1500.f * Dt;
		Z += VZ * Dt;
		Pos += Vel * Dt;
		Vel *= FMath::Max(0.f, 1.f - Dt * 0.5f);
		Yaw = WrapPi(Yaw + SpinRate * Dt * 0.3f);
		if (Z <= 0.f && VZ < 0.f)
		{
			Z = 0.f;
			VZ = 0.f;
			StartAction(EIRAction::Down, 1.1f);
			if (Game)
			{
				Game->Sfx(TEXT("Sfx/Fall_Ice"), GetPos3(), 1.f);
				Game->Shake(0.35f);
				if (Game->FX) { Game->FX->IceSpray(GetPos3(), Vel.GetSafeNormal(), 2.f); }
			}
		}
		FVector2D N;
		if (ClampInside(Pos, SkaterRadius, N))
		{
			const float Vn = FVector2D::DotProduct(Vel, N);
			if (Vn < 0.f)
			{
				if (Game) { Game->OnPlayerHitBoards(this, -Vn); }
				Vel -= N * Vn * 1.4f;
			}
		}
		return;
	}

	float SpeedScale = 1.f;
	FIRIntent Use = In;
	switch (Action)
	{
	case EIRAction::Down:
		Use.MoveWorld = FVector2D::ZeroVector;
		Vel *= FMath::Max(0.f, 1.f - Dt * 2.5f);
		Pos += Vel * Dt;
		if (ActionTime >= ActionDuration)
		{
			StartAction(EIRAction::GetUp, kGetUpLen);
			PlayOneShot(A(TEXT("A_GetUp")), 1.f, 0.1f);
		}
		break;
	case EIRAction::GetUp:
		Vel *= FMath::Max(0.f, 1.f - Dt * 3.f);
		Pos += Vel * Dt;
		if (ActionTime >= ActionDuration) { Action = EIRAction::None; }
		break;
	case EIRAction::Dive:
		Vel *= FMath::Max(0.f, 1.f - Dt * 1.1f);
		Pos += Vel * Dt;
		if (ActionTime >= ActionDuration + 0.25f)
		{
			// the dive ends face-down and GetUp starts face-up: a longer blend rolls him over
			StartAction(EIRAction::GetUp, kGetUpLen + 0.15f);
			PlayOneShot(A(TEXT("A_GetUp")), 1.f, 0.35f);
		}
		break;
	case EIRAction::Celebrate:
	case EIRAction::Dejected:
		Integrate(Dt, Use, 0.55f);
		break;
	default:
		if (Action == EIRAction::ShotCharge) { SpeedScale = 0.72f; }
		if (Action == EIRAction::Check) { SpeedScale = 1.15f; }
		if (StunTime > 0.f) { Use.MoveWorld *= 0.2f; }
		if (Action == EIRAction::FaceoffReady)
		{
			Use.MoveWorld = FVector2D::ZeroVector;
			Vel *= FMath::Max(0.f, 1.f - Dt * 8.f);
		}
		Integrate(Dt, Use, SpeedScale);
		HandleActions(Dt, Use);
		break;
	}

	// spin deke: rotate the body quickly while keeping velocity
	if (Action == EIRAction::Spin)
	{
		Yaw = WrapPi(Yaw + SpinRate * Dt);
		if (ActionTime >= ActionDuration)
		{
			Action = EIRAction::None;
			if (Vel.SizeSquared() > 1.f) { Yaw = YawOf(Vel); }
		}
	}

	// boards
	FVector2D N;
	if (ClampInside(Pos, SkaterRadius, N))
	{
		const float Vn = FVector2D::DotProduct(Vel, N);
		if (Vn < 0.f)
		{
			if (-Vn > 520.f && Game) { Game->OnPlayerHitBoards(this, -Vn); }
			Vel -= N * Vn * 1.25f;
		}
	}
	// nets
	for (int32 S = -1; S <= 1; S += 2)
	{
		FVector2D NN;
		if (PushOutOfBox(Pos, SkaterRadius * 0.8f, NetBox(S), NN))
		{
			const float Vn = FVector2D::DotProduct(Vel, NN);
			if (Vn < 0.f) { Vel -= NN * Vn * 1.2f; }
		}
	}
}

void AIRPlayer::HandleActions(float Dt, const FIRIntent& In)
{
	const bool bPuck = HasPuck();
	const FIRRatings& R = Info.R;

	// ------------------------------------------------ start new actions
	if (CanAct() && StunTime <= 0.f && Game && Game->IsLive())
	{
		if (bPuck)
		{
			if (In.bShootPressed)
			{
				const bool bPower = In.bTurbo && (Turbo >= 0.45f || Rage > 0.f);
				StartAction(EIRAction::ShotCharge, 10.f);
				ShotChargeTime = 0.f;
				PendingShot = bPower ? EIRShotKind::Power : EIRShotKind::Wrist;
				if (bPower && Rage <= 0.f) { Turbo = FMath::Max(0.f, Turbo - 0.45f); }
				if (AnimInst) { AnimInst->PlayUpper(A(TEXT("A_SlapWindup")), bPower ? 1.8f : 1.f, 0.06f); }
				if (bPower && Game->FX) { Game->FX->PowerCharge(this); }
			}
			else if (In.bPassPressed)
			{
				StartAction(EIRAction::Pass, kPassLen);
				bAutoOneTimer = false;
				if (AnimInst) { AnimInst->PlayUpper(A(TEXT("A_Pass")), 1.f, 0.05f); }
			}
			else if (In.bSwitchPressed)
			{
				StartAction(EIRAction::Spin, kSpinLen);
				SpinRate = 2.f * PI / kSpinLen * (FMath::RandBool() ? 1.f : -1.f);
				Vel *= 1.08f;
				Game->OnSpin(this);
			}
			else if (In.bHookPressed)
			{
				Game->OnPassReleased(this, nullptr, true);
			}
		}
		else
		{
			if (In.bShootPressed && OneTimerWindow > 0.f)
			{
				StartAction(EIRAction::OneTimerWindup, OneTimerWindow + 0.25f);
				if (AnimInst) { AnimInst->PlayUpper(A(TEXT("A_SlapWindup")), 1.6f, 0.05f); }
			}
			else if (In.bShootPressed)
			{
				const bool bPower = In.bTurbo && Turbo >= 0.3f;
				StartAction(EIRAction::Check, bPower ? kPCheckLen : kCheckLen);
				PendingShot = bPower ? EIRShotKind::Power : EIRShotKind::None;
				if (bPower) { Turbo = FMath::Max(0.f, Turbo - 0.3f); }
				Vel += Forward() * (bPower ? 560.f : 380.f);
				PlayOneShot(A(bPower ? TEXT("A_PowerCheck") : TEXT("A_Check")), 1.f, 0.08f);
			}
			else if (In.bPassPressed && In.bTurbo && Turbo > 0.2f)
			{
				StartAction(EIRAction::Dive, kDiveLen);
				Turbo = FMath::Max(0.f, Turbo - 0.2f);
				Vel = Forward() * FMath::Max(Vel.Size(), 650.f);
				PlayOneShot(A(TEXT("A_Dive")), 1.f, 0.08f);
			}
			else if (In.bPassPressed)
			{
				StartAction(EIRAction::Poke, kPokeLen);
				if (AnimInst) { AnimInst->PlayUpper(A(TEXT("A_PokeCheck")), 1.f, 0.05f); }
			}
			else if (In.bHookPressed)
			{
				StartAction(EIRAction::Hook, kHookLen);
				PendingShot = In.bTurbo ? EIRShotKind::Power : EIRShotKind::None;   // turbo hook = trip
				if (AnimInst) { AnimInst->PlayUpper(A(TEXT("A_Hook")), 1.f, 0.05f); }
			}
		}
	}

	// ------------------------------------------------ advance current action
	switch (Action)
	{
	case EIRAction::ShotCharge:
	{
		ShotChargeTime += Dt;
		if (!bPuck)
		{
			Action = EIRAction::None;
			if (AnimInst) { AnimInst->StopUpper(0.1f); }
			break;
		}
		if (In.bPassPressed && ShotChargeTime < 0.18f && PendingShot != EIRShotKind::Power)
		{
			// Shoot + Pass chord: give-and-go one-timer pass
			StartAction(EIRAction::Pass, kPassLen);
			bAutoOneTimer = true;
			if (AnimInst) { AnimInst->PlayUpper(A(TEXT("A_Pass")), 1.2f, 0.04f); }
			break;
		}
		bool bRelease = false;
		if (PendingShot == EIRShotKind::Power)
		{
			bRelease = ShotChargeTime >= 0.24f;
		}
		else if (In.ShotCharge >= 0.f)
		{
			bRelease = ShotChargeTime >= In.ShotCharge;
		}
		else
		{
			bRelease = !In.bShoot || ShotChargeTime > 1.3f;
		}
		if (bRelease)
		{
			if (PendingShot != EIRShotKind::Power)
			{
				PendingShot = ShotChargeTime < 0.17f ? EIRShotKind::Wrist : EIRShotKind::Slap;
			}
			if (PendingShot == EIRShotKind::Wrist)
			{
				StartAction(EIRAction::Shot, kWristLen);
				if (AnimInst) { AnimInst->PlayUpper(A(TEXT("A_ShotWrist")), 1.15f, 0.04f, 0.08f); }
			}
			else
			{
				StartAction(EIRAction::Shot, kSlapLen);
				if (AnimInst) { AnimInst->PlayUpper(A(TEXT("A_SlapRelease")), 1.f, 0.03f); }
			}
		}
		break;
	}
	case EIRAction::Shot:
	{
		const float Evt = PendingShot == EIRShotKind::Wrist ? (kWristEvt - 0.08f) / 1.15f : kSlapEvt;
		if (!bActionEvent && ActionTime >= Evt)
		{
			bActionEvent = true;
			if (bPuck && Game)
			{
				const float Power = PendingShot == EIRShotKind::Slap ? FMath::Clamp((ShotChargeTime - 0.1f) / 0.65f, 0.f, 1.f) : 1.f;
				Game->OnShotReleased(this, PendingShot, Power);
			}
		}
		if (ActionTime >= ActionDuration * 0.85f)
		{
			Action = EIRAction::None;
			if (AnimInst) { AnimInst->StopUpper(0.15f); }
		}
		break;
	}
	case EIRAction::OneTimerWindup:
		if (ActionTime >= ActionDuration)
		{
			Action = EIRAction::None;
			if (AnimInst) { AnimInst->StopUpper(0.15f); }
		}
		break;
	case EIRAction::Pass:
		if (!bActionEvent && ActionTime >= kPassEvt)
		{
			bActionEvent = true;
			if (bPuck && Game)
			{
				AIRPlayer* T = In.PassTo ? In.PassTo : Game->ChoosePassTarget(this, In.MoveWorld, In.MoveWorld.SizeSquared() > 0.2f);
				Game->OnPassReleased(this, T, false);
			}
		}
		if (ActionTime >= ActionDuration * 0.8f)
		{
			Action = EIRAction::None;
			if (AnimInst) { AnimInst->StopUpper(0.15f); }
		}
		break;
	case EIRAction::Check:
	{
		const bool bPower = PendingShot == EIRShotKind::Power;
		const float Evt = bPower ? kPCheckEvt : kCheckEvt;
		// active window: from the event time for ~0.16 s
		if (ActionTime >= Evt && ActionTime < Evt + 0.16f && !bActionEvent && Game)
		{
			Game->OnCheck(this, bPower);   // sets bActionEvent when it connects
		}
		if (ActionTime >= ActionDuration)
		{
			Action = EIRAction::None;
			PendingShot = EIRShotKind::None;
		}
		break;
	}
	case EIRAction::Poke:
		if (!bActionEvent && ActionTime >= kPokeEvt)
		{
			bActionEvent = true;
			if (Game) { Game->OnPoke(this); }
		}
		if (ActionTime >= ActionDuration)
		{
			Action = EIRAction::None;
			if (AnimInst) { AnimInst->StopUpper(0.12f); }
		}
		break;
	case EIRAction::Hook:
		if (!bActionEvent && ActionTime >= kHookEvt)
		{
			bActionEvent = true;
			if (Game) { Game->OnHook(this, PendingShot == EIRShotKind::Power); }
		}
		if (ActionTime >= ActionDuration)
		{
			Action = EIRAction::None;
			PendingShot = EIRShotKind::None;
			if (AnimInst) { AnimInst->StopUpper(0.12f); }
		}
		break;
	case EIRAction::FaceoffWin:
		if (ActionTime >= 0.4f) { Action = EIRAction::None; }
		break;
	default:
		break;
	}
	(void)R;
}

void AIRPlayer::SimulateGoalie(float Dt, const FIRIntent& In)
{
	if (Action == EIRAction::Down || Action == EIRAction::Flying || Action == EIRAction::GetUp)
	{
		// goalies can get bowled over by power checks too
		if (Action == EIRAction::Flying)
		{
			VZ -= 1500.f * Dt; Z += VZ * Dt; Pos += Vel * Dt;
			if (Z <= 0.f && VZ < 0.f) { Z = 0.f; VZ = 0.f; StartAction(EIRAction::Down, 0.8f); }
		}
		else if (Action == EIRAction::Down)
		{
			Vel *= FMath::Max(0.f, 1.f - Dt * 3.f); Pos += Vel * Dt;
			if (ActionTime >= ActionDuration) { StartAction(EIRAction::GetUp, kGetUpLen); PlayOneShot(A(TEXT("A_GetUp"))); }
		}
		else if (ActionTime >= ActionDuration)
		{
			Action = EIRAction::None;
		}
		FVector2D N;
		ClampInside(Pos, GoalieRadius, N);
		return;
	}
	// goalie movement: In.MoveWorld is a desired velocity (cm/s / max)
	const float Max = MaxSpeed() * (Action == EIRAction::GoalieSave ? 0.4f : 1.f);
	const FVector2D WantV = In.MoveWorld * Max;
	const float Accel = 5200.f;
	const FVector2D Dv = WantV - Vel;
	const float DvLen = Dv.Size();
	if (DvLen > 0.f)
	{
		Vel += Dv / DvLen * FMath::Min(DvLen, Accel * Dt);
	}
	Pos += Vel * Dt;
	if (In.bFaceTarget)
	{
		const float WantYaw = YawOf(In.FaceTarget - Pos);
		Yaw = WrapPi(Yaw + FMath::Clamp(WrapPi(WantYaw - Yaw), -9.f * Dt, 9.f * Dt));
	}
	switch (Action)
	{
	case EIRAction::GoalieSave:
	case EIRAction::GoaliePoke:
		if (Action == EIRAction::GoaliePoke && !bActionEvent && ActionTime >= 0.18f)
		{
			bActionEvent = true;
			if (Game) { Game->OnPoke(this); }
		}
		if (ActionTime >= ActionDuration) { Action = EIRAction::None; }
		break;
	case EIRAction::GoalieCover:
		Vel = FVector2D::ZeroVector;
		if (ActionTime >= ActionDuration)
		{
			Action = EIRAction::None;
			if (Game) { Game->OnGoalieCleared(this); }
		}
		break;
	default:
		if (CanAct() && In.bPassPressed && !HasPuck())
		{
			StartAction(EIRAction::GoaliePoke, 0.5f);
			PlayOneShot(A(TEXT("A_GoaliePoke")), 1.f, 0.06f);
		}
		break;
	}
	FVector2D N;
	ClampInside(Pos, GoalieRadius, N);
}

void AIRPlayer::SimulateReferee(float Dt, const FIRIntent& In)
{
	if (Action == EIRAction::RefDrop)
	{
		Vel = FVector2D::ZeroVector;
		if (ActionTime >= 1.0f) { Action = EIRAction::None; }
		return;
	}
	Integrate(Dt, In, 1.f);
	FVector2D N;
	ClampInside(Pos, SkaterRadius, N);
}

// ------------------------------------------------------------------------------------------------ fights

void AIRPlayer::EnterFight(AIRPlayer* Opponent)
{
	FightOpponent = Opponent;
	FightHealth = 1.f;
	Stamina = 1.f;
	StartAction(EIRAction::FightIdle, 1e6f);
	Vel = FVector2D::ZeroVector;
	if (AnimInst)
	{
		AnimInst->StopUpper(0.05f);
		AnimInst->StickScale = 0.f;
		AnimInst->Play(A(TEXT("A_FightIdle")), true, 1.f, 0.2f);
	}
}

void AIRPlayer::LeaveFight()
{
	FightOpponent = nullptr;
	Action = EIRAction::None;
	Anger = 0.f;
	if (AnimInst) { AnimInst->StickScale = 1.f; }
}

void AIRPlayer::FightTakeHit(float Damage, bool bUppercut)
{
	if (Action == EIRAction::FightKO)
	{
		return;
	}
	const bool bBlocking = Action == EIRAction::FightBlock;
	FightHealth -= bBlocking ? Damage * 0.22f : Damage;
	if (FightHealth <= 0.f)
	{
		FightKO();
		return;
	}
	if (!bBlocking)
	{
		StartAction(EIRAction::FightHit, bUppercut ? 0.7f : 0.45f);
		PlayOneShot(A(TEXT("A_FightHit")), bUppercut ? 0.75f : 1.f, 0.04f);
	}
}

void AIRPlayer::FightKO()
{
	FightHealth = 0.f;
	StartAction(EIRAction::FightKO, 1e6f);
	PlayOneShot(A(TEXT("A_FightKO")), 1.f, 0.08f);
}

void AIRPlayer::SimulateFight(float Dt, const FIRIntent& In)
{
	AIRPlayer* Opp = FightOpponent.Get();
	Stamina = FMath::Min(1.f, Stamina + Dt * 0.18f);
	if (Opp && Action != EIRAction::FightKO)
	{
		const FVector2D To = Opp->Pos - Pos;
		const float Dist = To.Size();
		const FVector2D Dir = Dist > 1.f ? To / Dist : Forward();
		Yaw = WrapPi(Yaw + FMath::Clamp(WrapPi(YawOf(Dir) - Yaw), -10.f * Dt, 10.f * Dt));
		// keep ~105 cm apart, strafe sideways with the stick
		const FVector2D Side(-Dir.Y, Dir.X);
		const float Lateral = FVector2D::DotProduct(In.MoveWorld, Side);
		FVector2D WantV = Side * Lateral * 160.f + Dir * (Dist - 105.f) * 4.f;
		if (Action == EIRAction::FightHit) { WantV -= Dir * 160.f; }
		Vel = FMath::Vector2DInterpTo(Vel, WantV, Dt, 8.f);
		Pos += Vel * Dt;
	}
	FVector2D N;
	ClampInside(Pos, SkaterRadius, N);

	switch (Action)
	{
	case EIRAction::FightIdle:
		if (AnimInst && !AnimInst->IsFinished() == false) { AnimInst->Play(A(TEXT("A_FightIdle")), true, 1.f, 0.15f); }
		if (In.bSwitchPressed || (In.bHook && In.bTurbo))
		{
			StartAction(EIRAction::FightBlock, 0.5f);
			PlayOneShot(A(TEXT("A_FightBlock")), 1.f, 0.05f);
		}
		else if (In.bShootPressed && In.bTurbo && Stamina >= 0.4f)
		{
			StartAction(EIRAction::FightAttack, 0.7f);
			PendingShot = EIRShotKind::Power;
			Stamina -= 0.4f;
			PlayOneShot(A(TEXT("A_FightUppercut")), 1.f, 0.05f);
		}
		else if (In.bShootPressed && Stamina >= 0.18f)
		{
			StartAction(EIRAction::FightAttack, 0.55f);
			PendingShot = EIRShotKind::Slap;
			Stamina -= 0.18f;
			PlayOneShot(A(TEXT("A_FightPunch")), 1.f, 0.05f);
		}
		else if (In.bPassPressed && Stamina >= 0.08f)
		{
			StartAction(EIRAction::FightAttack, 0.35f);
			PendingShot = EIRShotKind::Wrist;
			Stamina -= 0.08f;
			PlayOneShot(A(TEXT("A_FightJab")), 1.f, 0.04f);
		}
		else if (In.bHookPressed && Stamina >= 0.12f)
		{
			StartAction(EIRAction::FightAttack, 0.6f);
			PendingShot = EIRShotKind::Pass;
			Stamina -= 0.12f;
			PlayOneShot(A(TEXT("A_FightGrab")), 1.f, 0.05f);
		}
		break;
	case EIRAction::FightAttack:
	{
		const float Evt = PendingShot == EIRShotKind::Power ? 0.32f : PendingShot == EIRShotKind::Slap ? 0.25f : PendingShot == EIRShotKind::Pass ? 0.25f : 0.12f;
		if (!bActionEvent && ActionTime >= Evt)
		{
			bActionEvent = true;
			if (Game)
			{
				const int32 Kind = PendingShot == EIRShotKind::Wrist ? 0 : PendingShot == EIRShotKind::Slap ? 1 : PendingShot == EIRShotKind::Power ? 2 : 3;
				Game->FightPunch(this, Kind);
			}
		}
		if (ActionTime >= ActionDuration)
		{
			StartAction(EIRAction::FightIdle, 1e6f);
			if (AnimInst) { AnimInst->Play(A(TEXT("A_FightIdle")), true, 1.f, 0.12f); }
		}
		break;
	}
	case EIRAction::FightHit:
	case EIRAction::FightBlock:
		if (ActionTime >= ActionDuration)
		{
			StartAction(EIRAction::FightIdle, 1e6f);
			if (AnimInst) { AnimInst->Play(A(TEXT("A_FightIdle")), true, 1.f, 0.12f); }
		}
		break;
	default:
		break;
	}
}

// ------------------------------------------------------------------------------------------------ events

void AIRPlayer::TakeHit(AIRPlayer* From, float Power, bool bPowerCheck, FVector2D Dir)
{
	LastHitBy = From;
	LastHitTime = Game ? Game->GameTime : 0.f;
	const float FrenzyMul = (Game && Game->Opt.bFightFrenzy) ? 3.f : 1.f;
	Anger = FMath::Min(1.2f, Anger + (bPowerCheck ? 0.48f : 0.23f) * FrenzyMul * FMath::Lerp(0.75f, 1.25f, Info.R.Fight / 10.f));
	if (AnimInst) { AnimInst->StopUpper(0.05f); }
	PendingShot = EIRShotKind::None;
	if (bPowerCheck || (IsGoalie() && Power > 1.2f))
	{
		StartAction(EIRAction::Flying, 10.f);
		VZ = IsGoalie() ? 330.f : 560.f;
		Vel = Dir * (IsGoalie() ? 520.f : 980.f) + Vel * 0.2f;
		SpinRate = 9.f;
		PlayOneShot(A(TEXT("A_Flip")), 1.f, 0.05f);
		return;
	}
	const float Balance = 0.28f + Power * 0.45f - (Info.R.Check - 5) * 0.035f - (Info.Bulk - 1.f) * 1.2f;
	if (FMath::FRand() < Balance || (HasPuck() && FMath::FRand() < 0.5f))
	{
		StartAction(EIRAction::Down, kFallLen + 0.35f);
		Vel = Dir * 620.f + Vel * 0.3f;
		PlayOneShot(A(TEXT("A_HitFall")), 1.f, 0.06f);
	}
	else
	{
		Action = EIRAction::None;
		Vel += Dir * 420.f;
		StunTime = 0.4f;
		if (AnimInst) { AnimInst->PlayUpper(A(TEXT("A_FightHit")), 1.2f, 0.04f); }
	}
}

void AIRPlayer::Trip(AIRPlayer* From)
{
	LastHitBy = From;
	Anger = FMath::Min(1.2f, Anger + 0.15f);
	StartAction(EIRAction::Down, kFallLen + 0.2f);
	Vel = Vel * 0.75f;
	PlayOneShot(A(TEXT("A_Dive")), 1.3f, 0.06f);
}

void AIRPlayer::StartCelebrate(int32 Variant)
{
	StartAction(EIRAction::Celebrate, 3.f);
	static const TCHAR* Names[] = { TEXT("A_Celebrate1"), TEXT("A_Celebrate2"), TEXT("A_Celebrate3") };
	PlayOneShot(A(Names[FMath::Clamp(Variant, 0, 2)]), 1.f, 0.15f);
}

void AIRPlayer::StartDejected()
{
	StartAction(EIRAction::Dejected, 3.f);
	if (AnimInst) { AnimInst->StopUpper(0.1f); AnimInst->Play(A(TEXT("A_Dejected")), true, 1.f, 0.3f); }
}

void AIRPlayer::PlayGoalieSave(const FVector& Local, bool bCatch)
{
	// Local: X = depth toward shooter, Y = goalie's right (+) / left (-), Z = height
	StartAction(EIRAction::GoalieSave, 0.7f);
	const TCHAR* Clip = TEXT("A_GoalieButterfly");
	if (Local.Z > 70.f)
	{
		Clip = Local.Y < 0.f ? TEXT("A_GoalieGloveHigh") : TEXT("A_GoalieBlockerHigh");
	}
	else if (FMath::Abs(Local.Y) > 70.f)
	{
		Clip = Local.Y < 0.f ? TEXT("A_GoalieDiveL") : TEXT("A_GoalieDiveR");
		ActionDuration = 0.95f;
	}
	else if (FMath::Abs(Local.Y) > 30.f)
	{
		Clip = Local.Y < 0.f ? TEXT("A_GoaliePadL") : TEXT("A_GoaliePadR");
	}
	PlayOneShot(A(Clip), 1.25f, 0.04f);
	(void)bCatch;
}

void AIRPlayer::PlayGoalieCover()
{
	StartAction(EIRAction::GoalieCover, 0.75f);
	PlayOneShot(A(TEXT("A_GoalieCover")), 1.f, 0.08f);
}

void AIRPlayer::BeginFaceoff(FVector2D Spot, float FaceYaw)
{
	ResetForFaceoff();
	Teleport(Spot, FaceYaw);
	if (Role == EIRRole::Skater)
	{
		StartAction(EIRAction::FaceoffReady, 1e6f);
		if (AnimInst) { AnimInst->Play(A(TEXT("A_FaceoffReady")), true, 1.f, 0.1f); }
	}
}

void AIRPlayer::FaceoffWin()
{
	StartAction(EIRAction::FaceoffWin, 0.4f);
	PlayOneShot(A(TEXT("A_FaceoffWin")), 1.f, 0.05f);
}

// ------------------------------------------------------------------------------------------------ visuals

void AIRPlayer::SelectLocomotionAnim(float Dt)
{
	if (!AnimInst)
	{
		return;
	}
	const float Sp = Vel.Size();
	if (Role == EIRRole::Goalie)
	{
		if (Action == EIRAction::None)
		{
			const float Lat = FVector2D::DotProduct(Vel, Right());
			if (FMath::Abs(Lat) > 90.f)
			{
				AnimInst->Play(A(Lat > 0.f ? TEXT("A_GoalieShuffleR") : TEXT("A_GoalieShuffleL")), true, FMath::Clamp(FMath::Abs(Lat) / 300.f, 0.6f, 1.6f), 0.15f);
			}
			else
			{
				AnimInst->Play(A(TEXT("A_GoalieReady")), true, 1.f, 0.2f);
			}
		}
		return;
	}
	const bool bLoco = Action == EIRAction::None || Action == EIRAction::ShotCharge || Action == EIRAction::Shot || Action == EIRAction::Pass
		|| Action == EIRAction::Poke || Action == EIRAction::Hook || Action == EIRAction::OneTimerWindup || Action == EIRAction::Stop || Action == EIRAction::Spin
		|| (Role == EIRRole::Referee && Action != EIRAction::RefDrop);
	if (!bLoco)
	{
		return;
	}
	if (bStopping)
	{
		AnimInst->Play(A(TEXT("A_Stop")), false, 1.f, 0.1f);
		return;
	}
	if (Sp < 70.f)
	{
		AnimInst->Play(A(TEXT("A_Idle")), true, 1.f, 0.25f);
	}
	else if (bBackward)
	{
		AnimInst->Play(A(TEXT("A_SkateBack")), true, FMath::Clamp(Sp / 500.f, 0.6f, 1.5f), 0.2f);
	}
	else if (bTurboActive && Sp > 550.f)
	{
		AnimInst->Play(A(TEXT("A_SkateTurbo")), true, FMath::Clamp(Sp / 1200.f, 0.75f, 1.35f), 0.18f);
	}
	else if (HasPuck())
	{
		AnimInst->Play(A(TEXT("A_Carry")), true, FMath::Clamp(Sp / 780.f, 0.65f, 1.35f), 0.2f);
	}
	else if (Sp > 330.f && LastIntent.MoveWorld.SizeSquared() > 0.04f)
	{
		AnimInst->Play(A(TEXT("A_Skate")), true, FMath::Clamp(Sp / 760.f, 0.6f, 1.4f), 0.2f);
	}
	else
	{
		AnimInst->Play(A(TEXT("A_Glide")), true, 1.f, 0.3f);
	}
}

void AIRPlayer::UpdateVisuals(float Dt)
{
	SetActorLocationAndRotation(FVector(Pos.X, Pos.Y, Z), FRotator(0.f, FMath::RadiansToDegrees(Yaw), 0.f));
	const float Sp = Vel.Size();
	StrideTimer += Dt * FMath::Max(1.f, Sp / 120.f);

	// lean into turns
	YawRate = WrapPi(Yaw - LastYaw) / FMath::Max(Dt, 1e-3f);
	LastYaw = Yaw;
	const float TargetLean = (Role == EIRRole::Skater && Action == EIRAction::None) ? FMath::Clamp(YawRate * Sp * 0.0045f, -20.f, 20.f) : 0.f;
	LeanSmoothed = FMath::FInterpTo(LeanSmoothed, TargetLean, Dt, 8.f);

	if (AnimInst)
	{
		SelectLocomotionAnim(Dt);
		AnimInst->HeadScale = HeadScale;
		AnimInst->Lean = LeanSmoothed;
		AnimInst->Pitch = bTurboActive ? 6.f : 0.f;
		if (Role == EIRRole::Referee) { AnimInst->StickScale = 0.f; }
	}
	else
	{
		// placeholder bob + tilt
		for (UStaticMeshComponent* C : Placeholder)
		{
			C->SetRelativeRotation(FRotator(0.f, 0.f, -LeanSmoothed));
		}
		if (Action == EIRAction::Down || Action == EIRAction::Flying || Action == EIRAction::FightKO)
		{
			SetActorRotation(FRotator(80.f, FMath::RadiansToDegrees(Yaw), 0.f));
		}
	}

	// ring under the feet: human color with turbo arc, faint team color for CPU
	if (RingMID && Ring)
	{
		const bool bHuman = HumanIndex >= 0;
		FLinearColor C = RingColor;
		float Alpha = bHuman ? 1.f : 0.32f;
		if (Role == EIRRole::Goalie) { Alpha = GoalieGlow > 0.95f ? 0.9f : 0.0f; C = FLinearColor(1.f, 0.85f, 0.2f); }
		RingMID->SetVectorParameterValue(TEXT("Color"), C);
		RingMID->SetScalarParameterValue(TEXT("Alpha"), Alpha);
		RingMID->SetScalarParameterValue(TEXT("Turbo"), bHuman ? Turbo : 0.f);
		RingMID->SetScalarParameterValue(TEXT("Pulse"), bHuman && HasPuck() ? 1.f : 0.f);
		Ring->SetVisibility(Alpha > 0.01f && Z < 30.f && Role != EIRRole::Referee);
		Ring->SetWorldLocation(FVector(Pos.X, Pos.Y, 0.6f));
	}
	if (Shadow)
	{
		Shadow->SetWorldLocation(FVector(Pos.X, Pos.Y, 0.3f));
	}

	// skating feedback: stride sounds and ice spray
	if (Game && Role != EIRRole::Referee && Z <= 0.f)
	{
		if (Sp > 300.f && (Action == EIRAction::None || Action == EIRAction::ShotCharge))
		{
			FootstepPhase += Dt * Sp / (bTurboActive ? 260.f : 330.f);
			if (FootstepPhase > 1.f)
			{
				FootstepPhase -= 1.f;
				Game->Sfx(TEXT("Sfx/Skate_Stride"), GetPos3(), FMath::Clamp(Sp / 1200.f, 0.15f, 0.55f), FMath::FRandRange(0.92f, 1.08f));
			}
		}
		if (bStopping && !bWasStopping)
		{
			Game->Sfx(TEXT("Sfx/Skate_Stop"), GetPos3(), FMath::Clamp(Sp / 900.f, 0.35f, 1.f), FMath::FRandRange(0.95f, 1.05f));
			if (Game->FX) { Game->FX->IceSpray(GetPos3() + FVector(Forward() * 25.f, 0.f), Vel.GetSafeNormal(), 2.2f); }
		}
		if (bStopping)
		{
			SprayTimer -= Dt;
			if (SprayTimer <= 0.f)
			{
				SprayTimer = 0.035f;
				if (Game->FX) { Game->FX->IceSpray(GetPos3() + FVector(Forward() * 20.f, 0.f), Vel.GetSafeNormal(), FMath::Clamp(Sp / 700.f, 0.4f, 1.5f)); }
			}
		}
	}
	bWasStopping = bStopping;
}

void AIRPlayer::FireActionEvent()
{
}
