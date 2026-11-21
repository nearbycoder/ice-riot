#pragma once

#include "CoreMinimal.h"
#include "UObject/Object.h"
#include "IRAudio.generated.h"

class UAudioComponent;
class USoundAttenuation;
class USoundBase;
struct FIRGameOptions;

UCLASS()
class ICERIOT_API UIRAudio : public UObject
{
	GENERATED_BODY()
public:
	void Init(UWorld* InWorld, const FIRGameOptions* InOpt);
	void Tick(float Dt);

	/** "Sfx/Shot_Slap" style names; variations (_01.._NN) are picked automatically. */
	void Sfx(const FString& Name, const FVector& Where, float Volume = 1.f, float Pitch = 1.f);
	void Ui(const FString& Name, float Volume = 1.f);
	/** Queue an announcer line ("VO_Goal" picks a variation). Higher priority interrupts the queue. */
	void Announce(const FString& Line, float Priority = 1.f);
	void CrowdReaction(const FString& Name, float Volume = 1.f);
	void SetExcitement(float E) { TargetExcite = FMath::Clamp(E, 0.f, 1.f); }
	void Pulse(float Amount) { Excite = FMath::Min(1.f, Excite + Amount); }
	void PlayMusic(const FString& Name, float FadeTime = 1.f);
	void StopMusic(float FadeTime = 1.f);
	void SetMusicDuck(float D) { MusicDuck = D; }
	void SetCrowdEnabled(bool b) { bCrowd = b; }
	void StartLoop(const FString& Key, const FString& Name, float Volume);
	void StopLoop(const FString& Key);
	bool IsAnnouncerBusy() const;
	void StopAll();

	float Excite = 0.f;

private:
	UPROPERTY() TObjectPtr<UWorld> World;
	const FIRGameOptions* Opt = nullptr;
	UPROPERTY() TObjectPtr<USoundAttenuation> Atten;
	UPROPERTY() TObjectPtr<UAudioComponent> CrowdA;
	UPROPERTY() TObjectPtr<UAudioComponent> CrowdB;
	UPROPERTY() TObjectPtr<UAudioComponent> Music;
	UPROPERTY() TObjectPtr<UAudioComponent> MusicOld;
	UPROPERTY() TObjectPtr<UAudioComponent> Voice;
	UPROPERTY() TMap<FString, TObjectPtr<UAudioComponent>> Loops;
	TMap<FString, float> LoopVol;
	FString MusicName;
	float MusicFade = 1.f, MusicFadeSpeed = 1.f, MusicOldVol = 0.f, MusicDuck = 1.f;
	float TargetExcite = 0.2f;
	bool bCrowd = true;
	struct FLine { FString Name; float Priority; float Age; };
	TArray<FLine> Queue;
	float VoiceCooldown = 0.f;
	TMap<FString, float> LastPlayed;
	float Master() const;
	UAudioComponent* MakeLoop(const FString& Name);
};
