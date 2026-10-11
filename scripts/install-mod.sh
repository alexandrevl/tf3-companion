#!/usr/bin/env bash
# Copies the bridge mod into the game's staging_area (highest-priority mod folder).
# Re-run after every change to the mod; restart/reload the save to pick it up.
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
mod="tf3_companion_bridge"

if [[ -n "${TF3C_USERDATA_DIR:-}" ]]; then
  userdata="$TF3C_USERDATA_DIR"
else
  userdata="$(ls -dt "$HOME"/Library/Application\ Support/Steam/userdata/*/3493540/local 2>/dev/null | head -n 1)"
fi
if [[ -z "$userdata" || ! -d "$userdata" ]]; then
  echo "TF3 userdata not found; set TF3C_USERDATA_DIR" >&2
  exit 1
fi

target="$userdata/staging_area/$mod"
mkdir -p "$target"
rsync -a --delete "$repo/mod/$mod/" "$target/"
echo "installed $mod -> $target"
