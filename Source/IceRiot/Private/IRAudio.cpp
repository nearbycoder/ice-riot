#include "IRAudio.h"
#include "IRAssets.h"
#include "IRTypes.h"
#include "Components/AudioComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundAttenuation.h"
#include "Sound/SoundBase.h"
#include "Sound/SoundWave.h"

void UIRAudio::Init(UWorld* InWorld, const FIRGameOptions* InOpt)
{
	World = InWorld;
	Opt = InOpt;
	Atten = NewObject<USoundAttenuation>(this);
	Atten->Attenuation.bAttenuate = true;
	Atten->Attenuation.bSpatialize = true;
	Atten->Attenuation.AttenuationShape = EAttenuationShape::Sphere;
	Atten->Attenuation.AttenuationShapeExtents = FVector(2500.f, 0.f, 0.f);
	Atten->Attenuation.FalloffDistance = 6000.f;
	Atten->Attenuation.dBAttenuationAtMax = -12.f;
	Atten->Attenuation.SpatializationAlgorithm = ESoundSpatializationAlgorithm::SPATIALIZATION_Default;
	Atten->Attenuation.NonSpatializedRadiusStart = 300.f;
	Atten->Attenuation.NonSpatializedRadiusEnd = 100.f;

	CrowdA = MakeLoop(TEXT("Crowd/Crowd_Ambience"));
	CrowdB = MakeLoop(TEXT("Crowd/Crowd_Excited"));
	if (CrowdA) { CrowdA->SetVolumeMultiplier(0.f); CrowdA->Play(FMath::FRandRange(0.f, 20.f)); }
	if (CrowdB) { CrowdB->SetVolumeMultiplier(0.f); CrowdB->Play(FMath::FRandRange(0.f, 20.f)); }
}

UAudioComponent* UIRAudio::MakeLoop(const FString& Name)
{
	USoundBase* S = UIRAssets::Get()->Sound(Name);
	if (!S || !World)
	{
		return nullptr;
	}
	UAudioComponent* C = UGameplayStatics::CreateSound2D(World, S, 1.f, 1.f, 0.f, nullptr, true, false);
	if (C)
	{
		C->bAutoDestroy = false;
		C->bIsUISound = true;   // keep playing while paused
	}
	return C;
}

float UIRAudio::Master() const
{
	return Opt ? Opt->MasterVol : 1.f;
}

void UIRAudio::Sfx(const FString& Name, const FVector& Where, float Volume, float Pitch)
{
	if (!World)
	{
		return;
	}
	// prevent machine-gun stacking of the same sound
	const float Now = World->GetRealTimeSeconds();
	float& Last = LastPlayed.FindOrAdd(Name);
	if (Now - Last < 0.035f)
	{
		return;
	}
	Last = Now;
	USoundBase* S = UIRAssets::Get()->SoundVar(Name);
	if (!S)
	{
		return;
	}
	const float V = Volume * Master() * (Opt ? Opt->SfxVol : 1.f);
	if (V <= 0.001f)
	{
		return;
	}
	UGameplayStatics::PlaySoundAtLocation(World, S, Where, V, Pitch, 0.f, Atten);
}

void UIRAudio::Ui(const FString& Name, float Volume)
{
	USoundBase* S = UIRAssets::Get()->SoundVar(TEXT("UI/") + Name);
	if (!S || !World)
	{
		return;
	}
	const float V = Volume * Master() * (Opt ? Opt->SfxVol : 1.f);
	if (UAudioComponent* C = UGameplayStatics::CreateSound2D(World, S, V, 1.f, 0.f, nullptr, false, true))
	{
		C->bIsUISound = true;
		C->Play();
	}
}

void UIRAudio::CrowdReaction(const FString& Name, float Volume)
{
	USoundBase* S = UIRAssets::Get()->SoundVar(TEXT("Crowd/") + Name);
	if (!S || !World || !bCrowd)
	{
		return;
	}
	const float V = Volume * Master() * (Opt ? Opt->CrowdVol : 1.f);
	UGameplayStatics::PlaySound2D(World, S, V);
}

void UIRAudio::Announce(const FString& Line, float Priority)
{
	if (!UIRAssets::Get()->SoundVar(TEXT("Announcer/") + Line))
	{
		return;
	}
	if (Priority >= 3.f && Voice && Voice->IsPlaying())
	{
		Voice->FadeOut(0.08f, 0.f);
		Queue.Reset();
		VoiceCooldown = 0.f;
	}
	if (Queue.Num() >= 2)
	{
		Queue.Sort([](const FLine& A, const FLine& B) { return A.Priority > B.Priority; });
		if (Queue.Last().Priority < Priority) { Queue.Pop(); }
		else { return; }
	}
	Queue.Add({ Line, Priority, 0.f });
}

bool UIRAudio::IsAnnouncerBusy() const
{
	return (Voice && Voice->IsPlaying()) || Queue.Num() > 0;
}

