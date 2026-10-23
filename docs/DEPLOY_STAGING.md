# FitGate Staging Deployment Guide (cPanel Host)

This guide provides a step-by-step, click-by-click procedure for deploying FitGate to the Yegara shared cPanel hosting environment. It is written for a non-developer: follow each numbered step in order and copy-paste the exact commands into cPanel's Web Terminal.

---

## Local Development Updates After Pulling

After pulling changes from git, update your local Docker development environment (without removing volumes):

```bash
docker compose build backend
docker compose up -d
docker compose exec backend python manage.py check
```

---

## Later Releases Update Procedure

When deploying future updates after the initial setup, follow this short procedure:

1. **Pre-release PostgreSQL 13 Suite Validation (Local Laptop)**:
   Yegara cPanel runs PostgreSQL 13.23 (local dev uses 16). Before every release, validate the full suite against a temporary PostgreSQL 13 container:
   ```bash
   docker run -d --name pg13test --network fitgate_default -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=fitgate_test -e POSTGRES_USER=postgres postgres:13-alpine
   docker compose exec -e DATABASE_URL="postgres://postgres:postgres@pg13test:5432/fitgate_test" -e ALLOW_POSTGRES_13=1 backend pytest
   docker stop pg13test ; docker rm pg13test
   ```
2. **Build release archive on your laptop**:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\deploy\build_release.ps1
   ```
3. **Upload and extract into clean directory**:
   - In cPanel **File Manager**, rename your existing `fitgate` folder to `fitgate_backup_release` (or delete old files so new releases do not leave orphaned files behind).
   - Create a clean `fitgate` folder and extract the new `fitgate_release_*.zip` into `/home/<username>/fitgate`.
4. **Update dependencies (if requirements changed)**:
   - In cPanel **Setup Python App**, find `fitgate.tebebtech.com`.
   - In the **Configuration files** section, click **Run Pip Install** next to `requirements/prod.txt`.
5. **Take database backup before every migrate**:
   - In cPanel **Terminal**, take an immediate database backup before executing any database migration:
     ```bash
     mkdir -p ~/fitgate_backups
     pg_dump -h localhost -U <username>_fitgate_user -w -F c -b -f ~/fitgate_backups/fitgate_pre_migrate_$(date +%Y%m%d_%H%M%S).dump <username>_fitgate_prod
     ```
   - _(Requires `~/.pgpass` configured as shown in Step 7. If `pg_dump` is unavailable on the host, use cPanel **Backup Wizard** &rarr; **Back Up** &rarr; **PostgreSQL Databases** to download a copy before migrating)._
6. **Run database migrations**:
   - Open cPanel **Terminal** and run:
     ```bash
     source ~/virtualenv/fitgate/3.11/bin/activate && cd ~/fitgate/backend && python manage.py migrate
     ```
7. **Collect static assets**:
   - In cPanel **Terminal**, run:
     ```bash
     source ~/virtualenv/fitgate/3.11/bin/activate && cd ~/fitgate/backend && python manage.py collectstatic --noinput
     ```
8. **Restart the application**:
   - In cPanel **Setup Python App**, click the **Restart** button (circular arrow icon) next to `fitgate.tebebtech.com`.

---

## Step 0: Clean Up the Feasibility Spike

Before starting the real deployment, remove all temporary items created during the earlier feasibility spike:

1. **Delete Spike Python App & Virtualenv**:
   - In cPanel, navigate to **Software** &rarr; **Setup Python App**.
   - Locate the spike application associated with `fitgate.tebebtech.com` (or named `spike_app`).
   - Click the red **Delete** (trash can) icon and confirm deletion. This automatically deletes the associated virtual environment under `~/virtualenv/spike_app`.
   - In cPanel **File Manager**, check your home directory (`/home/<username>/`): if the folder `~/spike_app` still exists, right-click and delete it permanently.
2. **Remove Spike Subdomain**:
   - In cPanel, navigate to **Domains** &rarr; **Domains** (or **Subdomains**).
   - Find `spike1.fitgate.tebebtech.com`.
   - Click **Manage** (or **Remove**) &rarr; **Delete Subdomain** and confirm.
3. **Drop Spike Test Database & User**:
   - In cPanel, navigate to **Databases** &rarr; **PostgreSQL Databases**.
   - Under **Current Databases**, locate `<username>_fitspikedb` and click **Delete**.
   - Under **Current Users**, locate `<username>_fitspikeuser` and click **Delete**.

---

## Step 1: Create the Production PostgreSQL Database & User

1. Navigate to cPanel **Databases** &rarr; **PostgreSQL Databases**.
2. **Create New Database**:
   - In the **New Database** field, enter: `fitgate_prod`
   - Click **Create Database**. Note your full database name: `<username>_fitgate_prod`.
3. **Create Database User**:
   - Under **Add New User**, enter Username: `fitgate_user`
   - Use the password generator to generate a NEW strong password (at least 20 characters with letters, numbers, and symbols).
   - Click **Create User**. Note your full username: `<username>_fitgate_user` and the password.
4. **Grant Privileges**:
   - Under **Add User To Database**:
     - **User**: Select `<username>_fitgate_user`.
     - **Database**: Select `<username>_fitgate_prod`.
   - Click **Submit**.
   - Check the **ALL PRIVILEGES** checkbox and click **Make Changes**.
5. **Construct Your `DATABASE_URL`**:
   - The PostgreSQL connection URL has the format:
     `postgres://<username>_fitgate_user:<password>@localhost:5432/<username>_fitgate_prod`

