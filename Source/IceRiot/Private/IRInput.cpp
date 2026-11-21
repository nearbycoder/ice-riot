#include "IRInput.h"
#include "Framework/Application/SlateApplication.h"
#include "GenericPlatform/IInputInterface.h"

namespace
{
	struct FRumble { int32 ControllerId; float Strength; float TimeLeft; };
	TArray<FRumble> GRumbles;
	TMap<int32, int32> GPadController;  // device id -> controller id

	bool AnyDown(const TSet<FKey>& Down, const TSet<FKey>& Pressed, std::initializer_list<FKey> Keys)
	{
		for (const FKey& K : Keys)
		{
			if (Down.Contains(K) || Pressed.Contains(K)) { return true; }
		}
		return false;
	}
}

FIRInput& FIRInput::Get()
{
	static FIRInput Instance;
	return Instance;
}

void FIRInput::OnKey(const FInputKeyEventArgs& Args)
{
	const FKey& K = Args.Key;
	if (K.IsMouseButton() || K.IsTouch())
	{
		return;
	}
	FDev* D = nullptr;
	if (K.IsGamepadKey())
	{
		const int32 Id = Args.InputDevice.GetId();
		D = &PadDevs.FindOrAdd(Id);
		Pads.AddUnique(Id);
		GPadController.Add(Id, Args.ControllerId);
	}
	else
	{
		D = &Keyboard;
	}
	if (Args.Event == IE_Pressed || Args.Event == IE_Repeat)
	{
		if (Args.Event == IE_Pressed)
		{
			D->PressedSincePoll.Add(K);
			TimeSinceAnyInput = 0.f;
		}
		D->Down.Add(K);
	}
	else if (Args.Event == IE_Released)
	{
		D->Down.Remove(K);
	}
}

void FIRInput::OnAxis(const FInputKeyEventArgs& Args)
{
	const FKey& K = Args.Key;
	if (!K.IsGamepadKey())
	{
		return;
	}
	const int32 Id = Args.InputDevice.GetId();
	FDev& D = PadDevs.FindOrAdd(Id);
	Pads.AddUnique(Id);
	GPadController.Add(Id, Args.ControllerId);
	D.Axis.Add(K, Args.AmountDepressed);
	if (FMath::Abs(Args.AmountDepressed) > 0.5f)
	{
		TimeSinceAnyInput = 0.f;
	}
}

