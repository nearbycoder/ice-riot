// Live-play rules and interactions for AIRGameMode: puck control, shots, passes, hits, fights, goals, replays.
#include "IRGameMode.h"
#include "IceRiot.h"
#include "IRRink.h"
#include "IRCamera.h"
#include "IRAudio.h"
#include "IRFX.h"
#include "IRArena.h"
#include "IRAnimInstance.h"
#include "IRRoster.h"
#include "Animation/AnimSequence.h"

using namespace IRRink;

namespace
{
	float Gauss() { return FMath::Clamp((FMath::FRand() + FMath::FRand() + FMath::FRand() - 1.5f) * 1.6f, -2.5f, 2.5f); }
}

// ------------------------------------------------------------------------------------------------ live tick

void AIRGameMode::TickLive(float Dt)
{
	if (Mode != EIRMode::Practice)
	{
		Clock -= Dt;
		if (!bTwoMinuteCalled && Clock < 120.f && Opt.PeriodSeconds > 150 && Period == 3)
		{
			bTwoMinuteCalled = true;
			Announce(TEXT("VO_TwoMinutes"), 1.5f);
		}
		if (!bLastMinuteCalled && Clock < 60.f && Period >= 3 && !bOvertime)
		{
			bLastMinuteCalled = true;
			Announce(TEXT("VO_LastMinute"), 1.5f);
			Callout(TEXT("LAST MINUTE!"), FString(), FLinearColor(1.f, 0.3f, 0.2f), 2.f, 2);
		}
		if (Clock <= 0.f)
		{
			Clock = 0.f;
			EndPeriod();
			return;
		}
	}
	UpdateCatchup();
	HandleHumans(Dt);

	// intents
	TArray<AIRPlayer*> Players = AllPlayers();
	TArray<FIRIntent> Intents;
	Intents.SetNum(Players.Num());
	for (int32 i = 0; i < Players.Num(); ++i)
	{
		AIRPlayer* P = Players[i];
		if (P->IsGoalie()) { Intents[i] = ThinkGoalie(P, Dt); }
		else if (P->HumanIndex >= 0 && Humans.IsValidIndex(P->HumanIndex))
		{
			FIRHuman& H = Humans[P->HumanIndex];
			Intents[i] = H.Bind.Source == EIRSource::Autopilot ? ThinkAI(P, Dt) : H.LastIntent;
		}
		else { Intents[i] = ThinkAI(P, Dt); }
	}
	for (int32 i = 0; i < Players.Num(); ++i)
	{
		Players[i]->Simulate(Dt, Intents[i]);
		if (Phase != EIRMatchPhase::Live) { return; }   // a fight or whistle can start mid-step
	}
	ResolveCollisions(Dt);

	// puck
	if (Puck)
	{
		if (AIRPlayer* C = Puck->Carrier)
		{
			const FVector Blade = C->BladePos();
			Puck->Pos = FMath::VInterpTo(Puck->Pos, Blade, Dt, 30.f);
			Puck->Pos.Z = PuckHalfHeight;
			Puck->Vel = FVector(C->Vel, 0.f);
			// carried puck can't go through the boards
			FVector2D P2(Puck->Pos.X, Puck->Pos.Y), N;
			if (ClampInside(P2, PuckRadius + 2.f, N)) { Puck->Pos.X = P2.X; Puck->Pos.Y = P2.Y; }
			if (C->bBlazing && FX && FMath::FRand() < 0.5f) { FX->FireTrail(Puck->Pos, Puck->Vel); }
		}
		else
		{
			TArray<FIRPuckHit> Hits;
			Puck->Simulate(Dt, Hits);
			HandlePuckHits(Hits);
			if (Phase != EIRMatchPhase::Live) { return; }
			// trails
			const float Sp = Puck->Vel.Size();
			if (FX && Sp > 1400.f)
			{
				if (Puck->bOnFire) { FX->FireTrail(Puck->Pos, Puck->Vel); }
				else if (Opt.bPuckStreak) { FX->Streak(Puck->Pos, FLinearColor(0.55f, 0.25f, 1.f, 0.9f) * 1.5f, FMath::Clamp(Sp / 120.f, 10.f, 30.f)); }
			}
		}
		UpdatePuckInteractions(Dt);
	}
	RecordReplay();

	// practice: reset the puck after each attempt
	if (Mode == EIRMode::Practice && Puck && !Puck->Carrier && (Puck->FlightTime > 3.f || Puck->bFrozen) && PhaseTime > 1.f)
	{
		AIRPlayer* S = Skaters[0].Num() ? Skaters[0][0] : nullptr;
		if (S)
		{
			const FVector2D Spot(FMath::FRandRange(400.f, 1300.f) * AttackSign(0), FMath::FRandRange(-600.f, 600.f));
			S->ResetForFaceoff();
			S->Teleport(Spot - FVector2D(AttackSign(0) * 150.f, 0.f), AttackSign(0) > 0 ? 0.f : PI);
			Puck->bFrozen = false;
			Puck->PlaceAt(FVector(Spot, PuckHalfHeight));
			Puck->FlightTime = 0.f;
			PhaseTime = 0.f;
		}
	}
}

void AIRGameMode::ResolveCollisions(float Dt)
{
	TArray<AIRPlayer*> Ps = AllPlayers();
	for (int32 i = 0; i < Ps.Num(); ++i)
	{
		AIRPlayer* A = Ps[i];
		if (A->IsReferee() || A->Z > 40.f) { continue; }
		for (int32 j = i + 1; j < Ps.Num(); ++j)
		{
			AIRPlayer* B = Ps[j];
			if (B->IsReferee() || B->Z > 40.f) { continue; }
			if (A->IsInFight() && B->IsInFight()) { continue; }
			const float RA = A->IsGoalie() ? GoalieRadius : SkaterRadius;
			const float RB = B->IsGoalie() ? GoalieRadius : SkaterRadius;
			const FVector2D D = B->Pos - A->Pos;
			const float Len = D.Size();
			const float Min = RA + RB;
			if (Len >= Min || Len < 1e-3f) { continue; }
			const FVector2D N = D / Len;
			const float Push = (Min - Len);
			// goalies are heavy, players lying on the ice don't block much
			float WA = A->IsGoalie() ? 0.15f : (A->IsDown() ? 0.8f : 0.5f);
			float WB = B->IsGoalie() ? 0.15f : (B->IsDown() ? 0.8f : 0.5f);
			const float Sum = WA + WB;
			WA /= Sum; WB /= Sum;
			A->Pos -= N * Push * WA;
			B->Pos += N * Push * WB;
			const float Rel = FVector2D::DotProduct(B->Vel - A->Vel, N);
			if (Rel < 0.f)
			{
				const FVector2D Imp = N * Rel * 0.9f;
				A->Vel += Imp * WB * 2.f * 0.5f;
				B->Vel -= Imp * WA * 2.f * 0.5f;
				// incidental bumps between opponents at speed build anger and knock pucks loose
				if (A->Team != B->Team && -Rel > 750.f && !A->IsGoalie() && !B->IsGoalie())
				{
					Sfx(TEXT("Sfx/Check"), FVector((A->Pos + B->Pos) * 0.5f, 100.f), 0.5f);
					A->Anger = FMath::Min(1.2f, A->Anger + 0.05f);
					B->Anger = FMath::Min(1.2f, B->Anger + 0.05f);
				}
			}
		}
	}
}

// ------------------------------------------------------------------------------------------------ puck interactions

