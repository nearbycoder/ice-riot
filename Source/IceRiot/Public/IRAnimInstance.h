#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimInstanceProxy.h"
#include "IRAnimInstance.generated.h"

class UAnimSequence;

struct FIRAnimSlot
{
	UAnimSequence* Seq = nullptr;
	float Time = 0.f;
	float Rate = 1.f;
	bool bLoop = true;
};

USTRUCT()
struct FIRAnimProxy : public FAnimInstanceProxy
{
	GENERATED_BODY()

	FIRAnimProxy() {}
	FIRAnimProxy(UAnimInstance* InInstance) : FAnimInstanceProxy(InInstance) {}

	virtual void PreUpdate(UAnimInstance* InAnimInstance, float DeltaSeconds) override;
	virtual bool Evaluate(FPoseContext& Output) override;

	FIRAnimSlot Cur, Prev, Upper, UpperPrev;
	float Alpha = 1.f;          // cur vs prev
	float UpperWeight = 0.f;    // overlay weight
	float UpperAlpha = 1.f;     // upper vs upper prev
	float HeadScale = 1.f;
	float StickScale = 1.f;
	float Lean = 0.f;           // degrees, roll into turns
	float Pitch = 0.f;          // degrees, forward lean
	float Twist = 0.f;          // degrees, spine yaw (aiming)
	TArray<bool> UpperMask;     // per compact bone
	int32 CachedBoneCount = -1;
};

/**
 * Native animation instance (no Anim Blueprint). Gameplay picks a full-body clip with Play(), and can lay an
 * upper-body clip on top with PlayUpper() (shots/passes while the legs keep skating). Procedural lean/twist
 * and big-head/stick-hide are applied after sampling.
 */
UCLASS(Transient, NotBlueprintable)
class ICERIOT_API UIRAnimInstance : public UAnimInstance
{
	GENERATED_BODY()
public:
	void Play(UAnimSequence* Seq, bool bLoop, float Rate = 1.f, float BlendTime = 0.15f, float StartTime = 0.f, bool bRestart = false);
	void PlayUpper(UAnimSequence* Seq, float Rate = 1.f, float BlendIn = 0.08f, float StartTime = 0.f);
	void StopUpper(float BlendOut = 0.15f);
	void SetRate(float InRate) { Cur.Rate = InRate; }
	void SetTime(float InTime) { Cur.Time = InTime; }
	float GetTime() const { return Cur.Time; }
	float GetLength() const;
	bool IsFinished() const;
	bool IsUpperFinished() const;
	bool IsUpperActive() const { return Upper.Seq != nullptr && UpperTarget > 0.f; }
	float GetUpperTime() const { return Upper.Time; }
	UAnimSequence* GetCurrent() const { return Cur.Seq; }
	UAnimSequence* GetUpper() const { return UpperTarget > 0.f ? Upper.Seq : nullptr; }

	/** Freeze/drive time directly (replays). */
	void ForcePose(UAnimSequence* Seq, float Time, UAnimSequence* UpperSeq, float UpperTime, float UpperW);

	float HeadScale = 1.f;
	float StickScale = 1.f;
	float Lean = 0.f;
	float Pitch = 0.f;
	float Twist = 0.f;
	bool bFrozen = false;

protected:
	virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
	virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy) override;
	virtual void NativeUpdateAnimation(float DeltaSeconds) override;

	FIRAnimSlot Cur, Prev, Upper, UpperPrev;
	float BlendAlpha = 1.f, BlendDuration = 0.15f;
	float UpperWeight = 0.f, UpperTarget = 0.f, UpperBlendSpeed = 10.f;
	float UpperAlpha = 1.f, UpperBlendDuration = 0.1f;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UAnimSequence>> Referenced;

	friend struct FIRAnimProxy;
};