FIRPadState FIRInput::Read(const FIRBinding& B) const
{
	FIRPadState S;
	if (B.Source == EIRSource::Gamepad)
	{
		const FDev* D = PadDevs.Find(B.DeviceId);
		if (!D)
		{
			return S;
		}
		const TSet<FKey>& Dn = D->Down;
		const TSet<FKey>& Pr = D->PressedSincePoll;
		auto Ax = [D](const FKey& K) { const float* V = D->Axis.Find(K); return V ? *V : 0.f; };
		FVector2D M(Ax(EKeys::Gamepad_LeftX), Ax(EKeys::Gamepad_LeftY));
		if (AnyDown(Dn, Pr, { EKeys::Gamepad_DPad_Right })) { M.X += 1.f; }
		if (AnyDown(Dn, Pr, { EKeys::Gamepad_DPad_Left })) { M.X -= 1.f; }
		if (AnyDown(Dn, Pr, { EKeys::Gamepad_DPad_Up })) { M.Y += 1.f; }
		if (AnyDown(Dn, Pr, { EKeys::Gamepad_DPad_Down })) { M.Y -= 1.f; }
		// radial dead zone with rescale
		const float Len = M.Size();
		const float DZ = 0.22f;
		S.Move = Len < DZ ? FVector2D::ZeroVector : M / Len * FMath::Min(1.f, (Len - DZ) / (1.f - DZ));
		S.bShoot = AnyDown(Dn, Pr, { EKeys::Gamepad_FaceButton_Bottom });
		S.bPass = AnyDown(Dn, Pr, { EKeys::Gamepad_FaceButton_Left });
		S.bSwitch = AnyDown(Dn, Pr, { EKeys::Gamepad_FaceButton_Right });
		S.bHook = AnyDown(Dn, Pr, { EKeys::Gamepad_FaceButton_Top, EKeys::Gamepad_LeftShoulder });
		S.bTurbo = AnyDown(Dn, Pr, { EKeys::Gamepad_RightShoulder, EKeys::Gamepad_RightTrigger, EKeys::Gamepad_LeftTrigger })
			|| Ax(EKeys::Gamepad_RightTriggerAxis) > 0.3f || Ax(EKeys::Gamepad_LeftTriggerAxis) > 0.3f;
		S.bPausePressed = Pr.Contains(EKeys::Gamepad_Special_Right);
		S.bCameraPressed = Pr.Contains(EKeys::Gamepad_Special_Left);
		S.bStartPressed = Pr.Contains(EKeys::Gamepad_Special_Right);
		S.bConfirm = Pr.Contains(EKeys::Gamepad_FaceButton_Bottom) || Pr.Contains(EKeys::Gamepad_Special_Right);
		S.bBack = Pr.Contains(EKeys::Gamepad_FaceButton_Right);
		S.bAnyPressed = Pr.Num() > 0;
		return S;
	}
	if (B.Source == EIRSource::KeyboardFull || B.Source == EIRSource::KeyboardA || B.Source == EIRSource::KeyboardB)
	{
		const TSet<FKey>& Dn = Keyboard.Down;
		const TSet<FKey>& Pr = Keyboard.PressedSincePoll;
		const bool bA = B.Source != EIRSource::KeyboardB;
		const bool bB = B.Source != EIRSource::KeyboardA;
		FVector2D M = FVector2D::ZeroVector;
		if (bA)
		{
			if (AnyDown(Dn, Pr, { EKeys::D })) { M.X += 1.f; }
			if (AnyDown(Dn, Pr, { EKeys::A })) { M.X -= 1.f; }
			if (AnyDown(Dn, Pr, { EKeys::W })) { M.Y += 1.f; }
			if (AnyDown(Dn, Pr, { EKeys::S })) { M.Y -= 1.f; }
			S.bShoot |= AnyDown(Dn, Pr, { EKeys::J, EKeys::SpaceBar });
			S.bPass |= AnyDown(Dn, Pr, { EKeys::K });
			S.bTurbo |= AnyDown(Dn, Pr, { EKeys::L, EKeys::LeftShift });
			S.bSwitch |= AnyDown(Dn, Pr, { EKeys::I });
			S.bHook |= AnyDown(Dn, Pr, { EKeys::U });
			S.bPausePressed |= Pr.Contains(EKeys::Escape) || (B.Source == EIRSource::KeyboardFull && Pr.Contains(EKeys::P));
			S.bCameraPressed |= Pr.Contains(EKeys::C);
			S.bStartPressed |= Pr.Contains(EKeys::Enter);
			S.bConfirm |= Pr.Contains(EKeys::Enter) || Pr.Contains(EKeys::SpaceBar) || Pr.Contains(EKeys::J);
			S.bBack |= Pr.Contains(EKeys::Escape) || Pr.Contains(EKeys::BackSpace);
			S.bAnyPressed |= AnyDown(TSet<FKey>(), Pr, { EKeys::W, EKeys::A, EKeys::S, EKeys::D, EKeys::J, EKeys::K, EKeys::L, EKeys::I, EKeys::U, EKeys::SpaceBar, EKeys::Enter, EKeys::LeftShift });
		}
		if (bB)
		{
			if (AnyDown(Dn, Pr, { EKeys::Right })) { M.X += 1.f; }
			if (AnyDown(Dn, Pr, { EKeys::Left })) { M.X -= 1.f; }
			if (AnyDown(Dn, Pr, { EKeys::Up })) { M.Y += 1.f; }
			if (AnyDown(Dn, Pr, { EKeys::Down })) { M.Y -= 1.f; }
			S.bShoot |= AnyDown(Dn, Pr, { EKeys::NumPadOne, EKeys::Comma });
			S.bPass |= AnyDown(Dn, Pr, { EKeys::NumPadTwo, EKeys::Period });
			S.bTurbo |= AnyDown(Dn, Pr, { EKeys::NumPadThree, EKeys::Slash, EKeys::RightShift });
			S.bSwitch |= AnyDown(Dn, Pr, { EKeys::NumPadFour, EKeys::Semicolon });
			S.bHook |= AnyDown(Dn, Pr, { EKeys::NumPadFive, EKeys::Apostrophe });
			S.bPausePressed |= Pr.Contains(EKeys::P);
			S.bStartPressed |= Pr.Contains(EKeys::Enter);
			S.bConfirm |= Pr.Contains(EKeys::Enter) || Pr.Contains(EKeys::NumPadOne) || Pr.Contains(EKeys::Comma);
			S.bBack |= Pr.Contains(EKeys::BackSpace) || Pr.Contains(EKeys::Period) && B.Source == EIRSource::KeyboardB;
			S.bAnyPressed |= AnyDown(TSet<FKey>(), Pr, { EKeys::Up, EKeys::Down, EKeys::Left, EKeys::Right, EKeys::Comma, EKeys::Period, EKeys::Slash, EKeys::RightShift, EKeys::Semicolon, EKeys::NumPadOne, EKeys::NumPadTwo });
		}
		const float Len = M.Size();
		S.Move = Len > 1.f ? M / Len : M;
	}
	return S;
}

