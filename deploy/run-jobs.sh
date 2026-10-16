#!/bin/bash
# Background jobs (send queued emails, retries, …). auto-deploy.sh runs this every 10 minutes; by hand:
#   bash ~/repos/wcw-crm-portal/deploy/run-jobs.sh                # everything due
#   bash ~/repos/wcw-crm-portal/deploy/run-jobs.sh --only outbox  # some jobs
set -euo pipefail
REPO_DIR="${WCW_CRM_REPO_DIR:-$HOME/repos/wcw-crm-portal}"
APP_ROOT="${REPO_DIR#"$HOME"/}/backend"
# shellcheck disable=SC1090
source "$HOME/virtualenv/$APP_ROOT/3.11/bin/activate"
cd "$HOME/$APP_ROOT"
exec python -m app.workers.run_jobs "$@"
