#include "IRPlayerController.h"

AIRPlayerController::AIRPlayerController()
{
	bShowMouseCursor = false;
	bAutoManageActiveCameraTarget = false;
	PrimaryActorTick.bTickEvenWhenPaused = true;
	bShouldPerformFullTickWhenPaused = true;
}

void AIRPlayerController::BeginPlay()
{
	Super::BeginPlay();
	SetInputMode(FInputModeGameOnly());
}
