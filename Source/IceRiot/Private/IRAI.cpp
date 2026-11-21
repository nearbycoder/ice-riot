// CPU brains for skaters, goalies and fighters. Every AI decision goes through FIRIntent, exactly like a human pad.
#include "IRGameMode.h"
#include "IRRink.h"

using namespace IRRink;

namespace
{
	FVector2D Clamp2(FVector2D P, float Margin = 120.f)
	{
		FVector2D N;
		ClampInside(P, Margin, N);
		return P;
	}

	FVector2D Seek(const AIRPlayer* P, const FVector2D& Target, float SlowRadius = 250.f)
	{
		const FVector2D To = Target - P->Pos;
		const float D = To.Size();
		if (D < 1.f) { return FVector2D::ZeroVector; }
		return To / D * FMath::Clamp(D / SlowRadius, 0.f, 1.f);
	}
}

float AIRGameMode::LaneOpen(FVector2D From, FVector2D To, int32 DefTeam, float Width) const
{
	const FVector2D Seg = To - From;
	const float L2 = Seg.SizeSquared();
	float Open = 1.f;
	auto Test = [&](const AIRPlayer* D)
	{
		if (!D || D->IsDown() || D->IsInFight()) { return; }
		const float T = L2 > 1.f ? FMath::Clamp(FVector2D::DotProduct(D->Pos - From, Seg) / L2, 0.f, 1.f) : 0.f;
		if (T <= 0.02f || T >= 0.98f) { return; }
		const float Dist = FVector2D::Distance(From + Seg * T, D->Pos);
		Open = FMath::Min(Open, FMath::Clamp((Dist - 30.f) / Width, 0.f, 1.f));
	};
	for (AIRPlayer* D : Skaters[DefTeam]) { Test(D); }
	return Open;
}

float AIRGameMode::Pressure(AIRPlayer* P) const
{
	float Best = 0.f;
	for (AIRPlayer* D : Skaters[1 - P->Team])
	{
		if (D->IsDown() || D->IsInFight()) { continue; }
		const float Dist = FVector2D::Distance(D->Pos, P->Pos);
		Best = FMath::Max(Best, FMath::Clamp(1.f - (Dist - 110.f) / 380.f, 0.f, 1.f));
	}
	return Best;
}

float AIRGameMode::ShotQuality(AIRPlayer* P) const
{
	const int32 A = AttackSign(P->Team);
	const FVector2D Goal(GoalLineX * A, 0.f);
	const float Depth = (Goal.X - P->Pos.X) * A;          // distance in front of the goal line
	if (Depth < 60.f) { return 0.f; }                      // behind the net
	const float Dist = FVector2D::Distance(P->Pos, Goal);
	const float Angle = FMath::Abs(P->Pos.Y) / FMath::Max(Depth, 1.f);
	float Q = FMath::Clamp(1.f - (Dist - 450.f) / 1500.f, 0.f, 1.f);
	Q *= FMath::Clamp(1.4f - Angle * 0.55f, 0.15f, 1.f);
	Q *= 0.45f + 0.55f * LaneOpen(P->Pos, Goal, 1 - P->Team, 70.f);
	if (const AIRPlayer* G = Goalies[1 - P->Team])
	{
		// goalie out of position or down
		Q += FMath::Clamp((FMath::Abs(G->Pos.Y - P->Pos.Y * 0.15f) - 40.f) / 200.f, 0.f, 0.3f);
		if (G->IsDown() || G->Action == EIRAction::GoalieSave) { Q += 0.35f; }
	}
	return Q;
}

