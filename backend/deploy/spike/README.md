# FitGate Staging Spike: Real Yegara cPanel Host Feasibility Test

> [!IMPORTANT]
> **THROWAWAY TEST KIT**: This entire directory (`deploy/spike/`) is a temporary feasibility spike. It validates hosting assumptions on the real Yegara shared cPanel hosting environment before the full FitGate application is deployed. Once staging succeeds, this directory will be removed.

---

## 1. Overview & Goals

FitGate requires:

1. Shared cPanel hosting with no root or SSH access.
2. A single Python App Manager (Phusion Passenger WSGI) application serving both the main platform address (`fitgate.tebebtech.com`) and dynamically provisioned gym tenant subdomains (`*.fitgate.tebebtech.com`).
3. Automated subdomain provisioning via cPanel UAPI tokens at gym creation time.
4. AutoSSL certificates on all active subdomains.
5. Scheduled background tasks (nightly expiry sweep, reminders, audit retention) driven by cPanel Cron Jobs.
6. Database operations on cPanel-managed PostgreSQL via `psycopg`.

This spike kit lets you verify every one of these assumptions on the live host in under an hour.

---

## 2. Click-by-Click Guide for Non-Developers (cPanel Screens)

Follow these numbered steps in your cPanel dashboard:

### Step 1: Create the Subdomain for the Platform

1. Log in to your cPanel dashboard.
2. Under the **Domains** section, click **Domains** (or **Subdomains**).
3. Click **Create A New Domain**.
4. Enter the domain name: `fitgate.tebebtech.com`.
5. Uncheck _"Share document root"_ if prompted. Set the document root folder to `public_html/fitgate`.
6. Click **Submit**.

### Step 2: Create the Python Application

1. In cPanel, navigate to the **Software** section and click **Setup Python App**.
2. Click the blue **Create Application** button.
3. Configure the fields:
   - **Python version**: Select **3.11** (look at the dropdown options; note down every version offered in the results table below).
   - **Application root**: `spike_app` (this creates a folder in your home directory `/home/<username>/spike_app`).
   - **Application URL**: Select `fitgate.tebebtech.com`.
   - **Application startup file**: `passenger_wsgi.py`.
   - **Application Entry point**: `application`.
4. Click **Create** (top right).
5. At the top of the screen, cPanel will display a command to enter the virtual environment, for example:
   `source /home/<username>/virtualenv/spike_app/3.11/bin/activate && cd /home/<username>/spike_app`
   Keep note of this path—it shows the exact path to your Python interpreter.

### Step 3: Upload the Spike Verification App

