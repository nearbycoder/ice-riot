#include "IRRoster.h"

namespace
{
	struct FP { const TCHAR* First; const TCHAR* Last; int32 Num; uint8 Spd, Sht, Acc, Pas, Chk, Hnd, Fgt; float Skin; float H; float B; bool Lefty; };
	struct FT { const TCHAR* Id; const TCHAR* City; const TCHAR* Name; const TCHAR* Abbr; FLinearColor P, S, T; int32 Stars; FP Sk[6]; FP G; uint8 GoalieR; bool bSecret; };

	FLinearColor SkinTone(float T)
	{
		// 0 = light .. 1 = deep (linear-ish values that read well under arena lights)
		const FLinearColor A(0.85f, 0.62f, 0.50f), B(0.62f, 0.40f, 0.27f), C(0.30f, 0.17f, 0.10f), D(0.14f, 0.075f, 0.045f);
		if (T < 0.33f) { return FLinearColor::LerpUsingHSV(A, B, T / 0.33f); }
		if (T < 0.66f) { return FLinearColor::LerpUsingHSV(B, C, (T - 0.33f) / 0.33f); }
		return FLinearColor::LerpUsingHSV(C, D, (T - 0.66f) / 0.34f);
	}

	const FLinearColor White(0.88f, 0.88f, 0.9f);

