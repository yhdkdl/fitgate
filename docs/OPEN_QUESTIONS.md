# Open Questions

If less than 90% sure how a requirement should be implemented and the doubt does not touch security, money, tenancy or a conflict with docs/SPEC.md, choose the simplest option consistent with the SPEC, log the question, choice and why here, and continue.

## Decided & Clarifications

1. **Sprint 9 — Audit Log Immutability Enforcement Mechanism**
   - **Question/Context:** Original sprint plan specified a "restricted DB role (INSERT/SELECT only)". On shared hosting (Yegara cPanel) with a single database user, maintaining a second persistent database role or connection is restrictive and brittle.
   - **Chosen Solution:** Enforce immutability inside PostgreSQL via `BEFORE UPDATE`, `BEFORE DELETE`, and `BEFORE TRUNCATE` triggers on the `AuditLog` table that raise an exception on any modification attempt. Raw SQL tests through the application connection will verify these triggers block updates, deletes, and truncates.
   - **Known Limit:** PostgreSQL triggers cannot prevent someone with full owner/superuser privileges from executing `ALTER TABLE ... DISABLE TRIGGER` or dropping the triggers directly.

2. **Sprint 5 — Super Admin Access Scope for Gym Settings and Subdomain Operational Views**
   - **Question/Context:** SPEC §2 Table 3.1a shows '—' for Super Admin under 'Edit gym settings: branding, member reminder days, payment credentials' while Owner is 'Yes'. Does Super Admin have access to edit gym settings or access gym-level views (logo upload, first-run checklist)?
   - **Chosen Solution:** Super Admin access is strictly limited to platform-level apex endpoints (`/api/platform/gyms/<id>/config/`) to modify entitlements (`tier`, `has_*` flags, `freeze_days_allowed`, grace and reminder days). Gym settings (`brand_color`, `member_reminder_days`, `show_unavailable_equipment`, logo) and operational views (`checklist`, `gym-logo`) on gym subdomains are strictly Owner-only. Super Admin is denied (403/401) on gym operational settings views.

3. **Payment Credentials Modification Scope (SPEC §2 Table 3.1a)**
   - **Question/Context:** Table 3.1a indicates Owner can edit payment credentials.
   - **Chosen Solution:** Payment credentials must be Owner-only (never Super Admin), encrypted at rest in `GymPaymentConfig`, and never returned by any API.

4. **Sprint 7 / Increment 1 Review — US Navy Body Fat Estimation for Non-Binary Gender Selections**
   - **Question/Context:** Member registration captures date of birth, gender, and emergency contact. The US Navy circumference body composition formulas require distinct male (neck, waist) and female (neck, waist, hip) biological coefficients. What should be returned when gender is "other", "prefer_not_to_say", or blank?
   - **Chosen Solution:** When gender is "other", "prefer_not_to_say", or missing, `calculate_us_navy_body_fat` returns `None` (estimate unavailable). The API sets `estimated_body_fat_percentage: null` and the UI renders `—`, while BMI (`weight_kg / (height_m^2)`) continues to compute and display normally.

5. **Sprint 8 / Increment 1 Review — Member.get_subscription_period() Fallback Removal**
   - **Question/Context:** `Member.get_subscription_period()` originally defaulted to a synthetic 30-day window (`joined_at` + 30 days) when no `MemberSubscription` record existed. Should attendance calendar logs mark days as absent during this synthetic period?
   - **Chosen Solution:** The arbitrary 30-day fallback has been removed. When a member has no subscription, `get_subscription_period()` returns `(None, None)`. The daily attendance calendar log treats all days outside an active subscription as `"blank"` (neither present nor absent), preventing spurious absenteeism marks for members pending plan activation in Sprint 10.