---

## Step 2: Build and Upload the Release Package

1. **Build the Release Package on your laptop**:
   - Open PowerShell in the project root directory and run:
     ```powershell
     powershell -ExecutionPolicy Bypass -File .\deploy\build_release.ps1
     ```
   - This creates a dated release file in `dist/`, e.g. `dist/fitgate_release_YYYYMMDD_HHMMSS.zip`.
2. **Release Package Layout**:
   The release zip contains exactly ONE startup file (`passenger_wsgi.py`) at the root:
   ```text
   fitgate_release_*.zip
   ├── passenger_wsgi.py                  # Single WSGI startup file at release root
   ├── requirements/
   │   ├── base.txt
   │   └── prod.txt                       # Production requirements
   ├── frontend/
   │   └── dist/                          # Pre-compiled React SPA assets
   │       ├── index.html
   │       └── assets/
   ├── backend/                           # Django application code
   │   ├── manage.py
   │   ├── fitgate/
   │   └── apps/
   └── .env.production.example
   ```
3. **Upload and Extract via cPanel File Manager**:
   - In cPanel, open **File Manager** (under **Files**).
   - In the top right corner, click **Settings**, ensure **Show Hidden Files (dotfiles)** is checked, and click **Save**.
   - Navigate to your home directory (`/home/<username>/`).
   - Click **+ Folder** in the top toolbar and create a directory named `fitgate`.
   - Double-click into the new `fitgate` folder.
   - Click **Upload** in the top toolbar, select your `fitgate_release_*.zip` file, and wait for the upload progress bar to turn green (100%).
   - Return to File Manager, select the uploaded zip file, click **Extract** in the top bar, and extract directly into `/home/<username>/fitgate`.
   - Confirm the extracted folder contains `passenger_wsgi.py`, `backend/`, `frontend/dist/`, and `requirements/prod.txt`.

---

## Step 3: Create the Production Python Application

1. In cPanel, navigate to **Software** &rarr; **Setup Python App**.
2. Click the blue **Create Application** button.
3. Fill in the fields:
   - **Python version**: Select **3.11** (the host runs Python 3.11.17).
   - **Application root**: `fitgate`
   - **Application URL**: Select `fitgate.tebebtech.com`.
   - **Application startup file**: `passenger_wsgi.py`
   - **Application Entry point**: `application`
4. Click **Create** in the top right corner.
5. In the **Configuration files** section:
   - Enter `requirements/prod.txt` into the input field and click **Add**.
   - Click **Run Pip Install** next to `requirements/prod.txt`.
   - Wait for pip installation to finish with a success notice.

---

## Step 4: Create the Protected Environment File

Production settings are read from ONE protected file outside `public_html` and outside the release folder so the website, background cron jobs, and terminal sessions always share the exact same configuration.

1. **Enable Dotfiles Visibility in File Manager**:
   - In cPanel **File Manager**, click **Settings** (top right gear icon).
   - Check **Show Hidden Files (dotfiles)** and click **Save**. Without this, `.env` will be invisible in File Manager.
