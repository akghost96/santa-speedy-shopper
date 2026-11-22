#!/usr/bin/env bash
# Show that an OpenClaw checkout is commit 8b18b55 plus the official speed patch and nothing else.
#   scripts/verify-openclaw-build.sh [openclaw-checkout] [patch-file]
set -euo pipefail
here="$(dirname -- "$(dirname -- "$(realpath -- "${BASH_SOURCE[0]}")")")"
checkout="${1:-$here/.bounty-build}"
patch="${2:-$here/official-openclaw-speed.patch}"
base=8b18b5578f66eab1501cba4cef2310d88bfb9a41

echo "patch file sha256:   $(sha256sum "$patch" | cut -d' ' -f1)"
cd "$checkout"
echo "base is an ancestor: $(git merge-base --is-ancestor "$base" HEAD && echo yes || echo NO)"
echo "commits on top of the base:"
git log --format='  %h %s' "$base"..HEAD
echo "patch-ids in the patch file:"
git patch-id --stable < "$patch" | awk '{print "  " $1}'
echo "patch-ids of those commits:"
git format-patch --stdout "$base"..HEAD | git patch-id --stable | awk '{print "  " $1}'
changes="$(git status --porcelain)"
echo "uncommitted or untracked changes: ${changes:-none}"