6. **Sprint 9 / Increment 1 Review Round 3 — Audit Logging Scope: Public Submissions and High-Frequency Operations**
   - **Question/Context:** Which non-GET routes from Sprints 1-8 should write to `AuditLog`, and why are certain endpoints omitted?
   - **Chosen Solution & Policy:**
     - **Anonymous Public Demo Requests (`POST /api/platform/demo-requests/public/`):** Public lead submissions by prospective gym owners on the landing page create `DemoRequest` records. They do not write to `AuditLog` because `AuditLog` is scoped to authenticated actors, tenant state changes, and security events. Logging anonymous public submissions would leave the audit log vulnerable to spam/DDoS storage bloat. When a Super Admin updates a demo request status (`contacted`, `converted`), that administrative action is logged as `demo_request_updated`.
     - **Silent JWT Token Refresh (`POST /api/auth/refresh/`):** Standard DRF SimpleJWT token refresh is a background cryptographic rotation executed repeatedly by frontend clients. Logging every token refresh would bloat the audit log with noise. Genuine authentication events (`user_login`, `logout`, `password_changed`) are logged with full actor and gym context.
     - **Member QR Token Generation (`POST /api/members/me/qr-token/`):** Member dynamic QR tokens rotate every 90 seconds while the member views their pass. Logging each 90-second poll would generate severe database write churn without forensic or compliance utility. The actual state-changing event — physical check-in at the gate — is recorded in `Attendance` and fully logged as `attendance_qr_scan`.

7. **Sprint 7b — Body Measurement Recording for Gyms Without a Trainer**
   - **Question/Context:** Body measurements (weight, height, waist, neck, hip) are recorded exclusively by Trainers. What happens in gyms that currently have no trainers provisioned?
   - **Chosen Solution:** A gym with no trainer cannot record measurements, so BMI, body fat and AI plans show 'not measured yet'. Owner decided: no fallback for now.

8. **Staging Hosting — PostgreSQL 13.23 Compatibility & Version Override**
   - **Question/Context:** Yegara runs PostgreSQL 13.23, which Django 5.2 does not support; we run with a version-check override and the full suite passes on 13.
   - **Chosen Solution & Policy:**
     - The version-check override (`DatabaseFeatures.minimum_database_version = (13,)`) is restricted to production settings (`fitgate.settings.prod`) and opt-in local testing via `ALLOW_POSTGRES_13=1`. It is removed from `base.py`.
     - Before every release, run the suite on a PostgreSQL 13 container:
       ```bash
       docker run -d --name pg13test --network fitgate_default -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=fitgate_test -e POSTGRES_USER=postgres postgres:13-alpine
       docker compose exec -e DATABASE_URL="postgres://postgres:postgres@pg13test:5432/fitgate_test" -e ALLOW_POSTGRES_13=1 backend pytest
       docker stop pg13test ; docker rm pg13test
       ```
     - Ask the host whether PostgreSQL 14+ is available; if yes, remove the override. Pin the Django patch version.

9. **Domain Strategy: Demo/Staging Period and Production Transition**
   - **Question/Context:** Which domain will be used for staging and what is required when switching to a custom production domain?
   - **Chosen Solution & Policy:** Staying on `fitgate.tebebtech.com` for the demo/staging period. Switching to a final domain later is an operations task (update `DOMAIN` in `.env`, rebuild release package, re-provision every gym subdomain via cPanel, re-authenticate email DNS/DKIM for the new domain). No application code change is expected or allowed; nothing may hardcode the domain name. A subdomain re-provisioning management command may be added later.

10. **Check-in Credential Strategy & Architectural Extensibility**
    - **Question/Context:** What check-in credentials are supported in v1, and how will future credentials (NFC cards, biometrics) be supported without destabilizing gate logic?
    - **Chosen Solution & Policy:** Dynamic QR tokens are the sole credential in v1. The check-in pipeline is designed to be credential-agnostic: all entrances flow through a single internal check-in function, and the attendance record stores the method (`method` field: `qr` or `manual_override`). Later credential additions will be supported in this order:
      1. NFC card or wristband using signed cryptographic tags (NTAG 424 DNA, where each tap generates a one-time cryptographic code verified server-side, with tag secrets stored encrypted) read via Web NFC on an Android tablet.
      2. Fingerprint terminal operating as an autonomous device that verifies biometrics locally and calls a device-authenticated backend endpoint.
         Raw-UID RFID cards and cheap keyboard-wedge readers provide only staff-supervised desk convenience and must never be documented or marketed as secure unattended access. No credential table, device accounts, or hardware integrations are introduced in Increment 2.

11. **Notice Board Telegram Channel Bridge**
    - **Question/Context:** How does the gym communicate broadcast announcements to members without relying exclusively on in-app notifications?
    - **Chosen Solution & Policy:** The gym can optionally configure a Telegram channel username in its settings. When staff publish an in-app notice, it is also broadcast to that channel via a platform bot. The in-app notice remains the primary source of truth; Telegram posting is best-effort (failures do not block the in-app notice). Member Telegram user IDs are not collected. WhatsApp integration is not attempted in this version due to API barriers and partial Ethiopia coverage.

