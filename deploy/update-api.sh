#!/bin/bash
# Update the CRM API on HostItBro to the latest code from GitHub.
#   bash ~/repos/wcw-crm-portal/deploy/update-api.sh [branch]
# If installing or the tests fail, the previous code is restored and the running app is untouched.
set -euo pipefail
BRANCH="${1:-main}"
REPO_DIR="${WCW_CRM_REPO_DIR:-$HOME/repos/wcw-crm-portal}"
APP_ROOT="${REPO_DIR#"$HOME"/}/backend"   # cPanel Setup Python App → application root
VENV="$HOME/virtualenv/$APP_ROOT/3.11/bin/activate"
HEALTH="https://crm-api.windycitywares.com/health"
RESTARTED=0

cd "$REPO_DIR"
PREV=$(git rev-parse HEAD)
rollback() {
  if [ "$RESTARTED" = "0" ]; then
    echo "✗ update failed before restart — restoring $(git log --oneline -1 "$PREV")"
    git checkout -q -B "$BRANCH" "$PREV"
  fi
}
trap rollback ERR

echo "→ Fetching $BRANCH"
git fetch -q origin "$BRANCH"
git checkout -q -B "$BRANCH" "origin/$BRANCH"
git log --oneline -1

cd backend
# shellcheck disable=SC1090
source "$VENV"
echo "→ Installing packages"
pip install -q -r requirements.txt
echo "→ Running tests"
python -m unittest discover -q tests
echo "→ Database migrations"
alembic upgrade head
echo "→ Seed (first admin, default types — never changes existing data)"
python -m app.seed
echo "→ Restarting the app"
RESTARTED=1
SELECTOR=$(command -v cloudlinux-selector || ls /usr/sbin/cloudlinux-selector /usr/bin/cloudlinux-selector 2>/dev/null | head -1 || true)
if [ -z "$SELECTOR" ] || ! "$SELECTOR" restart --json --interpreter=python --app-root="$APP_ROOT" >/dev/null; then
  mkdir -p "$HOME/$APP_ROOT/tmp" && touch "$HOME/$APP_ROOT/tmp/restart.txt"
fi
code=000
for _ in $(seq 1 18); do   # the app can take a while to start (503 meanwhile): retry for ~90 s
  sleep 5
  body=$(curl -s -m 20 "$HEALTH" || true)
  case "$body" in *'"status":"ok"'*) code=200; break;; *) code=000;; esac
done
if [ "$code" = "200" ]; then echo "✓ CRM API is up (health 200)"; else echo "✗ restarted on the new code, but $HEALTH returns $code after 90 s — see backend/stderr.log"; exit 1; fi
