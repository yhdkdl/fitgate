# FitGate — Increment 2 End-to-End Test Script

This document is a comprehensive, numbered click-through guide for project owners, QA testers, and non-developers to verify all features built across **Increment 2** (Sprints 10 through 15, Sprint 9b email safety, and Increment 2 followup fixes).

---

## Prerequisites & Environment Setup

1. **Verify Services are Running**:
   In your terminal at the project root, ensure Docker Compose containers are up:

   ```bash
   docker compose ps
   ```

   All containers (`fitgate_backend`, `fitgate_frontend`, `fitgate_postgres`, `fitgate_redis`, `fitgate_pgadmin`) should be running and healthy.
   Frontend URLs:
   - Platform Apex: `http://localhost:5173`
   - Tenant Gym Subdomain: `http://<subdomain>.localhost:5173`

2. **Accessing Management Commands**:
   Run management commands inside the backend container:

   ```bash
   docker compose exec backend python manage.py <command_name>
   ```

---

## 1. Membership Plans (Sprint 10)

### 1.1 Create Plans (Days and Months Durations)

1. Sign in as gym **Owner** or **Manager** at `http://<gym-subdomain>.localhost:5173`.
2. Navigate to **Plans** (`/plans`).
3. Click **Add Plan**.
4. Create a daily plan:
   - Name: `10-Day Pass`
   - Duration Type: `Days`
   - Duration: `10`
   - Price: `500 ETB`
   - Includes Trainer: `No`
   - Click **Save**. Verify it appears in the active plans list.
5. Create a monthly plan:
   - Name: `1-Month Standard`
   - Duration Type: `Months`
   - Duration: `1`
   - Price: `1500 ETB`
   - Includes Trainer: `No`
   - Click **Save**. Verify it appears with accurate month-end calculation.

### 1.2 Price Change Immutability & Edit

1. Click **Edit** on `1-Month Standard`.
2. Change the price to `1800 ETB`.
3. Save the plan.
4. Verify existing members who previously subscribed at `1500 ETB` keep their original price in their receipts and subscription history; new subscriptions use `1800 ETB`.

### 1.3 Plan Deactivation

1. Click **Deactivate** on `10-Day Pass`.
2. Confirm the prompt. Verify the plan moves to the **Inactive** section and is hidden from front-desk staff when recording new memberships.
3. Verify existing subscriptions on `10-Day Pass` remain active until their normal expiration date.

### 1.4 Public Gym Entry Page & Plan Listing

1. Open an incognito browser window and navigate to the gym root address `http://<gym-subdomain>.localhost:5173/` (or `/public/entry`).
2. Verify it displays a modern public gym page with gym name, logo, brand color accent, active plans with prices, and "Log in" / "Register" buttons (without showing any member data, even while the gym certificate is being confirmed).
3. Scroll to the available plans list.
4. Confirm active plans (`1-Month Standard`) are visible with their prices, while inactive plans (`10-Day Pass`) are hidden.

---

## 2. Cash & Bank Payment Recording, Digital Receipts, and Upfront Registration

### 2.0 Staff Walk-in Member Registration with Upfront Payment

1. Sign in as **Reception** or **Owner** at `http://<gym-subdomain>.localhost:5173`.
2. Navigate to **Members** and click **Register Member**.
3. Enter required fields: Full Name, Phone (+251...), Date of Birth, Emergency Contact (phone number), and select Gender (**Female** or **Male**).
4. Check **Collect Payment Now**.
5. Select a plan and Payment Method (**Cash** or **Bank Transfer**).
6. If Bank Transfer is selected, enter the bank transaction reference, bank name, and optionally upload a transfer proof screenshot.
7. Click **Register & Record Payment**.
8. Verify member account, active subscription, and digital receipt are generated atomically in a single transaction.

### 2.1 Front-Desk Payment Recording (Existing Pending Member)

