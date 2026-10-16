# FitGate — Increment 1 End-to-End Test Script

This document is a comprehensive, numbered click-through guide for project owners, QA testers, and non-developers to verify all features built across **Increment 1** (Sprints 0 through 9a).

---

## Prerequisites & Environment Setup

1. **Verify Services are Running**:
   In your terminal at the project root, ensure Docker Compose containers are up:

   ```bash
   docker compose ps
   ```

   All 4 containers (`fitgate_backend`, `fitgate_postgres`, `fitgate_redis`, `fitgate_pgadmin`) should be running and healthy.

2. **Start Frontend Dev Server**:

   ```bash
   cd frontend
   npm run dev
   ```

   The frontend runs on port `5173`.
   - Apex platform domain: `http://localhost:5173`
   - Tenant gym subdomain: `http://<subdomain>.localhost:5173`

3. **Bootstrap Super Admin Account** (if not already done):

   ```bash
   docker compose exec backend python manage.py create_super_admin
   ```

   Default test credentials:
   - Email: `superadmin@fitgate.com`
   - Temporary Password: `AdminPassword123!` (or value from `.env`)

4. **Where to Find Email Links (Local Development)**:
   In local development, the console email backend is configured (`EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"`).
   All invitation, password setup, and email verification links are sent via transactional email only (on_commit) and are **never** returned in API responses or on-screen modals.
   To view or copy sent email links, run:
   ```bash
   docker compose logs backend | grep -A 5 "set-password"
   ```
   or view backend output in `docker compose logs backend`.

---

## Pending Manual Steps & External Service Status

As documented in `docs/MANUAL_STEPS.md`, external production credentials were systematically skipped during Increment 1 preflight by owner decision; verified fallbacks are active:

1. **Sprint 4 — cPanel UAPI Token & Subdomain Provisioning**:
   - _Status_: Pending real token.
   - _Fallback in use_: `MockCPanelUAPIClient` active for local development and test harness.
2. **Sprints 4, 6, 7 — Production SMTP Mailbox**:
   - _Status_: Pending real SMTP mailbox (Brevo / Resend / cPanel).
   - _Fallback in use_: Django console email backend (`EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`). All invite and verification links output directly to `docker compose logs backend`.
3. **Sprint 4b, 7 — Cloudinary File Storage**:
   - _Status_: Pending real Cloudinary credentials.
   - _Fallback in use_: Local protected filesystem storage behind Django's unified storage interface. Member photos served via backend permission checks.
4. **Sprint 8 — QR Check-in Asymmetric Signing Key Pair**:
   - _Status_: Key generation management command verified (`generate_qr_dev_keys`).
   - _Fallback in use_: Local management command prints generated RSA PEM keys as single-line escaped strings to stdout for manual copying into `.env` or cPanel; in-memory key pair in test fixtures. Production fails fast if unset.

---

## Test Scenario 1: Super Admin Authentication & Forced Password Change (Apex)

1. Open your browser and navigate to `http://localhost:5173/login`.
2. Notice the platform branding indicates **FitGate Platform Console**.
3. Attempt to sign in with an invalid password:
   - Email: `superadmin@fitgate.com`
   - Password: `WrongPassword999!`
4. **Expected Result**: Generic error message: _"Invalid email or password"_. No clue is leaked regarding which field was incorrect.
5. Sign in with valid bootstrap credentials:
   - Email: `superadmin@fitgate.com`
   - Password: `AdminPassword123!`
6. **Expected Result**: Because `must_change_password` is flagged on bootstrap, you are automatically redirected to `http://localhost:5173/forced-change-password`. Attempting to navigate elsewhere in the URL bar redirects right back.
7. Enter a strong new password (minimum 10 characters):
   - Current Password: `AdminPassword123!`
   - New Password: `SuperSecretPassword2026!`
   - Confirm Password: `SuperSecretPassword2026!`
8. Click **Update Password**.
9. **Expected Result**: Password updates successfully, sessions refresh, and you are redirected to the **Super Admin Platform Hub** (`http://localhost:5173/dashboard`).

---

## Test Scenario 2: Public Demo Requests (Apex) & Super Admin Lead Management