FVector2D AIRGameMode::SupportSpot(AIRPlayer* P, int32 Slot) const
{
	const AIRPlayer* C = PuckCarrier();
	const int32 A = AttackSign(P->Team);
	const FVector2D CP = C ? C->Pos : FVector2D(Puck->Pos.X, Puck->Pos.Y);
	const bool bInZone = CP.X * A > BlueLineX - 100.f;
	const float SideY = CP.Y > 0.f ? -1.f : 1.f;
	FVector2D S;
	if (bInZone)
	{
		switch (Slot % 3)
		{
		case 0: S = FVector2D((GoalLineX - 330.f) * A, SideY * 130.f); break;                          // crash the net, far post
		case 1: S = FVector2D(FMath::Clamp(CP.X * A + 150.f, BlueLineX + 300.f, GoalLineX - 500.f) * A, SideY * 560.f); break; // weak-side wing
		default: S = FVector2D((BlueLineX + 180.f) * A, CP.Y * 0.25f); break;                         // the point
		}
	}
	else
	{
		// breakout / neutral zone: spread out ahead of the carrier
		switch (Slot % 3)
		{
		case 0: S = FVector2D(CP.X + 650.f * A, SideY * 120.f); break;
		case 1: S = FVector2D(CP.X + 900.f * A, SideY * 640.f); break;
		default: S = FVector2D(CP.X - 250.f * A, -SideY * 500.f); break;
		}
	}
	// keep onside-ish and inside the rink
	S.X = FMath::Clamp(S.X * A, -GoalLineX + 150.f, GoalLineX - 250.f) * A;
	return Clamp2(S, 140.f);
}

