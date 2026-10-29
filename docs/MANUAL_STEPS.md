# Manual Steps

Note for local setup: after pulling new code run docker compose exec frontend npm install (and rebuild if needed).

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

7. **Sprint 11 — Local & Staging Chapa Test with ngrok (Payment Gateway Verification)**
   - **Overview:** Test real Chapa transactions locally on your laptop using ngrok to route incoming Chapa payment webhooks to your local Django backend.
   - **Chapa Official Documentation Pages:**
     - Base URL: `https://api.chapa.co/v1/`
     - Accept Payments (Initialize): `https://developer.chapa.co/docs/accept-payments/`
     - Verify Payments: `https://developer.chapa.co/docs/verify-payments/`
     - Webhooks: `https://developer.chapa.co/docs/webhooks/`
     - Banks: `https://developer.chapa.co/docs/banks/`
   - **Plain Steps for Owner (Local Chapa Test via ngrok):**
     1. Install ngrok on Windows, sign up for a free account at `https://dashboard.ngrok.com/signup`, and register the account's authtoken once on the laptop via `ngrok config add-authtoken <token>` (never paste the authtoken in chat, in a file, or in git).
     2. Start the local app with the Chapa mock off (`CHAPA_USE_MOCK=False` in `.env`).
     3. Run ngrok pointing at the port the local BACKEND listens on (port 8000, not the frontend port 5173): `ngrok http 8000`.
     4. Copy the https address ngrok prints (e.g., `https://abcdef123456.ngrok-free.app`). Put its host name only (no `https://`, no port) in the local `.env` as `DEV_TUNNEL_HOST=abcdef123456.ngrok-free.app` and restart the backend container (`docker compose restart backend`).
     5. In the Chapa test dashboard (`https://dashboard.chapa.co`), paste `<ngrok address>/api/webhooks/chapa/` (e.g. `https://abcdef123456.ngrok-free.app/api/webhooks/chapa/`) as the webhook URL and enter a webhook secret of the owner's choice.
     6. As Owner, sign in to the local gym, enter the three test keys (`CHAPUBK_TEST-xxxx`, `CHASECK_TEST-xxxx`, and the same webhook secret) in the local gym's payment settings, then press **Test connection**.
     7. As a member, pay a plan with a Chapa test card or test phone number. What the owner should see: subscription active, a digital receipt, and an in-app notification.
     8. **Static vs. Dynamic Address:** If the owner's ngrok account can reserve a free fixed address (under Cloud Edge &rarr; Domains in the ngrok dashboard, e.g. `ngrok http --domain=my-fixed-name.ngrok-free.app 8000`), use it so `DEV_TUNNEL_HOST` and the Chapa dashboard address stay the same permanently; otherwise both `DEV_TUNNEL_HOST` in `.env` and the Chapa dashboard webhook URL must be updated every time ngrok restarts.
   - **Troubleshooting List:**
     - **401 on the webhook:** Webhook secret in gym payment settings does not match the secret in the Chapa dashboard, or the HMAC signature check failed.
     - **ngrok address changed:** ngrok restarted without a reserved static domain; update `DEV_TUNNEL_HOST` in `.env`, restart the backend, and update the Chapa dashboard webhook URL.
     - **Keys mixed between test and live:** Public or secret keys have the wrong prefix (`CHAPUBK_LIVE-` / `CHASECK_LIVE-` instead of `_TEST-`), or test keys were generated on a different account.
     - **Webhook arrives but nothing activates:** Check `docker compose logs backend --tail=100`. Verify `tx_ref` matched a pending payment record, server-side verify returned `success`, and member/gym status is active.
     - **ngrok warning page or blocked host:** Free ngrok accounts show a browser interstitial for GET requests in browsers; server-to-server POST webhooks bypass this automatically. If testing via curl, pass `-H "ngrok-skip-browser-warning: true"`. If Django returns 400 Bad Request, ensure the host is in `ALLOWED_HOSTS` via `DEV_TUNNEL_HOST`.
     - **Wrong port:** ngrok pointed to port 5173 (frontend) instead of 8000 (backend). Ensure you run `ngrok http 8000`.
   - **What to Compare with the Mock Checklist:**
     - Webhook HMAC SHA-256 signature verification over raw request body matching `x-chapa-signature`.
     - Webhook payload structure and field names (`tx_ref`, `status`, `amount`, `currency`).
     - Server-side verification response structure (`GET https://api.chapa.co/v1/transaction/verify/{tx_ref}`).
     - Bank list retrieval structure (`GET https://api.chapa.co/v1/banks`).
     - Idempotent delivery behavior (no duplicate subscriptions or payments when webhook delivers multiple times).
     - Failed or abandoned checkout behavior (status marked `failed`, no subscription extension).
   - **Status:** Documented with plain steps; ready for owner local testing.

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

10. **Sprint 12b — Unreconciled Bank Transfers 7-Day Flagging Cron Job**
    - **What to do:** Configure a daily cPanel Cron Job running at 02:00 UTC to flag unreconciled bank transfers older than 7 days, notify the Owner with a single summary message per run, and record audit log entries naming the staff member who confirmed the payment.
    - **Cron Command:**
      ```bash
      0 2 * * * /home/<user>/virtualenv/fitgate_backend/3.11/bin/python /home/<user>/fitgate/backend/manage.py flag_unreconciled_bank_transfers >> /home/<user>/fitgate_logs/cron_bank_transfers.log 2>&1
      ```
    - **Status:** To be verified at staging.

