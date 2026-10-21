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
3. **Upload and extract**:
   - In cPanel **File Manager**, navigate to your application root folder (`/home/<username>/fitgate`).
   - Upload the new `fitgate_release_*.zip` from your laptop's `dist/` folder.
   - Right-click the uploaded zip file and select **Extract** to overwrite existing application files.
4. **Update dependencies (if requirements changed)**:
   - In cPanel **Setup Python App**, find `fitgate.tebebtech.com`.
   - In the **Configuration files** section, click **Run Pip Install** next to `requirements/prod.txt`.
5. **Run database migrations**:
   - Open cPanel **Terminal** and run:
     ```bash
     source ~/virtualenv/fitgate/3.11/bin/activate && cd ~/fitgate/backend && python manage.py migrate
     ```
6. **Collect static assets**:
   - In cPanel **Terminal**, run:
     ```bash
     source ~/virtualenv/fitgate/3.11/bin/activate && cd ~/fitgate/backend && python manage.py collectstatic --noinput
     ```
7. **Restart the application**:
   - In cPanel **Setup Python App**, click the **Restart** button (circular arrow icon) next to `fitgate.tebebtech.com`.

---

## Step 0: Clean Up the Feasibility Spike

Before starting the real deployment, remove all temporary items created during the earlier feasibility spike:

1. **Delete Spike Python App**:
   - In cPanel, navigate to **Software** &rarr; **Setup Python App**.
   - Locate the application associated with `fitgate.tebebtech.com` (or `spike_app`).
   - Click the red **Delete** (trash can) icon and confirm deletion.
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
2. **Upload and Extract via cPanel File Manager**:
   - In cPanel, open **File Manager** (under **Files**).
   - Navigate to your home directory (`/home/<username>/`).
   - Click **+ Folder** in the top toolbar and create a directory named `fitgate`.
   - Double-click into the new `fitgate` folder.
   - Click **Upload** in the top toolbar, select your `fitgate_release_*.zip` file, and wait for the upload progress bar to turn green (100%).
   - Return to File Manager, select the uploaded zip file, click **Extract** in the top bar, and extract directly into `/home/<username>/fitgate`.
   - Confirm the folder contains `backend`, `frontend/dist`, `deploy/passenger_wsgi.py`, `passenger_wsgi.py`, and `requirements/prod.txt`.

---

## Step 3: Create the Production Python Application

1. In cPanel, navigate to **Software** &rarr; **Setup Python App**.
2. Click the blue **Create Application** button.
3. Fill in the fields:
   - **Python version**: Select **3.11** (the host runs Python 3.11.17).
   - **Application root**: `fitgate`
   - **Application URL**: Select `fitgate.tebebtech.com`.
   - **Application startup file**: `deploy/passenger_wsgi.py` (or `passenger_wsgi.py`).
   - **Application Entry point**: `application`
4. Click **Create** in the top right corner.
5. In the **Configuration files** section:
   - Enter `requirements/prod.txt` into the input field and click **Add**.
   - Click **Run Pip Install** next to `requirements/prod.txt`.
   - Wait for pip installation to finish with a success notice.

---

## Step 4: Create the Protected Environment File

Production settings are read from ONE protected file outside `public_html` and outside the release folder so the website, background cron jobs, and terminal sessions always share the exact same configuration.

1. **Create directories and file in cPanel Terminal**:
   - Open cPanel **Terminal** (under **Advanced**) and run:
     ```bash
     mkdir -p ~/fitgate_env ~/fitgate_media ~/fitgate_logs
     touch ~/fitgate_env/.env
     chmod 600 ~/fitgate_env/.env
     ```
2. **Open the file in File Manager**:
   - In cPanel **File Manager**, navigate to `/home/<username>/fitgate_env/`.
   - Right-click `.env` and choose **Edit** (use UTF-8 encoding).
3. **Populate the configuration values**:
   - Paste the template below into `~/fitgate_env/.env`. Fill in every value:

```env
# Core & Domain
DOMAIN=fitgate.tebebtech.com
SECRET_KEY=<paste output of: python manage.py generate_secret_key>
DEBUG=False

# Database
DATABASE_URL=postgres://<username>_fitgate_user:<password>@localhost:5432/<username>_fitgate_prod

# cPanel UAPI Subdomain Provisioning
CPANEL_USE_MOCK=False
CPANEL_HOST=localhost
CPANEL_USERNAME=<your_cpanel_username>
CPANEL_API_TOKEN=<your_cpanel_api_token>
CPANEL_ROOT_DOMAIN=tebebtech.com
CPANEL_SUBDOMAIN_DOCROOT=public_html/fitgate

# Keys
TENANT_CREDENTIALS_KEY=<paste output of: python manage.py generate_tenant_credentials_key>
QR_JWT_PRIVATE_KEY=<paste private key output of: python manage.py generate_qr_dev_keys>
QR_JWT_PUBLIC_KEY=<paste public key output of: python manage.py generate_qr_dev_keys>

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
> **How to create the cPanel API Token**:
> In cPanel, navigate to **Security** &rarr; **Manage API Tokens**. Click **Create API Token**, enter token name `FitGate-UAPI`, select permission for the `SubDomain` module (`addsubdomain`, `delsubdomain`, `listsubdomains`), and save the generated token directly into `~/fitgate_env/.env`. Never paste this token into chat.

---

## Step 5: Email Configuration & Verification (Brevo)

The Brevo sending domain `fitgate.tebebtech.com` is already authenticated with DKIM, DMARC, and verified sender `noreply@fitgate.tebebtech.com`.

1. **Verify your `.env` contains the Brevo SMTP credentials**:
   - Ensure `EMAIL_HOST=smtp-relay.brevo.com`, `EMAIL_PORT=587`, `EMAIL_USE_TLS=True`, `EMAIL_USE_SSL=False`, and your Brevo login and SMTP key are typed into `~/fitgate_env/.env`.
2. **Send a test email from Web Terminal**:
   - Run the command, substituting your own email address:
     ```bash
     source ~/virtualenv/fitgate/3.11/bin/activate && cd ~/fitgate/backend && python manage.py send_test_email --to your-email@gmail.com
     ```
   - Look for: `[OK] Test email successfully delivered to your-email@gmail.com via smtp-relay.brevo.com:587.`
3. **Verify Deliverability in Gmail**:
   - Open the received email in Gmail.
   - Click the three dots (More) next to the reply button &rarr; **Show original**.
   - Verify that **SPF: PASS**, **DKIM: PASS**, and **DMARC: PASS** all display.
   - If the email does not appear in your inbox, check the **Spam** folder. If still not received, log in to Brevo &rarr; **Transactional** &rarr; **Real-time logs** and check if the address was placed on the blocked-contacts list.

---

## Step 6: Initialize Database, Static Files, and Admin in Web Terminal

Open cPanel **Terminal** (under **Advanced**) and run the following commands sequentially. Each command shows the expected output:

### 1. Apply Database Migrations

```bash
source ~/virtualenv/fitgate/3.11/bin/activate && cd ~/fitgate/backend && python manage.py migrate
```

- **Good result**: Lists migration operations ending with `Applying ... OK` with no errors.

### 2. Collect Static Files

```bash
python manage.py collectstatic --noinput
```

- **Good result**: `... static files copied to '/home/<username>/fitgate/backend/staticfiles'.`

### 3. Production Deployment Check

```bash
python manage.py check --deploy
```

- **Good result**: `System check identified 2 issues (0 silenced)` (only expected warnings `security.W004` and `security.W008` regarding the certificate safeguard; zero errors).

### 4. Bootstrap Super Admin Account

```bash
export SUPERADMIN_EMAIL=your-email@tebebtech.com
export SUPERADMIN_PASSWORD="YourStrongPassword123!"
python manage.py create_super_admin
```

- **Good result**: `Super Admin account 'your-email@tebebtech.com' successfully created.` (Must change password at first login).

### 5. Verify cPanel UAPI Host Connectivity

```bash
python manage.py check_cpanel_uapi
```

- **Good result**:
  ```text
  [OK] Host network path to cPanel UAPI (https://localhost:2083) is WORKING.
  Found 1 configured subdomain(s):
    - fitgate.tebebtech.com (docroot: public_html/fitgate)
  ```
  _(If the check fails due to outbound port 2083 firewall restrictions, see Section 9: Troubleshooting)._

---

## Step 7: Scheduled Maintenance & Database Backups (Cron Jobs)

1. **Verify Cron Environment Visibility**:
   - In cPanel, navigate to **Advanced** &rarr; **Cron Jobs**.
   - Under **Add New Cron Job**:
     - Common Settings: **Once Per Minute (`* * * * *`)**
     - Command:
       ```bash
       /home/<username>/virtualenv/fitgate/3.11/bin/python -c "import os, datetime; print(f'{datetime.datetime.utcnow().isoformat()} - Cron sees env file') if os.path.exists(os.path.expanduser('~/fitgate_env/.env')) else print('MISSING ENV')" >> /home/<username>/cron_probe.log 2>&1
       ```
     - Click **Add New Cron Job**.
     - In cPanel **File Manager**, watch `/home/<username>/cron_probe.log` for 2 minutes to confirm entries are logged.
     - Delete the test cron job after verification.
2. **Database Backups**:
   - In Web Terminal, test if `pg_dump` is available:
     ```bash
     which pg_dump
     ```
   - **If `pg_dump` exists**: In **Cron Jobs**, add a nightly backup job running at 02:00 AM (`0 2 * * *`):
     ```bash
     pg_dump -U <username>_fitgate_user -h localhost <username>_fitgate_prod > /home/<username>/db_backup_$(date +\%F).sql 2>> /home/<username>/fitgate_logs/backup.log
     ```
   - **If `pg_dump` is not found**: Use cPanel's built-in **Backup Wizard** (under **Files**) to download manual PostgreSQL backups on a regular schedule.

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
   - Navigate to the Gym Management section and click **Create Gym**.
   - Subdomain: enter `bole` (full domain will be `bole.fitgate.tebebtech.com`).
   - Owner Name & Email: enter your own secondary email address.
   - Payment method: `Bank Transfer`. Click **Create Gym**.
   - Verify: Gym is created, and the set-password invite link is displayed.
4. **Inspect "Still Securing" State**:
   - Open `http://bole.fitgate.tebebtech.com` in a browser tab.
   - Verify: The gym entry page displays with a security badge: "still being secured". Log in and registration are disabled until TLS is confirmed.
5. **AutoSSL Issuance**:
   - In cPanel, navigate to **Security** &rarr; **SSL/TLS Status**.
   - Locate `bole.fitgate.tebebtech.com` and click **Run AutoSSL**.
   - Wait ~15–20 minutes until the green lock icon appears for `bole.fitgate.tebebtech.com`.
6. **Confirm TLS Certificate in Super Admin**:
   - Return to the Super Admin dashboard at `https://fitgate.tebebtech.com`.
   - Find the gym in the gym list and click **Confirm Certificate**.
   - Verify: Gym status transitions to verified TLS active.
7. **Owner Account Activation**:
   - Check your inbox for the welcome email with sender: `FitGate <noreply@fitgate.tebebtech.com>`.
   - Click the set-password link, enter a password, and log in at `https://bole.fitgate.tebebtech.com/login`.
   - Verify: The Gym Owner dashboard loads with the First-Run Checklist.
8. **Invite Receptionist**:
   - Go to Staff Management &rarr; Invite Staff.
   - Enter name and email, role `Reception`. Send invitation.
9. **Register Member with Photo**:
   - Go to Members &rarr; Register Member.
   - Fill in details, upload a profile photo (JPEG/PNG), accept waiver, and submit.
   - Verify: Member profile photo displays and loads through `/api/media/member-photos/`.
10. **Test Entrance Scanner & QR Camera Check-in**:
    - Open the Entrance Scanner on a tablet or phone at `https://bole.fitgate.tebebtech.com/scanner`.
    - Hold the member's QR code in front of the camera.
    - Verify: Green access granted card appears with member photo, name, and check-in timestamp.
11. **Verify Audit Log**:
    - Navigate to Audit Logs in the dashboard.
    - Verify: Check-in, staff invitations, and gym creation events appear in chronological order.
12. **Test Unknown Gym Subdomain**:
    - In your browser, open `https://nonexistentgym.fitgate.tebebtech.com`.
    - Verify: The browser displays the unknown-gym message, not an internal error.

---

## Step 9: Troubleshooting & Rollback

### Application Logs

- Production logs are located at: `/home/<username>/fitgate_logs/fitgate.log`.
- To view recent log entries in Web Terminal:
  ```bash
  tail -n 100 /home/<username>/fitgate_logs/fitgate.log
  ```

### How to Restart the App

- In cPanel **Setup Python App**, find `fitgate.tebebtech.com` and click the **Restart** button (circular arrow icon).
- Alternatively, touch the restart file from Terminal:
  ```bash
  mkdir -p ~/fitgate/tmp && touch ~/fitgate/tmp/restart.txt
  ```

### Common Errors and Fixes

- **500 Internal Server Error immediately on load**:
  - Missing environment variable in `~/fitgate_env/.env`.
  - Check the end of `~/fitgate_logs/fitgate.log` to see which setting failed fast.
- **cPanel UAPI network timeout during gym creation**:
  - If `python manage.py check_cpanel_uapi` fails with connection refused or timeout to port 2083, the host firewall is blocking local loopback to port 2083.
  - Solution: In `~/fitgate_env/.env`, change `CPANEL_HOST` to your public cPanel server domain or IP rather than `localhost`.
- **Static files or CSS not loading (404)**:
  - Run `python manage.py collectstatic --noinput` in Web Terminal and restart the app.

### How to Roll Back to the Previous Release

1. Keep the previous release zip on your computer or in File Manager (e.g. `fitgate_release_previous.zip`).
2. In File Manager, extract the previous release zip into `/home/<username>/fitgate`, overwriting the files.
3. In Web Terminal, run `python manage.py migrate` (if reverse migrations are needed).
4. In **Setup Python App**, click **Restart**.
