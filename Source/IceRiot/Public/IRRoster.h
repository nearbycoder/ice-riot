#pragma once

#include "IRTypes.h"

namespace IRRoster
{
	/** All teams; the regular 8 first, then the secret super teams. */
	const TArray<FIRTeamInfo>& Teams();
	int32 NumSelectable(bool bIncludeSecret);
}
