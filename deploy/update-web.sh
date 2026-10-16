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
# LiteSpeed keeps Node processes running in the background and may keep serving the OLD build from memory
# even after a restart (seen 2026-10-16). End every process of THIS app; LiteSpeed starts a fresh one on the
# next request. Next.js renames its process to "next-server (vX)", so the command line doesn't name the
# folder — match on the working directory instead (server.js chdirs into the app root). The shop's and main
# site's Next servers have other working directories and are left alone.
stop_app_processes() {
  local pid cwd n=0
  for pid in $(pgrep -u "$(id -u)" -f 'next-server|node' 2>/dev/null); do
    cwd=$(readlink "/proc/$pid/cwd" 2>/dev/null || true)
    case "$cwd" in
      "$DEST"|"$DEST (deleted)") kill "$pid" 2>/dev/null && n=$((n + 1)) ;;
    esac
  done
  [ "$n" -gt 0 ] && echo "  ended $n old process(es) of this app"
  return 0
}
stop_app_processes
sleep 2

# Check that the site really serves the new build (its BUILD_ID appears in every page), not just that it's up.
BUILD_ID=$(cat "$DEST/.next/BUILD_ID" 2>/dev/null || true)
ok=0
for _ in $(seq 1 12); do
  page=$(curl -s -m 30 "$SITE/login?deploy=$NEW" || true)
  if [ -n "$BUILD_ID" ] && printf '%s' "$page" | grep -q "$BUILD_ID"; then ok=1; break; fi
  sleep 5
done
if [ "$ok" = 1 ]; then
  echo "✓ CRM web is up and serving build $BUILD_ID ($SITE/login)"
else
  echo "✗ CRM web isn't serving the new build ($BUILD_ID) after 60 s — check $DEST/stderr.log or stop/start the app in Setup Node.js App"
  exit 1
fi