2. **Create directories and file in cPanel Terminal**:
   - Open cPanel **Terminal** (under **Advanced**) and run:
     ```bash
     mkdir -p ~/fitgate_env ~/fitgate_media ~/fitgate_logs ~/fitgate_backups
     touch ~/fitgate_env/.env
     chmod 600 ~/fitgate_env/.env
     ```
3. **Generate Production Cryptographic Keys on Your Laptop**:
   - Django settings fail fast if `.env` does not exist on the host, so generate all three production keys on your laptop's running Docker container:
     ```bash
     docker compose exec backend python manage.py generate_secret_key
     docker compose exec backend python manage.py generate_tenant_credentials_key
     docker compose exec backend python manage.py generate_qr_keys
     ```
   - **Critical Security Rules**:
     - The host's QR keys must be NEW keys generated for staging/production, NEVER your laptop's local development keys.
     - Never save these production keys to a file on your laptop or share them.
     - `generate_qr_keys` prints single-line escaped PEM strings with literal `\n`, ready to paste straight into the `.env` template below.
4. **Populate the configuration values**:
   - In cPanel **File Manager**, navigate to `/home/<username>/fitgate_env/`.
   - Right-click `.env`, choose **Edit** (UTF-8 encoding), and paste the template below. Fill in every value:

```env
# Core & Domain
DOMAIN=fitgate.tebebtech.com
SECRET_KEY=<paste output of generate_secret_key>
DEBUG=False

# Database
DATABASE_URL=postgres://<username>_fitgate_user:<password>@localhost:5432/<username>_fitgate_prod

# cPanel UAPI Subdomain Provisioning
CPANEL_USE_MOCK=False
CPANEL_HOST=<cpanel_server_real_hostname>
CPANEL_USERNAME=<your_cpanel_username>
CPANEL_API_TOKEN=<your_cpanel_api_token>
CPANEL_ROOT_DOMAIN=tebebtech.com
CPANEL_SUBDOMAIN_DOCROOT=public_html/fitgate

# Keys
TENANT_CREDENTIALS_KEY=<paste output of generate_tenant_credentials_key>
QR_JWT_PRIVATE_KEY=<paste private key output of generate_qr_keys>
QR_JWT_PUBLIC_KEY=<paste public key output of generate_qr_keys>

# Outbound Email (Brevo SMTP)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_PORT=587
EMAIL_HOST_USER=<your_brevo_smtp_login>
EMAIL_HOST_PASSWORD=<your_brevo_smtp_master_key>
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
DEFAULT_FROM_EMAIL=noreply@fitgate.tebebtech.com

# Persistent Media & Logs
MEDIA_ROOT=/home/<username>/fitgate_media
LOG_DIR=/home/<username>/fitgate_logs
```

> [!IMPORTANT]
> **cPanel Hostname & API Token Requirements**:
> - **CPANEL_HOST**: FitGate's `uapi.py` enforces strict TLS certificate checking via `ssl.create_default_context()` with hostname verification ON. A connection to `localhost` or `127.0.0.1` on port 2083 will fail TLS verification because the cPanel SSL certificate is issued for the real server hostname. You MUST set `CPANEL_HOST` to the cPanel server's real hostname (the same hostname used during the laptop probe, without `https://` and without `:2083`). "localhost" is documented only as a fallback and will fail certificate checks.
> - **CPANEL_API_TOKEN**: In cPanel, navigate to **Security** &rarr; **Manage API Tokens**. Click **Create API Token**, enter name `FitGate-UAPI`, set an expiration date, and generate the token. (cPanel API tokens take only a name and expiration date and carry account access; no subdomain-specific permission checkbox is presented on this screen). Use a dedicated token for the host's env file, and delete any temporary laptop probe token after staging.

---

## Step 5: Email Configuration & Verification (Brevo)

The Brevo sending domain `fitgate.tebebtech.com` is authenticated with DKIM, DMARC, and verified sender `noreply@fitgate.tebebtech.com`.

1. **Verify your `.env` contains the Brevo SMTP credentials**:
   - Ensure `EMAIL_HOST=smtp-relay.brevo.com`, `EMAIL_PORT=587`, `EMAIL_USE_TLS=True`, `EMAIL_USE_SSL=False`, and your Brevo login and SMTP key are present in `~/fitgate_env/.env`.