1. Open an incognito browser window and navigate to `http://localhost:5173/request-demo`.
2. Fill out prospective gym inquiry details:
   - Gym Name: `Bole Elite Fitness`
   - Contact Person: `Tadesse Worku`
   - Phone Number: `+251911223344`
   - City: `Addis Ababa`
   - Email: `tadesse@boleelite.com`
   - Notes: `Interested in 200 member capacity with QR scanners.`
3. Click **Submit Demo Request**.
4. **Expected Result**: Confirmation card appears thanking the applicant.
5. Return to the Super Admin window (`http://localhost:5173/dashboard`).
6. Click on the **Demo Requests & Leads** tab.
7. **Expected Result**: `Bole Elite Fitness` appears in the lead table with status `New`.
8. Click **Convert to Gym** on the row.
9. **Expected Result**: Super Admin is transitioned to the **Gym Tenants** tab, and the Create Gym form is pre-filled with `Bole Elite Fitness`, `tadesse@boleelite.com`, and `+251911223344`.

---

## Test Scenario 3: Onboarding a New Gym Tenant & Subdomain Provisioning

1. In the **Create Gym Tenant** form (`http://localhost:5173/dashboard`):
   - Gym Name: `Bole Elite Fitness`
   - Subdomain: Click **Suggest Subdomain** (suggests `bole-elite-fitness` or type `boleelite`)
   - Owner Full Name: `Tadesse Worku`
   - Owner Email: `owner@boleelite.com`
   - Owner Phone: `+251911223344`
   - Tier: Select `Starter`
   - Payment Method: Select `Bank Transfer` (verified offline)
   - Payment Reference: `CBE-TX-987654321`
   - Payment Amount: `12000` ETB (matches placeholder price of 12,000 ETB/yr for Starter tier; Growth is 30,000 ETB, Pro is 60,000 ETB)
2. Click **Create Gym Tenant**.
3. **Expected Result**:
   - Backend atomically creates `GymTenant`, `GymConfig`, confirmed `Payment`, and `User` (Owner) with unusable password.
   - Per SPEC security rules, invite links are sent via transactional email only (on_commit) and are **never** returned in API responses or shown in modals.
4. Retrieve the Owner invitation link from backend logs:
   ```bash
   docker compose logs backend | grep -A 5 "set-password"
   ```
   Copy the link (e.g. `http://boleelite.localhost:5173/set-password?token=...`).

---

## Test Scenario 4: Gym Owner Account Activation & First-Run Setup (Gym Subdomain)

1. Open an incognito browser window and paste the invitation link:
   `http://boleelite.localhost:5173/set-password?token=...`
2. **Expected Result**:
   - Notice that the token is immediately stripped from the URL address bar (`history.replaceState`) to prevent browser history leaks.
   - The screen shows the gym branding context for `Bole Elite Fitness`.
3. Set initial password:
   - New Password: `OwnerPassword2026!`
   - Confirm Password: `OwnerPassword2026!`
4. Click **Activate Account**.
5. **Expected Result**: Success confirmation appears with a link to log in.
6. Click **Sign In**, and log in:
   - Email: `owner@boleelite.com`
   - Password: `OwnerPassword2026!`
7. **Expected Result**: You are redirected to the Gym Owner Dashboard (`http://boleelite.localhost:5173/dashboard`).
8. Notice the **First-Run Checklist Card**:
   - [ ] Set Gym Branding
   - [ ] Create First Membership Plan (Sprint 10)
   - [ ] Provision Staff Account
   - [ ] Register First Member
9. Click **Configure Branding**:
   - Change Brand Accent Color to `#E11D48` (Vibrant Crimson).
   - Click **Save Branding**.
10. **Expected Result**: Brand theme updates dynamically across the UI, success alert appears, and the checklist item ticks automatically.

---

## Test Scenario 5: Staff Provisioning & Role Enforcement (Manager, Trainer, Reception)

1. Scroll to the **Staff Management** section on the Owner dashboard.
2. Click **Invite Staff Member**:
   - Role: Select `Manager`
   - Email: `manager@boleelite.com`
   - Full Name: `Selamawit Bekele`
   - Phone: `+251922334455`
