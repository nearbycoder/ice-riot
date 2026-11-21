#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "IRPlayerController.generated.h"

/** Single local controller: it only owns the view. All player input goes through FIRInput (any device). */
UCLASS()
class ICERIOT_API AIRPlayerController : public APlayerController
{
	GENERATED_BODY()
public:
	AIRPlayerController();
	virtual void BeginPlay() override;
};