2. **Verify Click Tracking Stays Off in Brevo**:
   - Log in to your Brevo dashboard, navigate to **Transactional** &rarr; **Settings** &rarr; **Configuration**.
   - Verify that **Track clicks** is completely disabled. Click tracking must stay off for transactional email so member invitation tokens and password reset links point directly to `fitgate.tebebtech.com` without tracking redirect URLs.
3. **Send a test email from Web Terminal**:
   - Run the command, substituting your own email address:
     ```bash
     source ~/virtualenv/fitgate/3.11/bin/activate && cd ~/fitgate/backend && python manage.py send_test_email --to your-email@gmail.com
     ```
   - Look for: `[OK] Test email successfully delivered to your-email@gmail.com via smtp-relay.brevo.com:587.`
4. **Verify Deliverability in Gmail**:
   - Open the received email in Gmail.
   - Click the three dots (More) next to the reply button &rarr; **Show original**.
   - Verify that **SPF: PASS**, **DKIM: PASS**, and **DMARC: PASS** all display.
   - If the email does not appear in your inbox, check the **Spam** folder. If still not received, log in to Brevo &rarr; **Transactional** &rarr; **Real-time logs** and check if the address was placed on the blocked-contacts list.

---

## Step 6: Initialize Database, Static Files, Check, and Admin in Web Terminal

Open cPanel **Terminal** (under **Advanced**) and run the following commands sequentially. Each command shows the expected output:

### 1. Pre-Migrate Database Backup

Before applying any schema changes, take a database backup:

```bash
mkdir -p ~/fitgate_backups
pg_dump -h localhost -U <username>_fitgate_user -w -F c -b -f ~/fitgate_backups/fitgate_pre_migrate_$(date +%Y%m%d_%H%M%S).dump <username>_fitgate_prod
```

_(If `~/.pgpass` is not configured yet, run `echo "localhost:5432:<username>_fitgate_prod:<username>_fitgate_user:<password>" > ~/.pgpass && chmod 600 ~/.pgpass` first)._

### 2. Apply Database Migrations

```bash
source ~/virtualenv/fitgate/3.11/bin/activate && cd ~/fitgate/backend && python manage.py migrate
```

- **Good result**: Lists migration operations ending with `Applying ... OK` with zero errors.

### 3. Collect Static Files

```bash
python manage.py collectstatic --noinput
```

- **Good result**: `... static files copied to '/home/<username>/fitgate/backend/staticfiles'.`

### 4. Production Deployment Check

```bash
python manage.py check --deploy
```

- **Exact Expected Output**:
  ```text
  System check identified some issues:

  WARNINGS:
  ?: (drf_spectacular.W001) Warning: enum naming encountered a non-optimally resolvable collision for fields named "status". The same name has been used for multiple choice sets in multiple components. The collision was resolved with "StatusBa9Enum". add an entry to ENUM_NAME_OVERRIDES to fix the naming.
  ?: (drf_spectacular.W001) Warning: operationId "media_member_photos_retrieve" has collisions [('/api/media/member-photos/{gym_id}/', 'get'), ('/api/media/member-photos/{gym_id}/{filename}/', 'get')]. resolving with numeral suffixes.
  ?: (drf_spectacular.W002) /home/<username>/fitgate/backend/apps/memberships/views.py: Error [MemberSelfMetricsView]: unable to guess serializer. This is graceful fallback handling for APIViews. Consider using GenericAPIView as view base class, if view is under your control. Either way you may want to add a serializer_class (or method). Ignoring view for now.
  ?: (drf_spectacular.W002) /home/<username>/fitgate/backend/apps/tenants/views.py: Error [UploadMemberPhotoView]: unable to guess serializer. This is graceful fallback handling for APIViews. Consider using GenericAPIView as view base class, if view is under your control. Either way you may want to add a serializer_class (or method). Ignoring view for now.
  ?: (security.W004) You have not set a value for the SECURE_HSTS_SECONDS setting. If your entire site is served only over SSL, you may want to consider setting a value and enabling HTTP Strict Transport Security. Be sure to read the documentation first; enabling HSTS carelessly can cause serious, irreversible problems.
  ?: (security.W008) Your SECURE_SSL_REDIRECT setting is not set to True. Unless your site should be available over both SSL and non-SSL connections, you may want to either set this setting True or configure a load balancer or reverse-proxy server to redirect all connections to HTTPS.

  System check identified 6 issues (0 silenced).
  ```