1. Sign in as **Reception** or **Owner** at `http://<gym-subdomain>.localhost:5173`.
2. Navigate to **Members** and locate a newly registered `pending` member.
3. Click **Record Payment**.
4. Select payment method: **Cash** (or **Bank Transfer**).
5. Select plan: `1-Month Standard`.
6. Enter notes: `Paid in cash at front desk`.
7. Click **Confirm Payment**.
8. Notice the double-submit guard disables the button immediately while the transaction processes.
9. Verify the payment and membership subscription are created atomically in a single transaction, transitioning member status from `pending` to `active`.

### 2.2 Sequential Immutable Digital Receipts

1. Immediately upon payment confirmation, open the digital receipt dialog.
2. Verify the receipt number format matches `REC-000001` for the gym's first payment.
3. Record a second cash payment for another member; verify its receipt number is strictly `REC-000002` with no gaps.
4. Verify the receipt displays:
   - Gym name, contact info, and receipt number
   - Member name and email
   - Plan details, duration, start date, and end date
   - Payment method (Cash) and amount paid in ETB
   - Confirming staff member's name
   - Transaction date and timestamp

### 2.3 Member Payment History & Revenue Totals

1. Navigate to **Payments** (`/payments`) as **Owner** or **Manager**.
2. Verify the total confirmed revenue reflects the exact sum of cash payments recorded.
3. Sign out and sign in as the **Member**.
4. Navigate to **My payments** (`/payments`).
5. Verify the member sees their own payments, receipt numbers, and can view their digital receipt.
6. Verify platform **Super Admin** attempting to access member payment history or revenue totals receives an access denied error.

---

## 3. Bank Transfer Payments, Statement Reconciliation, and Reversal (Sprint 12b)

### 3.1 Reception Bank Transfer Entry

1. Sign in as **Reception** at `http://<gym-subdomain>.localhost:5173`.
2. Select an active or renewing member and click **Record Payment**.
3. Select payment method: **Bank Transfer**.
4. Enter a unique bank transfer transaction reference: `CBE-TX-998811`.
5. Enter bank name: `Commercial Bank of Ethiopia`.
6. Optionally upload a bank transfer proof screenshot (`.png`, `.jpg`, `.webp` up to 5MB).
7. Submit the payment.
8. Verify the subscription is activated and a receipt (`REC-000003`) is generated.
9. Attempt to record another payment using the exact same reference `CBE-TX-998811` (or `cbe-tx-998811` in lowercase); verify the system immediately rejects the duplicate reference.

### 3.2 Owner-Only Payment Reversal

1. Record an erroneous bank transfer payment (e.g. `CBE-TX-998812`) or use an unreconciled transfer.
2. As **Owner**, select the unreconciled bank transfer payment and click **Reverse Payment**.
3. Enter the required reason for reversal: `Customer bounced cheque / incorrect account credit`.
4. Confirm the reversal.
5. Verify:
   - The payment is marked as `Reversed`.
   - The member's subscription is restored to its exact prior state (if first purchase, returned to `pending` with pass deactivated; if renewal, restored to prior expiration date).
   - The bank reference remains permanently burned and cannot be reused.
   - An audit log entry is recorded naming the owner and reason.
   - Reception and staff cannot see or use the reversal button.

### 3.3 7-Day Unreconciled Flagging Command

1. In the terminal (PowerShell or Bash), execute the daily check:
   ```powershell
   docker compose exec backend python manage.py flag_unreconciled_bank_transfers
   ```
2. Verify bank transfers older than 7 days that remain unreconciled are flagged for owner review, and a single summary notification is dispatched to the gym owner without spamming.

### 3.4 Owner Statement Reconciliation

1. Sign in as **Owner** and navigate to **Bank transfers** (`/bank-transfers`).
2. Notice the valid transfer `CBE-TX-998811` is listed under **Unreconciled Bank Transfers**.
3. Check the item and click **Mark as Reconciled**.
4. Verify the transfer status updates to `Reconciled` with the timestamp and owner's name recorded.

---

## 4. Freeze Workflow (Sprint 13 & Followup)

### 4.0 Owner Freeze Allowance Configuration (Gym Settings)

