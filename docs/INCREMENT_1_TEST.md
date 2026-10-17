# FitGate — Increment 1 End-to-End Test Script

This document is a comprehensive, numbered click-through guide for project owners, QA testers, and non-developers to verify all features built across **Increment 1** (Sprints 0 through 9a).

---

## Prerequisites & Environment Setup

1. **Verify Services are Running**:
   In your terminal at the project root, ensure Docker Compose containers are up:

   ```bash
   docker compose ps
   ```

   All 5 containers (`fitgate_backend`, `fitgate_frontend`, `fitgate_postgres`, `fitgate_redis`, `fitgate_pgadmin`) should be running and healthy.
   The frontend runs inside Docker Compose on port `5173`:
   - Apex platform domain: `http://localhost:5173`
   - Tenant gym subdomain: `http://<subdomain>.localhost:5173`

   > **Troubleshooting**: If login shows a server error, run `docker compose logs frontend --tail 20` and look for "http proxy error".

2. **Bootstrap Super Admin Account** (if not already done):

   ```bash
   docker compose exec backend python manage.py create_super_admin
   ```

   Default test credentials:
   - Email: `superadmin@fitgate.com`
   - Temporary Password: `AdminPassword123!` (or value from `.env`)

3. **Where to Find Email Links (Local Development)**:
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
4. **Confirm Subdomain TLS Certificate (Super Admin Gate)**:
   - In the **Gym Tenants** table on the Super Admin dashboard, locate `Bole Elite Fitness` (shows yellow `Securing...` badge).
   - Click the **Confirm TLS** button to verify the security certificate and activate subdomain access.
   - **Expected Result**: The badge turns green (`Secured`). Subdomain API traffic is unlocked.
5. Retrieve the Owner invitation link from backend logs:
   ```bash
   docker compose logs backend | grep -A 5 "set-password"
   ```
   Copy the link (e.g. `http://boleelite.localhost:5173/set-password?token=...`).
   _(Note: In local development, the URL automatically includes `:5173` to route directly to the Vite frontend server)._

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

## Test Scenario 6: Member Registration & Trainer-Only Body Measurements

1. **Staff-Assisted Member Registration (No Measurement Fields)**:
   - On the Owner/Manager dashboard, scroll to **Member Management**.
   - Click **Register New Member**:
     - Full Name: `Dawit Kebede`
     - Email: `dawit@example.com`
     - Phone: `+251944556677`
     - Date of Birth: `1995-05-15`
     - Gender: `Male`
     - Emergency Contact: `Almaz - +251922001122`
     - Check: _"I accept the health waiver and liability disclaimer"_
   - Click **Register Member**.
   - **Expected Result**:
     - Member is created in verified state and appears in the member list.
     - An invitation set-password link is emailed to Dawit (retrieve via `docker compose logs backend`).
     - Clicking **View Profile** on Dawit Kebede shows: "Not measured yet. A trainer records measurements."
2. **Public Self-Service Registration (No Measurement Fields)**:
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
3. **Invite and Activate a Trainer**:
   - On the Owner/Manager dashboard, scroll to **Staff Management**.
   - Click **Invite Staff Member**:
     - Role: Select `Trainer`
     - Email: `trainer@boleelite.com`
     - Full Name: `Abebe Bikila`
     - Phone: `+251911998877`
   - Click **Send Invitation**.
   - Retrieve the set-password invite link from `docker compose logs backend`.
   - In an incognito browser window, open the invitation link, set password to `TrainerPassword2026!`, and click **Activate Account**.
4. **Trainer Records Measurements for Dawit**:
   - Log in as `trainer@boleelite.com` at `http://boleelite.localhost:5173/login` with password `TrainerPassword2026!`.
   - The Trainer dashboard displays the **Member Measurements** screen.
   - In the member search box, search for `Dawit` (or `dawit@example.com` or `+251944556677`).
   - Click `Dawit Kebede` in the search results.
   - The screen shows "Not measured yet. A trainer records measurements." and displays the measurement entry form.
   - In the measurement entry form, enter:
     - Height: `180` cm
     - Weight: `80` kg
     - Waist Circumference: `84` cm
     - Neck Circumference: `38` cm
     - (Hip Circumference can be left empty for male)
   - Click **Record Measurements**.
   - **Expected Result**:
     - A success confirmation appears.
     - The new record appears immediately in the member's measurement history table with today's date and the trainer's name (`Abebe Bikila`).
5. **View Member Profile with Labeled Body Composition Estimates**:
   - Dawit's measurement summary and profile now display:
     - BMI: `24.7` (labeled estimate)
     - Estimated Body Fat: `15.3%` (labeled estimate)
   - Log in as `dawit@example.com` at `http://boleelite.localhost:5173/login` on the Member Portal:
     - Dawit can view his measurements and history with the labeled BMI 24.7 and body fat 15.3% estimates.
     - No measurement entry form is shown on the member portal (members can only view their own measurements).

