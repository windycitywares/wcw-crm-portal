#!/bin/bash
# Install the latest CRM web build (published by GitHub Actions to the `web-build` branch) into the
# cPanel Node.js app, then restart it.
#   bash ~/repos/wcw-crm-portal/deploy/update-web.sh               # always redeploy
#   bash ~/repos/wcw-crm-portal/deploy/update-web.sh --if-changed  # only when there's a new build (cron)
set -euo pipefail

APP_ROOT="apps/crm/wcw-crm-web"       # cPanel Setup Node.js App → application root
DEST="$HOME/$APP_ROOT"
# Dependencies live one level up (~/apps/crm/node_modules): cPanel's Node selector doesn't allow a
# node_modules folder in the app root, and a separate parent keeps them apart from the shop's ~/apps/node_modules.
MODULES="$HOME/apps/crm/node_modules"
CACHE="$HOME/repos/wcw-crm-web-build"
REPO="git@github-wcw-crm:windycitywares/wcw-crm-portal.git"
SITE="https://crm.windycitywares.com"

if [ ! -d "$CACHE/.git" ]; then
  git clone -q --depth 1 --branch web-build "$REPO" "$CACHE"
fi
cd "$CACHE"
git fetch -q --depth 1 origin web-build
NEW=$(git rev-parse FETCH_HEAD)
OLD=$(cat "$DEST/.deployed_build" 2>/dev/null || echo none)
if [ "${1:-}" = "--if-changed" ] && [ "$NEW" = "$OLD" ]; then
  exit 0
fi
git reset -q --hard FETCH_HEAD
echo "$(date '+%F %T') deploying CRM web build $(cat BUILD_SHA 2>/dev/null) (bundle ${NEW:0:7})"

mkdir -p "$DEST"
rm -rf "$MODULES.new" "$MODULES.old"
cp -a "$CACHE/node_modules" "$MODULES.new"
[ -d "$MODULES" ] && mv "$MODULES" "$MODULES.old"
mv "$MODULES.new" "$MODULES"
rm -rf "$MODULES.old"
find "$DEST" -mindepth 1 -maxdepth 1 ! -name tmp ! -name .deployed_build -exec rm -rf {} +
tar -C "$CACHE" --exclude=./.git --exclude=./node_modules -cf - . | tar -C "$DEST" -xf -
echo "$NEW" > "$DEST/.deployed_build"

SELECTOR=$(command -v cloudlinux-selector || ls /usr/sbin/cloudlinux-selector /usr/bin/cloudlinux-selector 2>/dev/null | head -1 || true)
if [ -z "$SELECTOR" ] || ! "$SELECTOR" restart --json --interpreter=nodejs --app-root="$APP_ROOT" >/dev/null; then
  mkdir -p "$DEST/tmp" && touch "$DEST/tmp/restart.txt"
fi
sleep 3
code=$(curl -s -m 30 -o /dev/null -w '%{http_code}' "$SITE/login")
if [ "$code" = "200" ]; then
  echo "✓ CRM web is up ($SITE/login → 200)"
else
  echo "✗ CRM web returned $code — check $DEST/stderr.log"
  exit 1
fi