12. **Revenue by Plan & Scope of Premium Analytics in v1**
    - **Question/Context:** What metrics constitute premium analytics in this version, and which tiers have access?
    - **Chosen Solution & Policy:** Revenue by plan is categorized as a premium analytics feature, gated exclusively to Growth and Pro tiers (with an upgrade prompt displayed on Starter). In this version, the premium analytics block consists solely of revenue by plan; peak-hours heatmap, cohort retention, and referral analytics are deferred to a future version to prevent heavy aggregation overhead on shared hosting.

13. **Multi-Branch Execution Order and Tier Visibility**
    - **Question/Context:** When is multi-branch built and how is the Pro tier presented to users before multi-branch is implemented?
    - **Chosen Solution & Policy:** Increment 6 (Multi-Branch, Sprints 30–34) is kept as an optional final increment to be executed after Increment 7, depending on remaining timeline (decision date to be set by the project owner). Until Increment 6 ships, the Pro tier is not offered, advertised, or selectable: it is hidden from the public landing page and the Create Gym form. The tier value and flags remain in the database schema (Pro defaults equal Growth, with `has_multi_branch=false` until Increment 6 lands). If multi-branch does not ship, the product deploys smoothly with two tiers and no wasted effort.

14. **Member Status Single Source of Truth & 'Pending' State**
    - **Question/Context:** Where does member status come from, how does it stay accurate, and how are new members without subscriptions represented?
    - **Chosen Solution & Policy:** A fifth status value, `pending`, is added to represent registered members who do not yet have an active subscription. `MemberSubscription` is the single source of truth for membership standing. `Member.status` remains a stored, indexed column but is strictly derived: only one shared function updates it, computing the value directly from the member's subscription in the same transaction as every subscription change (purchase, renewal, freeze, unfreeze, expiration, suspension). Check-in never trusts static `Member.status`: it inspects the member's active subscription and dates directly, refusing pending members with a distinct plain message ("no active plan yet"). Sprint 10 will record the full implementation details and reasons when it runs.

15. **Notification Architecture & Increment 2 Verification**
    - **Question/Context:** How can acceptance criteria in Sprints 11 to 13 that require someone to be "notified" be verified before Sprint 15 (Notification center) is built, given that automatic emails are blocked until Sprint 9b?
    - **Chosen Solution & Policy:** Sprint 11 creates the database `Notification` record (platform-level/tenant base class, nullable `gym_id`, recipient FK to `User`, title, message, read flag, timestamps) and ONE shared internal helper function to record notifications. This helper strictly stores database rows (scoped to the recipient and gym) and sends no emails. Wherever Sprints 11, 12, and 13 require a notification, criteria specify that "a notification is recorded for X", making the behaviour testable and verifiable immediately. Sprint 15 is then dedicated to user-facing screens (bell icon, unread count badge, notification list modal/view, mark-as-read) and any missing UI interactions.

16. **Sprint 10: Member Status Single Source of Truth & 'Pending' State Implementation**
    - **Question/Context:** Where does member status come from, how does it stay accurate, and how are new members without subscriptions represented?
    - **Chosen Solution & Policy:** `MemberSubscription` is the single source of truth for membership status. `Member.status` is a derived and indexed column written exclusively by `update_member_status()`. Direct writes to `Member.status` raise `ValueError` on `save()`. A 5th choice `pending` was added to `Member.status` and `MemberSubscription.status` for newly registered members prior to subscription purchase. Check-in directly checks `MemberSubscription` validity and dates, refusing pending members with 'No active plan yet.' (reason='pending').
    - **Reason for choice:** Eliminates split-brain status bugs where `Member.status` drifts from subscription records while preserving fast indexing and query capability. Check-in directly validates `MemberSubscription` dates to prevent clock skew or stale flags from granting unauthorized physical access. No reasons were found against this design.

17. **Subscription Creation Pathways & Payment Binding**
    - **Question/Context:** Can staff create or renew member subscriptions arbitrarily without a payment, or what are the authorized pathways for subscription creation and renewal?
    - **Chosen Solution & Policy:** Subscriptions must never be creatable or renewable by staff or any standalone API endpoint without a recorded payment. The internal service `create_or_renew_subscription()` is kept strictly as an internal service. The ONLY paths that create or renew a subscription are: (a) a verified Chapa payment confirmation (Sprint 11), (b) a staff-confirmed cash payment (Sprint 12), and (c) a staff-confirmed bank-transfer payment (Sprint 12b), each executed in the exact same database transaction as its corresponding payment record.
    - **Reason for choice:** Enforces strict financial accounting integrity; prevents staff from granting unearned gym access or creating subscriptions without an audit trail of confirmed revenue.

