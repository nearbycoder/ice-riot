#!/usr/bin/env bash
# Build the game's own FX materials, HUD fonts and the empty arena map (Tools/ue_fx.py). Report: Saved/ue_fx_report.txt
set -euo pipefail
source "$(dirname "$0")/common.sh"
mkdir -p "$PROJECT_DIR/Saved"
"$UE_EDITOR_CMD" "$UPROJECT" -run=pythonscript -script="$PROJECT_DIR/Tools/ue_fx.py" -unattended -nosplash -AllowCommandletRendering > "$PROJECT_DIR/Saved/ue_fx.log" 2>&1 || true
cat "$PROJECT_DIR/Saved/ue_fx_report.txt"
