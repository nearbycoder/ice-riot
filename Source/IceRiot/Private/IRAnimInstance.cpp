#include "IRAnimInstance.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimationPoseData.h"
#include "AnimationRuntime.h"
#include "BonePose.h"

static float AdvanceTime(float T, float Dt, float Rate, float Len, bool bLoop)
{
	T += Dt * Rate;
	if (Len <= KINDA_SMALL_NUMBER)
	{
		return 0.f;
	}
	if (bLoop)
	{
		T = FMath::Fmod(T, Len);
		if (T < 0.f) { T += Len; }
	}
	else
	{
		T = FMath::Clamp(T, 0.f, Len);
	}
	return T;
}

static void Advance(FIRAnimSlot& S, float Dt)
{
	if (S.Seq)
	{
		S.Time = AdvanceTime(S.Time, Dt, S.Rate, S.Seq->GetPlayLength(), S.bLoop);
	}
}

void UIRAnimInstance::Play(UAnimSequence* Seq, bool bLoop, float Rate, float BlendTime, float StartTime, bool bRestart)
{
	if (!Seq)
	{
		return;
	}
	Referenced.AddUnique(Seq);
	if (Cur.Seq == Seq && !bRestart)
	{
		Cur.bLoop = bLoop;
		Cur.Rate = Rate;
		return;
	}
	if (Cur.Seq && BlendTime > 0.f)
	{
		Prev = Cur;
		BlendAlpha = 0.f;
		BlendDuration = BlendTime;
	}
	else
	{
		Prev = FIRAnimSlot();
		BlendAlpha = 1.f;
	}
	Cur.Seq = Seq;
	Cur.Time = StartTime;
	Cur.Rate = Rate;
	Cur.bLoop = bLoop;
}

void UIRAnimInstance::PlayUpper(UAnimSequence* Seq, float Rate, float BlendIn, float StartTime)
{
	if (!Seq)
	{
		return;
	}
	Referenced.AddUnique(Seq);
	if (Upper.Seq && UpperWeight > 0.05f && Upper.Seq != Seq)
	{
		UpperPrev = Upper;
		UpperAlpha = 0.f;
		UpperBlendDuration = FMath::Max(0.04f, BlendIn);
	}
	Upper.Seq = Seq;
	Upper.Time = StartTime;
	Upper.Rate = Rate;
	Upper.bLoop = false;
	UpperTarget = 1.f;
	UpperBlendSpeed = 1.f / FMath::Max(0.02f, BlendIn);
}

void UIRAnimInstance::StopUpper(float BlendOut)
{
	UpperTarget = 0.f;
	UpperBlendSpeed = 1.f / FMath::Max(0.02f, BlendOut);
}

float UIRAnimInstance::GetLength() const
{
	return Cur.Seq ? Cur.Seq->GetPlayLength() : 0.f;
}

bool UIRAnimInstance::IsFinished() const
{
	return Cur.Seq && !Cur.bLoop && Cur.Time >= GetLength() - KINDA_SMALL_NUMBER;
}

bool UIRAnimInstance::IsUpperFinished() const
{
	return !Upper.Seq || Upper.Time >= Upper.Seq->GetPlayLength() - KINDA_SMALL_NUMBER;
}

void UIRAnimInstance::ForcePose(UAnimSequence* Seq, float Time, UAnimSequence* UpperSeq, float UpperTime, float UpperW)
{
	if (Seq) { Referenced.AddUnique(Seq); }
	if (UpperSeq) { Referenced.AddUnique(UpperSeq); }
	Cur.Seq = Seq;
	Cur.Time = Time;
	Cur.Rate = 0.f;
	Prev = FIRAnimSlot();
	BlendAlpha = 1.f;
	Upper.Seq = UpperSeq;
	Upper.Time = UpperTime;
	Upper.Rate = 0.f;
	UpperPrev = FIRAnimSlot();
	UpperAlpha = 1.f;
	UpperWeight = UpperTarget = UpperSeq ? UpperW : 0.f;
}