---

## Test Scenario 7: QR Check-in, Scanner Validation & Manual Override

> **Note on Membership Subscriptions**: QR check-in tokens and scan validation fail closed: members without an active `MemberSubscription` cannot issue a QR pass (`/api/members/me/qr-token/` returns HTTP 400 with `reason: "expired"`). Membership plans and subscription billing are formally wired in Sprint 10. For Increment 1 end-to-end testing, provision an active subscription for test members via Django shell:

```bash
docker compose exec backend python manage.py shell -c "from apps.memberships.models import Member, MemberSubscription; from django.utils import timezone; from datetime import timedelta; member = Member.all_objects.get(user__email='dawit@example.com'); MemberSubscription.all_objects.create(gym=member.gym, member=member, status='active', start_date=timezone.localdate(), end_date=timezone.localdate()+timedelta(days=30))"
```

1. **Member QR Pass Issuance & Copying Code**:
   - Activate Dawit's account using the email link from backend logs, setting password to `MemberPassword2026!`.
   - Log in as Dawit at `http://boleelite.localhost:5173/login`.
   - The member dashboard displays the **Check-in QR Pass** card.
   - **On-Screen Display**:
     - High-contrast QR code is rendered with member title `Check-in QR Pass` and badge `ACTIVE`.
     - Live countdown timer displays `Valid for 90s` and dynamically ticks down.
     - Action buttons: **Refresh** and **Copy code** (both conforming to 44px min touch target).
   - Click the **Copy code** button. The button briefly transitions to `Copied!` with a green checkmark and copies the asymmetric RS256 token string directly to your clipboard for easy terminal entry.

2. **Reception / Scanner Terminal Check-in**:
   - Log in as Reception (`reception@boleelite.com`) or Owner at `http://boleelite.localhost:5173/dashboard`.
   - Scroll to the **Front Desk Attendance Scanner** section.
   - Paste the copied QR token into the input box labeled `Scan QR token or paste token JWT...`.
   - Click **Verify & Check In** (or press Enter).
   - **On-Screen Display (Success Card)**:
     - An emerald-green confirmation banner appears (`border-emerald-500/30 bg-emerald-500/10`).
     - Member avatar/photo displays with full name **Dawit Kebede** and badge `ACTIVE`.
     - Check-in details: `Checked in at HH:MM:SS • YYYY-MM-DD` alongside green `UserCheck` icon.
     - A **View History** button is available to inspect the member's attendance calendar.
     - Database verification: Exactly one `Attendance` row and one `AuditLog` row (`attendance_qr_scan`) created.

3. **Re-scan of Same Token (Token Replay Prevention)**:
   - Immediately paste the identical QR token into the scanner input and click **Verify & Check In**.
   - **On-Screen Display (Error Card)**:
     - A rose-red rejection banner appears (`border-rose-500/30 bg-rose-500/10`).
     - Header: `Check-in Rejected (token_consumed)`
     - Detail message: `This QR token has already been used.`
     - Rejection indicator: `Token already used. Single-use enforcement active.`
     - No new attendance record or audit log is created.

4. **Scan with Refreshed Token (Duplicate Same-Day Check-in Prevention)**:
   - On Dawit's member pass, click **Refresh** to generate a new token, then click **Copy code**.
   - In the scanner terminal, paste the new token and click **Verify & Check In**.
   - **On-Screen Display (Error Card)**:
     - A rose-red rejection banner appears with Dawit's `ACTIVE` badge.
     - Header: `Check-in Rejected (already_checked_in)`
     - Detail message: `Member Dawit Kebede has already checked in today.`
     - Warning banner: `Duplicate check-in detected today. Staff have been notified.`
     - An **Open Manual Override** shortcut button appears.

5. **Manual Check-in Override on Same Member (Refused on Duplicate)**:
   - In the scanner section, click **Manual Override** (or **Open Manual Override**).
   - A modal opens titled `Manual Attendance Override`.
   - In **Member UUID**, enter Dawit's ID.
   - In **Override Reason (Required)**, enter: _"Forgot phone at home."_
   - Click **Confirm Override**.
   - **On-Screen Display (Modal Alert)**:
     - Inside the modal, an alert banner appears:
       - Header: `Override Denied (already_checked_in)`
       - Detail: `Member Dawit Kebede has already checked in today.`
     - The modal remains open, preventing duplicate override. Click **Cancel** to close.