- **Expected Status**:
  - **Zero errors**.
  - The listed warnings above are expected.
  - **Anything else (any ERROR, or any `security.W0xx` warning other than `W004` and `W008`) means STOP AND ASK**.

- **Meaning of Expected Warnings**:
  - `drf_spectacular.W001` and `W002`: Informational notices generated by drf-spectacular's OpenAPI schema inspection during check; these do not affect application operation.
  - `security.W004` (SECURE_HSTS_SECONDS): HTTP Strict Transport Security is left optional during initial staging so that browser caching does not lock access before TLS validation.
  - `security.W008` (SECURE_SSL_REDIRECT): Must remain False in Django settings because HTTPS is terminated upstream by the cPanel Apache reverse proxy, which injects `HTTPS=on` into the WSGI environment. Having Django perform redirects would cause redirect loops.

### 5. Verify cPanel UAPI Host Connectivity (Must Pass Before Creating a Gym)

```bash
python manage.py check_cpanel_uapi
```

- **Good result**:
  ```text
  [OK] Host network path to cPanel UAPI (https://<cpanel_host>:2083) is WORKING.
  Found 1 configured subdomain(s):
    - fitgate.tebebtech.com (docroot: public_html/fitgate)
  ```
  _This check MUST succeed before proceeding to Step 8. If it fails, verify `CPANEL_HOST` matches the server SSL hostname and `CPANEL_API_TOKEN` is valid._

### 6. Bootstrap Super Admin Account (Using Hidden Password Prompt)

Never write your production password directly in bash commands, as terminal commands are saved to bash history. Use a hidden prompt:

```bash
echo -n "Enter Super Admin password: " && read -rs SUPERADMIN_PASSWORD && echo && export SUPERADMIN_PASSWORD
export SUPERADMIN_EMAIL="your-email@tebebtech.com"
python manage.py create_super_admin
unset SUPERADMIN_PASSWORD SUPERADMIN_EMAIL
```

- **Good result**: `Super Admin account 'your-email@tebebtech.com' successfully created.` (Must change password at first login).

---

## Step 7: Scheduled Maintenance & Database Backups (Cron Jobs)

1. **Verify Cron Environment Settings Visibility**:
   - In cPanel, navigate to **Advanced** &rarr; **Cron Jobs**.
   - Under **Add New Cron Job**:
     - Common Settings: **Once Per Minute (`* * * * *`)**
     - Command:
       ```bash
       cd /home/<username>/fitgate/backend && /home/<username>/virtualenv/fitgate/3.11/bin/python manage.py check >> /home/<username>/fitgate_logs/cron_probe.log 2>&1
       ```
     - Click **Add New Cron Job**.
     - In cPanel **File Manager**, check `/home/<username>/fitgate_logs/cron_probe.log` after 1 minute.
     - **What a good log looks like**:
       ```text
       System check identified no issues (0 silenced).
       ```
     - _If the log contains an `ImproperlyConfigured` error, the cron environment cannot read `~/fitgate_env/.env`._
     - **Delete the probe cron job** after verifying.
2. **Configure Database Password File (`~/.pgpass`)**:
   - In Web Terminal, create the PostgreSQL password file so `pg_dump` can authenticate automatically in cron:
     ```bash
     echo "localhost:5432:<username>_fitgate_prod:<username>_fitgate_user:<password>" > ~/.pgpass
     chmod 600 ~/.pgpass
     ```
3. **Configure Nightly Database Backup Cron Job**:
   - In cPanel **Cron Jobs**, add a job running nightly at 02:00 AM (`0 2 * * *`):
     ```bash
     pg_dump -h localhost -U <username>_fitgate_user -w -F c -b -f /home/<username>/fitgate_backups/fitgate_backup_$(date +\%Y\%m\%d_\%H\%M\%S).dump <username>_fitgate_prod >> /home/<username>/fitgate_backups/backup.log 2>&1 && (ls -t /home/<username>/fitgate_backups/*.dump | tail -n +15 | xargs -r rm -f)
     ```
   - This command runs `pg_dump` without password prompts, appends stdout/stderr to `backup.log`, and automatically deletes backups older than the last 14 files to prevent disk bloat.
   - **If `pg_dump` is not found on the host**: Use cPanel's built-in **Backup Wizard** (under **Files**) to download manual PostgreSQL backups on a regular schedule.

