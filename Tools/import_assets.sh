#!/usr/bin/env bash
# Import Art/Export into the Unreal project (/Game/IceRiot): textures, master materials + instances,
# static meshes, SK_Skater/SK_Goalie on SK_Skater_Skeleton, animations, and the /Game/Maps/Arena map.
#   Tools/import_assets.sh                              # all steps
#   IR_STEPS=static,materials Tools/import_assets.sh    # subset (textures,materials,static,skeletal,anims,map,verify)
#   IR_REBUILD_MASTERS=ALL Tools/import_assets.sh       # also rebuild the master material graphs
# Report: Saved/ue_import_report.txt   Full log: Saved/ue_import.log
set -euo pipefail
source "$(dirname "$0")/common.sh"
mkdir -p "$PROJECT_DIR/Saved"
if pgrep -fl "[B]uild.sh IceRiot" >/dev/null; then
  echo "waiting for a running IceRiot build to finish..."
  while pgrep -f "[B]uild.sh IceRiot" >/dev/null; do sleep 5; done
fi
"$UE_EDITOR_CMD" "$UPROJECT" -run=pythonscript -script="$PROJECT_DIR/Tools/ue_import.py" \
  -unattended -nosplash -AllowCommandletRendering -ini:Engine:[ConsoleVariables]:Interchange.FeatureFlags.Import.FBX=0 \
  > "$PROJECT_DIR/Saved/ue_import.log" 2>&1 || true
grep -E "Error: .*(Material|Shader)|game module could not be found" "$PROJECT_DIR/Saved/ue_import.log" | head -20 || true
tail -4 "$PROJECT_DIR/Saved/ue_import_report.txt"
