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
   - Payment Amount: `35000` ETB
2. Click **Create Gym Tenant**.
3. **Expected Result**:
   - Backend atomically creates `GymTenant`, `GymConfig`, confirmed `Payment`, `User` (Owner), and provisions the subdomain.
   - An on-screen modal displays the Owner's single-use, time-expiring Set-Password invitation link (e.g. `http://boleelite.localhost:5173/set-password?token=...`).
4. Copy the invitation link.

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
4. **Expected Result**: Manager appears in the staff table with status `Invited`. The invitation link is provided on screen.
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
8. Activate the Manager account in an incognito window using their invite link, setting their password to `ManagerPassword2026!`.
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
     - Height: `180` cm
     - Weight: `80` kg
     - Waist Circumference: `84` cm
     - Neck Circumference: `38` cm
     - Check: _"I accept the health waiver and liability disclaimer"_
   - Click **Register Member**.
   - **Expected Result**:
     - Member is created in verified state.
     - An invitation set-password link is generated for Dawit.
2. **View Member Details & Derived Body Composition**:
   - In the Member table, click **View Profile** on Dawit Kebede.
   - **Expected Result**:
     - BMI is displayed as labeled estimate: `24.7` (Normal weight).
     - Body Fat Percentage is displayed as labeled estimate via US Navy circumference formula: ~`16.8%`.
3. **Public Self-Service Registration**:
   - In an incognito window, navigate to `http://boleelite.localhost:5173/register`.
   - Enter details:
     - Full Name: `Almaz Ayana`
     - Email: `almaz@example.com`
     - Phone: `+251955667788`
     - Password: `MemberPassword2026!`
     - Check: _"I accept the health waiver and liability disclaimer"_
   - Click **Register Now**.
   - **Expected Result**: Confirmation informs the member to verify their email before logging in. Rate limiting prevents automated bot abuse.

---

## Test Scenario 7: QR Check-in, Scanner Validation & Manual Override

1. **Member QR Pass Issuance**:
   - Log in as a member (e.g., `dawit@example.com` after completing password setup).
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
     - Scan validates in under 2 seconds.
     - Success banner displays Dawit Kebede's details and photo placeholder.
     - Exactly one `Attendance` record is created.
3. **Duplicate Scan Prevention**:
   - Immediately rescan the same member's token.
   - **Expected Result**:
     - Scanner displays high-priority warning: _"Duplicate check-in detected for this member today"_.
     - No second `Attendance` row is inserted.
4. **Manual Check-in Override**:
   - In the scanner section, click **Manual Override**.
   - Select or search for member `Dawit Kebede`.
   - Enter mandatory reason: _"Member phone battery died, verified government ID."_
   - Click **Confirm Manual Check-in**.
   - **Expected Result**:
     - Manual check-in records successfully.
     - An audit log event `attendance_manual_override` is recorded with the supervisor's actor ID and reason.

---

## Test Scenario 8: Audit Log Viewer & Immutability Verification

1. On the Gym Owner or Manager dashboard, scroll down to **Audit Trail & Security Logs**:
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
   - Select Action Type: `QR Check-in Scan`.
   - Click **Filter**.
   - **Expected Result**: Table updates to display only `attendance_qr_scan` events.
   - Clear filters to restore all events.
   - In the Search box, enter `Dawit` or `Abebe`.
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
   - Open terminal and attempt to update or delete an audit log row using PostgreSQL CLI:
     ```bash
     docker compose exec backend python manage.py shell -c "from apps.accounts.models import AuditLog; log = AuditLog.all_objects.first(); log.action_type = 'tampered'; log.save()"
     ```
   - **Expected Result**: Blocked with `ValidationError: AuditLog is append-only and cannot be updated.`
   - Attempt a raw SQL update:
     ```bash
     docker compose exec backend python manage.py shell -c "from django.db import connection; cursor = connection.cursor(); cursor.execute('DELETE FROM accounts_auditlog;')"
     ```
   - **Expected Result**: Blocked by PostgreSQL trigger: `ProgrammingError: AuditLog is append-only and cannot be modified or deleted. (PL/pgSQL function prevent_auditlog_modification)`.

---

## Conclusion & Verification Sign-off

When all 8 scenarios execute with the expected results, Increment 1 has satisfied all acceptance criteria defined in `docs/SPRINTS.md`.
