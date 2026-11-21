#pragma once

#include "CoreMinimal.h"
#include "Engine/GameViewportClient.h"
#include "IRTypes.h"
#include "IRInput.generated.h"

/** Where a human's input comes from. */
enum class EIRSource : uint8 { None, KeyboardFull, KeyboardA, KeyboardB, Gamepad, Autopilot };

struct FIRBinding
{
	EIRSource Source = EIRSource::None;
	int32 DeviceId = -1;  // for gamepads
	bool IsValid() const { return Source != EIRSource::None; }
	bool operator==(const FIRBinding& O) const { return Source == O.Source && (Source != EIRSource::Gamepad || DeviceId == O.DeviceId); }
};

/**
 * Raw input hub. The viewport client feeds every key/axis event (with its device) in; the game polls one
 * FIRPadState per bound source each frame. Works for 2 keyboard halves + any number of gamepads.
 */
class ICERIOT_API FIRInput
{
public:
	static FIRInput& Get();

	void OnKey(const FInputKeyEventArgs& Args);
	void OnAxis(const FInputKeyEventArgs& Args);

	/** Call once per frame before reading states. */
	void BeginFrame(float DeltaTime);

	/** Logical state for a source this frame (edges computed against last frame). */
	const FIRPadState& State(const FIRBinding& B);

	/** Menu state merged over every source (anyone can drive a shared menu). */
	const FIRPadState& AnyState() const { return Any; }

	/** Sources that pressed a "join" button this frame (for the join screen). */
	TArray<FIRBinding> JoinRequests() const;

	/** Gamepad device ids seen so far. */
	const TArray<int32>& KnownPads() const { return Pads; }

	bool bKeyboardSplit = false;  // true once a second keyboard player joined: keyboard halves become separate
	float TimeSinceAnyInput = 0.f;

	/** Rumble a gamepad (best effort). */
	void Rumble(const FIRBinding& B, float Strength, float Duration);

private:
	struct FDev
	{
		TSet<FKey> Down;
		TSet<FKey> PressedSincePoll;
		TMap<FKey, float> Axis;
	};
	FDev Keyboard;
	TMap<int32, FDev> PadDevs;
	TArray<int32> Pads;

	struct FLogical
	{
		FIRPadState Cur;
		FIRPadState Prev;
		float RepeatTimer = 0.f;
		int32 RepeatDir = -1;
		uint64 Frame = 0;
		FIRBinding Bind;
	};
	TMap<uint32, FLogical> Logical;
	FIRPadState Any;
	uint64 FrameCounter = 0;
	float Dt = 0.016f;

	FIRPadState Read(const FIRBinding& B) const;
	static uint32 KeyOf(const FIRBinding& B) { return uint32(B.Source) << 24 | uint32(B.DeviceId & 0xFFFFFF); }
	void Finish(FLogical& L, const FIRPadState& Raw);
};

UCLASS()
class ICERIOT_API UIRViewportClient : public UGameViewportClient
{
	GENERATED_BODY()
public:
	virtual bool InputKey(const FInputKeyEventArgs& EventArgs) override;
	virtual bool InputAxis(const FInputKeyEventArgs& EventArgs) override;
};
