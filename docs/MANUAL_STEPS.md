# Manual Steps

Whenever a manual action comes up later, append numbered steps here (sprint, what to do, what to paste where, which fallback is in use), continue with the fallback, and track verification status.

---

## Facts Learned from the Staging Spike (Yegara cPanel Host)

The feasibility spike on the real Yegara cPanel host passed all checks:

- **Python:** 3.11.17 installed at `/usr/local/bin/ea-python311`.
- **PostgreSQL:** Yegara runs PostgreSQL 13.23, which Django 5.2 does not support; we run with a version-check override and the full suite passes on 13. Before every release, run the suite on a PostgreSQL 13 container (document the exact command). Ask the host whether PostgreSQL 14+ is available; if yes, remove the override. Pin the Django patch version.
  - Test command:
    ```bash
    docker run -d --name pg13test --network fitgate_default -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=fitgate_test -e POSTGRES_USER=postgres postgres:13-alpine
    docker compose exec -e DATABASE_URL="postgres://postgres:postgres@pg13test:5432/fitgate_test" -e ALLOW_POSTGRES_13=1 backend pytest
    docker stop pg13test ; docker rm pg13test
    ```
- **Phusion Passenger:** ONE Passenger application serves both the apex (`fitgate.tebebtech.com`) and gym tenant subdomains (`*.fitgate.tebebtech.com`) from a single document root (`public_html/fitgate`). It receives and passes the correct `Host` header to Django.
- **HTTPS Termination:** Terminated by the host's front-end proxy. The application receives no `X-Forwarded-Proto` header. `passenger_wsgi.py` sets `os.environ['HTTPS'] = 'on'` and injects `environ['HTTPS'] = 'on'` into the WSGI environment.
- **SSH Access:** The cPanel user has no SSH access. The owner runs database migrations via cPanel Web Terminal as documented in `docs/DEPLOY_STAGING.md`. Boot-time migrations are removed from `passenger_wsgi.py`.
- **Static Assets:** `collectstatic` cannot run on the host. Releases must be built locally (frontend build + Django collectstatic) and uploaded as a self-contained zip. WhiteNoise serves both the React single-page app and static files directly from the Passenger WSGI process.
- **Subdomain Provisioning:** cPanel UAPI `SubDomain::addsubdomain` requires root domain `tebebtech.com` and subdomain `<gym>.fitgate` pointing to `public_html/fitgate`. Tested and verified working with API tokens.
- **AutoSSL:** Automatically provisions Let's Encrypt SSL/TLS certificates for new subdomains within 15–30 minutes. The application's certificate safeguard holds unconfirmed subdomains in a 503 "still securing" state until confirmed.
- **Cron Jobs:** Scheduled tasks can be executed every 5 minutes via cPanel Cron Jobs calling `/home/<user>/virtualenv/fitgate_backend/3.11/bin/python manage.py <command>` with stderr redirected to log files.
- **File Storage:** Local filesystem storage in `/home/<user>/fitgate_media/` is used for member uploads, served securely via Django protected media views (never exposed directly by Apache/Passenger).

---

## Active & Pending Manual Steps

1. **Sprint 4 — cPanel UAPI Token & Subdomain Provisioning**
   - **What to do:** Create an API token in cPanel (Security &rarr; Manage API Tokens) with permission for `SubDomain::addsubdomain`.
   - **What to paste where:** In `/home/<user>/fitgate_env/.env`, set `CPANEL_API_TOKEN=<token>`, `CPANEL_HOST=127.0.0.1` (or host URL), `CPANEL_USERNAME=<cpanel_user>`, `CPANEL_USE_MOCK=False`, `CPANEL_SUBDOMAIN_DOCROOT=public_html/fitgate`.
   - **Fallback in use:** Mocked UAPI client in local development and automated tests.
   - **Status:** To be verified at staging.

2. **Sprints 4, 6, 7 — Production SMTP Mailbox (Brevo)**
   - **What to do:** Configure Brevo SMTP credentials and verify sender domain `fitgate.tebebtech.com`.
   - **What to paste where:** In `/home/<user>/fitgate_env/.env`, set `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST=smtp-relay.brevo.com`, `EMAIL_PORT=587`, `EMAIL_HOST_USER=<brevo_login>`, `EMAIL_HOST_PASSWORD=<brevo_smtp_key>`, `EMAIL_USE_TLS=True`, `EMAIL_USE_SSL=False`, and `DEFAULT_FROM_EMAIL=noreply@fitgate.tebebtech.com`.
   - **Fallback in use:** Console email backend (`EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`) and console default in local dev.
   - **Status:** To be verified at staging.

