#!/usr/bin/env bash
# Usage: scripts/push_fb_job.sh <job.json>
# Replaces the `media` branch with a single fresh commit holding the Facebook workflow,
# the publisher script and one job file. Pushing it triggers the "Publish Facebook Reel" Action.
# Run from the root of a clone of fanart-reels (main branch checked out).
set -euo pipefail
JOB="$1"
ROOT="$(git rev-parse --show-toplevel)"
TMP="$(mktemp -d)"
mkdir -p "$TMP/.github/workflows" "$TMP/scripts" "$TMP/jobs"
cp "$ROOT/.github/workflows/facebook-reel.yml" "$TMP/.github/workflows/"
cp "$ROOT/scripts/publish_fb_reel.py" "$TMP/scripts/"
cp "$JOB" "$TMP/jobs/"
cd "$TMP"
git init -q -b media
git config user.name "$(git -C "$ROOT" config user.name)"
git config user.email "$(git -C "$ROOT" config user.email)"
git add -A
git commit -qm "Facebook job $(basename "$JOB" .json)"
git remote add origin "$(git -C "$ROOT" remote get-url origin)"
git push -f origin media
echo "pushed $(git rev-parse HEAD)"
