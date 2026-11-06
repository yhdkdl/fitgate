# FitGate — Increment 7 End-to-End Test Script

This document is a comprehensive, numbered click-through guide for project owners, QA testers, and non-developers to verify all features built across **Increment 7** (Fix 1 Reminder Days Form, Fix 2 AutoSSL Trigger, Sprint 35 Super Admin Platform Dashboard & Gym Termination, Sprint 36 Feature-Flag Enforcement & Capabilities Render Gating, Sprint 37a Demo Gym Archive-and-Recreate, and Sprint 37 Offline-First PWA).

---

## Prerequisites & Environment Setup

1. **Verify Services are Running**:
   In your terminal, verify all Docker containers are up:

   ```bash
   docker compose ps
   ```

   Containers (`fitgate_backend`, `fitgate_frontend`, `fitgate_postgres`, `fitgate_redis`) must be running and healthy.

2. **Access Points**:
   - Apex Platform (Marketing & Super Admin): `http://localhost:5173`
   - Tenant Gym (e.g. Demo Gym): `http://demo.localhost:5173`
   - Ordinary Starter Gym: `http://starter-gym.localhost:5173`
   - Ordinary Growth Gym: `http://growth-gym.localhost:5173`

---

## 1. Fix 1: Reminder Days Inputs (Owner & Super Admin)

### 1.1 Owner Settings Screen (Gym Settings)

- **Role**: Gym Owner
- **Screen**: Gym Settings (`/settings`)
- **Steps**:
  1. Sign in as Gym Owner on the gym subdomain.
  2. Navigate to **Gym Settings**.
  3. Scroll to the **Member Expiry Reminders** section.
  4. Verify two distinct number input fields are displayed:
     - First reminder (e.g. `14` days before expiry)
     - Second reminder (e.g. `7` days before expiry)
  5. Enter an invalid configuration (e.g. second reminder greater than or equal to first reminder) and attempt to save.
  6. Verify validation error is displayed under the field: `"Second reminder must be smaller than the first reminder."`
  7. Enter valid numbers (e.g. `14` and `3`) and save. Verify changes persist upon page reload.

### 1.2 Super Admin Tenant Config

- **Role**: Super Admin
- **Screen**: Tenant Details / Entitlements Editor (`/platform/gyms/<id>/config/`)
- **Steps**:
  1. Sign in as Super Admin on apex (`http://localhost:5173`).
  2. Navigate to the gym's configuration modal/screen.
  3. Verify the same two number inputs exist for subscription reminder days.

---

## 2. Sprint 35: Super Admin Platform Dashboard & Lifecycle Management

### 2.1 Role Enablement and Disablement

- **Role**: Super Admin
- **Screen**: Tenant Management / Gym Configuration Modal
- **Steps**:
  1. As Super Admin, open the edit configuration modal for a gym.
  2. Locate the **Role Enablement** section with checkboxes for Manager, Reception, and Trainer.
  3. Disable the `trainer` role for the gym and save.
  4. Verify a platform audit log entry is written for the role change.
  5. Attempt to sign in as a Trainer on that gym subdomain: verify login is refused with `"Trainer role is currently disabled for this gym."`
  6. Attempt to invite a new Trainer on the Owner/Manager dashboard: verify Trainer is hidden or refused.
  7. Re-enable the role; verify login succeeds again.

### 2.2 Tenant List, Lapse Flags & Renewal

- **Role**: Super Admin
- **Screen**: Super Admin Dashboard — Tenants (`/platform/gyms`)
- **Steps**:
  1. Open the Tenants tab.
  2. Verify tenant table displays Tier, Status (`active`, `suspended`, `terminated`), Expiration Date, and Lapse flags.
  3. For an expired gym, click **Record Renewal**.
  4. Enter payment reference, bank name, and amount.
  5. Click **Confirm Renewal**.
  6. Verify the subscription expiry extends by 1 full year, lapse flag clears, and any suspension is lifted.

### 2.3 Suspension & 7-Day Export Window

- **Role**: Super Admin & Gym Owner
- **Screen**: Gym Suspension Modal & Owner Dashboard
- **Steps**:
  1. As Super Admin, select a lapsed gym and click **Suspend Gym**.
  2. Confirm suspension.
  3. Verify staff (Manager, Reception, Trainer) and members can no longer log in.
  4. Sign in as the **Owner** within 7 days of suspension:
     - Verify navigation is restricted exclusively to CSV Exports (`/reports/export`).
     - All operational views (adding members, check-ins, payments) are strictly blocked.
  5. Test login after the 7-day window has expired: verify Owner login is refused.