3. **Sprint 4b, 7 — File Storage Layer**
   - **What to do:** Member photos and media assets are stored on the local host filesystem under `/home/<user>/fitgate_media/` and served through Django's protected media permission checks.
   - **What to paste where:** In `/home/<user>/fitgate_env/.env`, set `MEDIA_ROOT=/home/<user>/fitgate_media`.
   - **Fallback in use:** Local filesystem storage.
   - **Status:** Skipped: local storage in production.

4. **Sprint 8 — QR Check-in Asymmetric Signing Key Pair**
   - **What to do:** Generate Ed25519 key pair for production QR token signing and verification using `python manage.py generate_qr_dev_keys`.
   - **What to paste where:** In `/home/<user>/fitgate_env/.env`, set `QR_JWT_PRIVATE_KEY` and `QR_JWT_PUBLIC_KEY` as single-line strings with literal `\n` escapes.
   - **Fallback in use:** Dev key generator / in-memory Ed25519 key pair in test fixtures.
   - **Status:** To be verified at staging.

5. **Sprint 8b/8c — Camera Scanning on Physical Devices**
   - **What to do:** Test camera QR scanning on real physical phone and tablet hardware over HTTPS.
   - **Fallback in use:** Laptop webcam on localhost and manual code entry field.
   - **Status:** To be verified at staging.

6. **Sprint 4d — Apex Platform Address Wiring**
   - **What to do:** Verify `fitgate.tebebtech.com` serves the public landing page with valid AutoSSL certificate.
   - **Fallback in use:** `http://localhost:5173`.
   - **Status:** To be verified at staging.

---

## Email & Domain Configuration (Brevo + cPanel)

- **Brevo Sender & Domain:**
  - Brevo domain (`fitgate.tebebtech.com`) and sender (`noreply@fitgate.tebebtech.com`) setup completed and verified in Brevo.
  - Transactional email click tracking stays off in Brevo settings so invitation and password reset links point directly to the app without redirect rewriting.
  - The Brevo SMTP key lives only in the host's environment file (`/home/<user>/fitgate_env/.env`).
- **cPanel Mail Routing:**
  - `tebebtech.com`: Remote Mail Exchanger (routed to external provider).
  - `fitgate.tebebtech.com`: Local Mail Exchanger with an MX record pointing to the cPanel host.
  - Subdomain default address: Currently forwards unrouted mail to an owner address for staging verification.
  - To do after testing: Change the subdomain default address to discard-with-error to prevent forwarding abuse.
  - To do before launch: Tighten DMARC policy from `p=none` to `p=quarantine` or `p=reject`.

---

## Follow-up Items for the Project Owner (Staging Deployment)

1. **Environment File Security:**
   - Store all production secrets in `/home/<user>/fitgate_env/.env` on the host with permissions `600` (`chmod 600 /home/<user>/fitgate_env/.env`).
   - Never commit `.env` to git, code repositories, or issue trackers.
   - The Brevo SMTP master key must live only in this file.
2. **DNS Records for Email:**
   - Add Brevo SPF (`v=spf1 include:spf.brevo.com ~all`), DKIM, and DMARC TXT records for `fitgate.tebebtech.com`.
   - Add cPanel MX record for `fitgate.tebebtech.com` pointing to the cPanel host.
3. **Database Backup Verification:**
   - Configure and test `pg_dump` via a scheduled cPanel Cron job once the staging app is live.
4. **Default Mail Address Hardening:**
   - After confirming test email delivery via `send_test_email`, change the `fitgate.tebebtech.com` default address in cPanel from "forward" to "discard with error" to prevent mail forwarding abuse and spam backscatter.
5. **DMARC Policy Enforcement:**
   - Before launch with real customer traffic, tighten DMARC from `p=none` to `p=quarantine` or `p=reject` after verifying SPF and DKIM alignment in the Brevo dashboard.
6. **Disable Click Tracking:**
   - In the Brevo dashboard under Transactional Email settings, disable link click tracking so invitation tokens and password reset links point directly to `fitgate.tebebtech.com` rather than Brevo tracking redirect URLs.