FIRIntent AIRGameMode::ThinkAI(AIRPlayer* P, float Dt)
{
	FIRIntent In;
	if (P->IsReferee())
	{
		// stay out of the play along the far boards
		const FVector2D Puck2 = Puck ? FVector2D(Puck->Pos.X, Puck->Pos.Y) : FVector2D::ZeroVector;
		const FVector2D Spot(FMath::Clamp(Puck2.X * 0.7f, -1500.f, 1500.f), -HalfWidth + 150.f);
		In.MoveWorld = Seek(P, Spot, 400.f) * 0.7f;
		return In;
	}
	if (Phase != EIRMatchPhase::Live || !Puck)
	{
		return In;
	}
	P->AITimer -= Dt;
	P->AIActTimer -= Dt;
	P->AIWeave += Dt;

	// skill: CPU opponents of humans scale with difficulty, CPU teammates of humans are solid, attract mode is even
	bool bVsHuman = false;
	for (const FIRHuman& H : Humans) { if (H.bActive && H.Team != P->Team) { bVsHuman = true; } }
	const float Skill = Mode == EIRMode::Attract ? 0.6f : (bVsHuman ? FMath::Lerp(0.25f, 1.f, Difficulty01()) : 0.65f);
	const float Boost = CatchupBoost[P->Team];

	const int32 A = AttackSign(P->Team);
	const FVector2D Goal(GoalLineX * A, 0.f);
	const FVector2D OwnGoal(-GoalLineX * A, 0.f);
	const FVector2D Puck2(Puck->Pos.X, Puck->Pos.Y);
	AIRPlayer* C = PuckCarrier();
	TArray<AIRPlayer*> Mates = TeamSkaters(P->Team);
	TArray<AIRPlayer*> Opps = TeamSkaters(1 - P->Team);

	// ------------------------------------------------------------ carrying the puck
	if (C == P)
	{
		// teammates (humans) can call for it or ask for a shot
		AIRPlayer* Caller = nullptr;
		for (AIRPlayer* M : Mates) { if (M != P && M->PassComboTimer > 0.f) { Caller = M; } }
		if (Caller && P->CanAct())
		{
			Caller->PassComboTimer = 0.f;
			In.bPassPressed = true;
			In.PassTo = Caller;
			return In;
		}
		const float Q = ShotQuality(P);
		const float Press = Pressure(P);
		const float Dist = FVector2D::Distance(P->Pos, Goal);

		// already winding up a slap shot: hold for the planned time
		if (P->Action == EIRAction::ShotCharge)
		{
			In.bShoot = true;
			In.ShotCharge = P->AIChargeTarget;
			In.MoveWorld = Seek(P, Goal, 800.f) * 0.5f;
			return In;
		}
		if (P->CanAct() && P->AITimer <= 0.f)
		{
			P->AITimer = FMath::Lerp(0.35f, 0.12f, Skill) + FMath::FRandRange(0.f, 0.15f);
			const bool bForcedShot = P->ShootComboTimer > 0.f;
			const float ShootThresh = FMath::Lerp(0.7f, 0.5f, Skill) - Boost * 0.05f - (Press > 0.7f ? 0.12f : 0.f) - FMath::Clamp(P->PossessTime - 2.5f, 0.f, 2.f) * 0.08f;
			if ((Q > ShootThresh && P->PossessTime > 0.35f && FMath::FRand() < 0.7f) || (bForcedShot && Q > 0.05f))
			{
				P->ShootComboTimer = 0.f;
				In.bShootPressed = true;
				In.bShoot = true;
				const bool bPower = (P->Turbo > 0.5f || P->Rage > 0.f) && Dist < 1700.f && FMath::FRand() < FMath::Lerp(0.15f, 0.45f, Skill) + (P->Rage > 0.f ? 0.5f : 0.f) + (bTestPowerShots ? 0.9f : 0.f);
				In.bTurbo = bPower;
				if (bPower) { P->AIChargeTarget = 0.f; }
				else if (Dist < 850.f || Press > 0.6f) { P->AIChargeTarget = 0.05f; }          // quick wrister
				else { P->AIChargeTarget = FMath::FRandRange(0.35f, 0.8f); }                 // slapper
				In.ShotCharge = P->AIChargeTarget;
				In.MoveWorld = Seek(P, Goal, 800.f);
				return In;
			}
			// pass when pressured or a teammate is in a much better spot
			AIRPlayer* Best = nullptr;
			float BestScore = 0.f;
			for (AIRPlayer* M : Mates)
			{
				if (M == P || M->IsDown() || M->IsInFight()) { continue; }
				const float Open = LaneOpen(P->Pos, M->Pos, 1 - P->Team, 90.f);
				if (Open < 0.45f) { continue; }
				float S = ShotQuality(M) - Q + Open * 0.3f - Pressure(M) * 0.4f + (M->Pos.X - P->Pos.X) * A / 2500.f;
				S += Press * 0.45f;
				if (M->HumanIndex >= 0) { S += 0.12f; }
				if (S > BestScore) { BestScore = S; Best = M; }
			}
			if (Best && BestScore > FMath::Lerp(0.45f, 0.25f, Skill) && FMath::FRand() < 0.8f)
			{
				In.bPassPressed = true;
				In.PassTo = Best;
				// set up the one-timer when the receiver is in a scoring spot
				if (ShotQuality(Best) > 0.45f && FMath::FRand() < Skill * 0.7f)
				{
					P->bAutoOneTimer = true;
				}
				return In;
			}
			// deke a close defender in front
			if (Press > 0.75f && FMath::FRand() < 0.18f + P->Info.R.Hands * 0.02f)
			{
				In.bSwitchPressed = true;
			}
			// stuck behind own net / along the boards with pressure: chip it up
			if (Press > 0.85f && P->Pos.X * A < -BlueLineX && FMath::FRand() < 0.3f)
			{
				In.bPassPressed = true;
				In.PassTo = Best;
				return In;
			}
		}
		// skate toward the slot, weaving around defenders
		FVector2D Target = FVector2D((GoalLineX - 380.f) * A, FMath::Sin(P->AIWeave * 1.3f + P->TeamIndex) * 260.f);
		if ((P->Pos.X * A) > GoalLineX - 250.f)
		{
			Target = FVector2D((GoalLineX - 500.f) * A, P->Pos.Y > 0 ? 250.f : -250.f);   // come out from behind the net
		}
		FVector2D Dir = (Target - P->Pos).GetSafeNormal();
		for (AIRPlayer* D : Opps)
		{
			const FVector2D To = D->Pos - P->Pos;
			const float DD = To.Size();
			if (DD < 400.f && DD > 1.f && FVector2D::DotProduct(To / DD, Dir) > 0.2f)
			{
				const FVector2D Side(-Dir.Y, Dir.X);
				const float S = FVector2D::DotProduct(To, Side) > 0.f ? -1.f : 1.f;
				Dir = (Dir + Side * S * (1.f - DD / 400.f) * 1.4f).GetSafeNormal();
			}
		}
		In.MoveWorld = Dir;
		const bool bOpenIce = Press < 0.3f && LaneOpen(P->Pos, Goal, 1 - P->Team, 140.f) > 0.8f;
		In.bTurbo = (bOpenIce && P->Turbo > 0.35f && FMath::FRand() < 0.8f) || (Press > 0.5f && P->Turbo > 0.6f);
		if (bOpenIce && (P->Pos.X * A) > 0.f && FMath::FRand() < Dt * 0.3f) { Announce(TEXT("VO_Breakaway"), 0.6f); }
		return In;
	}

	// ------------------------------------------------------------ our team has it: support
	if (C && C->Team == P->Team)
	{
		int32 Slot = 0;
		for (AIRPlayer* M : Mates)
		{
			if (M == C) { continue; }
			if (M == P) { break; }
			Slot++;
		}
		// a pass on its way to me: go get it and maybe one-time it
		if (P->OneTimerWindow > 0.f && Puck->Kind == EIRShotKind::Pass)
		{
			In.MoveWorld = Seek(P, Puck2 + FVector2D(Puck->Vel.X, Puck->Vel.Y) * 0.15f, 300.f) * 0.6f;
			const float Arrive = FVector2D::Distance(Puck2, P->Pos) / FMath::Max(300.f, FVector2D(Puck->Vel).Size());
			if (P->bAutoOneTimer || (ShotQuality(P) > 0.5f && Arrive < 0.35f && FMath::FRand() < Skill * 0.5f))
			{
				In.bShootPressed = P->Action == EIRAction::None;
				In.bShoot = true;
			}
			return In;
		}
		const FVector2D Spot = SupportSpot(P, Slot);
		In.MoveWorld = Seek(P, Spot, 300.f);
		In.bTurbo = FVector2D::Distance(P->Pos, Spot) > 900.f && P->Turbo > 0.5f;
		return In;
	}

	// ------------------------------------------------------------ the puck is loose (or a pass/shot is in flight)
	if (!C)
	{
		// who is closest (by time) among my team?
		const FVector2D PuckAhead = Puck2 + FVector2D(Puck->Vel.X, Puck->Vel.Y) * 0.25f;
		TArray<AIRPlayer*> Sorted = Mates;
		Sorted.Sort([&](const AIRPlayer& X, const AIRPlayer& Y) { return FVector2D::DistSquared(X.Pos, PuckAhead) < FVector2D::DistSquared(Y.Pos, PuckAhead); });
		const int32 Rank = Sorted.IndexOfByKey(P);
		const bool bOurShot = Puck->LastTouch && Puck->LastTouch->Team == P->Team && Puck->Kind != EIRShotKind::None;
		if (Rank == 0 || (Rank == 1 && !bOurShot && FVector2D::Distance(P->Pos, PuckAhead) < 900.f))
		{
			In.MoveWorld = Seek(P, PuckAhead, 120.f);
			In.bTurbo = P->Turbo > 0.3f && FVector2D::Distance(P->Pos, PuckAhead) > 250.f;
			// opponents near the loose puck get bumped
			for (AIRPlayer* D : Opps)
			{
				if (P->CanAct() && P->AIActTimer <= 0.f && FVector2D::Distance(D->Pos, P->Pos) < 160.f && FVector2D::DotProduct((D->Pos - P->Pos).GetSafeNormal(), P->Forward()) > 0.5f && FMath::FRand() < 0.25f * Skill)
				{
					In.bShootPressed = true;
					In.bTurbo = FMath::FRand() < 0.08f * Skill;   // turbo would turn the bump into a power check
					P->AIActTimer = 1.f;
				}
			}
			return In;
		}
		// others: slot coverage / support depending on where the puck is
		const bool bOurZone = Puck2.X * A < 0.f;
		FVector2D Spot = bOurZone ? FVector2D(OwnGoal.X * 0.75f, (Rank == 1 ? 1.f : -1.f) * 300.f) : SupportSpot(P, Rank);
		In.MoveWorld = Seek(P, Spot, 300.f);
		return In;
	}

	// ------------------------------------------------------------ defense: the other team has it
	TArray<AIRPlayer*> Sorted = Mates;
	const FVector2D CarrierAhead = C->Pos + C->Vel * 0.35f;
	Sorted.Sort([&](const AIRPlayer& X, const AIRPlayer& Y) { return FVector2D::DistSquared(X.Pos, CarrierAhead) < FVector2D::DistSquared(Y.Pos, CarrierAhead); });
	const int32 Rank = Sorted.IndexOfByKey(P);
	const float DistC = FVector2D::Distance(P->Pos, C->Pos);
	if (Rank == 0)
	{
		// pressure the carrier: take the inside lane toward our net
		FVector2D Intercept = C->Pos + C->Vel * FMath::Clamp(DistC / 1400.f, 0.1f, 0.6f);
		Intercept += (OwnGoal - C->Pos).GetSafeNormal() * 60.f;
		In.MoveWorld = Seek(P, Intercept, 80.f);
		In.bTurbo = DistC > 300.f && P->Turbo > 0.25f + (1.f - Skill) * 0.3f;
		if (P->CanAct() && P->AIActTimer <= 0.f && DistC < 230.f)
		{
			const float Facing = FVector2D::DotProduct((C->Pos - P->Pos).GetSafeNormal(), P->Forward());
			P->AIActTimer = FMath::Lerp(0.9f, 0.35f, Skill) + FMath::FRandRange(0.f, 0.3f);
			const float R = FMath::FRand();
			if (Facing > 0.4f && DistC < 170.f && R < 0.45f + Skill * 0.2f)
			{
				In.bShootPressed = true;                                   // body check
				In.bTurbo = P->Turbo > 0.6f && FMath::FRand() < 0.07f + Skill * 0.08f + Boost * 0.05f;   // power check!
			}
			else if (R < 0.85f)
			{
				In.bPassPressed = true;                                    // poke check
				In.bTurbo = false;
			}
			else
			{
				In.bHookPressed = true;
				In.bTurbo = FMath::FRand() < 0.2f;
			}
		}
		return In;
	}
	// second man covers the slot, third shadows the most dangerous open attacker (goal-side)
	if (Rank == 1)
	{
		const FVector2D Slot = OwnGoal + (C->Pos - OwnGoal).GetSafeNormal() * FMath::Clamp(FVector2D::Distance(C->Pos, OwnGoal) * 0.45f, 250.f, 900.f);
		In.MoveWorld = Seek(P, Clamp2(Slot), 200.f);
		In.bFaceTarget = true;
		In.FaceTarget = C->Pos;
		In.bTurbo = FVector2D::Distance(P->Pos, Slot) > 800.f && P->Turbo > 0.5f;
	}
	else
	{
		AIRPlayer* Mark = nullptr;
		float Danger = -1e9f;
		for (AIRPlayer* O : Opps)
		{
			if (O == C) { continue; }
			const float D = -FVector2D::Distance(O->Pos, OwnGoal);
			if (D > Danger) { Danger = D; Mark = O; }
		}
		const FVector2D Spot = Mark ? Mark->Pos + (OwnGoal - Mark->Pos).GetSafeNormal() * 150.f : OwnGoal * 0.7f;
		In.MoveWorld = Seek(P, Clamp2(Spot), 200.f);
		In.bFaceTarget = true;
		In.FaceTarget = Puck2;
		In.bTurbo = FVector2D::Distance(P->Pos, Spot) > 900.f && P->Turbo > 0.5f;
		// arcade: free hits on anyone in reach
		if (Mark && P->CanAct() && P->AIActTimer <= 0.f && FVector2D::Distance(Mark->Pos, P->Pos) < 150.f && FMath::FRand() < 0.1f * Skill)
		{
			In.bShootPressed = true;
			In.bTurbo = false;
			In.bFaceTarget = false;
			P->AIActTimer = 1.5f;
		}
	}
	// intercept passes that come near
	if (Puck->Kind == EIRShotKind::Pass && !C)
	{
		In.MoveWorld = Seek(P, Puck2, 200.f);
	}
	return In;
}

