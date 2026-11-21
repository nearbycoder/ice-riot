#!/usr/bin/env bash
# Automated visual check: run the game silently (audio rendered offline, nothing on the speakers) and save
# screenshots.  Tools/shoot.sh <outdir> <interval_s> <duration_s> [extra game args]   (default: -irwatch)
set -uo pipefail
source "$(dirname "$0")/common.sh"
OUT="${1:-$PROJECT_DIR/Saved/Shots}"; INT="${2:-3}"; DUR="${3:-30}"; shift 3 || true
EXTRA=("$@"); [ ${#EXTRA[@]} -eq 0 ] && EXTRA=(-irwatch)
mkdir -p "$OUT"; rm -f "$OUT"/shot_*.png
"$UE_EDITOR" "$UPROJECT" -game -windowed -ResX="${IR_RESX:-1600}" -ResY="${IR_RESY:-900}" -NonRealtimeAudio -nosound -autoshot="$OUT" -autoshotint="$INT" -autoshotdur="$DUR" -log -abslog="$OUT/game.log" "${EXTRA[@]}" >/dev/null 2>&1 &
PID=$!
LIMIT=$(( ${DUR%.*} + 120 ))
for ((i=0; i<LIMIT; i++)); do kill -0 $PID 2>/dev/null || break; sleep 1; done
kill -9 $PID 2>/dev/null
ls "$OUT"/shot_*.png 2>/dev/null | wc -l | xargs echo "screenshots:"
grep -E "IR_|Error|error:" "$OUT/game.log" | grep -v "LogTemp\|ShaderCompiler" | tail -20
