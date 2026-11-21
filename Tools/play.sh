#!/usr/bin/env bash
# Run the game through the editor binary (no packaging). Extra args pass through, e.g.:
#   Tools/play.sh                 windowed 1920x1080
#   Tools/play.sh -irwatch        CPU vs CPU
#   Tools/play.sh -irstart=practice
set -euo pipefail
source "$(dirname "$0")/common.sh"
exec "$UE_EDITOR" "$UPROJECT" -game -windowed -ResX=1920 -ResY=1080 -log "$@"
