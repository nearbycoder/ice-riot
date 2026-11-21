#!/usr/bin/env bash
# Zip the packaged builds and publish (or update) a GitHub release; publishing triggers the Pages deploy.
#   Tools/release.sh v1.0.0 "Release title"       (run Tools/package.sh web + mac first)
set -euo pipefail
source "$(dirname "$0")/common.sh"
TAG="${1:?tag}"; TITLE="${2:-ICE RIOT $1}"
OUT="$PROJECT_DIR/Release"; mkdir -p "$OUT"
rm -f "$OUT/IceRiot-macOS.zip" "$OUT/IceRiot-Web.zip"
( cd "$PROJECT_DIR/Build/Packaged/Mac" && ditto -c -k --sequesterRsrc --keepParent IceRiot.app "$OUT/IceRiot-macOS.zip" )
# GitHub Pages can't serve the .br siblings with Content-Encoding, so leave them out
( cd "$PROJECT_DIR/Build/Web/Wasm" && zip -r -q -X "$OUT/IceRiot-Web.zip" . -x "*.br" )
ls -lh "$OUT"/*.zip
NOTES="$OUT/notes.md"
[ -f "$NOTES" ] || echo "ICE RIOT $TAG" > "$NOTES"
if gh release view "$TAG" >/dev/null 2>&1; then
  gh release upload "$TAG" "$OUT/IceRiot-macOS.zip" "$OUT/IceRiot-Web.zip" --clobber
  gh release edit "$TAG" --title "$TITLE" --notes-file "$NOTES"
  gh workflow run pages.yml >/dev/null && echo "Pages redeploy triggered"
else
  gh release create "$TAG" "$OUT/IceRiot-macOS.zip" "$OUT/IceRiot-Web.zip" --title "$TITLE" --notes-file "$NOTES" --latest
fi