void AIRGameMode::UpdatePuckInteractions(float Dt)
{
	if (!Puck || Phase != EIRMatchPhase::Live)
	{
		return;
	}
	if (Puck->Carrier)
	{
		LooseTime = 0.f;
		return;
	}
	if (Puck->bFrozen)
	{
		return;
	}
	LooseTime += Dt;
	const FVector PP = Puck->Pos;
	const FVector2D P2(PP.X, PP.Y);
	const float Sp = FVector2D(Puck->Vel.X, Puck->Vel.Y).Size();

	// ---- pre-rolled goalie save: resolve when the puck reaches the goalie
	if (AIRPlayer* G = Puck->SaveGoalie.Get())
	{
		const int32 Sign = Puck->ShotSign;
		const float GoalieDepth = (GoalLineX * Sign - G->Pos.X) * Sign;  // distance of the goalie in front of the goal line
		const float PuckDepth = (GoalLineX * Sign - PP.X) * Sign;
		if (PuckDepth <= GoalieDepth + 35.f && PuckDepth > -10.f)
		{
			Puck->SaveGoalie = nullptr;
			OnSave(G, Puck->bSaveCatch, G->GoalieGlow >= 1.f);
			return;
		}
	}

	// ---- one-timers: armed receiver smacks the puck as it arrives
	for (AIRPlayer* P : AllPlayers())
	{
		if (P->IsGoalie() || P->IsReferee() || !P->CanPlayPuck())
		{
			continue;
		}
		const bool bArmed = P->Action == EIRAction::OneTimerWindup || (P->bAutoOneTimer && P->OneTimerWindow > 0.f);
		if (bArmed && PP.Z < 50.f && FVector2D::Distance(P->StickReachPoint(), P2) < 105.f && Puck->LastTouch != P)
		{
			Puck->SetCarried(P);
			P->bAutoOneTimer = false;
			P->OneTimerWindow = 0.f;
			P->StartAction(EIRAction::Shot, 0.55f);
			P->bActionEvent = true;
			P->PendingShot = EIRShotKind::OneTimer;
			if (P->AnimInst) { P->AnimInst->PlayUpper(P->A(TEXT("A_OneTimer")), 1.2f, 0.03f, 0.12f); }
			// face the net instantly for the shot
			const FVector2D ToNet = FVector2D(GoalLineX * AttackSign(P->Team), 0.f) - P->Pos;
			P->Yaw = FMath::Atan2(ToNet.Y, ToNet.X);
			OnShotReleased(P, EIRShotKind::OneTimer, 1.f);
			return;
		}
	}

	// ---- pickups / interceptions / deflections
	AIRPlayer* Best = nullptr;
	float BestD = 1e9f;
	for (AIRPlayer* P : AllPlayers())
	{
		if (P->IsReferee() || !P->CanPlayPuck())
		{
			continue;
		}
		if (P == Puck->LastTouch && Puck->FlightTime < 0.25f)
		{
			continue;
		}
		const bool bGoalie = P->IsGoalie();
		const float Reach = bGoalie ? 75.f : (P->Action == EIRAction::Dive ? 110.f : 70.f);
		const float MaxZ = bGoalie ? 140.f : 45.f;
		if (PP.Z > MaxZ)
		{
			continue;
		}
		FVector2D Pt = bGoalie ? P->Pos : P->StickReachPoint();
		float D = FVector2D::Distance(Pt, P2);
		if (!bGoalie)
		{
			// the body also stops pucks
			D = FMath::Min(D, FVector2D::Distance(P->Pos, P2) + 15.f);
		}
		if (D < Reach && D < BestD)
		{
			// fast pucks (shots, hard passes) are harder to corral for the other team
			if (Sp > 1600.f && Puck->LastTouch && Puck->LastTouch->Team != P->Team && !bGoalie)
			{
				const float Chance = FMath::Clamp(1.5f - Sp / 2400.f, 0.1f, 0.9f) * (P->Action == EIRAction::Dive ? 1.6f : 1.f) * Dt * 18.f;
				if (FMath::FRand() > Chance)
				{
					// deflection off the body/stick
					if (FMath::FRand() < Dt * 10.f)
					{
						const FVector2D N = (P2 - P->Pos).GetSafeNormal();
						FVector2D V(Puck->Vel.X, Puck->Vel.Y);
						V = (V - N * 2.f * FVector2D::DotProduct(V, N)) * 0.45f + N * 200.f;
						Puck->Vel = FVector(V, FMath::FRandRange(0.f, 200.f));
						Puck->SaveGoalie = nullptr;
						Puck->LastTouch = P;
						Puck->FlightTime = 0.f;
						Sfx(TEXT("Sfx/Stick_Clack"), PP, 0.7f);
						if (P->Action == EIRAction::Dive) { Callout(TEXT("BLOCKED!"), FString(), FLinearColor(0.6f, 0.9f, 1.f), 1.2f, 1); }
					}
					continue;
				}
			}
			BestD = D;
			Best = P;
		}
	}
	if (Best)
	{
		AIRPlayer* Prev = Puck->LastTouch;
		const bool bShot = Puck->Kind != EIRShotKind::None && Puck->Kind != EIRShotKind::Pass;
		if (Best->IsGoalie())
		{
			// a goalie who gets the puck freezes it briefly, then clears it
			if (bShot && Prev && Prev->Team != Best->Team)
			{
				OnSave(Best, true, false);
				return;
			}
			Puck->SetCarried(Best);
			Best->PlayGoalieCover();
			return;
		}
		Puck->SetCarried(Best);
		Puck->SaveGoalie = nullptr;
		Best->OneTimerWindow = 0.f;
		Best->bAutoOneTimer = false;
		Sfx(TEXT("Sfx/Stick_Handle"), PP, 0.5f);
		if (Prev && Prev->Team != Best->Team && Puck->Kind == EIRShotKind::Pass)
		{
			Best->Stats.Steals++;
			Callout(TEXT("PICKED OFF!"), Best->Info.Last.ToUpper(), TeamInfo[Best->Team].Primary, 1.2f, 1);
		}
		// auto-switch a human to the CPU teammate who caught his pass
		if (Opt.bAutoSwitch && Best->HumanIndex < 0 && Prev && Prev->Team == Best->Team && Prev->HumanIndex >= 0 && Humans.IsValidIndex(Prev->HumanIndex))
		{
			FIRHuman& H = Humans[Prev->HumanIndex];
			Prev->HumanIndex = -1;
			Prev->RingColor = TeamInfo[Prev->Team].Primary;
			Best->HumanIndex = int32(&H - Humans.GetData());
			Best->LastHumanIndex = Best->HumanIndex;
			Best->RingColor = H.Color;
			H.Controlled = Best;
		}
		Crowd(0.04f);
		return;
	}

	// a loose puck nobody can reach for a long time (pinned in a corner): whistle
	if (LooseTime > 9.f && Sp < 30.f)
	{
		HandleWhistle(NearestDot(P2), TEXT(""));
	}
}

void AIRGameMode::HandlePuckHits(const TArray<FIRPuckHit>& Hits)
{
	for (const FIRPuckHit& H : Hits)
	{
		const float V = FMath::Clamp(H.Speed / 2500.f, 0.15f, 1.f);
		switch (H.Type)
		{
		case EIRPuckEvent::Boards:
			Sfx(TEXT("Sfx/Puck_Boards"), H.Location, V);
			if (H.Speed > 2200.f) { Shake(0.12f); if (Arena) { Arena->FlashGlass(0.3f); } }
			if (Puck) { Puck->SaveGoalie = nullptr; }
			break;
		case EIRPuckEvent::Glass:
			Sfx(TEXT("Sfx/Puck_Glass"), H.Location, V);
			if (Arena) { Arena->FlashGlass(0.5f); }
			if (Puck) { Puck->SaveGoalie = nullptr; }
			break;
		case EIRPuckEvent::Post:
		case EIRPuckEvent::Crossbar:
			Sfx(H.Type == EIRPuckEvent::Post ? TEXT("Sfx/Puck_Post") : TEXT("Sfx/Puck_Crossbar"), H.Location, 1.f);
			if (FX) { FX->Sparks(H.Location, FLinearColor(1.f, 0.8f, 0.4f, 1.f) * 2.f, 14, 500.f); }
			if (H.Speed > 1000.f)
			{
				Announce(TEXT("VO_Post"), 1.2f);
				Crowd(0.3f, TEXT("Crowd_Ooh"));
				Callout(H.Type == EIRPuckEvent::Post ? TEXT("POST!") : TEXT("CROSSBAR!"), FString(), FLinearColor(0.85f, 0.85f, 0.9f), 1.2f, 1);
			}
			if (Puck) { Puck->SaveGoalie = nullptr; }
			break;
		case EIRPuckEvent::NetInside:
			Sfx(TEXT("Sfx/Net_Ripple"), H.Location, 0.8f);
			break;
		case EIRPuckEvent::NetOutside:
			Sfx(TEXT("Sfx/Puck_Boards"), H.Location, V * 0.6f);
			if (Puck) { Puck->SaveGoalie = nullptr; }
			break;
		case EIRPuckEvent::Ice:
			Sfx(TEXT("Sfx/Puck_Ice"), H.Location, V * 0.5f);
			break;
		case EIRPuckEvent::OutOfPlay:
			Crowd(0.1f, TEXT("Crowd_Aah"));
			HandleWhistle(NearestDot(FVector2D(H.Location.X, H.Location.Y)), TEXT("OUT OF PLAY"));
			return;
		case EIRPuckEvent::Goal:
			if (Phase == EIRMatchPhase::Live)
			{
				OnGoal(H.GoalSign);
				return;
			}
			break;
		default:
			break;
		}
	}
}

