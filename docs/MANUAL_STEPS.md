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
   - **What to do:** Create an API token in cPanel (Security &rarr; Manage API Tokens) with name `FitGate-UAPI` and an optional expiry. (cPanel API tokens take only a name and expiry and carry account access; no subdomain permission selection is offered). Use a dedicated token for the host's env file, and delete any laptop test token after staging.
   - **What to paste where:** In `/home/<user>/fitgate_env/.env`, set `CPANEL_API_TOKEN=<token>`, `CPANEL_HOST=<real_cpanel_hostname>` (e.g., matching the server SSL certificate, no `https://` and no port), `CPANEL_USERNAME=<cpanel_user>`, `CPANEL_USE_MOCK=False`, `CPANEL_ROOT_DOMAIN=tebebtech.com`, `CPANEL_SUBDOMAIN_DOCROOT=public_html/fitgate`.
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
   - **What to do:** Generate a brand-new Ed25519 key pair on your laptop using `docker compose exec backend python manage.py generate_qr_keys`. The host's QR keys must be NEW, never the laptop's dev keys, must never be saved in a file or shared, and `generate_qr_keys` prints single-line escaped keys.
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

7. **Sprint 11 — Chapa Test Keys & Online Payment Verification**
   - **What to do:** Obtain Chapa test merchant credentials (public key, secret key, webhook secret) from `chapa.et` dashboard and enter them into gym settings (`GymPaymentConfig`) on the staging host once deployed and secured with HTTPS.
   - **What to paste where:** In gym Owner settings under Payment Settings (stored encrypted in the database using `TENANT_CREDENTIALS_KEY`). In `/home/<user>/fitgate_env/.env`, set `TENANT_CREDENTIALS_KEY=<key>` generated via `docker compose exec backend python manage.py generate_tenant_credentials_key`. Outside test environments, the backend refuses to encrypt or decrypt credentials if this variable is missing or empty.
   - **Fallback in use:** Signed mocked webhooks and simulated checkout in automated tests and local dev.
   - **Live Test Checklist (to run later with real TEST keys on staging):**
     1. Confirm the real webhook arrives with the header `x-chapa-signature`.
     2. Confirm our HMAC check matches Chapa's real signature (Chapa's own documentation example hashes the re-serialized JSON body while our implementation hashes the raw request body, so check and verify this against live deliveries).
     3. Confirm the field names in the real webhook and verification responses match the mock (`tx_ref` reference field, `status`, `amount`, `currency`).
     4. Confirm the server-side verify call (`GET /transaction/verify/{tx_ref}`) and connection test (`GET /banks`) work with real keys.
     5. Confirm abandoned payments (after 30-minute timeout) and failed payments behave properly without activating subscriptions.
   - **Status:** Skipped for Increment 2 preflight per owner decision; feature marked "not verified against the real service".

8. **Sprint 10 — Manual Subscription Activation on Staging Before Sprint 12**
   - **What to do:** Because staff cannot create subscriptions without payments and cash payment arrives in Sprint 12, to manually assign an active subscription for check-in testing on staging before Sprint 12, run in cPanel Web Terminal:
     `/home/<user>/virtualenv/fitgate_backend/3.11/bin/python manage.py shell -c "from apps.memberships.models import Member, MembershipPlan; from apps.memberships.services import create_or_renew_subscription; m = Member.all_objects.first(); p = MembershipPlan.all_objects.filter(gym=m.gym, is_active=True).first(); create_or_renew_subscription(m, p)"`
   - **Status:** Testing convenience before Sprint 12.

9. **Sprint 11 — Abandoned Online Payments Sweep Cron Job**
   - **What to do:** Configure a cPanel Cron Job running every 5 minutes to sweep online payments left pending beyond 30 minutes, flag them as abandoned, and record notifications for staff and member follow-up.
   - **Cron Command:**
     ```bash
     */5 * * * * /home/<user>/virtualenv/fitgate_backend/3.11/bin/python /home/<user>/fitgate/backend/manage.py sweep_unfinished_payments >> /home/<user>/fitgate_logs/cron_sweep.log 2>&1
     ```
   - **Status:** To be verified at staging.

---

## Email & Domain Configuration (Brevo + cPanel)

- **Brevo Sender & Domain:**
  - Brevo domain (`fitgate.tebebtech.com`) and sender (`noreply@fitgate.tebebtech.com`) setup completed and verified in Brevo.
  - Click tracking must stay off for transactional email: the owner must verify this in Brevo so invitation and password reset links point directly to the app without redirect rewriting.
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
6. **Verify Click Tracking Stays Off:**
   - Click tracking must stay off for transactional email: the owner must verify this in Brevo (under Transactional Email settings) so invitation tokens and password reset links point directly to `fitgate.tebebtech.com` rather than Brevo tracking redirect URLs.