---

## Step 8: End-to-End Smoke Test Checklist

Work through this checklist step-by-step to confirm complete staging functionality:

1. **Landing Page over HTTPS**:
   - Open `https://fitgate.tebebtech.com` in your browser.
   - Verify: The FitGate platform landing page loads with pricing tiers, "Request a Demo", and dark theme styling.
2. **Super Admin Sign In**:
   - In the page footer, click "Platform sign in" (or visit `https://fitgate.tebebtech.com/login`).
   - Log in using your Super Admin credentials.
   - Verify: You are prompted to change your temporary password. Set a new password and confirm entry to the Super Admin dashboard.
3. **Create a Real Gym Tenant**:
   - In the Super Admin dashboard, navigate to the Gym Management section and click **Create Gym**.
   - Subdomain: enter `bole` (full domain will be `bole.fitgate.tebebtech.com`).
   - Owner Name & Email: enter your own secondary email address.
   - Payment method: `Bank Transfer`. Click **Create Gym**.
   - Verify: Gym creation succeeds. (Note: For security, the set-password invite link is NOT displayed on screen; it is sent directly via email). Check the secondary email's inbox for the activation email.
4. **Inspect "Still Securing" State**:
   - Open `http://bole.fitgate.tebebtech.com` in a browser tab.
   - Verify: The gym entry page displays with a security badge: "still being secured". Login and registration are disabled until TLS is confirmed.
5. **AutoSSL Issuance**:
   - cPanel AutoSSL runs automatically in the background (typically taking ~15–20 minutes to complete certificate issuance and DNS DCV verification).
   - In cPanel, navigate to **Security** &rarr; **SSL/TLS Status**. Locating `bole.fitgate.tebebtech.com` and clicking **Run AutoSSL** is optional and only speeds up the check.
   - Wait until the green certificate lock icon appears for `bole.fitgate.tebebtech.com`.
6. **Confirm TLS Certificate in Super Admin**:
   - Return to the Super Admin dashboard at `https://fitgate.tebebtech.com`.
   - Find `bole` in the gym list and click **Confirm Certificate**.
   - Verify: Gym status transitions to verified TLS active.
7. **Owner Account Activation**:
   - In your secondary email inbox, open the welcome email from `FitGate <noreply@fitgate.tebebtech.com>`.
   - Click the set-password link, enter a password, and log in at `https://bole.fitgate.tebebtech.com/login`.
   - Verify: The Gym Owner dashboard loads with the First-Run Checklist.
8. **Invite Receptionist**:
   - In the Gym Owner dashboard, go to Staff Management &rarr; Invite Staff.
   - Enter name and email, select role `Reception`, and send invitation.
9. **Register Member with Photo**:
   - Go to Members &rarr; Register Member.
   - Fill in details, upload a profile photo (JPEG/PNG), accept waiver, and submit.
   - Verify: Member profile photo displays and loads through `/api/media/member-photos/`.
10. **Provision Member Subscription & Test Mobile QR Pass**:
    - Member check-in requires an active subscription. Because self-service online plan checkout is scheduled for Sprint 10, provision an active 30-day subscription for the member in cPanel Web Terminal:
      ```bash
      python manage.py shell -c "from datetime import date, timedelta; from apps.memberships.models import Member, MemberSubscription; m = Member.objects.last(); MemberSubscription.objects.create(gym=m.gym, member=m, start_date=date.today(), end_date=date.today()+timedelta(days=30), status='active'); print('Created subscription for', m.full_name)"
      ```
    - Check the member's email inbox for the activation email, click the set-password link, set a password, and log in as the member on a mobile phone at `https://bole.fitgate.tebebtech.com/login`.
    - Verify: The member dashboard displays their dynamic QR Pass with a 90-second rotation countdown.