void AIRGameMode::HandleWhistle(FVector2D Spot, const FString& Reason)
{
	Sfx(TEXT("Sfx/Whistle_Short"), FVector(Spot, 0.f), 0.9f);
	PendingFaceoff = Spot;
	if (!Reason.IsEmpty()) { Callout(Reason, FString(), FLinearColor(0.9f, 0.9f, 0.95f), 1.2f, 1); }
	if (Puck) { Puck->SetCarried(nullptr); Puck->bFrozen = true; }
	SetPhase(EIRMatchPhase::Whistle);
}

// ------------------------------------------------------------------------------------------------ face-offs

void AIRGameMode::OnFaceoffDrop()
{
	if (Phase != EIRMatchPhase::Faceoff || !Puck)
	{
		return;
	}
	// the two centers race for it: humans by their button timing, CPU by reaction time
	AIRPlayer* C[2] = { Skaters[0].Num() ? Skaters[0][0] : nullptr, Skaters[1].Num() ? Skaters[1][0] : nullptr };
	if (!C[0] || !C[1])
	{
		// practice or broken lineup: give it to whoever exists
		AIRPlayer* W = C[0] ? C[0] : C[1];
		if (W)
		{
			W->Action = EIRAction::None;
			Puck->SetCarried(W);
		}
		SetPhase(EIRMatchPhase::Live);
		return;
	}
	if (PhaseTime < FaceoffDropTime + 0.12f)
	{
		return;   // give humans a moment to react
	}
	float Score2[2];
	FVector2D Dir[2];
	for (int32 t = 0; t < 2; ++t)
	{
		AIRPlayer* P = C[t];
		const int32 A = AttackSign(t);
		Dir[t] = FVector2D(-A, 0.f);   // default: draw it back to the defense
		float Reaction = FMath::FRandRange(0.f, 0.22f) - P->Info.R.Hands * 0.012f;
		if (P->HumanIndex >= 0 && Humans.IsValidIndex(P->HumanIndex) && Humans[P->HumanIndex].Bind.Source != EIRSource::Autopilot)
		{
			const FIRIntent& In = Humans[P->HumanIndex].LastIntent;
			const bool bPressed = In.bShoot || In.bPass || In.bShootPressed || In.bPassPressed;
			Reaction = bPressed ? FMath::FRandRange(-0.08f, 0.08f) - P->Info.R.Hands * 0.01f : 0.3f;
			if (In.MoveWorld.SizeSquared() > 0.2f) { Dir[t] = In.MoveWorld.GetSafeNormal(); }
		}
		else
		{
			Reaction -= Difficulty01() * 0.05f * (P->Team == 1 && Mode != EIRMode::Attract ? 1.f : 0.f);
			Dir[t] = FVector2D(-A, FMath::FRandRange(-0.6f, 0.6f)).GetSafeNormal();
		}
		Score2[t] = Reaction;
	}
	const int32 Win = Score2[0] <= Score2[1] ? 0 : 1;
	AIRPlayer* W = C[Win];
	W->FaceoffWin();
	C[1 - Win]->Action = EIRAction::None;
	TStats[Win].Faceoffs++;
	Puck->bFrozen = false;
	Puck->Release(FVector(Dir[Win] * 650.f, 0.f), EIRShotKind::Pass, W);
	Puck->Pos = FVector(FaceoffSpot, PuckHalfHeight);
	Puck->FlightTime = 0.2f;
	Sfx(TEXT("Sfx/Stick_Clack"), Puck->Pos, 0.8f);
	for (AIRPlayer* P : AllPlayers())
	{
		if (P->Action == EIRAction::FaceoffReady) { P->Action = EIRAction::None; }
	}
	if (Referee)
	{
		Referee->Action = EIRAction::None;
	}
	if (PhaseTime < 1.5f && Period == 1 && Score[0] + Score[1] == 0) { Announce(TEXT("VO_Faceoff"), 1.f); }
	SetPhase(EIRMatchPhase::Live);
}

// ------------------------------------------------------------------------------------------------ shooting

AIRPlayer* AIRGameMode::ChooseShotTarget(AIRPlayer* P) const
{
	return Goalies[1 - P->Team];
}

void AIRGameMode::OnShotReleased(AIRPlayer* Shooter, EIRShotKind Kind, float Power)
{
	if (!Puck || Puck->Carrier != Shooter)
	{
		return;
	}
	const int32 Sign = AttackSign(Shooter->Team);
	const FVector2D Goal(GoalLineX * Sign, 0.f);
	const FVector From = Puck->Pos;
	const FVector2D From2(From.X, From.Y);
	AIRPlayer* G = Goalies[1 - Shooter->Team];
	const FIRRatings& R = Shooter->Info.R;
	const float Dist = FVector2D::Distance(From2, Goal);

	// ---- aim: pick a corner. Humans steer with the stick, the CPU shoots for the open side.
	float SideY = 0.f;
	const FVector2D ToGoal = (Goal - From2).GetSafeNormal();
	const FIRIntent& In = Shooter->LastIntent;
	const float Cross = ToGoal.X * In.MoveWorld.Y - ToGoal.Y * In.MoveWorld.X;
	if (Shooter->HumanIndex >= 0 && FMath::Abs(Cross) > 0.25f)
	{
		SideY = -FMath::Sign(Cross) * Sign;   // stick left/right relative to the shot line
	}
	else if (G)
	{
		SideY = G->Pos.Y > 0.f ? -1.f : 1.f;
		if (FMath::Abs(G->Pos.Y) < 10.f) { SideY = FMath::RandBool() ? 1.f : -1.f; }
	}
	float TY = SideY * FMath::FRandRange(45.f, 78.f);
	float TZ = 0.f;
	float Speed = 0.f;
	float Sigma = 0.f;
	switch (Kind)
	{
	case EIRShotKind::Wrist:
		TZ = FMath::FRandRange(15.f, 95.f);
		Speed = 2350.f + R.Shot * 70.f;
		Sigma = 26.f;
		break;
	case EIRShotKind::Slap:
		TZ = FMath::FRandRange(10.f, 105.f);
		Speed = 2600.f + R.Shot * 90.f + Power * 1300.f;
		Sigma = 30.f + (1.f - Power) * 6.f;
		break;
	case EIRShotKind::OneTimer:
		TZ = FMath::FRandRange(10.f, 90.f);
		Speed = 3500.f + R.Shot * 80.f;
		Sigma = 30.f;
		break;
	case EIRShotKind::Power:
		TZ = FMath::FRandRange(55.f, 105.f);
		Speed = 5000.f + R.Shot * 60.f;
		Sigma = 18.f;
		break;
	default:
		TZ = 30.f;
		Speed = 2400.f;
		Sigma = 30.f;
		break;
	}
	if (Shooter->bBlazing) { Speed *= 1.1f; Sigma *= 0.7f; }
	Sigma *= FMath::Lerp(1.45f, 0.65f, (R.Accuracy - 1) / 9.f);
	Sigma *= FMath::Clamp(Dist / 1100.f, 0.6f, 1.8f);
	Sigma *= 1.f + FMath::Clamp(Shooter->Speed() / 1200.f, 0.f, 1.f) * 0.25f;
	if (Shooter->HumanIndex < 0 && Mode != EIRMode::Attract)
	{
		Sigma *= FMath::Lerp(1.35f, 0.8f, Difficulty01());
	}
	TY += Gauss() * Sigma;
	TZ += Gauss() * Sigma * 0.6f;
	TZ = FMath::Max(TZ, 4.f);

	const FVector Target(Goal.X + Sign * 40.f, TY, TZ);   // aim slightly behind the line so the puck crosses it
	FVector2D Flat(Target.X - From.X, Target.Y - From.Y);
	const float D = Flat.Size();
	const float T = D / Speed;
	const float Vz = (Target.Z - From.Z) / FMath::Max(T, 0.05f) + 0.5f * 980.f * T;
	FVector Vel(Flat / FMath::Max(D, 1.f) * Speed, Vz);

	Puck->Release(Vel, Kind, Shooter);
	Puck->bOnFire = Kind == EIRShotKind::Power || Shooter->bBlazing;
	Puck->ShotSign = Sign;
	Shooter->NoPickupTime = 0.3f;
	Shooter->Stats.Shots++;
	TStats[Shooter->Team].Shots++;
	LastShotTime = GameTime;

	// feedback
	const TCHAR* Snd = Kind == EIRShotKind::Power ? TEXT("Sfx/Shot_Power") : (Kind == EIRShotKind::Wrist ? TEXT("Sfx/Shot_Wrist") : TEXT("Sfx/Shot_Slap"));
	Sfx(Snd, From, 1.f, FMath::FRandRange(0.95f, 1.05f));
	if (Kind == EIRShotKind::Power)
	{
		TStats[Shooter->Team].PowerShots++;
		Shake(0.45f);
		HitStop = 0.05f;
		if (FX) { FX->Impact(From, 0.7f, FLinearColor(1.f, 0.5f, 0.1f, 1.f) * 2.f); }
		Callout(TEXT("POWER SHOT!"), FString(), FLinearColor(1.f, 0.45f, 0.05f), 1.2f, 1);
		RumbleFor(Shooter, 0.8f, 0.25f);
	}
	else if (Kind == EIRShotKind::Slap)
	{
		Shake(0.15f + Power * 0.15f);
		if (FX) { FX->IceSpray(From, Flat.GetSafeNormal(), 0.8f); }
		RumbleFor(Shooter, 0.4f, 0.12f);
		if (Power > 0.8f && FMath::FRand() < 0.3f) { Announce(TEXT("VO_Slapshot"), 0.8f); }
	}
	else if (Kind == EIRShotKind::OneTimer)
	{
		Shake(0.25f);
		Announce(TEXT("VO_OneTimer"), 1.2f);
		Callout(TEXT("ONE-TIMER!"), FString(), FLinearColor(0.3f, 0.9f, 1.f), 1.0f, 1);
		RumbleFor(Shooter, 0.5f, 0.15f);
	}
	if (Shooter->AnimInst && Kind != EIRShotKind::OneTimer && Shooter->Action != EIRAction::Shot)
	{
		Shooter->AnimInst->PlayUpper(Shooter->A(TEXT("A_SlapRelease")), 1.f, 0.03f);
	}
	PreRollShot(Shooter, Kind, Power);
}