3. Click **Send Invitation**.
4. **Expected Result**: Manager appears in the staff table with status `Invited`. Per security requirements, the invitation link is sent via email only (find it in `docker compose logs backend`).
5. Repeat to invite a Receptionist:
   - Role: Select `Reception`
   - Email: `reception@boleelite.com`
   - Full Name: `Kassahun Desta`
   - Phone: `+251933445566`
6. Click **Send Invitation**.
7. Test Deactivation & Reactivation:
   - On `Kassahun Desta`'s row, click **Deactivate**.
   - Confirm the dialog.
   - **Expected Result**: Status updates immediately to `Deactivated` (badge turns red/gray). The user is blocked from logging in.
   - Click **Reactivate**.
   - **Expected Result**: Status returns to active without needing a new account.
8. Activate the Manager account in an incognito window using their invite link from `docker compose logs backend`, setting their password to `ManagerPassword2026!`.
9. Log in as `manager@boleelite.com` at `http://boleelite.localhost:5173/login`:
   - Open Staff Management modal as Manager.
   - **Expected Result**: Manager can only invite `Trainer` and `Reception`. The `Manager` role is omitted from the dropdown. Attempts to forge a request return HTTP 403 Forbidden.

---

## Test Scenario 6: Member Registration (Self-Service & Staff-Assisted) & Body Composition

1. **Staff-Assisted Member Registration**:
   - On the Owner/Manager dashboard, scroll to **Member Management**.
   - Click **Register New Member**:
     - Full Name: `Dawit Kebede`
     - Email: `dawit@example.com`
     - Phone: `+251944556677`
     - Date of Birth: `1995-05-15`
     - Gender: `Male`
     - Emergency Contact: `Almaz - +251922001122`
     - Height: `180` cm
     - Weight: `80` kg
     - Waist Circumference: `84` cm
     - Neck Circumference: `38` cm
     - Check: _"I accept the health waiver and liability disclaimer"_
   - Click **Register Member**.
   - **Expected Result**:
     - Member is created in verified state.
     - An invitation set-password link is emailed to Dawit (retrieve via `docker compose logs backend`).
2. **View Member Details & Derived Body Composition**:
   - In the Member table, click **View Profile** on Dawit Kebede.
   - **Expected Result**:
     - BMI is displayed as labeled estimate: `24.7` (Normal weight, computed as `80 / (1.80^2)`).
     - Body Fat Percentage is displayed as labeled estimate via US Navy circumference formula: `15.3%` (computed as `495 / (1.0324 - 0.19077*log10(84-38) + 0.15456*log10(180)) - 450 = 15.3%`).
3. **Public Self-Service Registration**:
   - In an incognito window, navigate to `http://boleelite.localhost:5173/register`.
   - Enter details:
     - Full Name: `Almaz Ayana`
     - Email: `almaz@example.com`
     - Phone: `+251955667788`
     - Date of Birth: `1992-08-20`
     - Gender: `Female`
     - Emergency Contact: `Kebede - +251911002233`
     - Password: `MemberPassword2026!`
     - Check: _"I accept the health waiver and liability disclaimer"_
   - Click **Register Now**.
   - **Expected Result**: Confirmation informs the member to verify their email before logging in. Verification link is dispatched via email (inspect `docker compose logs backend`). Rate limiting prevents automated bot abuse.

---

## Test Scenario 7: QR Check-in, Scanner Validation & Manual Override

> **Note on Membership Subscriptions**: QR check-in tokens and scan validation fail closed: members without an active `MemberSubscription` cannot issue a QR pass (`/api/members/me/qr-token/` returns HTTP 400 with `reason: "expired"`). Membership plans and subscription billing are formally wired in Sprint 10. For Increment 1 end-to-end testing, provision an active subscription for test members via Django shell:

```bash
docker compose exec backend python manage.py shell -c "from apps.memberships.models import Member, MemberSubscription; from django.utils import timezone; from datetime import timedelta; member = Member.all_objects.get(user__email='dawit@example.com'); MemberSubscription.objects.create(gym=member.gym, member=member, status='active', start_date=timezone.localdate(), end_date=timezone.localdate()+timedelta(days=30))"
```