	const FT GTeams[] = {
		{ TEXT("NAR"), TEXT("Northport"), TEXT("Narwhals"), TEXT("NPT"), FLinearColor(0.0f, 0.42f, 0.40f), FLinearColor(0.008f, 0.025f, 0.10f), White, 4,
			{ { TEXT("Mikko"), TEXT("Halloran"), 19, 8, 7, 8, 9, 6, 8, 5, 0.05f, 1.0f, 0.98f, false },
			  { TEXT("Dez"), TEXT("Okafor"), 44, 7, 8, 6, 6, 8, 6, 7, 0.85f, 1.03f, 1.05f, false },
			  { TEXT("Rory"), TEXT("Lindqvist"), 7, 9, 6, 7, 8, 4, 9, 4, 0.1f, 0.97f, 0.95f, true },
			  { TEXT("Theo"), TEXT("Marchetti"), 22, 7, 7, 7, 7, 6, 7, 6, 0.25f, 1.0f, 1.0f, false },
			  { TEXT("Kai"), TEXT("Tanaka"), 11, 8, 6, 8, 7, 5, 8, 4, 0.3f, 0.96f, 0.95f, true },
			  { TEXT("Bram"), TEXT("Feeney"), 4, 6, 7, 5, 6, 8, 5, 8, 0.0f, 1.05f, 1.08f, false } },
			{ TEXT("Olli"), TEXT("Varga"), 31, 5, 5, 5, 5, 5, 5, 5, 0.15f, 1.04f, 1.05f, false }, 8, false },
		{ TEXT("INF"), TEXT("Brimstone"), TEXT("Inferno"), TEXT("BRM"), FLinearColor(0.50f, 0.01f, 0.015f), FLinearColor(1.0f, 0.25f, 0.0f), FLinearColor(0.02f, 0.02f, 0.02f), 4,
			{ { TEXT("Vince"), TEXT("Ashcroft"), 91, 8, 9, 8, 7, 5, 8, 5, 0.1f, 1.0f, 1.0f, false },
			  { TEXT("Marco"), TEXT("Delgado"), 17, 7, 9, 7, 6, 6, 7, 6, 0.4f, 0.99f, 1.0f, true },
			  { TEXT("Jax"), TEXT("Kowal"), 55, 6, 8, 6, 5, 8, 5, 8, 0.05f, 1.05f, 1.1f, false },
			  { TEXT("Tariq"), TEXT("Bell"), 9, 8, 8, 7, 7, 5, 8, 5, 0.75f, 0.98f, 0.97f, false },
			  { TEXT("Sully"), TEXT("Brennan"), 28, 7, 7, 6, 6, 7, 6, 7, 0.0f, 1.02f, 1.04f, false },
			  { TEXT("Niko"), TEXT("Petrakis"), 3, 6, 8, 6, 6, 7, 5, 6, 0.3f, 1.03f, 1.06f, true } },
			{ TEXT("Gus"), TEXT("Moreau"), 35, 5, 5, 5, 5, 5, 5, 5, 0.2f, 1.03f, 1.04f, false }, 6, false },
		{ TEXT("YET"), TEXT("Glacier Bay"), TEXT("Yetis"), TEXT("GLB"), FLinearColor(0.025f, 0.2f, 0.62f), White, FLinearColor(0.45f, 0.5f, 0.56f), 3,
			{ { TEXT("Bjorn"), TEXT("Eklund"), 8, 6, 7, 6, 7, 8, 6, 7, 0.0f, 1.06f, 1.1f, false },
			  { TEXT("Wes"), TEXT("Harlan"), 33, 6, 6, 6, 6, 9, 5, 8, 0.15f, 1.06f, 1.12f, false },
			  { TEXT("Ivan"), TEXT("Sorokin"), 14, 7, 7, 7, 7, 6, 7, 6, 0.05f, 1.0f, 1.02f, true },
			  { TEXT("Cole"), TEXT("Whitaker"), 21, 7, 6, 7, 8, 6, 7, 5, 0.1f, 0.99f, 1.0f, false },
			  { TEXT("Anders"), TEXT("Nyquist"), 2, 6, 6, 6, 6, 8, 5, 7, 0.0f, 1.04f, 1.08f, false },
			  { TEXT("Lev"), TEXT("Marek"), 26, 7, 7, 7, 6, 7, 6, 6, 0.2f, 1.0f, 1.03f, true } },
			{ TEXT("Sven"), TEXT("Rask"), 1, 5, 5, 5, 5, 5, 5, 5, 0.0f, 1.07f, 1.1f, false }, 9, false },
		{ TEXT("HAM"), TEXT("Steel Valley"), TEXT("Hammers"), TEXT("STV"), FLinearColor(0.018f, 0.018f, 0.022f), FLinearColor(1.0f, 0.6f, 0.02f), White, 3,
			{ { TEXT("Dutch"), TEXT("Kowalczyk"), 27, 6, 7, 6, 6, 9, 5, 9, 0.05f, 1.05f, 1.12f, false },
			  { TEXT("Rocco"), TEXT("Santangelo"), 12, 7, 7, 7, 7, 8, 6, 8, 0.3f, 1.01f, 1.05f, false },
			  { TEXT("Marcus"), TEXT("Greer"), 40, 6, 8, 6, 5, 9, 5, 9, 0.8f, 1.05f, 1.12f, false },
			  { TEXT("Danny"), TEXT("Pruitt"), 16, 7, 7, 7, 7, 7, 7, 6, 0.1f, 1.0f, 1.0f, true },
			  { TEXT("Hank"), TEXT("Oberlin"), 6, 5, 6, 5, 5, 9, 4, 10, 0.05f, 1.07f, 1.15f, false },
			  { TEXT("Eddie"), TEXT("Voss"), 18, 7, 7, 6, 6, 7, 6, 7, 0.2f, 1.0f, 1.02f, false } },
			{ TEXT("Moose"), TEXT("Lachance"), 30, 5, 5, 5, 5, 5, 5, 5, 0.1f, 1.06f, 1.1f, false }, 7, false },
		{ TEXT("BRW"), TEXT("Bayou"), TEXT("Brawlers"), TEXT("BAY"), FLinearColor(0.05f, 0.2f, 0.035f), FLinearColor(0.85f, 0.55f, 0.04f), FLinearColor(0.02f, 0.02f, 0.02f), 3,
			{ { TEXT("Boudreaux"), TEXT("LeBlanc"), 66, 7, 7, 6, 6, 8, 6, 10, 0.2f, 1.04f, 1.1f, false },
			  { TEXT("Tyrell"), TEXT("Fontenot"), 10, 8, 7, 7, 7, 6, 7, 7, 0.85f, 0.99f, 1.0f, false },
			  { TEXT("Gator"), TEXT("Thibodeaux"), 77, 6, 8, 6, 5, 8, 5, 9, 0.1f, 1.05f, 1.12f, true },
			  { TEXT("Remy"), TEXT("Guidry"), 15, 8, 6, 7, 8, 6, 8, 6, 0.3f, 0.98f, 0.98f, false },
			  { TEXT("Clay"), TEXT("Arceneaux"), 5, 6, 6, 5, 6, 8, 5, 9, 0.05f, 1.05f, 1.12f, false },
			  { TEXT("Luc"), TEXT("Hebert"), 24, 7, 7, 6, 6, 7, 6, 8, 0.15f, 1.01f, 1.04f, false } },
			{ TEXT("Big Earl"), TEXT("Comeaux"), 39, 5, 5, 5, 5, 5, 5, 5, 0.6f, 1.08f, 1.15f, false }, 6, false },
		{ TEXT("VIP"), TEXT("Neon Coast"), TEXT("Vipers"), TEXT("NCV"), FLinearColor(0.85f, 0.0f, 0.42f), FLinearColor(0.22f, 0.02f, 0.68f), White, 4,
			{ { TEXT("Zane"), TEXT("Castillo"), 88, 10, 7, 8, 8, 4, 10, 4, 0.35f, 0.96f, 0.93f, false },
			  { TEXT("Ricky"), TEXT("Nakamura"), 13, 9, 7, 8, 9, 4, 9, 4, 0.3f, 0.97f, 0.94f, true },
			  { TEXT("Jules"), TEXT("Moreno"), 23, 9, 8, 7, 7, 5, 8, 5, 0.45f, 0.98f, 0.96f, false },
			  { TEXT("Felix"), TEXT("Duarte"), 20, 8, 6, 8, 8, 5, 8, 5, 0.5f, 0.99f, 0.97f, false },
			  { TEXT("Ash"), TEXT("Kerrigan"), 71, 9, 7, 7, 7, 5, 8, 5, 0.05f, 0.97f, 0.95f, true },
			  { TEXT("Omar"), TEXT("Haddad"), 29, 8, 7, 7, 7, 6, 7, 6, 0.4f, 1.0f, 1.0f, false } },
			{ TEXT("Lucky"), TEXT("Reyes"), 37, 5, 5, 5, 5, 5, 5, 5, 0.4f, 1.0f, 1.0f, false }, 6, false },
		{ TEXT("GRZ"), TEXT("Timber Ridge"), TEXT("Grizzlies"), TEXT("TMR"), FLinearColor(0.18f, 0.07f, 0.025f), FLinearColor(0.95f, 0.33f, 0.02f), FLinearColor(0.85f, 0.74f, 0.52f), 3,
			{ { TEXT("Gunnar"), TEXT("Thorsen"), 34, 6, 9, 6, 6, 9, 5, 8, 0.0f, 1.07f, 1.14f, false },
			  { TEXT("Silas"), TEXT("McAllister"), 25, 7, 7, 7, 7, 7, 6, 7, 0.05f, 1.02f, 1.05f, true },
			  { TEXT("Jonah"), TEXT("Redcloud"), 47, 7, 8, 7, 6, 8, 6, 7, 0.4f, 1.03f, 1.06f, false },
			  { TEXT("Barrett"), TEXT("Kane"), 3, 6, 7, 6, 6, 8, 5, 8, 0.1f, 1.05f, 1.1f, false },
			  { TEXT("Tuck"), TEXT("Haywood"), 62, 7, 6, 6, 7, 7, 6, 7, 0.15f, 1.0f, 1.04f, false },
			  { TEXT("Arlo"), TEXT("Bergstrom"), 8, 8, 7, 7, 7, 6, 7, 6, 0.0f, 0.99f, 1.0f, true } },
			{ TEXT("Hoss"), TEXT("Dumont"), 33, 5, 5, 5, 5, 5, 5, 5, 0.05f, 1.07f, 1.12f, false }, 7, false },
		{ TEXT("COM"), TEXT("Rocket City"), TEXT("Comets"), TEXT("RCC"), FLinearColor(0.02f, 0.07f, 0.6f), FLinearColor(0.75f, 0.02f, 0.02f), White, 5,
			{ { TEXT("Ace"), TEXT("Donovan"), 97, 9, 9, 9, 8, 5, 9, 5, 0.1f, 1.0f, 0.98f, false },
			  { TEXT("Mateo"), TEXT("Rivera"), 41, 8, 8, 8, 8, 6, 8, 6, 0.4f, 0.99f, 1.0f, true },
			  { TEXT("Sasha"), TEXT("Volkov"), 74, 8, 9, 7, 7, 6, 8, 6, 0.0f, 1.01f, 1.02f, false },
			  { TEXT("Jamal"), TEXT("Pierce"), 21, 9, 7, 8, 8, 6, 8, 5, 0.85f, 0.99f, 0.98f, false },
			  { TEXT("Erik"), TEXT("Lund"), 5, 7, 8, 7, 7, 8, 6, 7, 0.0f, 1.04f, 1.08f, false },
			  { TEXT("Danny"), TEXT("O'Shea"), 12, 8, 7, 7, 8, 6, 7, 6, 0.05f, 0.98f, 0.98f, true } },
			{ TEXT("Vlad"), TEXT("Kasparov"), 40, 5, 5, 5, 5, 5, 5, 5, 0.05f, 1.05f, 1.06f, false }, 7, false },
		// secret super teams
		{ TEXT("ALL"), TEXT("Riot"), TEXT("All-Stars"), TEXT("ALL"), FLinearColor(0.85f, 0.85f, 0.88f), FLinearColor(0.95f, 0.65f, 0.05f), FLinearColor(0.03f, 0.03f, 0.05f), 5,
			{ { TEXT("Blaze"), TEXT("Maxwell"), 99, 10, 10, 9, 9, 7, 10, 7, 0.1f, 1.0f, 1.0f, false },
			  { TEXT("Ty"), TEXT("Thunder"), 66, 9, 10, 9, 8, 8, 9, 8, 0.8f, 1.03f, 1.05f, true },
			  { TEXT("Rex"), TEXT("Hammond"), 4, 8, 9, 8, 8, 10, 7, 10, 0.05f, 1.06f, 1.1f, false },
			  { TEXT("Nova"), TEXT("Quinn"), 10, 10, 9, 9, 10, 6, 10, 6, 0.4f, 0.98f, 0.96f, false },
			  { TEXT("Duke"), TEXT("Steele"), 77, 9, 9, 8, 8, 9, 8, 9, 0.2f, 1.04f, 1.06f, false },
			  { TEXT("Flash"), TEXT("Gordon"), 8, 10, 8, 9, 9, 6, 9, 6, 0.6f, 0.97f, 0.95f, true } },
			{ TEXT("Wall"), TEXT("Brickman"), 1, 5, 5, 5, 5, 5, 5, 5, 0.1f, 1.06f, 1.1f, false }, 10, true },
		{ TEXT("DEV"), TEXT("Pixel"), TEXT("Pushers"), TEXT("DEV"), FLinearColor(0.02f, 0.75f, 0.15f), FLinearColor(0.02f, 0.02f, 0.02f), FLinearColor(0.9f, 0.9f, 0.9f), 5,
			{ { TEXT("Null"), TEXT("Pointer"), 0, 10, 9, 9, 9, 8, 10, 8, 0.2f, 1.0f, 1.0f, false },
			  { TEXT("Stack"), TEXT("Overflow"), 64, 9, 10, 8, 8, 8, 9, 8, 0.5f, 1.02f, 1.04f, true },
			  { TEXT("Hot"), TEXT("Fix"), 42, 9, 9, 9, 9, 7, 9, 7, 0.1f, 1.0f, 1.0f, false },
			  { TEXT("Merge"), TEXT("Conflict"), 13, 8, 9, 8, 8, 10, 8, 10, 0.8f, 1.05f, 1.1f, false },
			  { TEXT("Byte"), TEXT("Size"), 8, 10, 8, 9, 9, 6, 10, 6, 0.3f, 0.95f, 0.94f, true },
			  { TEXT("Ship"), TEXT("It"), 1, 9, 9, 9, 9, 8, 9, 8, 0.0f, 1.01f, 1.02f, false } },
			{ TEXT("Code"), TEXT("Freeze"), 31, 5, 5, 5, 5, 5, 5, 5, 0.6f, 1.05f, 1.08f, false }, 10, true },
	};