1. Sign in as **Owner** at `http://<gym-subdomain>.localhost:5173`.
2. Navigate to **Settings** (`/settings`).
3. Locate the **Freeze Days Allowed** setting under Gym Settings.
4. Verify the UI displays the platform cap set by Super Admin (e.g., `Cap: 30 days`).
5. Enter a value within the cap (e.g., `14` days) and save; verify success.
6. Attempt to enter a value higher than the cap (e.g., `45` days); verify the form displays a validation error and blocks saving.

### 4.1 Member Freeze Request

1. Sign in as **Member** on a Growth or Pro tier gym.
2. Navigate to **My Membership** (`/membership`).
3. Click **Request Membership Freeze**.
4. Enter:
   - Start Date: Tomorrow's date
   - Number of Days: `7` (must not exceed gym allowance, e.g., 30 days)
   - Reason: `Traveling for work`
5. Submit the request. Verify status shows `Pending Approval`.

### 4.2 Owner Approval and Subscription Extension

1. Sign in as **Owner** or **Manager**.
2. Navigate to **Freeze requests** (`/freezes`).
3. Review the pending request for 7 days.
4. Click **Approve Freeze**.
5. Verify:
   - The member's subscription expiration date is extended by exactly 7 days.
   - Approving the same request again is blocked.
   - Member's remaining freeze allowance is decremented by 7 days.

### 4.3 Check-in Rejection for Frozen Members

1. When the freeze start date arrives, the member's status transitions to `frozen`.
2. Attempt to check in the member at the entrance scanner or via reception manual override.
3. Verify entry is denied with a clear, distinguishable reason: `Membership is currently frozen`.

### 4.4 Unfreeze Processing

1. To simulate freeze completion, run the unfreeze command:
   ```powershell
   docker compose exec backend python manage.py process_unfreezes
   ```
2. Verify completed freezes return the member's status to `active` and check-in passes are re-enabled.

### 4.5 Ending a Freeze Early (Staff Only)

1. Sign in as **Owner**, **Manager**, or **Reception** at `http://<gym-subdomain>.localhost:5173`.
2. Navigate to **Members** and open the detail modal for a currently frozen member (or go to **Freeze requests** `/freezes`).
3. Click the amber **End freeze early** button on the frozen member's card (or **End Early** in the freezes list).
4. Review the confirmation prompt and confirm.
5. Verify:
   - For an active freeze: actual days used are calculated from the start date to today (minimum 0). The subscription end date is reduced by the unused days, unused days return to the member's freeze allowance, the member's status returns to `active` immediately via the shared status engine, and their QR check-in pass works immediately.
   - For an approved future freeze that hasn't started yet: the freeze is cancelled completely, all extended days are removed from the subscription end date, and full freeze allowance is restored.
   - Idempotency & Concurrency: Clicking the button a second time or running `process_unfreezes` does not shorten the subscription twice or modify allowance again.
   - Audit logging & Notifications: An audit log entry is recorded with actor, member, days used, days returned, and old/new end dates; the member receives an in-app notification confirming the early freeze end.
   - Role enforcement: Members, Trainers, and Super Admin are refused on the server (HTTP 403) and cannot see or use the early unfreeze button.

---

## 5. Online Payment with Mocked Webhooks (Sprint 11)

### 5.0 Chapa Payment Gateway Configuration & Test Connection

1. Sign in as **Owner** at `http://<gym-subdomain>.localhost:5173`.
2. Navigate to **Settings** (`/settings`) and scroll to **Online Payment Gateway (Chapa)**.
3. Observe the notice:
   - With mock ON: `Simulated (mock mode): not checked with Chapa` and `Test environment: payments are simulated`.
   - Explanatory note: "Checks your secret key with Chapa. The webhook secret is confirmed when the first payment arrives."
4. Enter public key (`CHAPUBK_...`), secret key (`CHASECK_...`), and webhook secret. Verify that changing any key immediately resets verification status to "Not configured or unverified".
5. Click **Test connection**.
   - With mock ON: shows `Simulated (mock mode): not checked with Chapa`.
   - With mock OFF: makes an authenticated call to Chapa (`GET https://api.chapa.co/v1/banks`) using the secret key; if valid, status changes to `Verified`. If keys have invalid format or mismatched mode (Test vs Live), distinct plain error messages are displayed before calling Chapa.

