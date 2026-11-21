#pragma once

#include "CoreMinimal.h"

class UCanvas;
class UFont;
class UTexture;

/** Canvas helpers shared by the HUD and the jumbotron (text through FSlateFontInfo, which this engine needs). */
namespace IRDraw
{
	enum EAlign { Left, Center, Right };
	/** Draw text; Size is the pixel height. Returns the drawn width. */
	float Text(UCanvas* C, const FString& S, float X, float Y, float Size, const FLinearColor& Color, EAlign Align = Left, bool bDisplay = true, float Shadow = 0.f, const FLinearColor& ShadowColor = FLinearColor(0, 0, 0, 0.8f), float Outline = 0.f);
	FVector2D Measure(const FString& S, float Size, bool bDisplay = true);
	void Box(UCanvas* C, float X, float Y, float W, float H, const FLinearColor& Color);
	/** Parallelogram (skewed bar) - the arcade look. Skew in pixels. */
	void Slant(UCanvas* C, float X, float Y, float W, float H, float Skew, const FLinearColor& Color);
	void Image(UCanvas* C, UTexture* T, float X, float Y, float W, float H, const FLinearColor& Tint = FLinearColor::White);
	void Gradient(UCanvas* C, float X, float Y, float W, float H, const FLinearColor& Top, const FLinearColor& Bottom);
	void Circle(UCanvas* C, float X, float Y, float R, const FLinearColor& Color, int32 Segs = 24, float Fill = 1.f);
}
