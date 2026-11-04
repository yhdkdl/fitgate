# FitGate — Increment 5 End-to-End Test Script

This document is a comprehensive, numbered click-through guide for project owners, QA testers, and non-developers to verify all features built across **Increment 5** (Sprint 25 Equipment, Sprint 27 Analytics Dashboards, fix/equipment-registry-rules, Sprint 28 Notice Board & Telegram Bridge, Sprint 29 CSV Exports, Sprint 29a Expenses & Financial Ledger, and Sprint 26 Lean Group Classes).

---

## Prerequisites & Environment Setup

1. **Verify Services are Running**:
   In your PowerShell terminal at the project root, ensure Docker Compose containers are up:

   ```powershell
   docker compose ps
   ```

   Expected containers (`fitgate_backend`, `fitgate_frontend`, `fitgate_postgres`, `fitgate_redis`, `fitgate_pgadmin`) should be running and healthy.
   Base URLs:
   - Platform Apex: `http://localhost:5173`
   - Tenant Gym Subdomain: `http://<subdomain>.localhost:5173` (e.g. `http://fitgate-bole.localhost:5173`)

2. **Accessing Management Commands**:
   Run Django commands inside the backend container via PowerShell:

   ```powershell
   docker compose exec backend python manage.py <command_name>
   ```

---

## 1. Equipment Management & Rules Engine Integration (Sprint 25 & Fix)

### 1.1 Equipment Registry & Investment Tracking (Owner / Manager)

1. Sign in as gym **Owner** or **Manager** at `http://<subdomain>.localhost:5173`.
2. From the navigation sidebar, select **Equipment** (`/equipment`).
3. Click **Add Equipment**.
4. Enter equipment details:
   - Name: `LifeFitness Treadmill 95T`
   - Category: `Cardio`
   - Quantity: `3`
   - Usable Count: `3`
   - Status: `Usable`
   - Unit Purchase Price (ETB): `120,000`
   - Serial Number: `LF-TR-001`
   - Maintenance Notes: `Installed near north window.`
5. Click **Save Equipment**.
6. Verify the item appears in the registry and the header summary updates:
   - `Categories registered: 1 of 8`
   - `Total Investment: 360,000.00 ETB` (visible only to Owner and Manager).

### 1.2 Maintenance Logs & Status Update

1. Locate `LifeFitness Treadmill 95T` in the list and click **Log Maintenance / Issue**.
2. Select status change to `Maintenance`, enter description: `Belt tension adjustment needed.`, cost: `1,500 ETB`.
3. Save the log. Verify the equipment status reflects `In Maintenance` and the usable count is decremented.

### 1.3 Owner Equipment Completeness Setting & AI Plan Modes

1. As **Owner**, navigate to **Settings** (`/settings`).
2. Scroll to the equipment section:
   - **Show unavailable equipment to members in catalog**: Leave unchecked.
   - **My equipment list is complete**: Test the three rules engine modes:
     - **Mode 1 (Complete list OFF, no unavailable items)**: AI workout generation relies on client profile equipment preferences.
     - **Mode 2 (Complete list OFF, broken equipment)**: Mark all barbells as `Out of Service`. Generate a workout for a member who has barbell access; verify the engine filters out barbell exercises.
     - **Mode 3 (Complete list ON)**: Check `My equipment list is complete` and save settings. Verify AI generation uses only equipment actively registered and marked `Usable` in the gym's database, while always allowing basic bodyweight movements.
     - On the Trainer plan review screen, check the attribution line confirming the equipment mode source.

### 1.4 Member Equipment Privacy

1. Sign in as a gym **Member**.
2. Navigate to **Gym Equipment** (`/equipment`).
3. Verify members can view available equipment names and categories.
4. Verify serial numbers, internal maintenance notes, and purchase prices are strictly hidden.
5. Verify items marked `Maintenance` or `Out of Service` are hidden when the owner setting is unchecked.

---

## 2. Operational Dashboard & Revenue Analytics (Sprint 27)

### 2.1 Owner / Manager Analytics Overview

