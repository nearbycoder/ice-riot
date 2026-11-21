#include "IRDraw.h"
#include "IRAssets.h"
#include "Engine/Canvas.h"
#include "Engine/Font.h"
#include "CanvasItem.h"
#include "CanvasTypes.h"
#include "TextureResource.h"
#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"
#include "Rendering/SlateRenderer.h"

static FSlateFontInfo MakeFont(bool bDisplay, float Px)
{
	UFont* F = UIRAssets::Get()->Font(bDisplay);
	// Slate font sizes are in points at 96 dpi: px = pt * 96/72
	return FSlateFontInfo(F, FMath::Max(1, FMath::RoundToInt(Px * 0.75f)), bDisplay ? FName(TEXT("Default")) : FName(TEXT("Regular")));
}

FVector2D IRDraw::Measure(const FString& S, float Size, bool bDisplay)
{
	if (!FSlateApplication::IsInitialized())
	{
		return FVector2D(S.Len() * Size * 0.5f, Size);
	}
	return FSlateApplication::Get().GetRenderer()->GetFontMeasureService()->Measure(S, MakeFont(bDisplay, Size));
}

float IRDraw::Text(UCanvas* C, const FString& S, float X, float Y, float Size, const FLinearColor& Color, EAlign Align, bool bDisplay, float Shadow, const FLinearColor& ShadowColor, float Outline)
{
	if (!C || S.IsEmpty())
	{
		return 0.f;
	}
	const FVector2D Sz = Measure(S, Size, bDisplay);
	if (Align == Center) { X -= Sz.X * 0.5f; }
	else if (Align == Right) { X -= Sz.X; }
	const FSlateFontInfo Font = MakeFont(bDisplay, Size);
	auto Draw = [&](float DX, float DY, const FLinearColor& Col)
	{
		FCanvasTextItem Item(FVector2D(X + DX, Y + DY), FText::FromString(S), Font, Col);
		Item.BlendMode = SE_BLEND_Translucent;
		C->DrawItem(Item);
	};
	if (Outline > 0.f)
	{
		FLinearColor O = ShadowColor;
		O.A *= Color.A;
		const int32 N = 8;
		for (int32 i = 0; i < N; ++i)
		{
			const float A = i * 2.f * PI / N;
			Draw(FMath::Cos(A) * Outline, FMath::Sin(A) * Outline, O);
		}
	}
	if (Shadow > 0.f)
	{
		FLinearColor SC = ShadowColor;
		SC.A *= Color.A;
		Draw(Shadow, Shadow, SC);
	}
	Draw(0.f, 0.f, Color);
	return Sz.X;
}

void IRDraw::Box(UCanvas* C, float X, float Y, float W, float H, const FLinearColor& Color)
{
	if (!C || W <= 0.f || H <= 0.f)
	{
		return;
	}
	FCanvasTileItem T(FVector2D(X, Y), FVector2D(W, H), Color);
	T.BlendMode = SE_BLEND_Translucent;
	C->DrawItem(T);
}

void IRDraw::Slant(UCanvas* C, float X, float Y, float W, float H, float Skew, const FLinearColor& Color)
{
	if (!C)
	{
		return;
	}
	FCanvasTriangleItem T1(FVector2D(X + Skew, Y), FVector2D(X + W + Skew, Y), FVector2D(X, Y + H), GWhiteTexture);
	T1.SetColor(Color);
	T1.BlendMode = SE_BLEND_Translucent;
	C->DrawItem(T1);
	FCanvasTriangleItem T2(FVector2D(X + W + Skew, Y), FVector2D(X + W, Y + H), FVector2D(X, Y + H), GWhiteTexture);
	T2.SetColor(Color);
	T2.BlendMode = SE_BLEND_Translucent;
	C->DrawItem(T2);
}

void IRDraw::Image(UCanvas* C, UTexture* T, float X, float Y, float W, float H, const FLinearColor& Tint)
{
	if (!C || !T)
	{
		return;
	}
	FCanvasTileItem I(FVector2D(X, Y), T->GetResource(), FVector2D(W, H), Tint);
	I.BlendMode = SE_BLEND_Translucent;
	C->DrawItem(I);
}

void IRDraw::Gradient(UCanvas* C, float X, float Y, float W, float H, const FLinearColor& Top, const FLinearColor& Bottom)
{
	const int32 N = FMath::Clamp(int32(H / 6.f), 8, 96);
	for (int32 i = 0; i < N; ++i)
	{
		const float A = (i + 0.5f) / N;
		Box(C, X, Y + H * i / N, W, H / N + 0.5f, FMath::Lerp(Top, Bottom, A));
	}
}

void IRDraw::Circle(UCanvas* C, float X, float Y, float R, const FLinearColor& Color, int32 Segs, float Fill)
{
	if (!C)
	{
		return;
	}
	const int32 N = FMath::Max(3, FMath::RoundToInt(Segs * FMath::Clamp(Fill, 0.f, 1.f)));
	const float Total = 2.f * PI * FMath::Clamp(Fill, 0.f, 1.f);
	for (int32 i = 0; i < N; ++i)
	{
		const float A0 = -PI * 0.5f + Total * i / N, A1 = -PI * 0.5f + Total * (i + 1) / N;
		FCanvasTriangleItem T(FVector2D(X, Y), FVector2D(X + FMath::Cos(A0) * R, Y + FMath::Sin(A0) * R), FVector2D(X + FMath::Cos(A1) * R, Y + FMath::Sin(A1) * R), GWhiteTexture);
		T.SetColor(Color);
		T.BlendMode = SE_BLEND_Translucent;
		C->DrawItem(T);
	}
}
