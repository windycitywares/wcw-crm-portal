# Deploying the CRM to HostItBro (cPanel)

Same server, same approach as the shop (see the shop's `docs/DEPLOYMENT.md`): account `windycit`,
home `/home2/windycit`, Python 3.11.17, Node 20, PostgreSQL 13 (no extensions), cPanel Terminal + Git.

| URL | App | Folder on the server |
|---|---|---|
| `https://crm.windycitywares.com` | Next.js web app (Node 20) | `~/apps/crm/wcw-crm-web` (packages in `~/apps/crm/node_modules`) |
| `https://crm-api.windycitywares.com` | FastAPI (Python 3.11) | `~/repos/wcw-crm-portal/backend` |
| — | Source checkout | `~/repos/wcw-crm-portal` |
| — | Database | PostgreSQL `windycit_crm`, user `windycit_crmapp` |

GitHub Actions builds the web app (the server's 2 GB memory is too small for `next build`) and
publishes it to the `web-build` branch; the server only pulls. No server passwords are stored in GitHub.

---

## 0. Clean up the old crm.windycitywares.com (one time)

The subdomain already exists with an old site in its own folder and MySQL databases. **Back everything up
first, move rather than delete, and only drop the databases once the backups are safe on your computer.**

1. **Find the old folder** — cPanel → **Domains** → `crm.windycitywares.com` → note its *Document Root*
   (e.g. `/home2/windycit/crm.windycitywares.com`). Keep the domain itself; only its contents go.
2. **Back up the files** — cPanel → **Terminal** (replace the path with the one from step 1):
   ```bash
   OLD=/home2/windycit/crm.windycitywares.com
   mkdir -p ~/backups/crm-old
   tar -czf ~/backups/crm-old/files-$(date +%F).tar.gz -C "$(dirname "$OLD")" "$(basename "$OLD")"
   ls -lh ~/backups/crm-old/
   ```
   Download the `.tar.gz` (File Manager → `backups/crm-old` → Download) and keep it on your computer.
3. **Back up the databases** — cPanel → **MySQL Databases**: note every database the old CRM used
   (names usually contain `crm`). Then cPanel → **Backup** → *Download a MySQL Database Backup* → click each
   one and save the `.sql.gz` files on your computer.
4. **Look for leftovers** — cPanel → **Cron Jobs**: remove any job that points into the old folder.
   cPanel → **Setup Python App / Setup Node.js App**: if an app uses `crm.windycitywares.com`, note it and
   **Stop** it (don't delete yet).
5. **Empty the folder** (moved aside, so it's reversible):
   ```bash
   mv "$OLD" ~/backups/crm-old/docroot-$(date +%F)
   mkdir -p "$OLD"
   ```
   `https://crm.windycitywares.com` now shows an empty/403 page — expected until step 4 below.
6. **Drop the old databases** — only after steps 2–3 are saved on your computer: cPanel →
   **MySQL Databases** → *Delete* each old CRM database and its MySQL user. (The new CRM uses PostgreSQL.)
7. After a few weeks with the new CRM running, delete `~/backups/crm-old` on the server.

## 1. API subdomain

cPanel → **Domains** → *Create A New Domain* → `crm-api.windycitywares.com` (uncheck "share document root";
document root e.g. `crm-api.windycitywares.com`). Then **SSL/TLS Status** → *Run AutoSSL* so both
`crm.` and `crm-api.` have certificates.

## 2. Database

cPanel → **PostgreSQL Databases**: create database `windycit_crm` and user `windycit_crmapp` (strong
password), then add the user to the database with **ALL PRIVILEGES**.
Connection string: `postgresql+asyncpg://windycit_crmapp:PASSWORD@localhost:5432/windycit_crm`

## 3. Code from GitHub (read-only deploy key)

GitHub deploy keys work for one repository each, so the CRM gets its own key:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/wcw_crm_deploy -N "" && cat ~/.ssh/wcw_crm_deploy.pub
```
GitHub → `wcw-crm-portal` → **Settings → Deploy keys → Add deploy key** → paste, leave *write access* off.

```bash
cat >> ~/.ssh/config <<'CFG'
Host github-wcw-crm
  HostName github.com
  User git
  IdentityFile ~/.ssh/wcw_crm_deploy
CFG
mkdir -p ~/repos ~/logs && cd ~/repos && git clone git@github-wcw-crm:windycitywares/wcw-crm-portal.git
```

## 4. API (Setup Python App)

1. cPanel → **Setup Python App** → *Create application*:
   Python **3.11.17** · Application root `repos/wcw-crm-portal/backend` · Application URL
   `crm-api.windycitywares.com` · Startup file **`wsgi.py`** · Entry point `application`.
   (Never name our file `passenger_wsgi.py` — cPanel generates that loader itself.)
2. Copy the `source …/activate` command it shows, then:
   ```bash
   source /home2/windycit/virtualenv/repos/wcw-crm-portal/backend/3.11/bin/activate
   cd ~/repos/wcw-crm-portal/backend
   pip install -r requirements.txt
   cp .env.example .env && chmod 600 .env && nano .env
   ```
   ```ini
   ENVIRONMENT=production
   DATABASE_URL=postgresql+asyncpg://windycit_crmapp:PASSWORD@localhost:5432/windycit_crm
   JWT_SECRET=          # python -c "import secrets; print(secrets.token_urlsafe(48))"
   DATA_ENCRYPTION_KEY= # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ADMIN_EMAIL=you@windycitywares.com
   ADMIN_PASSWORD=      # temporary, 10+ characters; change it after the first sign-in
   ```
   `production.env` (committed) already sets `DB_USE_NULL_POOL`, `CORS_ORIGINS` and `SITE_URL` for
   crm.windycitywares.com. **Keep a copy of `DATA_ENCRYPTION_KEY` somewhere safe** — without it, secrets saved
   in Admin → Settings (e.g. the SMTP password) can't be read.
3. ```bash
   alembic upgrade head
   python -m app.seed      # creates the first admin from ADMIN_EMAIL / ADMIN_PASSWORD
   ```
4. **Restart** the app. Check `https://crm-api.windycitywares.com/health` → `{"status":"ok",…}`.

## 5. Web app (Setup Node.js App)

The bundle appears on the `web-build` branch after the first merge to `main` that touches `frontend/`
(Actions → *web*). Then in Terminal:

```bash
mkdir -p ~/apps/crm
cloudlinux-selector create --interpreter=nodejs --version=20 --app-root=apps/crm/wcw-crm-web \
  --domain=crm.windycitywares.com --app-uri=/ --app-mode=production --startup-file=server.js
bash ~/repos/wcw-crm-portal/deploy/update-web.sh
```

(Or create it in cPanel → **Setup Node.js App** with the same values.) Check `https://crm.windycitywares.com/login`.

## 6. Automatic updates

```bash
crontab -e
```
add (minute 5, 15, 25 … so it never overlaps the shop's job at 0, 10, 20 …):
```
* * * * * bash $HOME/repos/wcw-crm-portal/deploy/auto-deploy.sh >> $HOME/logs/wcw-crm-deploy.log 2>&1
```

- **API** — new commits on `main` → `update-api.sh`: install, run tests, migrate, seed, restart, check `/health`.
  If install or tests fail, the previous code is restored and the running API is untouched.
- **Web** — a new `web-build` → `update-web.sh`: swap in the new bundle, restart, check `/login`.
- **Jobs** — then `run-jobs.sh` (`python -m app.workers.run_jobs`): sends queued emails within the limits set in
  Admin → Settings → Email and retries failures. Modules add their own jobs (`CrmModule.jobs`).
- History: `~/logs/wcw-crm-deploy.log`. Run any script by hand to deploy immediately.

**Release flow: merge a PR into `main` → live within the interval set in Admin → Deployments (default 10 min),
or click *Deploy now* there (starts within a minute).**

The cron job runs every minute but only *looks* for updates when Admin → Deployments says so: automatically
every N minutes, only at set times (e.g. 02:00), paused, or right away after *Deploy now*. The page also shows
the live versions and the deploy log. If the gate can't answer (database down), the script looks for updates
as before, so updates never get stuck.

## 7. First sign-in

1. Open `https://crm.windycitywares.com`, sign in with `ADMIN_EMAIL` / `ADMIN_PASSWORD`.
2. **Your account** → change the password. Then remove `ADMIN_PASSWORD` from `backend/.env`.
3. **Users** → add your team with their roles (Admin, Manager, Sales, Support, Marketing, Read-only).

Outgoing email (password resets, later campaigns) waits in the outbox until the SMTP account is saved and
switched on in Admin → Settings → Email; use the **Send test email** button there to check it. Until then,
admins set passwords in **Users**.

## 8. Files customers send (attachments)

Mail that arrives on a mailbox the CRM reads is filed with whatever came with it — a photo of the damage, a
PDF invoice — kept against the ticket it belongs to. A message may bring up to 10 files of 15 MB each;
anything past that is counted, and the message itself says it was left behind.

The files live on the server's own disk, **outside the checkout** (a deploy replaces the checkout, and a
customer's photo has to outlive it):

```
~/apps/crm/wcw-crm-files/<aa>/<sha256>     # the default; the ATTACHMENTS_DIR setting overrides it
```

- Created on first use, owned by the app's own user: nothing to set up before the first message arrives.
- A file is named after the sha256 of its own bytes, so the same file sent twice is stored once.
- **Back this directory up with the database.** The rows know a file's name, type and size; the bytes are
  only here. Losing it doesn't break anything, but the files are gone for good.
- Removing a file (or a record that held it) drops the stored bytes only when nothing else points at them,
  so the directory is normally at least as small as the records suggest.

## Troubleshooting

Gotchas found during the first install (2026-10-16), handled by `deploy/first-setup.sh`:
- Creating the Python app **overwrites `backend/wsgi.py`** with cPanel's "It works!" template (which answers
  200 to every URL). Fix: `git -C ~/repos/wcw-crm-portal checkout -- backend/wsgi.py`, then Restart.
- After a web deploy the site can keep serving the **old build** (new pages 404): LiteSpeed keeps the old Node
  process alive in memory even through Restart/Stop/Start. Next.js renames that process `next-server (vX)`, so it
  can't be found by name; `update-web.sh` ends the processes whose working directory is the app folder and checks the
  served page carries the new `BUILD_ID`. By hand:
  `for p in $(pgrep -u $USER -f next-server); do [ "$(readlink /proc/$p/cwd)" = "$HOME/apps/crm/wcw-crm-web" ] && kill $p; done`
- A `.htaccess` written while the shell had `umask 077` is `0600`, so LiteSpeed ignores it and shows a
  directory listing / 404. Fix: `chmod 644 ~/crm.windycitywares.com/.htaccess`.

| Symptom | Look at |
|---|---|
| API 503 / 500 | `~/repos/wcw-crm-portal/backend/stderr.log`; Setup Python App → Restart |
| Web 503 | `~/apps/crm/wcw-crm-web/stderr.log`; `bash ~/repos/wcw-crm-portal/deploy/update-web.sh` |
| "Can't reach the CRM server" on the login page | `crm-api` SSL certificate, `CORS_ORIGINS` in `production.env`/`.env`, API health |
| Deploy didn't happen | `tail -50 ~/logs/wcw-crm-deploy.log`; `crontab -l` |
