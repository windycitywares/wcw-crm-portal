#!/bin/bash
# One-time server setup for the CRM on HostItBro. Run in cPanel → Terminal, after:
#   - ~/.wcw-crm-secrets exists (DATABASE_URL, JWT_SECRET, DATA_ENCRYPTION_KEY)
#   - the deploy key ~/.ssh/wcw_crm_deploy is added to the GitHub repo (read-only)
# Safe to run again: every step skips what is already done.
set -euo pipefail
umask 022   # web server must be able to read .htaccess files the selector writes
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
REPO="$HOME/repos/wcw-crm-portal"
API_ROOT="repos/wcw-crm-portal/backend"
WEB_ROOT="apps/crm/wcw-crm-web"
SECRETS="$HOME/.wcw-crm-secrets"
step() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

step "1/7 Checks"
[ -s "$SECRETS" ] || { echo "✗ $SECRETS is missing"; exit 1; }
chmod 600 "$SECRETS"
SEL=$(command -v cloudlinux-selector || ls /usr/sbin/cloudlinux-selector /usr/bin/cloudlinux-selector 2>/dev/null | head -1)
[ -n "$SEL" ] || { echo "✗ cloudlinux-selector not found"; exit 1; }
echo "✓ secrets file and selector found"

step "2/7 Code"
mkdir -p "$HOME/repos" "$HOME/logs" "$HOME/apps/crm"
if [ ! -d "$REPO/.git" ]; then
  ssh -o StrictHostKeyChecking=accept-new -T git@github-wcw-crm 2>&1 | head -1 || true
  git clone -q git@github-wcw-crm:windycitywares/wcw-crm-portal.git "$REPO"
fi
git -C "$REPO" fetch -q origin main && git -C "$REPO" checkout -q -B main origin/main
echo "✓ $(git -C "$REPO" log --oneline -1)"

step "3/7 Python app (crm-api.windycitywares.com)"
if [ ! -f "$HOME/virtualenv/$API_ROOT/3.11/bin/activate" ]; then
  "$SEL" create --json --interpreter=python --version=3.11 --app-root="$API_ROOT" \
    --domain=crm-api.windycitywares.com --app-uri=/ --startup-file=wsgi.py --entry-point=application
fi
# Creating the app replaces wsgi.py with cPanel's "It works!" template: put ours back.
git -C "$REPO" checkout -- backend/wsgi.py
# shellcheck disable=SC1090
source "$HOME/virtualenv/$API_ROOT/3.11/bin/activate"
cd "$REPO/backend"
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✓ packages installed"

step "4/7 Settings, database, first admin"
if [ ! -f .env ]; then
  read -rp "Admin email for the CRM: " ADMIN_EMAIL
  read -rsp "Temporary admin password (10+ characters, not shown): " ADMIN_PASSWORD; echo
  umask 077
  { echo "ENVIRONMENT=production"; grep -E '^(DATABASE_URL|JWT_SECRET|DATA_ENCRYPTION_KEY)=' "$SECRETS";
    echo "ADMIN_EMAIL=$ADMIN_EMAIL"; echo "ADMIN_PASSWORD=$ADMIN_PASSWORD"; } > .env
  unset ADMIN_PASSWORD
fi
chmod 600 .env
alembic upgrade head
python -m app.seed
sed -i '/^ADMIN_PASSWORD=/d' .env   # the account exists now; don't keep the password on disk

step "5/7 Start the API"
"$SEL" restart --json --interpreter=python --app-root="$API_ROOT" >/dev/null || { mkdir -p tmp && touch tmp/restart.txt; }
code=000
for _ in $(seq 1 18); do sleep 5; body=$(curl -s -m 20 https://crm-api.windycitywares.com/health || true); case "$body" in *'"status":"ok"'*) code=200; break;; esac; done
[ "$code" = 200 ] && echo "✓ https://crm-api.windycitywares.com/health → 200" || { echo "✗ health returned $code — see $REPO/backend/stderr.log"; exit 1; }

step "6/7 Web app (crm.windycitywares.com)"
if [ ! -d "$HOME/$WEB_ROOT" ]; then
  "$SEL" create --json --interpreter=nodejs --version=20 --app-root="$WEB_ROOT" \
    --domain=crm.windycitywares.com --app-uri=/ --app-mode=production --startup-file=server.js
fi
chmod 644 "$HOME/crm.windycitywares.com/.htaccess" "$HOME/crm-api.windycitywares.com/.htaccess" 2>/dev/null || true
bash "$REPO/deploy/update-web.sh"

step "7/7 Automatic updates (cron every 10 min)"
LINE='5-59/10 * * * * bash $HOME/repos/wcw-crm-portal/deploy/auto-deploy.sh >> $HOME/logs/wcw-crm-deploy.log 2>&1'
if crontab -l 2>/dev/null | grep -qF 'wcw-crm-portal/deploy/auto-deploy.sh'; then
  echo "✓ cron already set"
else
  (crontab -l 2>/dev/null; echo "$LINE") | crontab -
  echo "✓ cron added"
fi

printf '\n\033[1m✓ Done.\033[0m Open https://crm.windycitywares.com and sign in.\n'