### 5.1 Member Plan Selection & Online Checkout

1. Self-register a new member at `http://<gym-subdomain>.localhost:5173/register` and verify email, or sign in as an existing member.
2. If pending (no active plan), observe the prominent banner at the top of the Home dashboard: _"No active plan yet. Choose a plan to start checking in."_ with a direct button to **Choose a plan**.
3. Click the button or navigate to **My membership** (`/membership`).
4. For `pending` or `expired` members, verify the section header is **Choose a plan**; for `active` members, verify it shows **Renew**. If `frozen`, it shows _"Your membership is frozen."_; if `suspended`, _"Please see the front desk."_.
5. Verify the gym's active plans are listed with name, duration, price in ETB, and trainer inclusion.
6. If the gym's online payment is **Verified**:
   - Each plan card includes a **Pay online (Chapa)** button.
   - Below the plan cards, observe: _"Or pay at the front desk with cash or bank transfer."_ (plus gym phone/address if configured).
   - Click **Pay online (Chapa)** on any plan and verify immediate redirect to Chapa's hosted checkout page.
7. If online payment is **Not verified**:
   - Verify that online payment buttons are omitted and the card displays: _"Online payment is not available at this gym. Please pay at the front desk with cash or bank transfer and tell the staff which plan you want."_ (plus gym phone/address if configured).
8. **Final Member Flow (Pay Online, Chapa, Return Page, Confirmed):**
   - Click **Pay online (Chapa)** on any active plan and verify redirect to Chapa's hosted checkout page.
   - Complete payment using Chapa test credentials.
   - Chapa redirects the member back to the gym return URL: `http://<gym-subdomain>.localhost:5173/membership/payment-complete?tx_ref=<reference>` (or in production `https://<gym-subdomain>.<domain>/membership/payment-complete?tx_ref=<reference>`).
   - If the member session expired during checkout, verify they are redirected to `/login` and returned automatically to `/membership/payment-complete?tx_ref=<reference>` after logging in.
   - Observe the return page displaying _"Checking your payment..."_ while polling the member's own payment status every 3 seconds for up to 60 seconds.
   - Once confirmed via webhook, verify the screen updates to: _"Payment confirmed. Your plan is active."_ with working **View receipt** (opens digital receipt modal) and **Go to My membership** buttons.

### 5.2 Signed Webhook Simulation

1. Use the webhook test utility to send a valid HMAC-SHA256 signed Chapa payment confirmation webhook:
   ```bash
   docker compose exec backend python manage.py simulate_chapa_webhook --reference <payment_ref> --status success
   ```
2. Verify the webhook response returns `200 OK`.
3. Check the member dashboard: the subscription is atomically extended, receipt generated, and an in-app payment confirmation notification is received.

---

## 6. Scheduled Daily Maintenance Jobs (Sprint 14)

### 6.1 Idempotent Nightly Sweep

1. In the terminal, execute the daily membership sweep:
   ```bash
   docker compose exec backend python manage.py daily_membership_sweep
   ```
2. Verify the command performs the following actions:
   - Finds subscriptions where `end_date < today` and transitions them to `expired`.
   - Dispatches renewal reminder emails to members whose subscriptions expire within configured reminder days (e.g., 7 days or 3 days).
   - Re-enables passes for members whose scheduled freeze ended.
   - Flags abandoned payments and unreconciled bank transfers.
3. Run the command a second time immediately:
   ```bash
   docker compose exec backend python manage.py daily_membership_sweep
   ```
4. Verify strict idempotency: running twice never sends duplicate reminder emails, never expires twice, and produces zero duplicate notifications.

### 6.2 Suspended and Grace Period Gym Isolation

1. Verify gyms marked as `suspended` or past their platform payment grace period do not dispatch member emails or reminders during the sweep.
2. Verify an alert is logged for platform administrators when a gym's grace period expires, without mid-day operational lockouts.

---

## 7. Notification Center UI (Sprint 15)