FIRIntent AIRGameMode::ThinkGoalie(AIRPlayer* G, float Dt)
{
	FIRIntent In;
	if (!Puck)
	{
		return In;
	}
	const int32 S = -AttackSign(G->Team);   // our net
	const FVector2D Net(GoalLineX * S, 0.f);
	FVector2D Pk(Puck->Pos.X, Puck->Pos.Y);
	if (AIRPlayer* C = PuckCarrier()) { Pk = C->Pos + C->Vel * 0.15f; }
	FVector2D Want;
	const float Depth = (Net.X - Pk.X) * S;   // puck distance in front of our goal line
	if (Depth < 20.f)
	{
		// puck behind the net: hug the post on its side
		Want = FVector2D(Net.X - S * 25.f, FMath::Sign(Pk.Y) * (NetHalfWidth - 15.f));
	}
	else
	{
		const FVector2D Dir = (Pk - Net).GetSafeNormal();
		const float Out = FMath::Clamp(55.f + FVector2D::Distance(Pk, Net) * 0.05f, 55.f, 125.f);
		Want = Net + Dir * Out;
		Want.Y = FMath::Clamp(Want.Y, -NetHalfWidth - 15.f, NetHalfWidth + 15.f);
	}
	// incoming saved shot: slide toward it so the save looks right
	if (Puck->SaveGoalie.Get() == G)
	{
		const FVector V = Puck->Vel;
		if (FMath::Abs(V.X) > 1.f)
		{
			const float T = (G->Pos.X - Puck->Pos.X) / V.X;
			if (T > 0.f) { Want.Y = FMath::Clamp(Puck->Pos.Y + V.Y * T, -NetHalfWidth, NetHalfWidth); }
		}
	}
	const FVector2D To = Want - G->Pos;
	In.MoveWorld = To / 120.f;
	if (In.MoveWorld.SizeSquared() > 1.f) { In.MoveWorld.Normalize(); }
	In.bFaceTarget = true;
	In.FaceTarget = Pk;
	// poke-check a carrier who comes too close
	if (AIRPlayer* C = PuckCarrier())
	{
		if (C->Team != G->Team && FVector2D::Distance(C->Pos, G->Pos) < 150.f && G->CanAct() && FMath::FRand() < Dt * 2.5f)
		{
			In.bPassPressed = true;
		}
	}
	return In;
}