	FIRPlayerInfo Make(const FP& P)
	{
		FIRPlayerInfo I;
		I.First = P.First;
		I.Last = P.Last;
		I.Number = P.Num;
		I.R.Speed = P.Spd; I.R.Shot = P.Sht; I.R.Accuracy = P.Acc; I.R.Pass = P.Pas; I.R.Check = P.Chk; I.R.Hands = P.Hnd; I.R.Fight = P.Fgt;
		I.Skin = SkinTone(P.Skin);
		I.Height = P.H;
		I.Bulk = P.B;
		I.bLefty = P.Lefty;
		return I;
	}
}

const TArray<FIRTeamInfo>& IRRoster::Teams()
{
	static TArray<FIRTeamInfo> Out;
	if (Out.Num() == 0)
	{
		for (const FT& T : GTeams)
		{
			FIRTeamInfo I;
			I.Id = T.Id; I.City = T.City; I.Name = T.Name; I.Abbrev = T.Abbr;
			I.Primary = T.P; I.Secondary = T.S; I.Trim = T.T;
			I.Stars = T.Stars;
			I.bSecret = T.bSecret;
			for (int32 i = 0; i < IR_ROSTER_SKATERS; ++i)
			{
				I.Skaters[i] = Make(T.Sk[i]);
			}
			I.Goalie = Make(T.G);
			I.Goalie.R.Goalie = T.GoalieR;
			Out.Add(I);
		}
	}
	return Out;
}

int32 IRRoster::NumSelectable(bool bIncludeSecret)
{
	int32 N = 0;
	for (const FIRTeamInfo& T : Teams())
	{
		N += (!T.bSecret || bIncludeSecret) ? 1 : 0;
	}
	return N;
}