void FIRInput::Finish(FLogical& L, const FIRPadState& Raw)
{
	L.Prev = L.Cur;
	FIRPadState S = Raw;
	S.bShootPressed = S.bShoot && !L.Prev.bShoot;
	S.bShootReleased = !S.bShoot && L.Prev.bShoot;
	S.bPassPressed = S.bPass && !L.Prev.bPass;
	S.bPassReleased = !S.bPass && L.Prev.bPass;
	S.bTurboPressed = S.bTurbo && !L.Prev.bTurbo;
	S.bSwitchPressed = S.bSwitch && !L.Prev.bSwitch;
	S.bHookPressed = S.bHook && !L.Prev.bHook;

	// menu directions with auto-repeat
	int32 Dir = -1;
	if (S.Move.Y > 0.6f) { Dir = 0; }
	else if (S.Move.Y < -0.6f) { Dir = 1; }
	else if (S.Move.X < -0.6f) { Dir = 2; }
	else if (S.Move.X > 0.6f) { Dir = 3; }
	bool bFire = false;
	if (Dir != L.RepeatDir)
	{
		L.RepeatDir = Dir;
		L.RepeatTimer = 0.38f;
		bFire = Dir >= 0;
	}
	else if (Dir >= 0)
	{
		L.RepeatTimer -= Dt;
		if (L.RepeatTimer <= 0.f)
		{
			L.RepeatTimer = 0.1f;
			bFire = true;
		}
	}
	S.bUp = bFire && Dir == 0;
	S.bDown = bFire && Dir == 1;
	S.bLeft = bFire && Dir == 2;
	S.bRight = bFire && Dir == 3;
	L.Cur = S;
}

void FIRInput::BeginFrame(float DeltaTime)
{
	Dt = DeltaTime;
	++FrameCounter;
	TimeSinceAnyInput += DeltaTime;

	// merged menu state over every source
	FLogical& AnyL = Logical.FindOrAdd(0xFFFFFFFFu);
	FIRPadState Raw = Read({ EIRSource::KeyboardFull, -1 });
	for (int32 Id : Pads)
	{
		const FIRPadState P = Read({ EIRSource::Gamepad, Id });
		if (P.Move.SizeSquared() > Raw.Move.SizeSquared()) { Raw.Move = P.Move; }
		Raw.bShoot |= P.bShoot; Raw.bPass |= P.bPass; Raw.bTurbo |= P.bTurbo; Raw.bSwitch |= P.bSwitch; Raw.bHook |= P.bHook;
		Raw.bPausePressed |= P.bPausePressed; Raw.bStartPressed |= P.bStartPressed; Raw.bCameraPressed |= P.bCameraPressed;
		Raw.bConfirm |= P.bConfirm; Raw.bBack |= P.bBack; Raw.bAnyPressed |= P.bAnyPressed;
	}
	Finish(AnyL, Raw);
	Any = AnyL.Cur;

	// per-binding states are computed lazily in State(); pressed sets are cleared at the end of the frame via
	// a deferred flag (they must survive until every State() call of this frame).
	for (FRumble& R : GRumbles)
	{
		R.TimeLeft -= DeltaTime;
	}
	if (FSlateApplication::IsInitialized())
	{
		if (IInputInterface* II = FSlateApplication::Get().GetInputInterface())
		{
			TMap<int32, float> Strength;
			for (const FRumble& R : GRumbles)
			{
				float& S = Strength.FindOrAdd(R.ControllerId);
				S = FMath::Max(S, R.TimeLeft > 0.f ? R.Strength : 0.f);
			}
			for (const TPair<int32, float>& P : Strength)
			{
				FForceFeedbackValues V;
				V.LeftLarge = V.RightLarge = P.Value;
				V.LeftSmall = V.RightSmall = P.Value * 0.6f;
				II->SetForceFeedbackChannelValues(P.Key, V);
			}
		}
	}
	GRumbles.RemoveAll([](const FRumble& R) { return R.TimeLeft < -0.1f; });

	// evaluate every binding seen so far while this frame's pressed sets are still intact
	for (TPair<uint32, FLogical>& P : Logical)
	{
		if (P.Key != 0xFFFFFFFFu)
		{
			P.Value.Frame = FrameCounter;
			Finish(P.Value, Read(P.Value.Bind));
		}
	}
	Keyboard.PressedSincePoll.Reset();
	for (TPair<int32, FDev>& P : PadDevs)
	{
		P.Value.PressedSincePoll.Reset();
	}
}

const FIRPadState& FIRInput::State(const FIRBinding& B)
{
	FLogical& L = Logical.FindOrAdd(KeyOf(B));
	L.Bind = B;
	if (L.Frame == 0)
	{
		L.Frame = FrameCounter;
		Finish(L, Read(B));
	}
	return L.Cur;
}

TArray<FIRBinding> FIRInput::JoinRequests() const
{
	TArray<FIRBinding> Out;
	return Out;
}

void FIRInput::Rumble(const FIRBinding& B, float Strength, float Duration)
{
	if (B.Source != EIRSource::Gamepad)
	{
		return;
	}
	if (const int32* C = GPadController.Find(B.DeviceId))
	{
		GRumbles.Add({ *C, FMath::Clamp(Strength, 0.f, 1.f), Duration });
	}
}

bool UIRViewportClient::InputKey(const FInputKeyEventArgs& EventArgs)
{
	FIRInput::Get().OnKey(EventArgs);
	return Super::InputKey(EventArgs);
}

bool UIRViewportClient::InputAxis(const FInputKeyEventArgs& EventArgs)
{
	FIRInput::Get().OnAxis(EventArgs);
	return Super::InputAxis(EventArgs);
}