void AIRGameMode::PreRollShot(AIRPlayer* Shooter, EIRShotKind Kind, float Power)
{
	AIRPlayer* G = Goalies[1 - Shooter->Team];
	if (!Puck || !G)
	{
		return;
	}
	const int32 Sign = Puck->ShotSign;
	// where does the puck cross the goal line?
	const FVector P0 = Puck->Pos;
	const FVector V = Puck->Vel;
	if (FMath::Abs(V.X) < 1.f || (GoalLineX * Sign - P0.X) * Sign < 0.f || V.X * Sign <= 0.f)
	{
		return;
	}
	const float T = (GoalLineX * Sign - P0.X) / V.X;
	const float Y = P0.Y + V.Y * T;
	const float Zc = P0.Z + V.Z * T - 0.5f * 980.f * T * T;
	const bool bOnTarget = FMath::Abs(Y) < NetHalfWidth - PuckRadius && Zc < NetHeight - PuckRadius && Zc > -5.f;
	Puck->bShotOnTarget = bOnTarget;
	if (!bOnTarget)
	{
		return;
	}
	const float Dist = FVector2D::Distance(FVector2D(P0.X, P0.Y), FVector2D(GoalLineX * Sign, 0.f));
	const float Spd = V.Size();
	float P = 0.60f + (G->Info.R.Goalie - 6) * 0.03f;
	P += FMath::Clamp((Dist - 800.f) / 3000.f, -0.15f, 0.25f);
	P -= FMath::Clamp((Spd - 2600.f) / 2600.f, -0.1f, 0.25f) * 0.5f;
	switch (Kind)
	{
	case EIRShotKind::OneTimer: P -= 0.16f; break;
	case EIRShotKind::Power: P -= 0.10f; break;
	case EIRShotKind::Wrist: P += 0.02f; break;
	default: break;
	}
	// rebounds and dekes catch goalies out of position
	if (GameTime - LastShotTime < 0.01f && G->Action == EIRAction::GoalieSave) { P -= 0.18f; }
	if (Shooter->Action == EIRAction::Spin || Shooter->ShootComboTimer > 0.f) { P -= 0.06f; }
	const float OutOfPos = FMath::Abs(G->Pos.Y - Y) - 35.f;
	P -= FMath::Clamp(OutOfPos / 160.f, 0.f, 0.35f);
	if (FMath::Abs(Y) > 60.f || Zc > 85.f) { P -= 0.07f; }
	if (G->IsDown()) { P -= 0.4f; }
	// difficulty: humans face better goalies on hard, CPU shooters are kinder on easy
	if (Mode != EIRMode::Attract)
	{
		const bool bHumanShooter = Shooter->HumanIndex >= 0 || Shooter->LastHumanIndex >= 0 && Shooter->Team == (Humans.Num() ? Humans[0].Team : 0);
		P += bHumanShooter ? (Opt.Difficulty - 2) * 0.035f : -(Opt.Difficulty - 2) * 0.03f;
	}
	P -= CatchupBoost[Shooter->Team] * 0.04f;
	P += CatchupBoost[G->Team] * 0.04f;
	P = FMath::Clamp(P, 0.12f, 0.92f);
	if (G->GoalieGlow >= 1.f) { P = 0.98f; }
	if (FMath::FRand() < P)
	{
		Puck->SaveGoalie = G;
		Puck->bSaveCatch = Zc > 55.f && FMath::FRand() < 0.55f && Kind != EIRShotKind::Power;
	}
	else
	{
		// beaten: the goalie still flails at it
		G->PlayGoalieSave(FVector(0.f, (Y - G->Pos.Y) * -Sign, Zc), false);
	}
}

void AIRGameMode::OnSave(AIRPlayer* G, bool bCatch, bool bPower)
{
	if (!Puck)
	{
		return;
	}
	const int32 Sign = Puck->ShotSign != 0 ? Puck->ShotSign : (G->Pos.X > 0.f ? 1 : -1);
	const FVector Local(0.f, (Puck->Pos.Y - G->Pos.Y) * -Sign, Puck->Pos.Z);
	G->PlayGoalieSave(Local, bCatch);
	G->Stats.Saves++;
	TStats[G->Team].Saves++;
	const bool bWasPower = Puck->Kind == EIRShotKind::Power;
	Puck->bOnFire = false;
	if (bPower)
	{
		G->GoalieGlow = 0.f;
		Sfx(TEXT("Sfx/Save_Power"), Puck->Pos, 1.f);
		Announce(TEXT("VO_PowerSave"), 2.f);
		Callout(TEXT("BRICK WALL!"), G->Info.Last.ToUpper(), FLinearColor(1.f, 0.8f, 0.2f), 1.6f, 0, 0.8f);
		if (FX) { FX->Impact(Puck->Pos, 1.f, FLinearColor(1.f, 0.85f, 0.3f, 1.f) * 2.f); }
		Shake(0.4f);
	}
	else
	{
		G->GoalieGlow = FMath::Min(1.f, G->GoalieGlow + (bWasPower ? 0.3f : 0.13f));
	}
	if (bCatch && !bWasPower)
	{
		Sfx(TEXT("Sfx/Save_Glove"), Puck->Pos, 1.f);
		Puck->SetCarried(G);
		Puck->Kind = EIRShotKind::None;
		G->PlayGoalieCover();
		G->ActionDuration = 0.9f;
	}
	else
	{
		Sfx(Local.Z > 70.f ? TEXT("Sfx/Save_Blocker") : TEXT("Sfx/Save_Pad"), Puck->Pos, 1.f);
		// rebound: out toward the slot or the corners
		const float Ang = FMath::FRandRange(-75.f, 75.f);
		FVector2D Out = FVector2D(-Sign, 0.f).GetRotated(Ang);
		const float Sp = FMath::FRandRange(500.f, 1300.f) * (bWasPower ? 1.5f : 1.f);
		Puck->Release(FVector(Out * Sp, FMath::FRandRange(0.f, 250.f)), EIRShotKind::None, G);
		Puck->Pos.X = G->Pos.X - Sign * 55.f;
		Puck->FlightTime = 0.f;
		if (FX) { FX->IceSpray(Puck->Pos, Out, 1.f); }
		if (bWasPower && FX) { FX->Smoke(Puck->Pos, 0.5f); }
	}
	Shake(bWasPower ? 0.3f : 0.1f);
	const bool bBig = bWasPower || Puck->Vel.Size() > 3000.f || FMath::Abs(Local.Y) > 60.f;
	if (bBig || FMath::FRand() < 0.35f)
	{
		Announce(TEXT("VO_Save"), 1.f);
	}
	Crowd(bBig ? 0.35f : 0.15f, bBig ? TEXT("Crowd_Ooh") : FString());
	Callout(TEXT("SAVE!"), G->Info.Last.ToUpper(), FLinearColor(0.75f, 0.9f, 1.f), 1.f, 1);
}