### 7.1 Accessible Notification Bell and Badge

1. Sign in as any user (Owner, Manager, Reception, or Member).
2. Look at the top navigation header on the dashboard.
3. Locate the **Notification Bell** icon.
4. Verify an amber or red badge indicates the number of unread notifications.

### 7.2 Dropdown and Prioritization

1. Click the notification bell to open the dropdown menu.
2. Verify:
   - Unread notifications appear at the top with distinct visual highlighting.
   - Each notification shows an icon/tag corresponding to its type (`payment`, `renewal`, `freeze`, `alert`), a descriptive message, and a timestamp.
   - Screen reader attributes (`aria-label="Notifications"`, `aria-expanded`) are present.

### 7.3 Mark as Read & Mark All as Read

1. Click **Mark as read** on an individual notification. Verify its unread dot disappears and the badge count decreases by 1.
2. Click **Mark all as read** at the top of the dropdown.
3. Verify all notifications are marked read, the unread badge clears, and reopening the menu retains read status.
4. Verify gym members only see notifications for their gym, while Super Admin at apex sees only platform-level maintenance alerts.

---

## 8. Email Safety Safeguards (Sprint 9b)

### 8.1 Disposable Email Blocking & Gender Selection on Registration

1. Navigate to the public member registration form at `http://<gym-subdomain>.localhost:5173/register`.
2. Verify the Gender field requires selection of strictly **Female** or **Male** (no 'Other' or 'Prefer not to say').
3. Attempt to register using a known disposable domain (e.g., `user@tempmail.com` or `test@10minutemail.com`).
4. Verify the form rejects the submission with a clear message: `Disposable email domains are not allowed. Please use your personal or business email.`
5. Verify staff creating a member at the front desk are allowed lenient entry if needed, but warned if the address is problematic.

### 8.2 Confirmation of Owner Email on Gym Creation

1. Sign in as **Super Admin** at `http://localhost:5173`.
2. Navigate to **Create Gym**.
3. Enter the gym details and an owner email (e.g., `owner@newgym.et`).
4. Enter a mismatched confirmation email (e.g., `owner2@newgym.et`).
5. Verify the form displays a validation error: `Owner email and confirmation email do not match` and blocks creation until corrected.

### 8.3 Daily 3-Resend Limit & Suppression Check

1. Sign in as **Owner** and view the staff or member invitations list.
2. Click **Resend Invite** for an invited user. Verify the invite is sent.
3. Resend the invite 3 times on the same calendar day.
4. Attempt a 4th resend: verify the system blocks the action with a clear rate limit message: `Daily resend limit reached (3 per day). Please wait until tomorrow.`
5. Simulate a Brevo bounce webhook:
   ```powershell
   # In PowerShell:
   Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/webhooks/brevo/" -ContentType "application/json" -Headers @{ "X-Brevo-Webhook-Secret" = "<configured_secret>" } -Body '{"event": "hardBounce", "email": "bounced@example.com"}'

   # Or using curl in Windows CMD / PowerShell:
   curl -X POST http://localhost:8000/api/webhooks/brevo/ -H "Content-Type: application/json" -H "X-Brevo-Webhook-Secret: <configured_secret>" -d "{"event": "hardBounce", "email": "bounced@example.com"}"
   ```
6. Verify future invite attempts to `bounced@example.com` are suppressed immediately, showing `Email delivery suppressed due to prior bounce`.

---

### 8.4 Demo Request Submission & Return Home

1. Open a browser window to `http://localhost:5173` and click **Request a Demo** (or navigate to `http://localhost:5173/request-demo`).
2. Fill in the demo request form: gym name, contact person, phone number, email, and message.
3. Click **Submit Demo Request**.
4. Verify the confirmation card displays thanking the applicant, does **not** show a "Sign in" or "Submit another" link, and provides a **Back to home** button that navigates directly to `http://localhost:5173` (with auto-redirect after 5 seconds).

---

## 9. Manual Steps Still Pending (Verification Checklist)

The following items are configured with verified mock/console fallbacks in development and are pending final production credentials at staging:

- [ ] **Production SMTP (Brevo)**: Configured via console backend in development; Brevo API key and webhook secret to be set in staging environment.
- [ ] **cPanel UAPI Subdomain Provisioning**: Tested with `MockCPanelUAPIClient`; real token to be supplied in cPanel production environment.
- [ ] **QR Asymmetric Signature Keys**: Local key generator command available; production key pair to be generated and stored in staging `.env`.
- [ ] **Camera Device Permissions**: Verified in modern browsers on localhost/HTTPS; final multi-device physical tablet checks at gym entrance.
- [ ] **Chapa Production Merchant Credentials**: Tested with signed mock webhooks; production live/test keys to be connected when merchant accounts are issued.

---

## Appendix: Time-Dependent Steps (Django Shell Snippets)

To test time-dependent logic without waiting days in real time, use the following Windows-safe PowerShell Django shell snippets to adjust database timestamps:

### A.1 Flagging 7-Day Unreconciled Bank Transfers

Simulate a bank transfer payment recorded 8 days ago that has not yet been reconciled:

```powershell
docker compose exec backend python manage.py shell -c "from datetime import timedelta; from django.utils import timezone; from apps.payments.models import Payment; p = Payment.objects.filter(payment_method='bank_transfer', status='confirmed', reconciled_at__isnull=True).order_by('-created_at').first(); Payment.objects.filter(id=p.id).update(created_at=timezone.now() - timedelta(days=8)) if p else None; print(f'Payment {p.receipt_number} backdated to 8 days ago' if p else 'No unreconciled transfer found')"
```

Then run the flagging command:

```powershell
docker compose exec backend python manage.py flag_unreconciled_bank_transfers
```

### A.2 Ending a Freeze (Scheduled Unfreeze)

Advance an active approved freeze so its end date passed yesterday:

```powershell
docker compose exec backend python manage.py shell -c "from datetime import timedelta; from django.utils import timezone; from apps.memberships.models import MemberFreeze; f = MemberFreeze.objects.filter(status='approved').order_by('-start_date').first(); MemberFreeze.objects.filter(id=f.id).update(start_date=timezone.localdate() - timedelta(days=8), end_date=timezone.localdate() - timedelta(days=1)) if f else None; print(f'Freeze {f.id} backdated to end yesterday' if f else 'No approved freeze found')"
```

Then process the unfreezes:

```powershell
docker compose exec backend python manage.py process_unfreezes
```

### A.3 Expiring a Subscription (Nightly Sweep)

Advance an active subscription so its expiration date was yesterday:

```powershell
docker compose exec backend python manage.py shell -c "from datetime import timedelta; from django.utils import timezone; from apps.memberships.models import MemberSubscription; s = MemberSubscription.objects.filter(status='active').order_by('-created_at').first(); MemberSubscription.objects.filter(id=s.id).update(end_date=timezone.localdate() - timedelta(days=1)) if s else None; print(f'Subscription {s.id} end date set to yesterday' if s else 'No active subscription found')"
```

Then run the daily sweep:

```powershell
docker compose exec backend python manage.py daily_membership_sweep
```

### A.4 Ending a Freeze Early (Day 4 of a 7-Day Freeze)

Simulate a 7-day freeze that started 3 days ago so today is Day 4:

```powershell
docker compose exec backend python manage.py shell -c "from datetime import timedelta; from django.utils import timezone; from apps.memberships.models import MemberFreeze, MemberSubscription; f = MemberFreeze.objects.filter(status='approved').order_by('-created_at').first(); (MemberFreeze.objects.filter(id=f.id).update(start_date=timezone.localdate() - timedelta(days=3), end_date=timezone.localdate() + timedelta(days=3)), MemberSubscription.objects.filter(id=f.subscription_id).update(freeze_start_date=timezone.localdate() - timedelta(days=3))) if f else None; print(f'Freeze {f.id} set to Day 4 (started 3 days ago)' if f else 'No approved freeze found')"
```

Then in the UI, log in as **Reception**, **Manager**, or **Owner**, open the frozen member's details, and click **End freeze early**.