11. **Test Entrance Scanner Tablet Check-in**:
    - On a tablet (or secondary device), log in as the gym **Owner**, **Manager**, or **Receptionist**.
    - Navigate to the verified scanner route: `https://bole.fitgate.tebebtech.com/attendance/scanner` (or `/scanner`).
    - Point the tablet camera at the member's QR pass displayed on their phone.
    - Verify: Access Granted green card appears with member photo, name, and check-in timestamp.
12. **Verify Audit Log**:
    - In the gym dashboard, navigate to Audit Logs.
    - Verify: Check-in, staff invitations, and gym creation events appear in chronological order.
13. **Test Unknown Gym Subdomain**:
    - Note: Browsing to a random subdomain with no DNS record (e.g. `https://nonexistent.fitgate.tebebtech.com`) simply displays the browser's own DNS "Site Not Found" error page.
    - To verify FitGate's branded unknown gym handling:
      1. In cPanel, navigate to **Domains** &rarr; **Domains** (or **Subdomains**).
      2. Create a temporary subdomain `ghost.fitgate.tebebtech.com` pointing to document root `public_html/fitgate`.
      3. Open `https://ghost.fitgate.tebebtech.com` in your browser.
      4. Verify: FitGate displays its branded "Gym Not Found" / 404 message.
      5. Return to cPanel **Domains** and delete the `ghost` subdomain.

---

## Step 9: Troubleshooting & Rollback

### Application Logs & Diagnostics

- **Runtime application errors**:
  - Once Django boots successfully, runtime errors are written to `/home/<username>/fitgate_logs/fitgate.log`.
  - In Web Terminal:
    ```bash
    tail -n 100 /home/<username>/fitgate_logs/fitgate.log
    ```
- **Boot-time crashes (Missing environment variables or settings errors)**:
  - If Django settings fail to load at startup (e.g. `ImproperlyConfigured`, syntax error, or missing secret in `.env`), Python crashes before the Django logging engine initializes. In this case, **nothing reaches `fitgate.log`**.
  - Check the boot failure in:
    1. cPanel **Metrics** &rarr; **Errors** (Apache error log).
    2. cPanel **Setup Python App** &rarr; click the log icon or inspect stderr logs.
    3. Run `python manage.py check` directly in cPanel Web Terminal, which immediately prints the exact missing environment variable or settings traceback.

### How to Restart the App

- In cPanel **Setup Python App**, find `fitgate.tebebtech.com` and click the **Restart** button (circular arrow icon).
- Alternatively, touch the restart file from Terminal:
  ```bash
  mkdir -p ~/fitgate/tmp && touch ~/fitgate/tmp/restart.txt
  ```

### Common Errors and Fixes

- **500 Internal Server Error immediately on load**:
  - Missing environment variable in `~/fitgate_env/.env`.
  - Check cPanel **Metrics** &rarr; **Errors** or run `python manage.py check` in Terminal.
- **cPanel UAPI network timeout or TLS verification failure during gym creation**:
  - If `python manage.py check_cpanel_uapi` fails with connection refused, timeout, or hostname verification failure, `CPANEL_HOST` is either set to `localhost` or port 2083 is blocked.
  - Solution: In `~/fitgate_env/.env`, set `CPANEL_HOST` to your cPanel server's real public hostname (matching its SSL certificate, e.g. `srv1.yegara.com` or `tebebtech.com`) rather than `localhost`.
- **Static files or CSS not loading (404)**:
  - Run `python manage.py collectstatic --noinput` in Web Terminal and restart the app.

### How to Roll Back to the Previous Release

1. **Check for Database Migrations**:
   - Roll back code only if no new database migrations were applied since the previous release.
   - If migrations were applied, you must restore your pre-migration database backup first:
     ```bash
     pg_restore -h localhost -U <username>_fitgate_user -d <username>_fitgate_prod --clean ~/fitgate_backups/fitgate_pre_migrate_*.dump
     ```
2. **Extract into a Clean Folder**:
   - Extracting an old zip over an existing release leaves behind newly created files from the newer release.
   - In cPanel **File Manager**, rename the current `fitgate` directory to `fitgate_failed_$(date +%s)`.
   - Create a clean `fitgate` directory and extract your previous release zip (`fitgate_release_previous.zip`) into `/home/<username>/fitgate`.
3. **Restart the Application**:
   - In cPanel **Setup Python App**, click the **Restart** button.