6. **Manual Check-in Override on Different Member with Active Subscription**:
   - Provision a subscription for `Almaz Ayana` via Django shell:
     ```bash
     docker compose exec backend python manage.py shell -c "from apps.memberships.models import Member, MemberSubscription; from django.utils import timezone; from datetime import timedelta; member = Member.all_objects.get(user__email='almaz@example.com'); MemberSubscription.all_objects.create(gym=member.gym, member=member, status='active', start_date=timezone.localdate(), end_date=timezone.localdate()+timedelta(days=30))"
     ```
   - In the scanner section, click **Manual Override**.
   - In **Member UUID**, enter Almaz Ayana's ID.
   - In **Override Reason (Required)**, enter: _"Phone screen broken, verified ID."_
   - Click **Confirm Override**.
   - **On-Screen Display (Success Card)**:
     - The modal closes automatically.
     - An emerald-green confirmation banner appears displaying **Almaz Ayana**.
     - Status badges: `ACTIVE` and `OVERRIDE`.
     - Timestamp: `Checked in at HH:MM:SS • YYYY-MM-DD`.
     - Override note: `Reason: Phone screen broken, verified ID.`
     - Button: **View History**.
     - Exactly one `Attendance` record (`is_override=True`) and one `AuditLog` row (`attendance_manual_override`) created.

---

## Test Scenario 8: Audit Log Viewer & Immutability Verification

1. **Tenant Audit Log View (Owner / Manager)**:
   - On the Gym Owner or Manager dashboard (`http://boleelite.localhost:5173/dashboard`), scroll down to the **Audit Trail & Security Logs** section (badged `Read-Only`). (Reception role gets HTTP 403 Forbidden per SPEC §2 RBAC).
   - **On-Screen Display (Table)**:
     - Filter bar at top: Search input, Action Type dropdown (`All Action Types`), Date From, Date To, **Filter** and **Clear** buttons.
     - Table columns: `TIMESTAMP`, `ACTION`, `ACTOR`, `AFFECTED RECORD`, `DETAILS`.
     - Rows appear ordered newest-first with colored action badges:
       - `attendance_manual_override` (green badge), Actor: `Gym Owner (owner)`, Affected: `Attendance`
       - `attendance_qr_scan` (green badge), Actor: `Gym Reception (reception)`, Affected: `Attendance`
       - `member_registered` (secondary badge), Actor: `Gym Reception (reception)`, Affected: `Member`
       - `staff_reactivated` (secondary badge), Actor: `Gym Owner (owner)`, Affected: `User`
       - `staff_deactivated` (secondary badge), Actor: `Gym Owner (owner)`, Affected: `User`
       - `staff_provisioned` (secondary badge), Actor: `Gym Owner (owner)`, Affected: `User`
       - `user_login` (primary badge), Actor: `Gym Owner (owner)`, Affected: `User`
     - Each row includes an **Inspect** button on the right.
     - Pagination controls at bottom display current page and total entries.

2. **Testing Filter Controls**:
   - In the **Action Type** dropdown, select `Manual Check-in Override` (`attendance_manual_override`).
   - Click **Filter**.
   - **On-Screen Display**: Table refreshes instantly; all rows display the `attendance_manual_override` badge.
   - Click **Clear**: All filters reset and the full list of operational events returns.
   - In the **Search** input, enter `Dawit` and click **Filter**.
   - **On-Screen Display**: Table shows only entries associated with Dawit's check-in or registration.

3. **Inspecting Event Metadata & Payload Sanitization**:
   - Click the **Inspect** button on any audit row.
   - A modal titled **Audit Event Details** opens with badge `Read-Only`.
   - **On-Screen Display (Modal Fields)**:
     - `Event ID`: Displayed as a UUID string.
     - `Timestamp`: Formatted date and time.
     - `Action Type`: Displayed with badge.
     - `Actor`: Full name, email, and role.
     - `Affected Record`: Record type and UUID.
     - `Metadata (JSON)`: Formatted JSON preview displaying operational keys (e.g., `is_override: true`, `override_reason: "Phone screen broken, verified ID."`).
     - **Sanitization Verification**: Passwords, hashed passwords, raw tokens, JWT strings, and secret keys are completely absent from the JSON metadata.
   - Click **Close** (or 'X') to dismiss modal.

4. **Super Admin Platform Audit View**:
   - Log in as Super Admin at `http://localhost:5173/dashboard`.
   - View the **Audit Trail & Security Logs** section.
   - **On-Screen Display**:
     - The table includes an additional column: `GYM TENANT`.
     - Gym tenant events display the gym name (e.g. `Bole Elite Hub`), while platform operations display the badge `Apex Platform` (e.g. `gym_created`, `super_admin_created`).
     - Super Admin sees operational logs across all gyms without tenant boundaries.
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