void UIRAudio::PlayMusic(const FString& Name, float FadeTime)
{
	if (Name == MusicName && Music && Music->IsPlaying())
	{
		return;
	}
	if (Music)
	{
		if (MusicOld) { MusicOld->Stop(); }
		MusicOld = Music;
		MusicOldVol = MusicFade;
	}
	MusicName = Name;
	Music = MakeLoop(TEXT("Music/") + Name);
	MusicFade = 0.f;
	MusicFadeSpeed = 1.f / FMath::Max(0.05f, FadeTime);
	if (Music)
	{
		Music->SetVolumeMultiplier(0.f);
		Music->Play();
	}
}

void UIRAudio::StopMusic(float FadeTime)
{
	if (Music)
	{
		if (MusicOld) { MusicOld->Stop(); }
		MusicOld = Music;
		MusicOldVol = MusicFade;
		Music = nullptr;
		MusicFadeSpeed = 1.f / FMath::Max(0.05f, FadeTime);
	}
	MusicName.Reset();
}

void UIRAudio::StartLoop(const FString& Key, const FString& Name, float Volume)
{
	LoopVol.Add(Key, Volume);
	if (TObjectPtr<UAudioComponent>* C = Loops.Find(Key))
	{
		if (*C && (*C)->IsPlaying()) { return; }
	}
	if (UAudioComponent* C = MakeLoop(Name))
	{
		C->SetVolumeMultiplier(Volume * Master() * (Opt ? Opt->SfxVol : 1.f));
		C->Play();
		Loops.Add(Key, C);
	}
}

void UIRAudio::StopLoop(const FString& Key)
{
	if (TObjectPtr<UAudioComponent>* C = Loops.Find(Key))
	{
		if (*C) { (*C)->FadeOut(0.3f, 0.f); }
		Loops.Remove(Key);
	}
}

void UIRAudio::StopAll()
{
	Queue.Reset();
	if (Voice) { Voice->Stop(); }
	for (TPair<FString, TObjectPtr<UAudioComponent>>& P : Loops)
	{
		if (P.Value) { P.Value->Stop(); }
	}
	Loops.Reset();
}

void UIRAudio::Tick(float Dt)
{
	const float M = Master();
	// crowd bed follows excitement
	Excite = FMath::FInterpTo(Excite, TargetExcite, Dt, Excite > TargetExcite ? 0.6f : 2.5f);
	const float CrowdV = M * (Opt ? Opt->CrowdVol : 1.f) * (bCrowd ? 1.f : 0.f);
	const bool bTalking = Voice && Voice->IsPlaying();
	const float Duck = bTalking ? 0.72f : 1.f;
	if (CrowdA) { CrowdA->SetVolumeMultiplier(CrowdV * FMath::Lerp(0.85f, 0.35f, Excite) * Duck); }
	if (CrowdB) { CrowdB->SetVolumeMultiplier(CrowdV * FMath::Lerp(0.05f, 1.f, Excite) * Duck); }

	// music crossfade
	const float MusicV = M * (Opt ? Opt->MusicVol : 0.7f) * MusicDuck * (bTalking ? 0.8f : 1.f);
	MusicFade = FMath::Min(1.f, MusicFade + Dt * MusicFadeSpeed);
	if (Music) { Music->SetVolumeMultiplier(MusicV * MusicFade); }
	if (MusicOld)
	{
		MusicOldVol -= Dt * MusicFadeSpeed;
		if (MusicOldVol <= 0.f) { MusicOld->Stop(); MusicOld = nullptr; }
		else { MusicOld->SetVolumeMultiplier(MusicV * MusicOldVol); }
	}
	for (TPair<FString, TObjectPtr<UAudioComponent>>& P : Loops)
	{
		if (P.Value) { P.Value->SetVolumeMultiplier(LoopVol.FindRef(P.Key) * M * (Opt ? Opt->SfxVol : 1.f)); }
	}

	// announcer queue
	VoiceCooldown -= Dt;
	for (FLine& L : Queue) { L.Age += Dt; }
	Queue.RemoveAll([](const FLine& L) { return L.Age > 2.5f; });
	if (!bTalking && VoiceCooldown <= 0.f && Queue.Num() > 0)
	{
		Queue.Sort([](const FLine& A, const FLine& B) { return A.Priority > B.Priority; });
		const FLine L = Queue[0];
		Queue.RemoveAt(0);
		if (USoundBase* S = UIRAssets::Get()->SoundVar(TEXT("Announcer/") + L.Name))
		{
			const float V = M * (Opt ? Opt->VoiceVol : 1.f);
			Voice = UGameplayStatics::CreateSound2D(World, S, V, 1.f, 0.f, nullptr, false, true);
			if (Voice)
			{
				Voice->bIsUISound = true;
				Voice->Play();
			}
			VoiceCooldown = 0.25f;
		}
	}
}