1. Go back to the cPanel home screen and open **File Manager** (under **Files**).
2. Navigate to your application root directory: `/home/<username>/spike_app`.
3. Locate the default `passenger_wsgi.py` that cPanel generated and delete or rename it.
4. Click **Upload** in the File Manager top bar.
5. Upload the file [`deploy/spike/hello_app/passenger_wsgi.py`](file:///d:/personal%20projects/fitgate/deploy/spike/hello_app/passenger_wsgi.py).
6. Return to **Setup Python App**, find `fitgate.tebebtech.com`, and click the **Restart** button (circular arrow icon).

### Step 4: Open the Platform Address & Inspect Output

1. Open a browser and visit: `http://fitgate.tebebtech.com` (or `https://fitgate.tebebtech.com`).
2. You will see a plain text diagnosis page detailing:
   - **Host Header (`HTTP_HOST`)**: Verify it shows `fitgate.tebebtech.com`.
   - **Proxy Headers**: Inspect `X-Forwarded-Host` and `X-Forwarded-Proto`.
   - **Python Version & Executable**: Verify the version (e.g. 3.11.x).
   - **Filesystem Write Test**: Confirms whether the app can create and delete files in its directory.
   - **Outbound HTTPS (Cloudinary)**: Verifies port 443 outbound connections to `https://api.cloudinary.com`.
3. **Test SMTP Outbound Connectivity**:
   - In the browser address bar, append query parameters to test your SMTP provider:
     - For Brevo (port 587):
       `https://fitgate.tebebtech.com/?smtp_host=smtp-relay.brevo.com&smtp_port=587`
     - For Resend (port 465 or 587):
       `https://fitgate.tebebtech.com/?smtp_host=smtp.resend.com&smtp_port=465`
   - Check whether the response says `SUCCESS: Connected ... in X ms` or `FAILED: Connection timed out`.

### Step 5: Test Subdomain Provisioning via UAPI Probe

Run the probe from your local machine inside the backend Docker container (this uses the credentials in your gitignored local `.env` file):

1. Ensure your local `.env` file has:
   ```env
   CPANEL_HOST=your-cpanel-server.com
   CPANEL_USERNAME=your_cpanel_username
   CPANEL_API_TOKEN=your_cpanel_api_token
   ```
2. Run the probe to list current subdomains:
   ```bash
   docker compose exec backend python deploy/spike/uapi_probe.py list
   ```
3. Add a test second-level subdomain (`spike1.fitgate` under root domain `tebebtech.com`) pointing its document root to the SAME directory as the main app (`public_html/fitgate`):
   ```bash
   docker compose exec backend python deploy/spike/uapi_probe.py add --domain spike1.fitgate --rootdomain tebebtech.com --dir public_html/fitgate
   ```
4. Verify DNS resolution:
   - In your browser, open: `http://spike1.fitgate.tebebtech.com`
   - Check the plain text output:
     - Does the page load the same WSGI app?
     - **Host Header (`HTTP_HOST`)**: Does it show `spike1.fitgate.tebebtech.com`?
   - _(If the subdomain fails to resolve in DNS, check Step 10 below regarding external DNS vs cPanel DNS)._
5. Delete the test subdomain when done:
   ```bash
   docker compose exec backend python deploy/spike/uapi_probe.py delete --domain spike1.fitgate.tebebtech.com
   ```

### Step 6: Test AutoSSL & Certificate Timing

1. In cPanel, navigate to **Security** &rarr; **SSL/TLS Status**.
2. Locate `fitgate.tebebtech.com` and the newly created `spike1.fitgate.tebebtech.com`.
3. Click the blue **Run AutoSSL** button.
4. Note:
   - Does AutoSSL issue a certificate for `fitgate.tebebtech.com`?
   - Does it issue a certificate for multi-level subdomain `spike1.fitgate.tebebtech.com`?
   - How many minutes does the issuance take?

### Step 7: Test Cron Jobs & Execution Interval

1. In cPanel, navigate to the **Advanced** section and click **Cron Jobs**.
2. In the **Add New Cron Job** section:
   - Under **Common Settings**, select **Once Per Minute (`* * * * *`)**. If cPanel rejects this or shows a warning that the minimum allowed interval is 5 or 15 minutes, note the restriction.
   - Enter the command:
     ```bash
     echo $(date -u) >> /home/<username>/cron_test.log
     ```
   - Click **Add New Cron Job**.
3. In File Manager, watch `/home/<username>/cron_test.log` for 3–5 minutes. Check the timestamp delta between lines.
4. Next, test running Python via Cron:
   - Change the cron command to use the virtualenv Python path from Step 2:
     ```bash
     /home/<username>/virtualenv/spike_app/3.11/bin/python -c "import sys; print(sys.version)" >> /home/<username>/cron_py.log 2>&1
     ```
   - Verify that `/home/<username>/cron_py.log` is created and contains the Python 3.11 version string.
5. Delete both test cron jobs when finished.

### Step 8: Test Running Commands Without SSH

FitGate must be able to run `python manage.py migrate` and `python manage.py create_super_admin` on the host without SSH access. Test which of these three methods works:

- **Method A: cPanel Terminal**
  - Check the **Advanced** section of cPanel for a **Terminal** icon.
  - If present and allowed by Yegara, click it to see if a web-based shell opens.
- **Method B: Python App Manager "Run Command"**
  - In **Setup Python App**, check if there is an input field for "Run JS/Python script" or virtualenv commands.
- **Method C: One-Time Cron Job**
  - In **Cron Jobs**, schedule a one-time cron job:
    ```bash
    cd /home/<username>/spike_app && /home/<username>/virtualenv/spike_app/3.11/bin/python -c "print('One-time command executed successfully')" > /home/<username>/cmd_test.log 2>&1
    ```
  - Wait 1 minute, check `/home/<username>/cmd_test.log`, then delete the cron job.

### Step 9: Test PostgreSQL Database & Driver Connectivity

1. In cPanel, go to the **Databases** section and click **PostgreSQL Databases**.
2. Under **Create New Database**, enter `fitspikedb` (the full name will be `<username>_fitspikedb`). Click **Create Database**.
3. Under **Add New User**, enter `fitspikeuser` and a strong password. Click **Create User**.
4. Under **Add User To Database**, select the user and database, grant **ALL PRIVILEGES**, and click **Submit**.
5. Test connecting via the spike app:
   - Open in your browser:
     `https://fitgate.tebebtech.com/?db_host=localhost&db_name=<username>_fitspikedb&db_user=<username>_fitspikeuser&db_pass=<password>`
   - The diagnosis page will test connecting with `psycopg` (v3) or `psycopg2` and report the server version or the missing package error.

### Step 10: Check Resource Usage Limits

1. In cPanel, navigate to **Metrics** &rarr; **Resource Usage** (or **CPU and Concurrent Connection Usage**).
2. Click **Details**.
3. Review and record your account limits:
   - **PMEM (Physical Memory)**: e.g. 512 MB, 1024 MB, or 2048 MB.
   - **CPU**: e.g. 100% (1 core).
   - **EP (Entry Processes)**: e.g. 20 concurrent connections.
   - **NPROC (Number of Processes)**: e.g. 100.
   - **IO / IOPS**: disk throughput limits.

---

## 3. Official Documentation References

When building `uapi_probe.py` and the UAPI provisioning service, the following official cPanel documentation was consulted:

1. **`SubDomain::addsubdomain`**:
   - URL: https://docs.cpanel.net/b/uapi/subdomain-addsubdomain/
   - Key parameters:
     - `domain`: Subdomain prefix string.
     - `rootdomain`: Parent registered domain.
     - `dir`: Document root path relative to home (e.g. `public_html/fitgate`).
     - `disallowdot`: Integer. Set to `0` to prevent cPanel from stripping dot characters. This is required for multi-level labels like `spike1.fitgate`.
2. **`SubDomain::delsubdomain`**:
   - URL: https://docs.cpanel.net/b/uapi/subdomain-delsubdomain/
   - Key parameters:
     - `domain`: Fully qualified domain name (e.g. `spike1.fitgate.tebebtech.com`) or `domainkey` (`subdomain_rootdomain`).
     - `disallowdot`: Set to `0` to preserve dots.
3. **`SubDomain::listsubdomains`**:
   - URL: https://docs.cpanel.net/b/uapi/subdomain-listsubdomains/
   - Returns the list of configured subdomains, their document root directories (`dir`), and unique `domainkey` values.
4. **DNS Resolution for Multi-Level Subdomains**:
   - If nameservers for `tebebtech.com` are hosted outside cPanel (e.g. Cloudflare, Namecheap, Route53), cPanel's internal DNS zone updates will not resolve on the public internet.
   - Solution: Create a wildcard A record in the authoritative DNS provider pointing `*.fitgate.tebebtech.com` to the cPanel server IP address.

---

## 4. Results Table (Owner Fills In)

Fill in this table with the observations from the spike test:

| #       | Question to Answer                                                                                                                                                                                                                                                                                               | What We Saw on the Host | Worked? (Yes/No) |
| ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- | ---------------- |
| **(a)** | Which Python versions are offered, and is Python 3.11 available?                                                                                                                                                                                                                                                 |                         |                  |
| **(b)** | Can ONE application answer for both the main address (`fitgate.tebebtech.com`) and a second-level subdomain (`spike1.fitgate.tebebtech.com`), and does the app see the correct `Host` header for each? _(If an `.htaccess` or Passenger block must be copied into each subdomain document root, record details)_ |                         |                  |
| **(c)** | Does the UAPI token create and delete a subdomain, and does DNS resolve automatically with no manual step? _(If DNS is outside cPanel, record what external record was needed, e.g. `*.fitgate` A record)_                                                                                                       |                         |                  |
| **(d)** | How long until AutoSSL covers a new subdomain, and does it cover second-level subdomains (`*.fitgate.tebebtech.com`)?                                                                                                                                                                                            |                         |                  |
| **(e)** | Does cPanel Cron run, what is the minimum allowed interval, and can it run a management command with the app's virtualenv Python?                                                                                                                                                                                |                         |                  |
| **(f)** | How to run `migrate` and `create_super_admin` without SSH? _(Terminal, Python App Manager script runner, or one-time Cron Job)_                                                                                                                                                                                  |                         |                  |
| **(g)** | Are outbound HTTPS (port 443) and SMTP ports (port 587, 465, or 2525) open for external providers (Brevo, Resend, Cloudinary)?                                                                                                                                                                                   |                         |                  |
| **(h)** | What is the PostgreSQL connection format, and does `psycopg` connect cleanly from the Python app?                                                                                                                                                                                                                |                         |                  |
| **(i)** | What are the account resource limits (PMEM, CPU, Entry Processes), and are they sufficient for Django + DRF?                                                                                                                                                                                                     |                         |                  |

---

## 5. Product-Code Gaps for Real Deployment

Before deploying the real FitGate codebase to production, the following concrete items must be addressed in product code and configuration:

1. **`backend/apps/tenants/uapi.py`**:
   - `CPANEL_USE_MOCK` currently defaults to `True`. Production must enforce `CPANEL_USE_MOCK=False` or fail fast if credentials are unset.
   - The UAPI request URL must pass `disallowdot=0` and separate the apex registered domain (`tebebtech.com`) from the multi-level prefix (`<subdomain>.fitgate`), rather than passing `fitgate.tebebtech.com` as `rootdomain`.
2. **`backend/apps/accounts/permissions.py`**:
   - `DocsPermission` checks `settings.DEBUG`. In production (`DEBUG=False`), Swagger and Redoc API documentation endpoints are strictly restricted to authenticated Super Admins at the platform apex domain.
3. **`backend/requirements.txt`**:
   - Development and testing packages (`pytest`, `pytest-django`, `freezegun`, `ruff`, `black`) are unpinned and mixed into `requirements.txt`. Production should use a clean runtime requirements list (`requirements/prod.txt`) to avoid compiling dev dependencies on shared host memory.
4. **`backend/fitgate/settings/prod.py`**:
   - `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and `CORS_ALLOWED_ORIGIN_REGEXES` must dynamically match all gym tenant subdomains (e.g. `.{DOMAIN}` or regex `r"^https://[a-zA-Z0-9-]+\.{re.escape(DOMAIN)}$"`), otherwise tenant SPA requests will be rejected with HTTP 403 Forbidden.
5. **`backend/fitgate/settings/base.py` & `backend/fitgate/settings/prod.py` (Static Files)**:
   - Django does not serve static files when `DEBUG=False`. Production deployment needs `whitenoise.middleware.WhiteNoiseMiddleware` configured or an Apache alias in cPanel pointing `/static/` to `STATIC_ROOT`.
6. **`frontend/` & `backend/fitgate/urls.py` (Serving the Built React SPA)**:
   - In local dev, Vite runs on port 5173. In production under Phusion Passenger, how the compiled SPA (`frontend/dist/index.html` and bundled assets) is served across the apex domain and every gym subdomain must be handled (either via Django template catch-all or Apache rewrites).
7. **Production Environment Variables (Names Only)**:
   - Required in `.env` / cPanel environment:
     `SECRET_KEY`, `DEBUG`, `DOMAIN`, `DATABASE_URL` (or `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`), `CPANEL_HOST`, `CPANEL_USERNAME`, `CPANEL_API_TOKEN`, `CPANEL_USE_MOCK`, `TENANT_CREDENTIALS_KEY`, `QR_JWT_PRIVATE_KEY`, `QR_JWT_PUBLIC_KEY`, `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`, `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`, `AI_PROVIDER_API_KEY`.
8. **Cron Commands for Nightly Jobs**:
   - Format: `/home/<username>/virtualenv/<app>/3.11/bin/python /home/<username>/<app>/manage.py <command>`
   - Commands to configure:
     - Nightly subscription expiration sweep (e.g. `0 2 * * *`).
     - Audit log retention / archive sweep.
