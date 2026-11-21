#!/usr/bin/env bash
# Package ICE RIOT.
#   Tools/package.sh mac  [Shipping|Development]   -> Build/Packaged/Mac/IceRiot.app
#   Tools/package.sh web  [Shipping|Development]   -> Build/Web/Wasm (the site folder for /play/)
set -euo pipefail
source "$(dirname "$0")/common.sh"
WHAT="${1:-mac}"; CFG="${2:-Shipping}"
# another project's UBT run makes the editor's SDK check fail ("Failed to SetupSDK"): wait for it
while pgrep -f "[U]nrealBuildTool.dll" >/dev/null; do echo "waiting for another UnrealBuildTool..."; sleep 10; done
if [[ "$WHAT" == mac ]]; then
  "$UE_UAT" -WaitForUATMutex BuildCookRun -project="$UPROJECT" -platform=Mac -clientconfig="$CFG" \
    -build -cook -stage -pak -iostore -archive -archivedirectory="$PROJECT_DIR/Build/Packaged" -noP4 -utf8output -unattended -map=/Game/Maps/Arena
  rm -rf "$PROJECT_DIR/Build/Packaged/Mac/IceRiot.app"; mkdir -p "$PROJECT_DIR/Build/Packaged/Mac"
  APP=$(ls -d "$PROJECT_DIR"/Saved/StagedBuilds/Mac/IceRiot*.app | head -1)
  ditto "$APP" "$PROJECT_DIR/Build/Packaged/Mac/IceRiot.app"
  codesign --force --deep -s - "$PROJECT_DIR/Build/Packaged/Mac/IceRiot.app" || true
  echo "Packaged: $PROJECT_DIR/Build/Packaged/Mac/IceRiot.app"
else
  "$UE_UAT" -WaitForUATMutex BuildCookRun -project="$UPROJECT" -platform=Wasm -clientconfig="$CFG" \
    -build -cook -stage -pak -iostore -package -archive -archivedirectory="$PROJECT_DIR/Build/Web" -noP4 -utf8output -unattended -map=/Game/Maps/Arena \
    -AdditionalCookerOptions="-unattended -nopause -nosplash -nullrhi"
  "$UE_ROOT/Engine/Binaries/ThirdParty/Python3/Mac/bin/python3" "$UE_ROOT/Engine/Platforms/Wasm/Build/Tools/deploy/check_stage.py" "$PROJECT_DIR/Build/Web/Wasm" || true
  echo "Web stage: $PROJECT_DIR/Build/Web/Wasm"
fi