void AIRGameMode::OnGoalieCleared(AIRPlayer* G)
{
	if (!Puck || Puck->Carrier != G || Phase != EIRMatchPhase::Live)
	{
		return;
	}
	// pass it up to the most open teammate (keeps the arcade game flowing)
	AIRPlayer* Best = nullptr;
	float BestScore = -1e9f;
	for (AIRPlayer* P : Skaters[G->Team])
	{
		if (P->IsDown() || P->IsInFight()) { continue; }
		const float Open = LaneOpen(G->Pos, P->Pos, 1 - G->Team, 110.f);
		const float S = Open * 1000.f - FVector2D::Distance(G->Pos, P->Pos) * 0.3f + (P->HumanIndex >= 0 ? 250.f : 0.f);
		if (S > BestScore) { BestScore = S; Best = P; }
	}
	if (Best)
	{
		OnPassReleased(G, Best, false);
	}
	else
	{
		Puck->Release(FVector(FVector2D(-AttackSign(1 - G->Team) * 900.f, FMath::FRandRange(-500.f, 500.f)), 0.f), EIRShotKind::Clear, G);
	}
}

// ------------------------------------------------------------------------------------------------ passing

AIRPlayer* AIRGameMode::ChoosePassTarget(AIRPlayer* Passer, FVector2D StickDir, bool bStrict) const
{
	AIRPlayer* Best = nullptr;
	float BestScore = -1e9f;
	const FVector2D Dir = StickDir.SizeSquared() > 0.04f ? StickDir.GetSafeNormal() : Passer->Forward();
	const int32 Sign = AttackSign(Passer->Team);
	for (AIRPlayer* P : Skaters[Passer->Team])
	{
		if (P == Passer || P->IsDown() || P->IsInFight()) { continue; }
		const FVector2D To = P->Pos - Passer->Pos;
		const float D = To.Size();
		if (D < 150.f) { continue; }
		const float Align = FVector2D::DotProduct(To / D, Dir);
		float S = Align * (bStrict ? 1600.f : 500.f);
		S += LaneOpen(Passer->Pos, P->Pos, 1 - Passer->Team, 85.f) * 600.f;
		S += P->Pos.X * Sign * 0.15f;            // prefer forward options
		S -= FMath::Max(0.f, D - 1400.f) * 0.4f; // and not too far
		if (P->HumanIndex >= 0) { S += 120.f; }
		if (S > BestScore) { BestScore = S; Best = P; }
	}
	return Best;
}

void AIRGameMode::OnPassReleased(AIRPlayer* Passer, AIRPlayer* Target, bool bDrop)
{
	if (!Puck || Puck->Carrier != Passer)
	{
		return;
	}
	if (bDrop || !Target)
	{
		// drop pass / clear: leave it behind or fire it up the ice
		FVector V = bDrop ? FVector(Passer->Vel * 0.15f, 0.f) : FVector(Passer->Forward() * 1600.f, 0.f);
		Puck->Release(V, bDrop ? EIRShotKind::Pass : EIRShotKind::Dump, Passer);
		Passer->NoPickupTime = bDrop ? 0.6f : 0.3f;
		Sfx(TEXT("Sfx/Pass"), Puck->Pos, 0.6f);
		return;
	}
	const FIRRatings& R = Passer->Info.R;
	const FVector From = Puck->Pos;
	float Speed = 1900.f + R.Pass * 75.f;
	const float Dist0 = FVector2D::Distance(FVector2D(From), Target->Pos);
	Speed += FMath::Clamp(Dist0 - 800.f, 0.f, 1200.f) * 0.5f;
	// lead the receiver
	float T = Dist0 / Speed;
	FVector2D Aim = Target->StickReachPoint() + Target->Vel * T * 0.85f;
	FVector2D N;
	ClampInside(Aim, 70.f, N);
	T = FVector2D::Distance(FVector2D(From), Aim) / Speed;
	const float ErrDeg = Gauss() * (11 - R.Pass) * 0.45f;
	FVector2D Dir = (Aim - FVector2D(From)).GetSafeNormal().GetRotated(ErrDeg);
	float Vz = 0.f;
	// saucer pass over sticks when the lane is blocked
	if (LaneOpen(FVector2D(From), Aim, 1 - Passer->Team, 70.f) < 0.5f)
	{
		Vz = 0.5f * 980.f * T;
	}
	Puck->Release(FVector(Dir * Speed, Vz), EIRShotKind::Pass, Passer);
	Puck->bOnFire = Passer->bBlazing;
	Passer->NoPickupTime = 0.3f;
	Target->ArmOneTimer(T + 0.35f);
	Target->bAutoOneTimer = Passer->bAutoOneTimer;
	Passer->bAutoOneTimer = false;
	Sfx(TEXT("Sfx/Pass"), From, 0.8f);
	if (Target->bAutoOneTimer)
	{
		Callout(TEXT("GIVE AND GO!"), FString(), FLinearColor(0.4f, 1.f, 0.6f), 0.9f, 1);
	}
}

// ------------------------------------------------------------------------------------------------ defense

void AIRGameMode::OnCheck(AIRPlayer* Att, bool bPower)
{
	AIRPlayer* Victim = nullptr;
	float BestD = bPower ? 175.f : 145.f;
	for (AIRPlayer* P : AllPlayers())
	{
		if (P->Team == Att->Team || P->IsReferee() || P->IsDown() || P->IsInFight() || P->Z > 30.f) { continue; }
		const FVector2D To = P->Pos - Att->Pos;
		const float D = To.Size();
		if (D > BestD || D < 1.f) { continue; }
		if (FVector2D::DotProduct(To / D, Att->Forward()) < 0.25f) { continue; }
		if (P->IsGoalie() && !bPower) { continue; }
		Victim = P;
		BestD = D;
	}
	if (!Victim)
	{
		return;
	}
	Att->bActionEvent = true;
	const bool bHadPuck = Victim->HasPuck();
	FVector2D Dir = (Victim->Pos - Att->Pos).GetSafeNormal() * 0.6f + Att->Vel.GetSafeNormal() * 0.4f;
	Dir.Normalize();
	const float RelSpeed = FMath::Max(0.f, FVector2D::DotProduct(Att->Vel - Victim->Vel, Dir));
	float Power = RelSpeed / 1000.f + Att->Info.R.Check / 14.f + (Att->Info.Bulk - Victim->Info.Bulk) * 2.f;
	if (Victim->Action == EIRAction::Spin) { Power *= 0.4f; }
	Victim->TakeHit(Att, Power, bPower, Dir);
	Att->Vel *= 0.45f;
	Att->Stats.Hits++;
	TStats[Att->Team].Hits++;
	const FVector Where = FVector((Att->Pos + Victim->Pos) * 0.5f, 110.f);
	if (bHadPuck && Puck)
	{
		Puck->Release(FVector(Victim->Vel * 0.6f + FVector2D(FMath::FRandRange(-300.f, 300.f), FMath::FRandRange(-300.f, 300.f)), 0.f), EIRShotKind::None, Victim);
		Victim->NoPickupTime = 0.6f;
		Puck->FlightTime = 0.3f;
	}
	if (bPower)
	{
		Sfx(TEXT("Sfx/Check_Power"), Where, 1.f);
		Shake(1.0f);
		HitStop = 0.11f;
		if (FX) { FX->Impact(Where, 1.4f, FLinearColor(1.f, 0.9f, 0.6f, 1.f) * 1.5f); FX->Stars(Victim->HeadPos()); }
		Announce(TEXT("VO_PowerHit"), 2.f);
		Crowd(0.6f, TEXT("Crowd_Cheer_Small"));
		Callout(TEXT("CRUSHED!"), Victim->Info.Last.ToUpper(), FLinearColor(1.f, 0.25f, 0.15f), 1.5f, 0, 0.8f);
		AmbulanceTime = GameTime;
		Sfx(TEXT("Sfx/Ambulance_Siren"), FVector(0, 0, 0), 0.7f);
		RumbleFor(Att, 1.f, 0.35f);
		RumbleFor(Victim, 1.f, 0.5f);
		if (Arena) { Arena->FlashGlass(0.6f); }
	}
	else
	{
		Sfx(TEXT("Sfx/Check"), Where, 0.9f);
		Shake(0.3f);
		HitStop = 0.05f;
		if (FX) { FX->Impact(Where, 0.6f, FLinearColor(1.f, 1.f, 1.f, 0.8f)); }
		if (Victim->IsDown() && FMath::FRand() < 0.6f) { Announce(TEXT("VO_Hit"), 1.2f); }
		Crowd(0.3f, Victim->IsDown() ? TEXT("Crowd_Ooh") : FString());
		RumbleFor(Att, 0.6f, 0.15f);
		RumbleFor(Victim, 0.7f, 0.25f);
	}
	// tempers flare
	const bool bRecentFight = GameTime - LastFightTime < (Opt.bFightFrenzy ? 8.f : 40.f);
	if (Opt.bFighting && !bRecentFight && Victim->Anger >= 1.f && FMath::FRand() < 0.6f && !Victim->IsGoalie() && !Att->IsGoalie() && Phase == EIRMatchPhase::Live && Mode != EIRMode::Practice)
	{
		StartFight(Victim, Att);
	}
}