1. **Member QR Pass Issuance**:
   - Activate Dawit's account using the email link from backend logs, setting password to `MemberPassword2026!`.
   - Log in as Dawit at `http://boleelite.localhost:5173/login`.
   - The member dashboard displays the **Check-in QR Pass**.
   - **Expected Result**:
     - High-contrast QR code is rendered with member name and status badge `ACTIVE`.
     - 90-second countdown timer dynamically updates.
     - A Refresh button allows rotating the token.

2. **Reception / Scanner Terminal Check-in**:
   - Log in as Reception (`reception@boleelite.com`) or Owner at `http://boleelite.localhost:5173/dashboard`.
   - Scroll to the **Attendance Scanner Terminal** section.
   - Enter or scan the valid QR token string.
   - Click **Process Scan**.
   - **Expected Result**:
     - HTTP 200 OK:
       ```json
       {
         "status": "success",
         "message": "Welcome, Dawit Kebede!",
         "member": { "id": "...", "full_name": "Dawit Kebede", "status": "active", ... },
         "attendance": { "id": "...", "date": "...", "is_override": false },
         "next_token": "..."
       }
       ```
     - Exactly one `Attendance` record is created.
     - Exactly one `AuditLog` row is created with `action_type = "attendance_qr_scan"`.

3. **Re-scan of Same Token (Token Replay Prevention)**:
   - Immediately attempt to re-submit the identical QR token.
   - **Expected Result**:
     - HTTP 400 Bad Request:
       ```json
       {
         "detail": "This QR token has already been used.",
         "reason": "token_consumed"
       }
       ```
     - Token is blocked from replay; no attendance row is created.

4. **Scan with Refreshed Token (Duplicate Same-Day Check-in Prevention)**:
   - As Dawit, refresh the QR pass to obtain a new valid token.
   - Scan the refreshed token at the terminal.
   - **Expected Result**:
     - HTTP 400 Bad Request:
       ```json
       {
         "detail": "Member Dawit Kebede has already checked in today.",
         "reason": "already_checked_in",
         "member": { "id": "...", "full_name": "Dawit Kebede" }
       }
       ```
     - Duplicate scan is denied on calendar day; no second attendance row is created.

5. **Manual Check-in Override on Same Member (Refused on Duplicate)**:
   - In the scanner section, click **Manual Override**.
   - Select member `Dawit Kebede`.
   - Enter mandatory reason: _"Forgot phone at home."_
   - Click **Confirm Manual Check-in**.
   - **Expected Result**:
     - HTTP 400 Bad Request:
       ```json
       {
         "detail": "Member Dawit Kebede has already checked in today.",
         "reason": "already_checked_in"
       }
       ```

6. **Manual Check-in Override on Different Member with Active Subscription**:
   - Provision a subscription for `Almaz Ayana`:
     ```bash
     docker compose exec backend python manage.py shell -c "from apps.memberships.models import Member, MemberSubscription; from django.utils import timezone; from datetime import timedelta; member = Member.all_objects.get(user__email='almaz@example.com'); MemberSubscription.objects.create(gym=member.gym, member=member, status='active', start_date=timezone.localdate(), end_date=timezone.localdate()+timedelta(days=30))"
     ```
   - In the scanner section, click **Manual Override**.
   - Select member `Almaz Ayana`.
   - Enter mandatory reason: _"Phone screen broken, verified ID."_
   - Click **Confirm Manual Check-in**.
   - **Expected Result**:
     - HTTP 201 Created:
       ```json
       {
         "status": "success",
         "message": "Manual check-in recorded for Almaz Ayana.",
         "member": { "id": "...", "full_name": "Almaz Ayana" },
         "attendance": {
           "id": "...",
           "is_override": true,
           "override_reason": "Phone screen broken, verified ID."
         }
       }
       ```
     - Exactly one `Attendance` record created (`is_override=True`).
     - Exactly one `AuditLog` event recorded (`action_type="attendance_manual_override"`).

---

## Test Scenario 8: Audit Log Viewer & Immutability Verification