### 2.4 Gym Termination & Reinstatement (Real End State)

- **Role**: Super Admin
- **Screen**: Super Admin Dashboard — Gym Details
- **Steps**:
  1. Select a gym that has been suspended and whose 7-day export window has ended.
  2. Click **Terminate Gym**.
  3. Verify the modal requires typing the gym's exact subdomain to confirm.
  4. Confirm termination.
  5. Verify gym status is updated to `terminated`.
  6. Visit the public gym entry page (`http://<subdomain>.localhost:5173`):
     - Verify it displays: `"This gym is no longer on FitGate"`.
     - Log in attempt by any user (including Owner) is strictly refused.
  7. Verify all database rows and audit history remain intact.
  8. Click **Reinstate Gym**, type subdomain, and confirm:
     - Verify status returns to `suspended` (not active).
     - The 7-day export window does NOT restart.

### 2.5 Platform Notices

- **Role**: Super Admin & Gym Owner
- **Screen**: Platform Notices (`/platform/announcements`) & Owner Home (`/dashboard`)
- **Steps**:
  1. As Super Admin, create a platform announcement with title `"Scheduled Platform Maintenance"`.
  2. Sign in as Gym **Owner** on any gym (Starter or Growth).
  3. Verify the platform notice appears prominently on the **Owner Home** dashboard.
  4. Verify the platform notice is NEVER broadcast to Telegram.
  5. Sign in as a **Member**, **Trainer**, **Reception**, or **Manager**: verify platform notices are NOT displayed to non-owners.

---

## 3. Sprint 36: Tier Feature-Flag Enforcement & Render Gating

### 3.1 Contract Test Verification

- Run the tier gate contract test in backend container:
  ```bash
  docker compose exec backend pytest apps/accounts/tests/test_permissions_and_contracts.py -k test_all_tier_gated_views_declare_required_flag
  ```
- Verify 100% of views declare either a required tier flag or an explicit no-tier marker.

### 3.2 Starter Tier vs Growth Tier Enforcement

- **Starter Tier Gym**:
  - Sign in as Gym Owner on a Starter tier gym.
  - Verify sidebar navigation **hides**:
    - Trainers & My clients
    - AI Workout Plans
    - Freeze Requests
    - Group Classes
    - Notice Board
    - Expenses & Financial Reports
  - Verify Owner dashboard displays single upgrade prompt: `"Upgrade to unlock revenue by plan"`.
  - In Plan Management, attempt to create a plan with `"Trainer included"` checked: verify the backend rejects creation and the checkbox is disabled/hidden.
  - Direct URL traversal test:
    - Type `/trainers`, `/classes`, `/notices`, `/expenses`, `/freezes` directly into browser address bar.
    - Verify client immediately redirects to Home with zero error screens.

- **Growth Tier Gym**:
  - Sign in as Gym Owner on a Growth tier gym.
  - Verify all features (Trainers, AI Plans, Freeze, Classes, Notices, Expenses) are visible and fully accessible.

### 3.3 Dynamic Capabilities Re-sync

- Keep a Gym Owner tab open on a Starter gym.
- In another tab as Super Admin, upgrade the gym to Growth tier.
- Switch back to the Owner tab (triggering browser `visibilitychange` focus event).
- Verify capabilities re-sync automatically and new navigation items appear without requiring a manual page refresh.

---

## 4. Sprint 37a: Demo Gym (Archive-and-Recreate)

### 4.1 Execution Guard & Re-seed

- **Command**:
  ```bash
  # Attempt without flag (must fail)
  docker compose exec backend python manage.py seed_demo_gym
  # Expected: "Refused: ALLOW_DEMO_SEED is not enabled."

  # Run with execution guard
  docker compose exec -e ALLOW_DEMO_SEED=True backend python manage.py seed_demo_gym
  ```
- Verify command runs cleanly, printing the demo subdomain (`demo`), role logins, and row counts.

### 4.2 Archive-and-Recreate Architecture

- Re-run the command a second time:
  ```bash
  docker compose exec -e ALLOW_DEMO_SEED=True backend python manage.py seed_demo_gym
  ```
- Verify in database:
  - Previous demo gym was renamed to `demo-archive-1` and marked `terminated`.
  - Previous demo users were renamed with `.archived.1` emails.
  - Fresh demo gym provisioned on subdomain `demo` with receipt counter starting at `REC-000001`.
  - Non-demo gyms and their payments/receipts are completely untouched.

### 4.3 Demo Credentials Login Helper