1. Sign in as **Owner** or **Manager**.
2. Open the main **Dashboard** (`/`).
3. Confirm the four primary operational metric cards:
   - **Active Members**: Total members holding active subscriptions.
   - **Today's Check-ins**: Number of QR and manual check-ins recorded today.
   - **Monthly Net Revenue**: Confirmed receipts minus reversed payments for the current calendar month.
   - **Expiring Soon**: Count of subscriptions ending within 7 days.
4. Verify the 30-day attendance trend bar chart renders recent visit patterns.

### 2.2 Tier-Gated Plan Revenue Breakdown

1. For gyms on **Growth** or **Pro** tier:
   - Verify the **Revenue by Membership Plan** section displays tabular breakdown of active subscriptions, total revenue per plan, and average revenue per member.
2. For gyms on **Starter** tier:
   - Verify the section displays a friendly upgrade prompt: `Revenue by Plan Locked: Upgrade to Growth or Pro to unlock revenue by plan breakdowns.`

---

## 3. Gym Notice Board & Telegram Bridge (Sprint 28)

### 3.1 Post and Manage Gym Notices

1. Sign in as **Owner** or **Manager**.
2. Navigate to **Notices** (`/notices`).
3. Click **Create Notice**:
   - Title: `Holiday Operating Hours`
   - Content: `The gym will open from 8:00 AM to 2:00 PM on Meskel holiday.`
   - Priority: `High (Pinned)`
   - Target Audience: `All Members`
   - Optional Expiry Date: Choose tomorrow's date.
4. Click **Publish Notice**.
5. Sign in as a **Member** and view Home: verify the pinned notice appears prominently at the top of the Member dashboard.

### 3.2 Telegram Channel Bridge Setup & Mock Delivery

1. Sign in as **Owner**, go to **Settings** (`/settings`).
2. Scroll to **Telegram Channel Bridge (Optional)**.
3. Note the instructions: The single FitGate platform bot is added as Administrator to the gym's channel. Gym owners never create bots or touch bot tokens.
4. Enter channel handle: `@my_gym_channel` and click **Save Branding Settings**.
5. Enter a channel handle already used by another gym; verify server validation rejects it with: `This Telegram channel is already connected to another gym.`
6. With the mock sender enabled (`TELEGRAM_USE_MOCK=True`), click **Send test message**.
7. Verify an in-app confirmation banner reports: `Test message broadcast simulated successfully to @my_gym_channel.`
8. Publish a notice with Telegram broadcast checked; verify simulated delivery without errors.

---

## 4. CSV Data Exports (Sprint 29)

### 4.1 Export Members, Payments, and Attendance

1. Sign in as **Owner** or **Manager**.
2. Navigate to **Data Export** (`/export`).
3. Test each export type:
   - **Members Export**: Select format CSV, date range (default last 90 days), click **Download Members CSV**.
   - **Payments Export**: Select date range, click **Download Payments CSV**.
   - **Attendance Export**: Select date range, click **Download Attendance CSV**.
4. Open the downloaded CSV files in Microsoft Excel or text editor:
   - Verify the file begins with the UTF-8 Byte Order Mark (`\xef\xbb\xbf`) so Amharic text and special characters render cleanly without character corruption.
   - Verify date ranges greater than 365 days are rejected with a clear validation prompt.
   - Verify any text field beginning with `=`, `+`, `-`, or `@` has been prepended with a single quote (`'`) to guard against spreadsheet formula injection.

### 4.2 Security & Tenancy Verification

1. Attempt to access `/export` or call `/api/gym/export/` as **Reception**, **Trainer**, or **Member**; verify access is strictly denied (403 Forbidden).
2. Verify Super Admin cannot export individual tenant gym data.
3. Sign in as Owner, open **Audit Logs** (`/audit-logs`), and verify each export event was recorded with actor, IP, record count, and timestamp.

---

## 5. Expenses & Financial Ledger (Sprint 29a)

### 5.1 Record Operating Expenses