FAnimInstanceProxy* UIRAnimInstance::CreateAnimInstanceProxy()
{
	return new FIRAnimProxy(this);
}

void UIRAnimInstance::DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy)
{
	delete static_cast<FIRAnimProxy*>(InProxy);
}

void UIRAnimInstance::NativeUpdateAnimation(float DeltaSeconds)
{
	Super::NativeUpdateAnimation(DeltaSeconds);
	if (bFrozen)
	{
		return;
	}
	Advance(Cur, DeltaSeconds);
	if (Prev.Seq && BlendAlpha < 1.f)
	{
		Advance(Prev, DeltaSeconds);
		BlendAlpha = FMath::Min(1.f, BlendAlpha + DeltaSeconds / FMath::Max(0.01f, BlendDuration));
		if (BlendAlpha >= 1.f) { Prev = FIRAnimSlot(); }
	}
	Advance(Upper, DeltaSeconds);
	if (UpperPrev.Seq && UpperAlpha < 1.f)
	{
		Advance(UpperPrev, DeltaSeconds);
		UpperAlpha = FMath::Min(1.f, UpperAlpha + DeltaSeconds / UpperBlendDuration);
		if (UpperAlpha >= 1.f) { UpperPrev = FIRAnimSlot(); }
	}
	UpperWeight = FMath::FInterpConstantTo(UpperWeight, UpperTarget, DeltaSeconds, UpperBlendSpeed);
	if (UpperWeight <= 0.f && UpperTarget <= 0.f)
	{
		Upper = FIRAnimSlot();
	}
}

void FIRAnimProxy::PreUpdate(UAnimInstance* InAnimInstance, float DeltaSeconds)
{
	FAnimInstanceProxy::PreUpdate(InAnimInstance, DeltaSeconds);
	const UIRAnimInstance* I = CastChecked<UIRAnimInstance>(InAnimInstance);
	Cur = I->Cur;
	Prev = I->Prev;
	Upper = I->Upper;
	UpperPrev = I->UpperPrev;
	const float A = FMath::Clamp(I->BlendAlpha, 0.f, 1.f);
	Alpha = A * A * (3.f - 2.f * A);
	const float W = FMath::Clamp(I->UpperWeight, 0.f, 1.f);
	UpperWeight = W * W * (3.f - 2.f * W);
	const float UA = FMath::Clamp(I->UpperAlpha, 0.f, 1.f);
	UpperAlpha = UA * UA * (3.f - 2.f * UA);
	HeadScale = I->HeadScale;
	StickScale = I->StickScale;
	Lean = I->Lean;
	Pitch = I->Pitch;
	Twist = I->Twist;
}

static void Sample(const FIRAnimSlot& S, FPoseContext& Out)
{
	FAnimationPoseData D(Out);
	S.Seq->GetAnimationPose(D, FAnimExtractContext(double(S.Time), false, FDeltaTimeRecord(), S.bLoop));
}

static void SampleBlended(const FIRAnimSlot& A, const FIRAnimSlot& B, float Alpha, FPoseContext& Out)
{
	Sample(A, Out);
	if (B.Seq && Alpha < 0.999f)
	{
		FPoseContext P(Out);
		Sample(B, P);
		FAnimationPoseData OD(Out), PD(P);
		FAnimationRuntime::BlendTwoPosesTogetherInPlace(OD, PD, Alpha);
	}
}

static int32 BoneIdx(const FBoneContainer& BC, const TCHAR* Name)
{
	const int32 MeshIdx = BC.GetPoseBoneIndexForBoneName(FName(Name));
	if (MeshIdx == INDEX_NONE)
	{
		return INDEX_NONE;
	}
	return BC.MakeCompactPoseIndex(FMeshPoseBoneIndex(MeshIdx)).GetInt();
}

