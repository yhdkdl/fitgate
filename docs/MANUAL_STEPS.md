# Manual Steps

Whenever a manual action comes up later, append numbered steps here (sprint, what to do, what to paste where, which fallback is in use), continue with the fallback, and mark the feature 'not verified against the real service'.

1. **Sprint 4 — cPanel UAPI Token & Subdomain Provisioning**
   - **What to do:** Create an API token in cPanel (Security &rarr; Manage API Tokens) with permission for `SubDomain::addsubdomain`.
   - **What to paste where:** In `.env`, set `CPANEL_API_TOKEN=<token>`, `CPANEL_HOST=<cpanel-host>`, `CPANEL_USERNAME=<username>`.
   - **Fallback in use:** Mocked UAPI client in local development and automated tests.
   - **Status:** Not verified against the real service.

2. **Sprints 4, 6, 7 — Production SMTP Mailbox**
   - **What to do:** Configure SMTP credentials from cPanel Email Accounts or an external provider (Brevo / Resend).
   - **What to paste where:** In `.env`, set `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS=True`, and `DEFAULT_FROM_EMAIL`.
   - **Fallback in use:** Console email backend (`EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`) and console default `DEFAULT_FROM_EMAIL=webmaster@localhost`.
   - **Status:** Not verified against the real service.

3. **Sprint 4b, 7 — Cloudinary File Storage**
   - **What to do:** Create a free Cloudinary account and obtain API credentials.
   - **What to paste where:** In `.env`, set `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`.
   - **Fallback in use:** Local filesystem storage behind Django's unified storage interface; member photos served via backend permission checks.
   - **Status:** Not verified against the real service.

4. **Sprint 8 — QR Check-in Asymmetric Signing Key Pair**
   - **What to do:** Generate RSA / Ed25519 key pair for production QR token signing and verification.
   - **What to paste where:** In `.env` or cPanel environment variables, set `QR_JWT_PRIVATE_KEY` and `QR_JWT_PUBLIC_KEY` as single-line strings with literal `\n` escapes.
   - **Fallback in use:** Local management command `generate_qr_dev_keys` prints generated RSA PEM keys as single-line escaped strings to stdout for manual copying into `.env` or cPanel; in-memory key pair in test fixtures. Production fails fast if unset.
   - **Status:** Not verified against the real service.

5. **Sprint 8b/8c: camera scanning on a real tablet or phone needs HTTPS (a valid certificate). Fallback: laptop webcam on localhost and the manual code field. Status: not verified on a real device.**

6. **Sprint 4d: wire fitgate.tebebtech.com: create the cPanel subdomain for the platform, set DOMAIN=fitgate.tebebtech.com in the production environment, and wait for AutoSSL to issue the certificate. Fallback: http://localhost:5173. Status: not verified against the real service.**