1. Sign in as **Owner** or **Manager**.
2. Navigate to **Expenses** (`/expenses`).
3. Click **Record Expense**:
   - Date: Today's date
   - Category: `Utilities`
   - Amount: `4,500.00 ETB`
   - Vendor / Payee: `Ethiopian Electric Utility`
   - Description: `Monthly electricity bill`
4. Click **Save Expense**. Verify it appears in the ledger with receipt attachment option.

### 5.2 Equipment Integration Checkbox

1. Click **Record Expense** again:
   - Category: `Equipment`
   - Amount: `25,000.00 ETB`
   - Vendor: `Addis Fitness Supplies`
   - Description: `Olympic barbell set`
   - Check the box: **Track as gym equipment purchase**.
2. Save expense.
3. Navigate to **Equipment** (`/equipment`) and verify the equipment registry total investment reflects this addition.

### 5.3 Void Expense Flow & Net Financial Summary

1. In **Expenses**, locate an entry and click **Void**.
2. Enter required reason: `Duplicate invoice entered in error.`
3. Confirm the void. Verify the expense is crossed out with a `Voided` tag and is excluded from financial totals.
4. Review the monthly financial summary at the top of the screen:
   - Confirmed Member Revenue (receipts minus reversed payments)
   - Minus Total Operating Expenses
   - Equals **Net Operating Income**

---

## 6. Lean Group Classes (Sprint 26)

### 6.1 Tier Gating (Starter vs. Growth/Pro)

1. In a gym on the **Starter** tier, verify **Classes** is hidden from the sidebar menu, and direct navigation to `/classes` shows the Growth/Pro tier feature lock.
2. In a gym on **Growth** or **Pro** tier, verify **Classes** is reachable from the navigation menu.

### 6.2 Schedule Class Sessions (Owner / Manager)

1. Sign in as **Owner** or **Manager** at `http://<subdomain>.localhost:5173`.
2. Navigate to **Classes** (`/classes`).
3. Click **Add Class Type**:
   - Name: `High-Intensity Interval Training (HIIT)`
   - Description: `Full body conditioning circuit.`
   - Default Capacity: `12`
   - Default Duration: `60 minutes`
4. Click **Schedule Session**:
   - Class Type: `HIIT`
   - Assigned Trainer: Select an active trainer from the dropdown.
   - Start Time: Tomorrow at `09:00 AM`.
   - Max Capacity: `12`.
5. Save the session and verify it appears on the weekly class calendar.

### 6.3 Trainer View

1. Sign in as the **Trainer** assigned to the class.
2. Navigate to **My Classes** (`/trainer/classes`).
3. Verify tomorrow's `09:00 AM HIIT` session appears with `0/12 Booked`.

### 6.4 Member Booking & 2-Hour Cancellation Rule

1. Sign in as an active **Member**.
2. Navigate to **Classes** (`/classes`).
3. Locate tomorrow's `09:00 AM HIIT` session and click **Book Spot**.
4. Confirm booking. Verify status changes to **Booked (Spot 1 of 12)**.
5. In another browser tab, book up to the maximum capacity (12 members); verify the 13th member sees **Class Full** and cannot book.
6. Test cancellation:
   - For a class scheduled tomorrow (> 2 hours away): click **Cancel Booking**; verify cancellation succeeds and opens the spot for others.
   - For a class scheduled within 2 hours: verify the **Cancel** button is disabled with notice: `Cancellations must be made at least 2 hours before class starts.`

### 6.5 Class Attendance Roster

1. As **Trainer**, **Reception**, or **Owner**, open the session roster.
2. Check off booked members as **Attended** or **No Show**.
3. Verify class attendance is recorded without generating duplicate regular gym check-in records.

---

## Increment 5 Verification Sign-off

- [x] Equipment Registry CRUD, purchase prices, and 3 AI rules engine modes verified.
- [x] Analytics Dashboard with net revenue wording verified.
- [x] Notice Board and Telegram Bridge with per-gym channel uniqueness verified.
- [x] CSV Exports with Excel UTF-8 BOM, date caps, and injection escaping verified.
- [x] Expenses ledger, void audit trails, and net income summaries verified.
- [x] Lean Group Classes tier-gating, booking capacity locking, and 2-hour cancellation verified.
