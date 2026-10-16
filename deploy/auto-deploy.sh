#!/bin/bash
# Cron entry point (every 10 minutes, offset from the shop's): deploy whatever is new on GitHub.
#   5-59/10 * * * * bash $HOME/repos/wcw-crm-portal/deploy/auto-deploy.sh >> $HOME/logs/wcw-crm-deploy.log 2>&1
# - API: when `main` has new commits, run update-api.sh (tests must pass before it restarts).
# - Web: when GitHub Actions has published a new build to `web-build`, run update-web.sh.
# - Then the background jobs (queued emails, retries …): run-jobs.sh.
set -uo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"   # cron's default PATH is minimal
exec 9>"$HOME/.wcw-crm-deploy.lock"
flock -n 9 || exit 0   # a previous run is still going

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export WCW_CRM_REPO_DIR="$REPO"
cd "$REPO" || exit 1
git fetch -q origin main || { echo "$(date '+%F %T') git fetch failed"; exit 1; }
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  echo "$(date '+%F %T') API: updating to $(git log --oneline -1 origin/main)"
  # Run the copy from origin/main so script changes take effect immediately.
  git show origin/main:deploy/update-api.sh > "$HOME/.wcw-crm-update-api.sh"
  bash "$HOME/.wcw-crm-update-api.sh" main || echo "$(date '+%F %T') API update FAILED — see the ✗ line above"
fi

bash "$REPO/deploy/update-web.sh" --if-changed || echo "$(date '+%F %T') web update FAILED"

[ -f "$REPO/deploy/run-jobs.sh" ] && { bash "$REPO/deploy/run-jobs.sh" || echo "$(date '+%F %T') background jobs FAILED"; }