FIRIntent AIRGameMode::ThinkFighter(AIRPlayer* P, float Dt)
{
	FIRIntent In;
	AIRPlayer* Opp = P->FightOpponent.Get();
	if (!Opp || P->Action == EIRAction::FightKO)
	{
		return In;
	}
	bool bVsHuman = Opp->HumanIndex >= 0;
	const float Skill = Mode == EIRMode::Attract ? 0.6f : (bVsHuman ? FMath::Lerp(0.3f, 1.f, Difficulty01()) : 0.6f);
	P->AITimer -= Dt;
	In.MoveWorld = FVector2D(FMath::Sin(P->AIWeave * 1.7f), FMath::Cos(P->AIWeave * 1.3f)) * 0.6f;
	P->AIWeave += Dt;
	// block incoming haymakers
	if (Opp->Action == EIRAction::FightAttack && Opp->ActionTime < 0.15f && P->Action == EIRAction::FightIdle && FMath::FRand() < Skill * 0.55f)
	{
		In.bSwitchPressed = true;
		return In;
	}
	if (P->AITimer <= 0.f && P->Action == EIRAction::FightIdle)
	{
		P->AITimer = FMath::Lerp(0.9f, 0.35f, Skill) + FMath::FRandRange(0.f, 0.4f);
		const float R = FMath::FRand();
		if (R < 0.45f) { In.bPassPressed = true; }
		else if (R < 0.8f) { In.bShootPressed = true; }
		else if (R < 0.92f) { In.bShootPressed = true; In.bTurbo = true; }
		else { In.bHookPressed = true; }
	}
	return In;
}

FIRIntent AIRGameMode::ThinkFaceoff(AIRPlayer* P, float Dt)
{
	return FIRIntent();
}