18. **Member Bank Transfer Payments, Owner Reconciliation, and Immutable Reversal (Sprint 12b)**
    - **Question/Context:** Why is bank transfer enabled for members, reversing the earlier "no bank transfer for members" rule, and how are fraud and reconciliation handled?
    - **Chosen Solution & Policy:**
      - In Ethiopian gyms, direct mobile/bank transfers (CBE Birr, Telebirr, Awash, etc.) are standard practice among members. Excluding bank transfer would force all non-Chapa members to bring physical cash.
      - To preserve front-desk operational velocity, staff record the payment with bank transaction reference and transfer date, activating the subscription immediately.
      - Every bank-transfer payment starts as "unreconciled". Only the gym Owner can clear transfers against bank statements (individually or in bulk). Payments recorded by the Owner auto-clear.
      - A daily cron command flags unreconciled transfers older than 7 days, sets a flagged timestamp once, notifies the Owner with a single count summary, and writes an audit log naming confirming staff.
      - The Owner can reverse an unreconciled transfer with a 5-500 character reason. Reversal is recorded in an immutable DB table (`PaymentReversal` with database triggers preventing update/delete), marks the receipt as reversed, excludes the payment from ledger revenue, and restores the subscription to its exact previous state (pending for first purchase, previous end date/status for renewal). Reversal is refused if subsequent payments, freezes, or subscription changes have occurred.
    - **Reason for choice:** Solves real Ethiopian gym payment dynamics while providing strict financial controls against fake SMS/uncredited transfers through Owner-only reconciliation, immutable reversals, and complete state restoration.

19. **Item 12: Owner Freeze Days Setting Gated by Super Admin Entitlement Cap**
    - **Question/Context:** How does the gym owner configure freeze days allowed, and how does the platform prevent owners from offering excessive freeze durations beyond platform policy?
    - **Chosen Solution & Policy:** `GymConfig.freeze_days_cap` is introduced as a Super Admin-only entitlement field (default 30 days). The gym Owner can configure `GymConfig.freeze_days_allowed` in Gym Settings up to `freeze_days_cap`. The owner cannot exceed this cap (validated with 400 Bad Request); attempting to modify `freeze_days_cap` directly returns 403 Forbidden.
    - **Reason for choice:** Allows gym owners operational flexibility to define freeze terms for their members while giving platform super admins contractual control over freeze limits per tier.

20. **Item 13: Gender Field Requirements & Allowed Values**
    - **Question/Context:** What are the permitted gender values for member registration, and is gender mandatory?
    - **Chosen Solution & Policy:** Member registration requires gender to be provided as either "Female" or "Male" (`female` / `male` in backend enum). Ambiguous and non-binary options ("other", "prefer_not_to_say") were removed per owner requirements to simplify physical facility management and ensure deterministic US Navy body fat estimation.
    - **Reason for choice:** Gym operations in Ethiopia require binary gender segregation for certain facilities/classes and body composition calculation requires biological gender formulas.

21. **Item 14: Member Self-Profile Lockdown**
    - **Question/Context:** Can members edit their personal profile information (name, phone, email, photo) directly via self-service?
    - **Chosen Solution & Policy:** Members are locked down from editing their profile fields (`full_name`, `phone`, `email`, `photo`). `PATCH /api/auth/me/`, `PATCH /api/members/me/`, and `POST /api/media/member-photos/{gym_id}/` strictly reject member role requests with 403 Forbidden. Members may only change their password via `/api/auth/change-password/`. Only authorized gym staff (Owner, Manager, Reception) can update member details or upload/change member photos.
    - **Reason for choice:** Prevents identity spoofing, member credential sharing, unauthorized photo changes to bypass front-desk identification, and audit trail circumvention.

