#!/usr/bin/env bash
# Compile the C++ game module for the editor (needed before play.sh / import_assets.sh).
set -euo pipefail
source "$(dirname "$0")/common.sh"
"$UE_BUILD" IceRiotEditor Mac Development -project="$UPROJECT" -waitmutex 2>&1 | grep -E "error|warning:|Result:" || true