void AIRGameMode::OnPoke(AIRPlayer* Att)
{
	if (!Puck)
	{
		return;
	}
	AIRPlayer* C = Puck->Carrier;
	const FVector2D Reach = Att->StickReachPoint();
	const float D = FVector2D::Distance(Reach, FVector2D(Puck->Pos.X, Puck->Pos.Y));
	Sfx(TEXT("Sfx/Stick_Clack"), Puck->Pos, 0.4f);
	if (!C)
	{
		if (D < 100.f && Puck->Pos.Z < 40.f && Att->CanPlayPuck() && !Att->IsGoalie())
		{
			Puck->SetCarried(Att);
		}
		return;
	}
	if (C->Team == Att->Team || D > 100.f)
	{
		return;
	}
	float Chance = 0.42f + (Att->Info.R.Hands - C->Info.R.Hands) * 0.04f;
	if (Att->HumanIndex < 0 && Mode != EIRMode::Attract) { Chance += (Opt.Difficulty - 2) * 0.05f; }
	if (C->Action == EIRAction::Spin) { Chance *= 0.2f; }
	if (C->Action == EIRAction::ShotCharge) { Chance += 0.15f; }
	if (Att->IsGoalie()) { Chance += 0.2f; }
	if (FMath::FRand() < Chance)
	{
		const FVector2D Away = (Att->Forward() * 0.7f + FVector2D(FMath::FRandRange(-0.5f, 0.5f), FMath::FRandRange(-0.5f, 0.5f))).GetSafeNormal();
		Puck->Release(FVector(Away * FMath::FRandRange(300.f, 600.f), 0.f), EIRShotKind::None, Att);
		C->NoPickupTime = 0.45f;
		if (C->AnimInst) { C->AnimInst->StopUpper(0.1f); }
		if (C->Action == EIRAction::ShotCharge) { C->Action = EIRAction::None; }
		Att->Stats.Steals++;
		C->Anger = FMath::Min(1.2f, C->Anger + 0.08f);
		Sfx(TEXT("Sfx/Stick_Clack"), Puck->Pos, 0.9f);
		if (FMath::FRand() < 0.35f) { Announce(TEXT("VO_Steal"), 1.f); }
		Callout(TEXT("STOLEN!"), Att->Info.Last.ToUpper(), TeamInfo[Att->Team].Primary, 1.f, 1);
		RumbleFor(Att, 0.3f, 0.1f);
	}
}

void AIRGameMode::OnHook(AIRPlayer* Att, bool bTrip)
{
	AIRPlayer* C = PuckCarrier();
	if (!C || C->Team == Att->Team)
	{
		return;
	}
	if (FVector2D::Distance(Att->StickReachPoint(), C->Pos) > 170.f)
	{
		return;
	}
	Sfx(TEXT("Sfx/Stick_Clack"), FVector(C->Pos, 50.f), 0.7f);
	C->Anger = FMath::Min(1.2f, C->Anger + 0.12f);
	if (bTrip && Att->Turbo > 0.15f)
	{
		Att->Turbo -= 0.15f;
		C->Trip(Att);
		if (Puck) { Puck->Release(FVector(C->Vel * 0.5f, 0.f), EIRShotKind::None, C); }
		C->NoPickupTime = 0.8f;
		Callout(TEXT("TRIPPED!"), FString(), FLinearColor(1.f, 0.6f, 0.2f), 1.f, 1);
		Crowd(0.2f, TEXT("Crowd_Boo"));
	}
	else
	{
		C->HookedTime = 0.9f;
		if (FMath::FRand() < 0.3f + (Att->Info.R.Hands - C->Info.R.Hands) * 0.03f && Puck)
		{
			Puck->Release(FVector(C->Vel * 0.3f, 0.f), EIRShotKind::None, C);
			C->NoPickupTime = 0.5f;
		}
	}
}

void AIRGameMode::OnSpin(AIRPlayer* Carrier)
{
	Sfx(TEXT("Sfx/Skate_Turbo"), Carrier->GetPos3(), 0.6f, 1.2f);
	if (FX) { FX->IceSpray(Carrier->GetPos3(), Carrier->Vel.GetSafeNormal(), 1.2f); }
	if (FMath::FRand() < 0.3f) { Announce(TEXT("VO_Deke"), 0.8f); }
}

void AIRGameMode::OnPlayerHitBoards(AIRPlayer* P, float Speed)
{
	Sfx(TEXT("Sfx/Boards_Slam"), P->GetPos3(), FMath::Clamp(Speed / 1200.f, 0.3f, 1.f));
	if (Arena) { Arena->FlashGlass(FMath::Clamp(Speed / 1500.f, 0.2f, 1.f)); }
	if (Speed > 900.f) { Shake(0.35f); Crowd(0.2f, TEXT("Crowd_Ooh")); }
}

// ------------------------------------------------------------------------------------------------ fights

void AIRGameMode::StartFight(AIRPlayer* A, AIRPlayer* B)
{
	if (Phase == EIRMatchPhase::Fight || !A || !B)
	{
		return;
	}
	Fight = FIRFightState();
	LastFightTime = GameTime;
	Fight.A = A;
	Fight.B = B;
	if (Puck)
	{
		Puck->SetCarried(nullptr);
		Puck->Vel = FVector::ZeroVector;
		Puck->bFrozen = true;
	}
	// square off 1.1 m apart where they stand
	const FVector2D Mid = (A->Pos + B->Pos) * 0.5f;
	FVector2D Axis = (B->Pos - A->Pos).GetSafeNormal();
	if (Axis.IsNearlyZero()) { Axis = FVector2D(1.f, 0.f); }
	FVector2D C = Mid;
	FVector2D N;
	ClampInside(C, 200.f, N);
	A->Pos = C - Axis * 55.f;
	B->Pos = C + Axis * 55.f;
	A->Z = B->Z = 0.f;
	A->EnterFight(B);
	B->EnterFight(A);
	A->Yaw = FMath::Atan2(Axis.Y, Axis.X);
	B->Yaw = FMath::Atan2(-Axis.Y, -Axis.X);
	TStats[A->Team].Fights++;
	TStats[B->Team].Fights++;
	Sfx(TEXT("Sfx/Whistle_Long"), FVector(C, 0.f), 0.8f);
	Sfx(TEXT("Sfx/Gloves_Drop"), FVector(C, 0.f), 1.f);
	Announce(TEXT("VO_Fight"), 3.f);
	Crowd(1.f, TEXT("Crowd_Cheer_Big"));
	if (Audio) { Audio->SetExcitement(1.f); }
	Callout(TEXT("FIGHT!"), FString::Printf(TEXT("%s vs %s"), *A->Info.Last.ToUpper(), *B->Info.Last.ToUpper()), FLinearColor(1.f, 0.15f, 0.1f), 2.f, 0, 1.1f);
	SetPhase(EIRMatchPhase::Fight);
}