22. **Item 16: Upfront Payment During Staff-Assisted Member Registration**
    - **Question/Context:** Can staff collect payment and activate a membership plan immediately when registering a new member at the desk?
    - **Chosen Solution & Policy:** The staff member registration endpoint (`POST /api/members/`) supports optional upfront payment data (`plan_id`, `payment_method` [cash/bank_transfer], `reference_number`, `proof_screenshot`, `amount`). When provided, member creation, subscription activation, payment recording, and digital receipt generation execute in a single atomic database transaction. If omitted, the member is registered in `pending` status as before.
    - **Reason for choice:** Streamlines front-desk onboarding by eliminating redundant steps: receptionist registers the walk-in member and records their cash or bank transfer payment in a single action.

23. **Item 17: Public Gym Payment Configuration Status**
    - **Question/Context:** Can unauthenticated public clients (e.g. prospective members registering self-service) discover what payment methods a gym accepts?
    - **Chosen Solution & Policy:** `GET /api/payments/public-status/<gym_id>/` is introduced as a public, unauthenticated endpoint. It returns public payment acceptance flags (`accepts_cash`, `accepts_bank_transfer`, `bank_account_name`, `bank_account_number`, `bank_name`, `chapa_active`). It strictly excludes secret credentials, API keys, or merchant tokens.
    - **Reason for choice:** Allows member registration and payment landing flows to render appropriate payment options and transfer instructions without exposing sensitive credentials or requiring prior authentication.

24. **Item 21: Bank Transfer Payment Proof Screenshot Upload**
    - **Question/Context:** How do staff or members provide proof of bank transfer during payment recording?
    - **Chosen Solution & Policy:** `Payment.transfer_screenshot` stores a secure relative path to uploaded transfer confirmation screenshots (Telebirr/CBE Birr transaction confirmation screens). The endpoint `POST /api/payments/bank-transfer-screenshot/` handles secure upload, image validation (max 5MB, JPEG/PNG/WebP), and encrypted tenant storage. Screenshots are served only to authorized staff via authenticated media streaming.
    - **Reason for choice:** Provides verifiable proof for owner reconciliation and dispute resolution when clearing bank transfers.

25. **Trainer Default Client Capacity (Sprint 16)**
    - **Question/Context:** SPEC §8 defines `Trainer` with `max_clients`, but does not specify a numerical default.
    - **Chosen Solution:** Default `max_clients` is set to 20 for newly provisioned trainer profiles, with an allowed range of 1 to 200, editable by Owner and Manager.
    - **Reason for choice:** 20 provides an operationally sensible client cap for individual trainers while preventing unbounded assignment overload.
26. **Trainer Assignment Lifecycle & Subscription Expiry (Sprint 17)**
    - **Question/Context:** What happens to an active `TrainerAssignment` when a member's subscription expires or ends?
    - **Chosen Solution:** An active assignment remains open until the trainer-inclusive subscription expires, ends, or is manually reassigned by Owner/Manager. On renewal of a trainer-inclusive plan, the existing assignment is preserved without triggering reassignment. If an assignment is manually changed or the trainer is deactivated with client reassignments, the prior assignment is closed (`ended_at` set to current timestamp) and the new assignment is opened atomically.
    - **Reason for choice:** Preserves trainer-client continuity across standard renewal cycles while ensuring client counts accurately reflect active assignments.

27. **Item 27: Ending a Freeze Early by Staff**
    - **Question/Context:** Can a member's approved or active membership freeze be terminated before its scheduled end date, and who is authorized to do so?
    - **Chosen Solution & Policy:** Authorized gym staff (Owner, Manager, Reception) of the same gym can end a member's freeze early via `POST /api/gym/freezes/<id>/end-early/` or `POST /api/gym/members/<id>/end-freeze-early/`. For an active freeze (`today >= start_date`), actual days used are calculated as `(today - start_date).days` (minimum 0). Unused days (`original_days - actual_days_used`) are deducted from the subscription end date and returned to the member's annual freeze allowance (`freeze.days = actual_days_used`), with the member returned to `active` status immediately via `update_member_status()` and their QR check-in pass reactivated immediately. For an approved future freeze (`today < start_date`), it is cancelled completely with all extended days removed and full allowance restored. The action is row-locked (`select_for_update`), idempotent against repeat clicks and cron sweeps, audit-logged, and dispatches an in-app notification to the member. Members, Trainers, Super Admin, and other gyms are refused (403).
    - **Reason for choice:** Real gym members frequently return to training early. Allowing front-desk staff to reactivate passes immediately without losing unused freeze allowance provides fair customer experience while preserving strict audit and financial integrity.