11. **Sprint 13 — Automatic Unfreeze Cron Job**
    - **What to do:** Configure a cPanel Cron Job running every 5 minutes to process ended membership freezes, reactivate subscriptions, and activate today's freezes via `process_unfreezes`.
    - **Cron Command:**
      ```bash
      */5 * * * * /home/<user>/virtualenv/fitgate_backend/3.11/bin/python /home/<user>/fitgate/backend/manage.py process_unfreezes >> /home/<user>/fitgate_logs/cron_unfreeze.log 2>&1
      ```
    - **Status:** To be verified at staging.

12. **Sprint 9b — Brevo Webhook Configuration & Email Safety Settings**
    - **What to do:** In the Brevo dashboard (or via Brevo API `POST /webhooks`), create a transactional webhook for bounce, suppression, and complaint events.
      - **Webhook URL:** `https://fitgate.tebebtech.com/api/webhooks/brevo/` (apex only).
      - **Event types:** `hardBounce`, `blocked`, `spam`, `invalid` (transactional events).
      - **Headers / Authentication:** Custom header `X-Webhook-Secret: <BREVO_WEBHOOK_SECRET>` (or query parameter `?secret=<BREVO_WEBHOOK_SECRET>`).
      - **Click tracking stays off:** Under **Transactional &rarr; Settings &rarr; Configuration**, verify that click tracking is disabled so activation tokens and reset links point directly to FitGate without redirect rewrites.
    - **Brevo Official Documentation Pages Consulted:**
      - Overview & Webhook Configuration: `https://developers.brevo.com/docs/webhooks`
      - Webhooks API Reference: `https://developers.brevo.com/reference/createwebhook`
      - Transactional Webhook Events & Payload Formats: `https://developers.brevo.com/docs/transactional-webhooks`
      - Webhook Authentication: `https://developers.brevo.com/docs/webhook-authentication`
    - **Silent Security Response:** Requests with wrong or missing webhook secret return the exact same response as an unknown event (`{"status": "ignored"}` with HTTP 200 OK) to prevent secret probing.
    - **What to paste where:** In `/home/<user>/fitgate_env/.env`:
      - `EMAIL_STRICT_MODE=True` (required in production; no default in production).
      - `BREVO_WEBHOOK_SECRET=<generated_secret>` (required in production; constant-time validated).
      - Optional: `EMAIL_ALLOWED_RECIPIENTS=` (comma-separated list of allowed recipient addresses/domains on staging).
      - Optional: `EMAIL_HOURLY_CAP_PER_GYM=100` and `EMAIL_HOURLY_CAP_PLATFORM=500`.
    - **Throw-away domain list updates:** The bundled disposable domain list lives in `backend/apps/accounts/disposable_domains.py`. To add new domains, append them to `DISPOSABLE_EMAIL_DOMAINS` in that file and run the test suite.
    - **Unverified Accounts Cleanup Cron Job:**
      - Daily cPanel Cron Job running at 03:00 UTC to mark unverified public registrations older than 7 days as expired:
      ```bash
      0 3 * * * /home/<user>/virtualenv/fitgate_backend/3.11/bin/python /home/<user>/fitgate/backend/manage.py cleanup_unverified_members >> /home/<user>/fitgate_logs/cron_cleanup_unverified.log 2>&1
      ```
    - **Status:** To be verified at staging.

13. **Step 13 — Sprint 14: Scheduled Jobs & Nightly Membership Sweep Cron Job**
    - **Nightly Membership Sweep Cron Job:**
      - Runs daily at 01:00 UTC: expires past member subscriptions, derives member status via `update_member_status()`, checks gym suspension/grace period, dispatches member renewal reminder notices and platform renewal notices strictly through `send_fitgate_email`, reactivates completed freezes via `process_unfreezes`, and runs payments housekeeping:
      ```bash
      0 1 * * * /home/<user>/virtualenv/fitgate_backend/3.11/bin/python /home/<user>/fitgate/backend/manage.py daily_membership_sweep >> /home/<user>/fitgate_logs/cron_daily_sweep.log 2>&1
      ```
    - **Status:** To be verified at staging.

---

## Scheduled Cron Jobs Summary (Single Reference Table)

The table below lists every recurring cron job required by the FitGate production deployment. Each command is executed via `/home/<user>/virtualenv/fitgate_backend/3.11/bin/python /home/<user>/fitgate/backend/manage.py <command> >> /home/<user>/fitgate_logs/<log_file>.log 2>&1`.

| Command                            | Schedule                         | Purpose                                                                                                  | Overlap & Concurrency Notes                                                                             |
| :--------------------------------- | :------------------------------- | :------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------ |
| `sweep_unfinished_payments`        | `*/5 * * * *` (Every 5 minutes)  | Marks pending online checkouts older than 30 mins as abandoned                                           | Safe. Fast execution. Row-level locking on payment records prevents duplicate status transitions.       |
| `process_unfreezes`                | `*/5 * * * *` (Every 5 minutes)  | Reactivates subscriptions for ended freezes and activates pending freezes for today                      | Safe. Idempotent date checks; handles today's unfreezes once.                                           |
| `daily_membership_sweep`           | `0 1 * * *` (Daily at 01:00 UTC) | Expires ended subscriptions, sends renewal reminder emails (7d, 3d), logs platform grace-period warnings | Daily run. Strictly idempotent: never double-expires or sends duplicate renewal emails on the same day. |
| `flag_unreconciled_bank_transfers` | `0 2 * * *` (Daily at 02:00 UTC) | Flags manual bank transfers pending reconciliation > 7 days and alerts gym owner                         | Daily run. Idempotent single daily summary notification.                                                |
| `cleanup_unverified_members`       | `0 3 * * *` (Daily at 03:00 UTC) | Marks unverified self-registered accounts older than 7 days as `EXPIRED` (`is_active=False`)             | Daily run. Idempotent bulk query; leaves user records inactive and member status `expired`.             |

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
