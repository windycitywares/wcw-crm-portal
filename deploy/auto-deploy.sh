#!/bin/bash
# Cron entry point — runs EVERY MINUTE:
#   * * * * * bash $HOME/repos/wcw-crm-portal/deploy/auto-deploy.sh >> $HOME/logs/wcw-crm-deploy.log 2>&1
# 1. Ask the gate (Admin → Deployments) whether to look for updates now: "Deploy now" clicked, paused,
#    every N minutes, or at scheduled times. If the gate can't answer (e.g. DB down), behave as before: look.
# 2. API: when `main` has new commits, run update-api.sh (tests must pass before it restarts).
# 3. Web: when GitHub Actions has published a new build to `web-build`, run update-web.sh.
# 4. Tell the gate what happened (shown in Admin → Deployments), then run the background jobs.
set -uo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"   # cron's default PATH is minimal
exec 9>"$HOME/.wcw-crm-deploy.lock"
flock -n 9 || exit 0   # a previous run is still going

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export WCW_CRM_REPO_DIR="$REPO"
API_ROOT="${REPO#"$HOME"/}/backend"
VENV="$HOME/virtualenv/$API_ROOT/3.11/bin/activate"
ts() { date '+%F %T'; }
gate() {  # gate begin | gate end ok|failed "summary"
  # shellcheck disable=SC1090
  ( source "$VENV" && cd "$REPO/backend" && python -m app.workers.deploy_gate "$@" ) 2>>"$HOME/logs/wcw-crm-gate.err"
}

decision=$(gate begin || true)
case "$decision" in
  go*) reason="${decision#go }" ;;
  skip*) [ -f "$REPO/deploy/run-jobs.sh" ] && { bash "$REPO/deploy/run-jobs.sh" || echo "$(ts) background jobs FAILED"; }
         exit 0 ;;
  *) reason="gate unavailable" ;;
esac

ok=1
summary=""
cd "$REPO" || exit 1
if ! git fetch -q origin main; then
  echo "$(ts) git fetch failed"
  ok=0; summary="git fetch failed"
elif [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  target="$(git log --oneline -1 origin/main)"
  echo "$(ts) API: updating to $target ($reason)"
  # Run the copy from origin/main so script changes take effect immediately.
  git show origin/main:deploy/update-api.sh > "$HOME/.wcw-crm-update-api.sh"
  if bash "$HOME/.wcw-crm-update-api.sh" main; then
    summary="API updated to $target"
  else
    echo "$(ts) API update FAILED — see the ✗ line above"
    ok=0; summary="API update to $target failed — the previous version keeps running"
  fi
fi

web_out=$(bash "$REPO/deploy/update-web.sh" --if-changed 2>&1); web_rc=$?
[ -n "$web_out" ] && echo "$web_out"
if [ "$web_rc" -ne 0 ]; then
  echo "$(ts) web update FAILED"
  ok=0; summary="${summary:+$summary; }web update failed"
elif [ -n "$web_out" ]; then
  summary="${summary:+$summary; }web build $(cut -c1-7 "$HOME/apps/crm/wcw-crm-web/BUILD_SHA" 2>/dev/null)"
fi

[ "$reason" = "manual" ] && [ -z "$summary" ] && echo "$(ts) deploy now: already up to date"
if [ "$ok" = 1 ]; then gate end ok "${summary:-already up to date} ($reason)" >/dev/null
else gate end failed "$summary ($reason)" >/dev/null; fi

[ -f "$REPO/deploy/run-jobs.sh" ] && { bash "$REPO/deploy/run-jobs.sh" || echo "$(ts) background jobs FAILED"; }
exit 0
