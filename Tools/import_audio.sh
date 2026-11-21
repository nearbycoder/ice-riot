#!/usr/bin/env bash
# Generate (optional) and import ICE RIOT audio into Unreal (/Game/IceRiot/Audio).
#   Tools/import_audio.sh            # import Art/Export/Audio (run Tools/gen_audio.py first)
#   Tools/import_audio.sh --gen      # regenerate all audio, then import
# Needs the editor module built (Tools/build.sh). Report: Saved/ue_import_audio_report.txt
set -euo pipefail
source "$(dirname "$0")/common.sh"
cd "$PROJECT_DIR"
if [[ "${1:-}" == "--gen" ]]; then
  "$BLENDER_PY" Tools/gen_audio.py
fi
if [[ ! -f Art/Export/Audio/manifest.json ]]; then
  echo "Art/Export/Audio/manifest.json missing: run $BLENDER_PY Tools/gen_audio.py first" >&2
  exit 1
fi
while pgrep -f "[B]uild.sh IceRiot" > /dev/null; do echo "waiting for an IceRiot build to finish..."; sleep 10; done
mkdir -p Saved
"$UE_EDITOR_CMD" "$UPROJECT" -run=pythonscript -script="$PROJECT_DIR/Tools/ue_import_audio.py" \
  -unattended -nosplash -nullrhi > Saved/ue_import_audio.log 2>&1 || true
grep -E "^(COUNTS|FAILED|EXCEPTION|AUDIO IMPORT DONE)" Saved/ue_import_audio_report.txt || tail -20 Saved/ue_import_audio.log
grep -q "AUDIO IMPORT DONE OK" Saved/ue_import_audio_report.txt