1. **Tenant Audit Log View (Owner / Manager)**:
   - On the Gym Owner or Manager dashboard (`http://boleelite.localhost:5173/dashboard`), scroll to **Audit Trail & Security Logs**. (Reception role gets HTTP 403 Forbidden per SPEC §2 RBAC).
   - **Expected Result**:
     - Paginated list of events appears ordered newest first:
       - `attendance_manual_override`
       - `attendance_qr_scan`
       - `member_registered`
       - `staff_reactivated`
       - `staff_deactivated`
       - `staff_provisioned`
       - `user_login`
2. **Testing Filter Controls**:
   - Select Action Type: `Manual Attendance Override` (`attendance_manual_override`).
   - Click **Filter**.
   - **Expected Result**: Table updates to display only manual override events.
   - Clear filters to restore all events.
   - In the Search box, enter `Dawit` or `Selamawit`.
   - **Expected Result**: Fast, matching event records are filtered.
3. **Inspecting Event Metadata & Payload Sanitization**:
   - Click **Inspect** on any event.
   - A modal opens displaying Event UUID, Action Type, Timestamp, Actor Name/Role, and JSON metadata.
   - **Verification**: Sensitive secrets, passwords, and JWT tokens are completely absent from the metadata payload.
4. **Super Admin Platform Audit View**:
   - Log in as Super Admin at `http://localhost:5173/dashboard`.
   - Click on the **Audit & Security Logs** tab.
   - **Expected Result**: Platform-wide view displays events across all gyms plus platform operations (`gym_created`, `super_admin_created`).
5. **Database Immutability Trigger Protection**:
   - **Test ORM Update Protection**:
     ```bash
     docker compose exec backend python manage.py shell -c "from apps.accounts.models import AuditLog; log = AuditLog.all_objects.first(); log.action_type = 'tampered'; log.save()"
     ```
     **Real Output**:
     ```
     django.core.exceptions.ValidationError: ['AuditLog is append-only and cannot be updated.']
     ```
   - **Test ORM Delete Protection**:
     ```bash
     docker compose exec backend python manage.py shell -c "from apps.accounts.models import AuditLog; log = AuditLog.all_objects.first(); log.delete()"
     ```
     **Real Output**:
     ```
     django.core.exceptions.ValidationError: ['AuditLog is append-only and cannot be deleted.']
     ```
   - **Test Raw SQL UPDATE Protection (PostgreSQL Trigger)**:
     ```bash
     docker compose exec backend python manage.py shell -c "from django.db import connection; cursor = connection.cursor(); cursor.execute(\"UPDATE accounts_auditlog SET action_type = 'tampered'\")"
     ```
     **Real Output**:
     ```
     django.db.utils.ProgrammingError: AuditLog is append-only and cannot be modified or deleted.
     CONTEXT:  PL/pgSQL function prevent_auditlog_modification() line 12 at RAISE
     ```
   - **Test Raw SQL DELETE Protection (PostgreSQL Trigger)**:
     ```bash
     docker compose exec backend python manage.py shell -c "from django.db import connection; cursor = connection.cursor(); cursor.execute('DELETE FROM accounts_auditlog')"
     ```
     **Real Output**:
     ```
     django.db.utils.ProgrammingError: AuditLog is append-only and cannot be modified or deleted.
     CONTEXT:  PL/pgSQL function prevent_auditlog_modification() line 12 at RAISE
     ```
   - **Test Raw SQL TRUNCATE Protection (PostgreSQL Trigger)**:
     ```bash
     docker compose exec backend python manage.py shell -c "from django.db import connection; cursor = connection.cursor(); cursor.execute('TRUNCATE accounts_auditlog')"
     ```
     **Real Output**:
     ```
     django.db.utils.ProgrammingError: AuditLog is append-only and cannot be modified or deleted.
     CONTEXT:  PL/pgSQL function prevent_auditlog_modification() line 12 at RAISE
     ```

---

## Conclusion & Verification Sign-off

When all 8 scenarios execute with the expected results, Increment 1 has satisfied all acceptance criteria defined in `docs/SPRINTS.md`.