bool FIRAnimProxy::Evaluate(FPoseContext& Output)
{
	if (!Cur.Seq)
	{
		Output.ResetToRefPose();
		return true;
	}
	SampleBlended(Cur, Prev, Alpha, Output);
	const FBoneContainer& BC = Output.Pose.GetBoneContainer();
	const int32 NumBones = Output.Pose.GetNumBones();

	if (Upper.Seq && UpperWeight > 0.001f)
	{
		if (CachedBoneCount != NumBones)
		{
			CachedBoneCount = NumBones;
			UpperMask.Init(false, NumBones);
			const int32 Spine = BoneIdx(BC, TEXT("spine_01"));
			for (int32 i = 0; i < NumBones; ++i)
			{
				int32 B = i;
				while (B != INDEX_NONE && B != Spine)
				{
					B = BC.GetParentBoneIndex(FCompactPoseBoneIndex(B)).GetInt();
				}
				UpperMask[i] = (B == Spine) && Spine != INDEX_NONE;
			}
		}
		FPoseContext UP(Output);
		SampleBlended(Upper, UpperPrev, UpperAlpha, UP);
		for (int32 i = 0; i < NumBones; ++i)
		{
			if (UpperMask.IsValidIndex(i) && UpperMask[i])
			{
				const FCompactPoseBoneIndex CI(i);
				FTransform T = Output.Pose[CI];
				T.BlendWith(UP.Pose[CI], UpperWeight);
				Output.Pose[CI] = T;
			}
		}
	}

	auto RotateBone = [&](const TCHAR* Name, const FRotator& R)
	{
		const int32 I = BoneIdx(BC, Name);
		if (I != INDEX_NONE)
		{
			const FCompactPoseBoneIndex CI(I);
			Output.Pose[CI].SetRotation(R.Quaternion() * Output.Pose[CI].GetRotation());
		}
	};
	// Procedural lean (whole body roll into turns) applied at the pelvis in component space terms: the skater faces
	// -Y in mesh space, so a roll around the forward axis is a rotation around Y.
	if (!FMath::IsNearlyZero(Lean) || !FMath::IsNearlyZero(Pitch))
	{
		const int32 I = BoneIdx(BC, TEXT("pelvis"));
		if (I != INDEX_NONE)
		{
			const FCompactPoseBoneIndex CI(I);
			// mesh-space rotation: forward = -Y, so roll is about Y, pitch about X
			const FQuat MeshRot = FQuat(FVector(0, 1, 0), FMath::DegreesToRadians(-Lean)) * FQuat(FVector(1, 0, 0), FMath::DegreesToRadians(-Pitch));
			// pelvis is a child of root (identity rotation), so its local rotation lives in mesh space
			Output.Pose[CI].SetRotation(MeshRot * Output.Pose[CI].GetRotation());
		}
	}
	if (!FMath::IsNearlyZero(Twist))
	{
		RotateBone(TEXT("spine_02"), FRotator::ZeroRotator);
		const int32 I = BoneIdx(BC, TEXT("spine_02"));
		if (I != INDEX_NONE)
		{
			// twist around the bone's own length axis is unknown; rotate around the parent-space up vector instead
			const FCompactPoseBoneIndex CI(I);
			const FQuat Q(Output.Pose[CI].GetRotation().Inverse().RotateVector(FVector::UpVector), FMath::DegreesToRadians(Twist));
			Output.Pose[CI].SetRotation(Output.Pose[CI].GetRotation() * Q);
		}
	}
	if (!FMath::IsNearlyEqual(HeadScale, 1.f))
	{
		const int32 I = BoneIdx(BC, TEXT("head"));
		if (I != INDEX_NONE)
		{
			Output.Pose[FCompactPoseBoneIndex(I)].SetScale3D(FVector(HeadScale));
		}
	}
	if (!FMath::IsNearlyEqual(StickScale, 1.f))
	{
		const int32 I = BoneIdx(BC, TEXT("stick"));
		if (I != INDEX_NONE)
		{
			Output.Pose[FCompactPoseBoneIndex(I)].SetScale3D(FVector(FMath::Max(0.001f, StickScale)));
		}
	}
	return true;
}