void AIRGameMode::FightPunch(AIRPlayer* Att, int32 Kind)
{
	AIRPlayer* Opp = Att->FightOpponent.Get();
	if (!Opp || Fight.bOver)
	{
		return;
	}
	if (FVector2D::Distance(Att->Pos, Opp->Pos) > 165.f)
	{
		Sfx(TEXT("Sfx/Fight_Block"), Opp->HeadPos(), 0.3f);
		return;
	}
	const float Mul = FMath::Lerp(0.8f, 1.3f, Att->Info.R.Fight / 10.f) * (Att->HumanIndex < 0 && Mode != EIRMode::Attract ? FMath::Lerp(0.75f, 1.15f, Difficulty01()) : 1.f);
	float Dmg = 0.f;
	const TCHAR* Snd = TEXT("Sfx/Fight_Jab");
	switch (Kind)
	{
	case 0: Dmg = 0.07f; break;
	case 1: Dmg = 0.15f; Snd = TEXT("Sfx/Fight_Punch"); break;
	case 2: Dmg = 0.27f; Snd = TEXT("Sfx/Fight_Uppercut"); break;
	case 3: Dmg = 0.03f; Snd = TEXT("Sfx/Fight_Grab"); Opp->StunTime = 0.7f; if (Opp->Action == EIRAction::FightBlock) { Opp->StartAction(EIRAction::FightIdle, 1e6f); } break;
	}
	const bool bBlocked = Opp->Action == EIRAction::FightBlock && Kind != 3;
	Opp->FightTakeHit(Dmg * Mul, Kind == 2);
	Sfx(bBlocked ? TEXT("Sfx/Fight_Block") : Snd, Opp->HeadPos(), 1.f, FMath::FRandRange(0.9f, 1.1f));
	if (!bBlocked)
	{
		Shake(Kind == 2 ? 0.6f : (Kind == 1 ? 0.3f : 0.12f));
		if (Kind >= 1) { HitStop = Kind == 2 ? 0.1f : 0.04f; }
		if (FX) { FX->Sparks(Opp->HeadPos(), FLinearColor(1.f, 1.f, 0.9f, 1.f), Kind == 2 ? 16 : 6, 300.f); }
		Crowd(Kind == 2 ? 0.3f : 0.12f, Kind == 2 ? TEXT("Crowd_Ooh") : FString());
		RumbleFor(Opp, 0.4f + Kind * 0.2f, 0.15f);
	}
	if (Opp->Action == EIRAction::FightKO)
	{
		Fight.bOver = true;
		Fight.OverTime = 0.f;
		Fight.Winner = Att;
		Att->Stats.FightsWon++;
		Att->Rage = 15.f;
		for (AIRPlayer* T : Skaters[Att->Team]) { T->Turbo = 1.f; }
		if (FX) { FX->Stars(Opp->HeadPos()); }
		Announce(TEXT("VO_FightWin"), 3.f);
		Crowd(0.8f, TEXT("Crowd_Cheer_Big"));
		Callout(FString::Printf(TEXT("%s WINS!"), *Att->Info.Last.ToUpper()), TEXT("RAGE: FREE POWER SHOTS"), TeamInfo[Att->Team].Primary, 2.5f, 0, 0.8f);
		Att->StartCelebrate(0);
	}
}

void AIRGameMode::TickFight(float Dt)
{
	Fight.Time += Dt;
	AIRPlayer* A = Fight.A.Get();
	AIRPlayer* B = Fight.B.Get();
	for (AIRPlayer* P : AllPlayers())
	{
		FIRIntent In;
		if (P == A || P == B)
		{
			if (P->HumanIndex >= 0 && Humans.IsValidIndex(P->HumanIndex) && Humans[P->HumanIndex].Bind.Source != EIRSource::Autopilot)
			{
				HandleHumans(0.f);
				In = Humans[P->HumanIndex].LastIntent;
			}
			else
			{
				In = ThinkFighter(P, Dt);
			}
		}
		else if (P->IsGoalie())
		{
			In = ThinkGoalie(P, Dt);
		}
		else if (A && B)
		{
			// everyone else forms a ring around the scrap
			const FVector2D C = (A->Pos + B->Pos) * 0.5f;
			const FVector2D To = P->Pos - C;
			const float D = To.Size();
			const FVector2D Want = C + (D > 1.f ? To / D : FVector2D(1, 0)) * 420.f;
			In.MoveWorld = (Want - P->Pos) / 300.f;
			if (In.MoveWorld.SizeSquared() > 1.f) { In.MoveWorld.Normalize(); }
			In.bFaceTarget = true;
			In.FaceTarget = C;
		}
		P->Simulate(Dt, In);
	}
	ResolveCollisions(Dt);
	if (Fight.bOver)
	{
		Fight.OverTime += Dt;
		if (Fight.OverTime > 2.8f)
		{
			// the loser heads to the dressing room: a fresh skater from the bench takes his place
			AIRPlayer* Loser = (Fight.Winner == A) ? B : A;
			if (Loser)
			{
				const int32 T = Loser->Team;
				const int32 Next = BenchNext[T] % IR_ROSTER_SKATERS;
				BenchNext[T]++;
				bool bInUse = false;
				for (AIRPlayer* S : Skaters[T]) { if (S->Info.Number == TeamInfo[T].Skaters[Next].Number) { bInUse = true; } }
				if (!bInUse) { Loser->SetInfo(TeamInfo[T].Skaters[Next]); }
				Loser->FightHealth = 1.f;
			}
			if (A) { A->LeaveFight(); }
			if (B) { B->LeaveFight(); }
			const FVector2D Spot = A && B ? NearestDot((A->Pos + B->Pos) * 0.5f) : FVector2D::ZeroVector;
			SetupFaceoff(Spot);
			SetPhase(EIRMatchPhase::FaceoffSetup);
		}
	}
	else if (Fight.Time > 22.f)
	{
		// linesmen break it up
		Fight.bOver = true;
		Fight.OverTime = 1.5f;
		Callout(TEXT("BROKEN UP"), FString(), FLinearColor::White, 1.5f, 1);
	}
}

// ------------------------------------------------------------------------------------------------ goals

void AIRGameMode::OnGoal(int32 Sign)
{
	const int32 ScoringTeam = AttackSign(0) == Sign ? 0 : 1;
	AIRPlayer* Scorer = Puck ? Puck->LastShooter.Get() : nullptr;
	if (!Scorer || Scorer->Team != ScoringTeam)
	{
		Scorer = Puck ? Puck->LastTouch.Get() : nullptr;
	}
	if (Scorer && Scorer->Team != ScoringTeam)
	{
		// own goal: credit the last attacker on the ice
		Scorer = Skaters[ScoringTeam].Num() ? Skaters[ScoringTeam][0] : nullptr;
	}
	AIRPlayer* Assist = Puck ? Puck->PrevTouch.Get() : nullptr;
	if (Assist == Scorer || (Assist && Assist->Team != ScoringTeam)) { Assist = nullptr; }
	Score[ScoringTeam]++;
	TStats[ScoringTeam].GoalsByPeriod[FMath::Clamp(Period - 1, 0, 3)]++;
	LastGoalTeam = ScoringTeam;
	LastScorer = Scorer;
	LastAssist = Assist;
	GoalSignLast = Sign;
	bLastGoalPower = Puck && Puck->bOnFire;
	if (Scorer)
	{
		Scorer->Stats.Goals++;
		Scorer->GoalsThisGame++;
		if (Scorer->LastHumanIndex >= 0 && Humans.IsValidIndex(Scorer->LastHumanIndex)) { Humans[Scorer->LastHumanIndex].Stats.Goals++; }
	}
	if (Assist)
	{
		Assist->Stats.Assists++;
		if (Assist->LastHumanIndex >= 0 && Humans.IsValidIndex(Assist->LastHumanIndex)) { Humans[Assist->LastHumanIndex].Stats.Assists++; }
	}
	// scoring streaks
	if (ScoringStreakTeam == ScoringTeam) { ScoringStreak++; }
	else
	{
		ScoringStreakTeam = ScoringTeam;
		ScoringStreak = 1;
		// the opponents scored: blazing players cool off after two goals against
		for (AIRPlayer* P : Skaters[1 - ScoringTeam]) { if (P->bBlazing && FMath::FRand() < 0.5f) { P->bBlazing = false; } }
	}

	SetPhase(EIRMatchPhase::Goal);
	SlowMo = 0.3f;
	SlowMoTime = 0.7f;
	GoalLightTime[Sign > 0 ? 0 : 1] = GameTime;
	if (Arena) { Arena->SetGoalLight(Sign, true); }
	Sfx(TEXT("Sfx/Goal_Horn"), FVector::ZeroVector, 1.f);
	Shake(0.6f);
	Crowd(1.f, TEXT("Crowd_Cheer_Big"));
	if (Audio) { Audio->SetExcitement(1.f); Audio->CrowdReaction(TEXT("Organ_Charge"), 0.8f); }
	const FVector NetPos(GoalLineX * Sign + Sign * 50.f, 0.f, 60.f);
	if (bLastGoalPower)
	{
		NetFireTime[Sign > 0 ? 0 : 1] = GameTime;
		Sfx(TEXT("Sfx/Flame_Burst"), NetPos, 1.f);
		if (FX) { FX->FireBurst(NetPos, 1.6f); }
		Announce(TEXT("VO_PowerGoal"), 3.f);
		// the goalie gets blown into the net
		if (AIRPlayer* G = Goalies[1 - ScoringTeam])
		{
			G->TakeHit(Scorer, 2.f, true, FVector2D(Sign, 0.f));
		}
	}
	else
	{
		Announce(TEXT("VO_Goal"), 3.f);
	}
	if (FX) { FX->Confetti(FVector(NetPos.X * 0.6f, 0.f, 0.f), TeamInfo[ScoringTeam].Primary, TeamInfo[ScoringTeam].Secondary, 160); }
	const FString Who = Scorer ? FString::Printf(TEXT("%s #%d"), *Scorer->Info.Last.ToUpper(), Scorer->Info.Number) : FString();
	const FString AssistS = Assist ? FString::Printf(TEXT("ASSIST: %s"), *Assist->Info.Last.ToUpper()) : FString();
	Callout(TEXT("GOAL!"), Who + (AssistS.IsEmpty() ? FString() : TEXT("   ") + AssistS), TeamInfo[ScoringTeam].Primary, 3.2f, 0, 1.4f);

	// hat trick!
	if (Scorer && Scorer->GoalsThisGame == 3)
	{
		Scorer->bBlazing = true;
		HatRainTime = GameTime;
		if (FX) { FX->Hats(40); }
		Sfx(TEXT("Sfx/Hat_Rain"), FVector::ZeroVector, 1.f);
		Announce(TEXT("VO_HatTrick"), 3.5f);
		Callout(TEXT("HAT TRICK!"), TEXT("HE'S BLAZING!"), FLinearColor(1.f, 0.55f, 0.05f), 3.5f, 2);
	}
	else if (Scorer && ScoringStreak == 3 && !Scorer->bBlazing)
	{
		Scorer->bBlazing = true;
		Announce(TEXT("VO_Blazing"), 2.f);
		Callout(TEXT("BLAZING!"), TEXT("THREE STRAIGHT"), FLinearColor(1.f, 0.5f, 0.05f), 2.f, 2);
	}
	if (Score[ScoringTeam] - Score[1 - ScoringTeam] == 0 && Score[ScoringTeam] >= 2)
	{
		Announce(TEXT("VO_Comeback"), 1.5f);
	}

	for (AIRPlayer* P : AllPlayers())
	{
		if (P->IsReferee() || P->IsGoalie()) { continue; }
		if (P->Team == ScoringTeam) { P->StartCelebrate(P == Scorer ? FMath::RandRange(0, 2) : 0); }
		else { P->StartDejected(); }
	}
	for (FIRHuman& H : Humans)
	{
		if (AIRPlayer* P = H.Controlled.Get()) { RumbleFor(P, H.Team == ScoringTeam ? 0.6f : 0.2f, 0.5f); }
	}
}