- **Screen**: Demo Gym Login (`http://demo.localhost:5173/login`)
- **Steps**:
  1. Open the login page on `http://demo.localhost:5173`.
  2. Verify an expandable **Demo credentials** panel is visible.
  3. Click on **Owner** (`owner@demo.local`): verify email and password auto-fill.
  4. Click **Sign in**: verify instant access to Owner Dashboard with 90 seeded members, equipment, expenses, classes, and receipts.
  5. Log out and visit an ordinary non-demo gym login page: verify the Demo credentials panel is hidden.

---

## 5. Sprint 37: Offline-First PWA & Check-in Sync

### 5.1 Service Worker Caching Boundary

- **Screen**: Browser DevTools -> Application / Network
- **Steps**:
  1. Open DevTools on `http://demo.localhost:5173`.
  2. Verify Service Worker (`/sw.js`) is registered and active.
  3. Inspect Cache Storage:
     - Verify cache `fitgate-shell-v1` contains ONLY static app shell assets (`/`, `/index.html`, `/manifest.webmanifest`, CSS/JS bundles, icons).
     - Verify NO `/api/*` responses and NO `/media/*` images/receipts exist in the Cache Storage.

### 5.2 Offline Check-in Queuing (Entrance Scanner)

- **Role**: Reception / Staff
- **Screen**: Entrance Scanner (`/scanner`)
- **Steps**:
  1. Sign in as Receptionist and open the **Entrance Scanner**.
  2. In DevTools Network tab, switch network to **Offline**.
  3. Verify the header displays an amber badge: `"Offline Mode — Scans queued locally"`.
  4. Scan a valid 90-second member QR code (or enter via manual code input).
  5. Verify large green overlay appears: `"Offline Scan (Queued)"`.
  6. Verify the badge in header updates: `"Queued: 1 (Sync Now)"`.
  7. Scan an expired QR token (older than 90s):
     - Verify local validation immediately displays amber refusal screen: `"Pass Code Expired"`.

### 5.3 Sync Replay on Reconnect

- **Screen**: Entrance Scanner (`/scanner`)
- **Steps**:
  1. With 1 or more scans queued, toggle network back to **Online** (or focus the browser tab).
  2. Within 5 seconds, background replay executes automatically.
  3. Verify queued count drops to `0`.
  4. Check the backend database: verify exactly 1 `Attendance` row was created for the member.
  5. If an offline scan was queued for a suspended or frozen member, verify a red notification banner appears on staff screen: `"Queued Check-in Refused: Member subscription is suspended."`

### 5.4 Logout Clears Offline Queue

- **Screen**: Any Screen -> Log out
- **Steps**:
  1. While offline, queue 2 check-in scans.
  2. Click **Log out** in the user menu.
  3. Open DevTools -> Application -> IndexedDB -> `fitgate_offline_db` -> `checkin_queue`.
  4. Verify the `checkin_queue` store is completely empty (`0` records), ensuring zero data leak across users.

### 5.5 PWA Install Prompt & Standalone Mode

- **Role**: Member
- **Screen**: Member Home Dashboard (`/dashboard`)
- **Steps**:
  1. Sign in as a gym **Member** on an Android/Chromium browser over HTTPS or localhost.
  2. Verify the **Download App** card appears on the Member Home dashboard.
  3. Click **Download App**: verify native browser install prompt appears.
  4. In iOS Safari (or simulated user agent), verify the card displays: `"Add FitGate to Home Screen: tap Share, then select Add to Home Screen."`
  5. Open the installed PWA: verify it launches in standalone display mode with no browser URL address bar.

### 5.6 320px Responsive Viewport Audit

- In DevTools device mode, set viewport width to `320px` (e.g. iPhone SE / small Android).
- Audit each screen added in Increments 3 to 5:
  - **Group Classes** (`/classes`): Class sessions, schedule grid, and booking modals fit cleanly without horizontal scrolling.
  - **Equipment Registry** (`/equipment`): Table scrolls cleanly inside container (`overflow-x-auto`), header and total investment wrap cleanly.
  - **Expenses & Reports** (`/expenses`): Expense filters, expense table, and summary cards wrap cleanly.
  - **Receipt Review Queue** (`/receipt-reviews`): Review queue cards and modal actions fit within 320px width.
  - **Trainer Clients & Measurements** (`/trainers`): Client list, measurement cards, and progress metrics adapt smoothly without clipping.
  - **Gym Notices** (`/notices`): Notice cards and create notice modal display cleanly.

---

## 6. Increment 7 Automated Test Suite Pass

Execute full backend and frontend automated test suites:

```bash
# Backend test suite
docker compose exec backend pytest

# Frontend test suite
docker compose exec frontend npm run test
```

Expected result: All backend and frontend tests pass 100% green.
