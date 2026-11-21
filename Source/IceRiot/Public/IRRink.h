#pragma once

#include "CoreMinimal.h"

/**
 * Rink geometry in Unreal cm (Blender meters * 100 with Y mirrored; the rink is symmetric so it doesn't matter).
 * Center ice at the origin, ice surface at Z = 0.
 */
namespace IRRink
{
	constexpr float HalfLength = 2300.f;
	constexpr float HalfWidth = 1050.f;
	constexpr float CornerRadius = 650.f;
	constexpr float BoardHeight = 107.f;
	constexpr float GlassHeight = 245.f;
	constexpr float GoalLineX = 1950.f;
	constexpr float BlueLineX = 600.f;
	constexpr float NetHalfWidth = 91.5f;
	constexpr float NetHeight = 122.f;
	constexpr float NetDepth = 100.f;
	constexpr float PostRadius = 3.f;
	constexpr float CreaseRadius = 180.f;
	constexpr float FaceoffCircleR = 400.f;
	constexpr float PuckRadius = 3.8f;
	constexpr float PuckHalfHeight = 1.27f;
	constexpr float SkaterRadius = 42.f;
	constexpr float GoalieRadius = 55.f;

	/** End-zone dots (sign of X = end, sign of Y = side), neutral dots and center. */
	inline FVector2D EndDot(int32 SideX, int32 SideY) { return FVector2D(1450.f * SideX, 550.f * SideY); }
	inline FVector2D NeutralDot(int32 SideX, int32 SideY) { return FVector2D(450.f * SideX, 550.f * SideY); }

	/** Goal mouth center on the ice for the net at end Sign (+1 = +X). */
	inline FVector GoalCenter(int32 Sign) { return FVector(GoalLineX * Sign, 0.f, 0.f); }

	/**
	 * Signed distance from P to the board's inner face (positive inside the rink) and the inward normal of the
	 * closest board point.
	 */
	inline float BoardDistance(const FVector2D& P, FVector2D& OutInwardNormal)
	{
		const float Ax = FMath::Abs(P.X), Ay = FMath::Abs(P.Y);
		const float Sx = P.X >= 0.f ? 1.f : -1.f, Sy = P.Y >= 0.f ? 1.f : -1.f;
		const float Cx = HalfLength - CornerRadius, Cy = HalfWidth - CornerRadius;
		if (Ax > Cx && Ay > Cy)
		{
			const FVector2D D(Ax - Cx, Ay - Cy);
			const float Len = D.Size();
			const FVector2D N = Len > 1e-3f ? D / Len : FVector2D(0.7071f, 0.7071f);
			OutInwardNormal = FVector2D(-N.X * Sx, -N.Y * Sy);
			return CornerRadius - Len;
		}
		const float Dx = HalfLength - Ax, Dy = HalfWidth - Ay;
		if (Dx < Dy)
		{
			OutInwardNormal = FVector2D(-Sx, 0.f);
			return Dx;
		}
		OutInwardNormal = FVector2D(0.f, -Sy);
		return Dy;
	}

	/** Push a circle of Radius back inside the boards. Returns true (and the inward normal) on contact. */
	inline bool ClampInside(FVector2D& P, float Radius, FVector2D& OutNormal)
	{
		const float D = BoardDistance(P, OutNormal);
		if (D < Radius)
		{
			P += OutNormal * (Radius - D);
			return true;
		}
		return false;
	}

	/** Net body (posts + frame + mesh) as an axis-aligned box behind the goal line at end Sign. */
	inline FBox2D NetBox(int32 Sign)
	{
		const float X0 = GoalLineX * Sign, X1 = (GoalLineX + NetDepth) * Sign;
		return FBox2D(FVector2D(FMath::Min(X0, X1), -NetHalfWidth - PostRadius), FVector2D(FMath::Max(X0, X1), NetHalfWidth + PostRadius));
	}

	/** Push a circle out of an axis-aligned box. */
	inline bool PushOutOfBox(FVector2D& P, float Radius, const FBox2D& B, FVector2D& OutNormal)
	{
		const FVector2D Closest(FMath::Clamp(P.X, B.Min.X, B.Max.X), FMath::Clamp(P.Y, B.Min.Y, B.Max.Y));
		FVector2D D = P - Closest;
		float Len = D.Size();
		if (Len >= Radius)
		{
			return false;
		}
		if (Len < 1e-3f)
		{
			// center inside the box: push out along the smallest axis
			const float L = P.X - B.Min.X, R = B.Max.X - P.X, Dn = P.Y - B.Min.Y, U = B.Max.Y - P.Y;
			const float M = FMath::Min(FMath::Min(L, R), FMath::Min(Dn, U));
			if (M == L) { D = FVector2D(-1, 0); Len = -L; }
			else if (M == R) { D = FVector2D(1, 0); Len = -R; }
			else if (M == Dn) { D = FVector2D(0, -1); Len = -Dn; }
			else { D = FVector2D(0, 1); Len = -U; }
			OutNormal = D;
			P += D * (Radius - Len);
			return true;
		}
		OutNormal = D / Len;
		P += OutNormal * (Radius - Len);
		return true;
	}

	/** Attack direction helpers: is X inside the offensive zone of a team attacking toward Sign? */
	inline bool InOffensiveZone(float X, int32 AttackSign) { return X * AttackSign > BlueLineX; }

	/** Nearest face-off dot to a location (used after stoppages). */
	inline FVector2D NearestDot(const FVector2D& P)
	{
		const int32 Sx = P.X >= 0 ? 1 : -1, Sy = P.Y >= 0 ? 1 : -1;
		if (FMath::Abs(P.X) > 1000.f) { return EndDot(Sx, Sy); }
		if (FMath::Abs(P.X) > 250.f) { return NeutralDot(Sx, Sy); }
		return FVector2D::ZeroVector;
	}
}
