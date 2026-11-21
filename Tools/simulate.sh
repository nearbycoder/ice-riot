#!/usr/bin/env bash
# Headless CPU-vs-CPU full games as fast as possible (no rendering, no sound). Prints one IR_SIM_RESULT line per game.
#   Tools/simulate.sh [games=3] [period_seconds=120] [extra args]
set -uo pipefail
source "$(dirname "$0")/common.sh"
N="${1:-3}"; PER="${2:-120}"; shift 2 || true
for ((i=0; i<N; i++)); do
  LOG="$PROJECT_DIR/Saved/sim_$i.log"
  timeout 600 "$UE_EDITOR" "$UPROJECT" -game -nullrhi -nosound -benchmark -fps=30 -irsimexit -irperiod="$PER" -unattended -log -abslog="$LOG" "$@" >/dev/null 2>&1
  grep -h "IR_SIM_RESULT\|Error: appError\|Assertion failed" "$LOG" | sed 's/.*IR_SIM_RESULT/IR_SIM_RESULT/' | head -3
done
