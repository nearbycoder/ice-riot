#!/usr/bin/env bash
# Regenerate every ICE RIOT art asset from the procedural Blender generators into Art/Export.
#   Tools/build_art.sh             # everything (~6 min)
#   Tools/build_art.sh branding    # team crests, banners, logo, board ads, digits, teams.json
#   Tools/build_art.sh rink        # ice + markings, boards, glass, nets, goal light, puck
#   Tools/build_art.sh arena       # bowl, crowd, jumbotron
#   Tools/build_art.sh props       # hats, ambulance, resurfacer, title logo
#   Tools/build_art.sh chars       # SK_Skater, SK_Goalie, loose helmet/glove/stick + all animations
#   Tools/build_art.sh anims       # animations only
# Then run Tools/import_assets.sh to bring everything into Unreal.
set -euo pipefail
source "$(dirname "$0")/common.sh"
cd "$PROJECT_DIR"
BL="${BLENDER_BIN:-/opt/homebrew/bin/blender}"
[[ -x "$BL" ]] || BL="$BLENDER"
WHAT="${1:-all}"
LOGDIR="$PROJECT_DIR/Saved/ArtLogs"
mkdir -p "$LOGDIR" Art/Export Art/Blend Art/Previews

run() {
  local script="$1"; shift
  echo "=== $script $*"
  local t0=$SECONDS
  if ! "$BL" -b --factory-startup --python-exit-code 1 -P "Blender/$script" -- "$@" > "$LOGDIR/${script%.py}.log" 2>&1; then
    echo "!!! $script failed, see $LOGDIR/${script%.py}.log"; tail -n 25 "$LOGDIR/${script%.py}.log"; exit 1
  fi
  grep -E "^(MESH|CHARACTER|BAKED|RINK DONE|ARENA DONE|BRANDING DONE|PROPS DONE|ANIMS DONE)" "$LOGDIR/${script%.py}.log" | tail -60 || true
  echo "    ($script took $((SECONDS - t0))s)"
}

case "$WHAT" in all|branding) run gen_branding.py ;; esac
case "$WHAT" in all|rink) run gen_rink.py ;; esac
case "$WHAT" in all|arena) run gen_arena.py ;; esac
case "$WHAT" in all|props) run gen_props.py ;; esac
case "$WHAT" in all|chars) run gen_character.py ;; esac
case "$WHAT" in all|chars|anims) run gen_anims.py ;; esac
echo "Art rebuilt in Art/Export. Run Tools/import_assets.sh to bring it into Unreal."