// ------------------------------------------------------------------------------------------------ catch-up

void AIRGameMode::UpdateCatchup()
{
	for (int32 t = 0; t < 2; ++t)
	{
		const int32 Diff = Score[1 - t] - Score[t];
		CatchupBoost[t] = Opt.bCatchUp ? FMath::Clamp((Diff - 1) * 0.5f, 0.f, 1.5f) : 0.f;
	}
}

// ------------------------------------------------------------------------------------------------ replay

void AIRGameMode::RecordReplay()
{
	if (Mode == EIRMode::Attract && Screen != EIRScreen::Playing)
	{
		return;
	}
	const float Interval = 1.f / 30.f;
	if (ReplayBuf.Num() > 0 && GameTime - ReplayBuf.Last().T < Interval)
	{
		return;
	}
	FIRReplayFrame F;
	F.T = GameTime;
	for (AIRPlayer* P : AllPlayers())
	{
		FIRReplayActor A;
		A.Pos = P->GetPos3();
		A.Yaw = P->Yaw;
		A.Seq = P->AnimInst ? P->AnimInst->GetCurrent() : nullptr;
		A.Time = P->AnimInst ? P->AnimInst->GetTime() : 0.f;
		A.UpperSeq = P->AnimInst ? P->AnimInst->GetUpper() : nullptr;
		A.UpperTime = P->AnimInst ? P->AnimInst->GetUpperTime() : 0.f;
		A.UpperW = A.UpperSeq ? 1.f : 0.f;
		A.StickScale = P->AnimInst ? P->AnimInst->StickScale : 1.f;
		F.Actors.Add(A);
	}
	F.Puck = Puck ? Puck->Pos : FVector::ZeroVector;
	F.bPuckFire = Puck && Puck->bOnFire;
	ReplayBuf.Add(MoveTemp(F));
	// keep ~7 s
	const int32 Max = 7 * 30;
	if (ReplayBuf.Num() > Max)
	{
		ReplayBuf.RemoveAt(0, ReplayBuf.Num() - Max, EAllowShrinking::No);
	}
}

void AIRGameMode::StartReplay()
{
	// find the goal moment in the buffer (when the phase switched to Goal)
	const float GoalT = GameTime - PhaseTime;
	ReplayStart = GoalT - 3.6f;
	ReplayEnd = GoalT + 1.2f;
	if (ReplayBuf.Num() > 0) { ReplayStart = FMath::Max(ReplayStart, ReplayBuf[0].T); }
	ReplayCursor = ReplayStart;
	bReplaying = true;
	if (Cam) { Cam->SetShot(EIRShot::Replay, 0.f); Cam->Cut(); }
	if (Arena) { Arena->SetGoalLight(GoalSignLast, false); }
	if (FX) { FX->Clear(); }
}

void AIRGameMode::EndReplay()
{
	bReplaying = false;
	for (AIRPlayer* P : AllPlayers())
	{
		if (P->AnimInst) { P->AnimInst->bFrozen = false; P->AnimInst->StickScale = 1.f; }
	}
	SetupFaceoff(FVector2D::ZeroVector);
	SetPhase(EIRMatchPhase::FaceoffSetup);
}

void AIRGameMode::TickReplay(float Dt)
{
	const FIRPadState& Any = FIRInput::Get().AnyState();
	if (ReplayBuf.Num() < 2 || (PhaseTime > 0.5f && (Any.bConfirm || Any.bShootPressed || Any.bPausePressed)))
	{
		EndReplay();
		return;
	}
	ReplayCursor += Dt * 0.55f;
	if (ReplayCursor >= ReplayEnd)
	{
		EndReplay();
		return;
	}
	// find the frame pair
	int32 I = 0;
	while (I < ReplayBuf.Num() - 2 && ReplayBuf[I + 1].T < ReplayCursor) { ++I; }
	const FIRReplayFrame& F0 = ReplayBuf[I];
	const FIRReplayFrame& F1 = ReplayBuf[I + 1];
	const float A = FMath::Clamp((ReplayCursor - F0.T) / FMath::Max(1e-3f, F1.T - F0.T), 0.f, 1.f);
	TArray<AIRPlayer*> Ps = AllPlayers();
	for (int32 i = 0; i < Ps.Num() && i < F0.Actors.Num() && i < F1.Actors.Num(); ++i)
	{
		const FIRReplayActor& X0 = F0.Actors[i];
		const FIRReplayActor& X1 = F1.Actors[i];
		const FVector P = FMath::Lerp(X0.Pos, X1.Pos, A);
		float DY = X1.Yaw - X0.Yaw;
		while (DY > PI) { DY -= 2 * PI; }
		while (DY < -PI) { DY += 2 * PI; }
		const float Yaw = X0.Yaw + DY * A;
		Ps[i]->SetActorLocationAndRotation(P, FRotator(0.f, FMath::RadiansToDegrees(Yaw), 0.f));
		if (UIRAnimInstance* AI = Ps[i]->AnimInst)
		{
			const bool bSame = X0.Seq == X1.Seq;
			const float T = bSame ? FMath::Lerp(X0.Time, X1.Time, A) : X1.Time;
			AI->bFrozen = true;
			AI->StickScale = X1.StickScale;
			AI->ForcePose(bSame ? X0.Seq : X1.Seq, T, X1.UpperSeq, X1.UpperTime, X1.UpperW);
		}
		if (Ps[i]->Ring) { Ps[i]->Ring->SetVisibility(false); }
	}
	if (Puck)
	{
		Puck->Pos = FMath::Lerp(F0.Puck, F1.Puck, A);
		if (FX && F1.bPuckFire) { FX->FireTrail(Puck->Pos, F1.Puck - F0.Puck); }
	}
}
