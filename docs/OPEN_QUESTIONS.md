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

28. **Item 28: Increment 4 AI Personal Training Flow & Safety Architecture**
    - **Question/Context:** How should fitness profile intake, plan generation, trainer review, weekly check-in, and AI provider interaction be structured to keep the trainer in full professional control while protecting free tier API quotas and member privacy?
    - **Chosen Solution & Policy:**
      - **Fitness Profile Intake:** The assigned trainer captures the profile directly on the client's page during the first visit (in a "Fitness profile" section next to measurements), replacing registration capture. Owner/Manager can view/edit; Member has read-only visibility on their own page; unrelated trainers, Reception, Super Admin, and other gyms receive 403. Height, weight, body fat %, lean body mass, and resting heart rate are read strictly from latest trainer measurements and never retyped.
      - **One Week Per Plan (Monday-Anchored):** Plans cover a single week (`week_start_date` on Monday) with sessions named Session A, Session B, etc. (one per training day, not bound to specific weekdays). Mid-week joiners receive a plan for the current week immediately with default intensity for their phase.
      - **Plan Generation & Safety:** Assigned trainer or Owner/Manager clicks "Generate plan" (members/reception refused 403). Only plain, non-identifiable demographic and biometric data are passed to the AI (age, gender, goal, fitness level, training days, session length, equipment, limitations, dietary notes, trainer note, latest measurements; name, phone, email, and member ID are strictly excluded). Free-text fields are sanitized and treated as data, not instructions. Output must conform to fixed JSON schema or count as a provider failure.
      - **Draft Limits & Quotas:** At most 3 drafts per member per plan week (initial + 2 regenerations). On draft 3, rejection is blocked and the trainer must edit and approve directly ("Edit this draft yourself"). Only one open pending draft per member per week. A gym-wide rate limit of 20 generations per hour prevents quota exhaustion.
      - **Trainer Review & Audit Logging:** Drafts are saved as `pending_review` and completely hidden from members until approved. Trainers can edit exercises and nutrition directly before approving. Rejections require a written reason (5–500 characters) which triggers one new draft. Editing, approval, and rejection are audit-logged (including `was_edited` flag). Members see only the current week's approved plan (or previous approved plan labelled with week if new week is pending; otherwise "Waiting for your trainer").
      - **Decoupled Weekly Check-In:** Monday check-in (energy, recovery, motivation 1–5) adjusts the rules engine intensity for future generations and notifies the trainer; it does not automatically generate plans.
    - **Reason for choice:** Establishes the AI as a capable assistant rather than an autonomous substitute, ensuring professional oversight, preventing hallucinated or unsafe exercise recommendations, complying with data privacy, and guarding system resources.

29. **Item 29: Fitness Profile Selectable Lists, Medical Caution, and Structured Review Actions**
    - **Question/Context:** How should health limitations, equipment access, dietary choices, weekly trainer focus, and rejection reasons be standardized across frontend and backend to eliminate free-text inconsistency, ensure deterministic rules engine exclusions, and protect member health?
    - **Chosen Solution & Policy:**
      - **Selectable Lists:** Health limitations, equipment access, and dietary notes are stored as lists of standard codes with optional 'other' text (max 200 chars). Server enforces authoritative validation. 'None' / 'No restrictions' are mutually exclusive with specific codes.
      - **Medical Caution Notice:** If cardiovascular, metabolic, respiratory, pregnancy, or recent surgery codes are selected (`heart_condition`, `high_blood_pressure`, `diabetes`, `asthma`, `pregnancy_postpartum`, `recent_surgery`), an alert banner ("Confirm with the member's doctor; review plans for this member extra carefully") is displayed on profile entry and plan review screen; it never blocks plan creation.
      - **Deterministic Rules Engine Exclusions:** Body-area limitation codes exclude matching exercise categories (e.g. `lower_back` excludes axial spinal loading such as barbell back squat and deadlift; `shoulder` excludes strict barbell overhead press; `knee` excludes heavy fixed leg press). Equipment codes define allowable exercise types combined with gym maintenance status. 'Other' text is treated as plain data passed to AI, never as instructions.
      - **Weekly Focus & Rejection Checklist:** Weekly note is replaced with 'Focus this week' multi-select (`no_focus`, `legs`, `upper_body`, `core`, `cardio`, `mobility`, `other`). Plan rejection uses a mandatory checkbox list (`too_hard`, `too_easy`, `exercises_not_suitable`, `equipment_not_available`, `nutrition_not_suitable`, `other` + required 5–200 char text).
    - **Reason for choice:** Standardized codes prevent prompt injection, guarantee deterministic exercise filtering, and ensure safety warnings are reliably triggered without relying on unstructured AI interpretation.

30. **Item 30: Deferral of Member Weekly Check-in & Streamlined Sprint 24 Scope (November 1, 2026)**
    - **Question/Context:** Why are the member Monday check-in form, trainer notification on check-in submission, Monday evening reminder, and check-in driven dynamic intensity adjustment deferred to future work, and how does plan intensity compute in this release?
    - **Chosen Solution & Policy:**
      - The weekly member check-in form (energy, recovery, motivation ratings 1–5), the trainer notification upon check-in, the scheduled Monday reminder, and dynamic check-in intensity adjustments are moved to 'Deferred to Future Work' (SPEC §10).
      - Intensity is determined deterministically by the training phase and fitness level; trainers adjust intensity directly by editing the draft prior to approval.
      - The adaptive intensity strategy in the rules engine and its tests are retained, ready for future check-in integration, but not wired to member-facing forms or runtime plan generation.
      - Sprint 24 scope is trimmed to the Trainer Overview card and client list ('Clients with no approved plan this week') showing clients without an approved plan for the current Monday-anchored week, with distinct statuses ('No draft yet' vs. 'Draft waiting for your review') linking directly to each client's plan screen.
    - **Reason for choice:** Reduces complexity and member-side friction for Increment 4 launch while preserving trainer oversight, direct draft editing controls, and full architectural readiness for check-ins in a future release.

31. **Item 31: Plan Upgrade with Prorated Credit (Sprint 12c)**
    - **Question/Context:** How are mid-subscription plan changes handled for active gym members wanting to move to a higher-priced plan (e.g. standard to trainer-inclusive)?
    - **Chosen Solution & Policy:**
      - **Prorated Credit:** Server-only quote calculation: `Credit = floor(net_paid_for_current_sub * remaining_days / total_days)` to 2 decimals. Whole days where `used_days = today - start_date`, `remaining_days = total_days - used_days`. Client-submitted credit/net fields are completely ignored.
      - **Strict Upgrade Gate:** New plan price must be strictly greater than current plan price. Lower or equal-price different plans are refused with: `"This plan costs less than your current one. It can start when your current plan ends on <date>."` Same plan is treated as normal renewal.
      - **Status Transitions:** Old subscription ends immediately with new status `superseded`. New subscription starts on the upgrade date for its full duration. Member status is recalculated strictly through `update_member_status()`. Check-in, attendance, sweep, and renewal reminders ignore superseded subscriptions.
      - **Financial Integrity:** Payment records gross amount, credit amount, and net cash received. The sequential digital receipt displays all three. Revenue totals and revenue by plan track net cash received. No cash refunds: net amount <= 0 is refused. Upgrade payments cannot be reversed by bank transfer reversal.
      - **Chapa In-Flight Protection:** The quote is locked on payment creation. If the member's situation changed before webhook arrival (frozen, suspended, or subscription changed), the payment is captured, not activated automatically, and flagged for Owner resolution via notifications without loss of funds.
    - **Reason for choice:** Replaces complex refund-and-repurchase workflows with a clean, immutable accounting model that protects gym revenue, eliminates double-counting, prevents downgrade fraud, and honors already-paid subscription value.

32. **Item 32: AI Generation Reliability, Single Shared Lists, and Lightweight Failure Accounting**
    - **Question/Context:** How do we ensure high AI generation success rates, synchronize list options across client and server without mismatch crashes, and monitor failures without bloating audit tables and owner notification inboxes?
    - **Chosen Solution & Policy:**
      - **Single Shared Choice Lists:** The server is authoritative for 5 standardized choice lists: weekly focus (`no_focus`, `legs`, `upper_body`, `core`, `cardio`, `mobility`, `other`), health limitations (15 codes + other), equipment access (8 categories + other), dietary notes (11 restrictions + other), and rejection reasons (`too_hard`, `too_easy`, `exercises_not_suitable`, `equipment_not_available`, `nutrition_not_suitable`, `other` + 5–200 char note). Unagreed options like "Wrong Phase" are removed. Frontend interfaces consume these identical definitions, sending valid server codes.
      - **Lenient Output Parsing & Strict Safety Gate:** Strips markdown code fences (`json ... `) and surrounding conversational text from AI responses before parsing. Tolerates numbers as strings or vice-versa (`sets`, `reps`, `rpe`, `rest_seconds`), defaulting optional notes to empty string and missing rest to 60 seconds. Strictly rejects as failure: wrong session counts, empty sessions, excluded exercises/equipment based on member limitations, missing nutrition guidance, and numeric calorie precision.
      - **Ordered Model Fallback & Rate-Limit Retry:** Providers are ordered by live empirical success rate. On HTTP 429 rate limits, the provider pauses 2 seconds and retries the same model once before moving down the fallback chain.
      - **Failure Accounting Without Bloat:** Per-attempt audit log rows and per-attempt owner notifications are eliminated. Audit logs are preserved strictly for significant domain events: draft created, edit, approval, rejection. Provider failures increment an atomic daily counter (`AIDailyFailureCounter`) per model per reason per day (zero PII), automatically pruned after 30 days by the nightly maintenance command. If all attempts in a request fail, at most ONE summary notification per gym per day is delivered to the Owner ("Plan generation had problems today. Trainers can retry later.").
    - **Reason for choice:** Eliminates UI crashes caused by divergent codes, dramatically increases live generation resilience against benign model quirks while maintaining strict injury safety, and prevents database table explosion from high-frequency failure logging on shared hosting.

33. **Item 33: Increment 5 Architectural and Policy Decisions (November 1, 2026)**
    - **Question/Context:** What architectural, security, and algorithmic decisions govern equipment management, dashboard analytics, notice broadcasts, CSV export, and expense tracking?
    - **Chosen Solution & Policy:**
      - **Equipment Registry & AI Wiring (Sprint 25):** Equipment category is required and chosen from the rules engine's equipment catalog (`barbell`, `dumbbells`, `cable_machine`, `resistance_bands`, `kettlebells`, `pull_up_bar`, `bench`, `leg_press`, `squat_rack`, `cardio_machines`, `bodyweight`, `other`). Name is free text (2–100 chars, letters/digits/spaces/hyphen/apostrophe/period). Quantity is 0–10,000; min quantity optional (0–10,000) triggering low-quantity alert when <= min threshold. Issue reporting uses a fixed checklist (`broken`, `worn_out`, `noisy_unsafe`, `other` with short text up to 200 chars). Usable equipment for AI plan generation is gym registry items with condition `good` or `needs_maintenance` and quantity > 0, mapped through category and intersected with member profile equipment access. If the gym has no registry items, gym-side filtering is OFF (member profile alone decides).
      - **Dashboard Analytics (Sprint 27):** Owner and Manager only (all other roles refused 403). Active members count derived `active` status (`frozen` shown separately). Today's check-ins use `Africa/Addis_Ababa` calendar day. Monthly revenue counts confirmed NET cash received this calendar month (including upgrade net amount, excluding reversed payments). Expiring memberships count active subscriptions ending in <= 7 days with no queued following renewal. Superseded subscriptions are never counted. Revenue by plan is Growth/Pro only (`has_analytics=True`), with Starter seeing an upgrade prompt. Seeded benchmark (1,000 members, 1 year attendance) executes in under 3 seconds.
      - **Notice Board & Telegram Bridge (Sprint 28):** GymNotice model stores notices (title up to 100 chars, body up to 1,000 chars) displayed on member Home and Notices screens; individual notification rows are NOT created per member. Optional Telegram channel (@name, 5–32 chars) configured in Gym Settings with "Send test message" button. Platform bot token `TELEGRAM_BOT_TOKEN` read from environment. Development uses a mock sender; failures or missing tokens do not block in-app notice creation.
      - **CSV Export Scoping & Formula Injection Protection (Sprint 29):** Owner and Manager only, audit-logged with export type and row count. UTF-8 BOM (`\ufeff`) ensures correct Amharic rendering in Excel. All cell values starting with `=`, `+`, `-`, or `@` receive a leading apostrophe (`'`). Members export strictly excludes health limitations, dietary notes, measurements, and photos. Optional date range is capped at 1 year.
      - **Expenses & Void Lifecycle (Sprint 29a):** Owner and Manager log expenses with amount (> 0 up to 10,000,000 ETB), category (`rent`, `salaries`, `utilities`, `equipment`, `maintenance`, `marketing`, `supplies`, `other`), optional note (up to 500 chars), and date (not in future). Mistakes cannot be hard-deleted: they are voided (`is_void=True`), retained for audit, and excluded from totals. Net income combines confirmed net payments minus active expenses for the period.
    - **Reason for choice:** Enforces strict role access, prevents formula injection and memory exhaustion on export, aligns AI equipment filtering with actual gym inventory, and provides an immutable financial audit trail.

### Decision: Equipment Registry Completeness, AI Plan Sources, Price Tracking, and Privacy (November 2, 2026)

- **Question:** How does the gym equipment registry integrate with member profile equipment during AI training plan generation?
- **Decision:**
  1. Default mode (setting off): If registry has items, unusable items (under maintenance / out of service) are removed from the member's profile equipment selection. If registry is empty, profile equipment is used directly.
  2. Complete registry mode: Gym Owner enables "My equipment list is complete" in Gym Settings (`is_equipment_list_complete`, default off). Plan generator intersects profile equipment with registered usable equipment (good or needs maintenance with quantity > 0, matched by category). Bodyweight exercises are always permitted.
  3. Visibility & Audit: Review screen surfaces `Equipment source: member profile only | gym registry (unusable items removed) | gym registry (complete list)`. Equipment registry displays `Categories registered: x of y`.
  4. Investment tracking: Equipment includes optional unit purchase price (ETB, > 0, max 10,000,000.00, 2 decimals). Equipment screen shows `Total investment` (sum of price x quantity) and `N items have no price`. Restricted exclusively to Owner and Manager roles. Price updates are audit-logged.
  5. Member view: Members view usable equipment unless Owner setting "Members see unavailable equipment" is enabled. Members never see maintenance notes, serial numbers, or prices.

- **Sprint 28 Notice Board & Telegram Channel Bridge (November 2, 2026):** Confirmed implementation decisions:
  - Notices stored in `GymNotice` model with `title` (2–100 chars) and `body` (5–1,000 chars), scoped to the gym. Members see notices on Home and dedicated Notices views without per-member Notification rows.
  - Gym-level Telegram channel configured on `GymConfig.telegram_channel` in `@channel_name` format with "Send test message" action. Uses platform bot token `TELEGRAM_BOT_TOKEN`.
  - Development and automated tests use a mock sender recording messages in memory; failure to deliver to Telegram never prevents in-app notice publication.

34. **Item 34: Sprint 26 Lean Group Classes Architecture & Rules (November 3, 2026)**
    - **Question/Context:** How are group class scheduling, capacity limits, member bookings, and class attendance architected without bloating recurrence engines or polluting daily facility check-ins?
    - **Chosen Solution & Policy:**
      - **Lean Session Model (`ClassSession`):** Includes `title` chosen from fixed list (`yoga`, `zumba`, `spinning`, `boxing`, `aerobics`, `crossfit`, `strength_circuit`, `stretching_mobility`, or `other` with `other_title` up to 50 chars), `trainer` (must belong to same gym and have `Trainer.status='active'`), `start_time` (timezone `Africa/Addis_Ababa`, cannot be in past at creation), `duration_minutes` (choice of 30, 45, 60, 90), `end_time` (computed), `capacity` (integer 1 to 200), and `status` (`scheduled`, `cancelled`).
      - **Creation & Weekly Repeat:** Owner and Manager can create and edit sessions. Option 'Repeat weekly for N weeks' (1 to 12) generates N distinct, separate session records immediately. No recurrence engine is used.
      - **Overlap Prevention:** A trainer cannot be scheduled for two overlapping sessions (start-to-end windows overlap); creation or update is refused naming the conflicting time window. A member cannot book two overlapping sessions; booking is refused naming the conflict.
      - **Concurrency & Row Locking (`select_for_update`):** Booking executes inside an atomic transaction with `ClassSession.objects.select_for_update()`. If active bookings count equals or exceeds capacity, booking is rejected ("Class is full").
      - **Booking Eligibility & Cancellation Window:** Active members can book scheduled future classes; non-active members are refused with a clear status reason. One active booking per member per session. A member can cancel their own booking up to 2 hours before the start time. Reception, Manager, and Owner can book or cancel on behalf of a member at any time before session start.
      - **Attendance Separation:** Trainer, Owner, and Manager can mark booked members as `attended` or `not attended` from the class start time until 24 hours after the class ends. Marking class attendance updates `ClassBooking.attended` and does NOT create daily `Attendance` check-in rows, leaving dashboard check-in totals unaltered.
      - **Tier Gating (`has_group_classes`):** Enabled for Growth and Pro tiers; disabled for Starter tier. Direct API calls from Starter gyms receive 403; frontend navigation and actions are hidden. Super Admin and cross-tenant users are denied access.
    - **Reason for choice:** Provides a rock-solid, concurrent booking workflow that prevents overbooking and scheduling conflicts while keeping the implementation lean, avoiding complex recurring event state machines, and maintaining clean separation between facility check-ins and class participation.

35. **Item 35: Owner Switch for Online (Chapa) Payments Architecture & Lifecycle (November 3, 2026)**
    - **Question/Context:** How is the "Accept online payments (Chapa)" switch managed, what does it control, and how are in-flight transactions protected?
    - **Chosen Solution & Policy:**
      - **Dedicated Toggle on `GymPaymentConfig`:** Added `is_enabled` (boolean, default True). Configurable by Gym Owner and Super Admin in Gym Settings, completely independent of key storage.
      - **Verification Pre-condition:** Turning the switch ON is refused with `"Verify your Chapa connection first."` unless `is_verified` is true. Turning the switch OFF keeps keys and verification status intact.
      - **Enforcement & Refusal:** When OFF, every new online Chapa checkout (new subscription, renewal, upgrade) is refused on the server with `"Online payment is not available at this gym. Please pay at the front desk."` Frontend screens hide "Pay online" buttons and show this message in the upgrade modal and pending-payment card. The public payment status reports online as unavailable.
      - **Continuity for In-Flight Payments:** Payments initiated prior to turning the switch off continue to process through webhooks, verification checks, the 5-minute abandoned-payment sweep, and unresolved review flows. Cash and bank transfer remain unaffected for all roles.
      - **Audit Logging & Accounting:** Switch transitions are audit-logged (`online_payments_toggled`) with actor, prior and new states. When turning off, the response reports the number of unfinished online payments currently pending.
    - **Reason for choice:** Gives gym owners operational control over accepting digital payments without losing configured credentials or interrupting in-flight member transactions.

36. **Item 36: Sprint 12d Direct Bank Receipt Verification Architecture & Risk Controls (November 3, 2026)**
    - **Question/Context:** How is automatic bank receipt verification implemented without sending gym bank accounts and member receipt references to third-party services, how are unannounced bank endpoint changes handled, and how does the review queue protect against concurrency and flood attacks?
    - **Chosen Solution & Policy:**
      - **Zero Third-Party Data Leakage:** The Python package `cheki` (MIT licence, exact version `1.6.0` pinned, released October 19, 2026) is used strictly in its direct verification mode (`cheki[direct]`). Direct mode executes direct HTTPS requests from our backend container to the bank/telecom provider's own public web endpoints (`https://mb.cbe.com.et/api/v1/transactions/public/transaction-detail/<id>` for CBE, `https://transactioninfo.ethiotelecom.et/receipt/<ref>` for Telebirr). No data leaves to `cheki.et` or any third-party hosted service.
      - **Swappable Verifier & Mock Strategy:** Verification is isolated behind a swappable interface (`BankReceiptVerifier`). A mock verifier (`MockBankReceiptVerifier`) is active in development and all automated tests, providing deterministic responses based on mock reference prefixes (`MOCK-VERIFIED`, `MOCK-MISMATCH`, `MOCK-ERROR`). The real direct verifier is invoked only at staging/production when `RECEIPT_VERIFICATION_ENABLED=True`.
      - **Platform Kill Switch & Host Change Risk:** Unofficial bank web pages may change or go down without notice. A platform-level kill switch in the environment (`RECEIPT_VERIFICATION_ENABLED`, default False) can instantly disable bank receipt checks across the entire platform. When disabled or when a check fails, the gym's fallback policy ensures payments are never permanently trapped.
      - **Timing, Timeout, & Platform Rate Limiting:** All lookups execute BEFORE opening the database transaction and never while holding a row lock. Single lookup with strict 8-second timeout, no in-request retries. Reference syntax is validated against bank patterns before dispatch. A platform-wide limit of 20 lookups per minute uses a database rate counter; exceeding requests fail-open to "could not check".
      - **Outcome Mapping & Review Queue:**
        1. `VERIFIED`: Auto-reconciled (`is_reconciled=True`, badge "Verified by bank receipt"), activates immediately, no statement reconciliation needed.
        2. `COULD NOT CHECK`: Under default policy `activate_and_reconcile_later`, activates immediately as unreconciled for the Owner; under `hold_for_approval`, enters `pending_review`.
        3. `MISMATCH`: Activates nothing. Reception sees side-by-side comparison, uploads required receipt photo, and submits to Owner/Manager queue as `pending_review`.
      - **Review Queue Integrity:** Owner and Manager only (Reception and Super Admin denied 403). Concurrency row locking (`Payment.objects.select_for_update()`) prevents duplicate decisions. Approved payments activate atomically, issue next sequential receipt, and verify in-flight member state. Declined payments release the reference for member retry without consuming receipt numbers. Members cannot check in while in queue. Max 2 open review items per member server-enforced to prevent flood attacks. Items in `pending_review` and `declined` are excluded from revenue, dashboard metrics, CSV exports, receipt sequences, and 7-day sweeps.
    - **Reason for choice:** Guarantees absolute tenant and financial data privacy, eliminates third-party dependencies, protects against bank scraping flakiness, and provides rock-solid concurrency and financial controls.

37. **Demo Gym Reset: Archive-and-Recreate vs. Database Trigger Exception (November 3, 2026)**
    - **Question/Context:** Re-running the demo seed command needs to reset demo data, but receipts and audit log rows are protected by immutable database triggers preventing update and delete.
    - **Chosen Solution & Policy:** Archive and recreate. Re-running the demo command renames the old demo gym's subdomain to `demo-archive-N` (database only), renames its users' emails to archived addresses, marks it `is_demo=True` and `status='terminated'`, and provisions a new demo gym on subdomain `demo` with a fresh receipt counter starting at `REC-000001`. `tls_confirmed_at` is carried over. No trigger bypass or conditional exception is introduced, ensuring triggers remain universally immutable and non-demo gyms are mathematically untouched.
    - **Proof of Tenant Safety:** Tested by seeding an ordinary gym before re-running demo seed, asserting every row of the non-demo gym is byte-for-byte identical before and after.

38. **Gym Termination vs. Scheduled Data Purge (November 3, 2026)**
    - **Question/Context:** In Sprint 35, gym termination becomes a real end state for suspended gyms whose 7-day export window has elapsed. Should terminated gym rows be purged automatically on a schedule?
    - **Chosen Solution & Policy:** A scheduled purge is NOT built in this version. Receipts, payments, reversal rows, and audit logs are protected by database triggers and foreign keys. Digital receipts are immutable and contain names; financial transactions carry legal record-retention requirements under commercial law. A future purge mechanism must anonymize personal data (names, phones, emails, photos, health notes, fitness profiles, measurements) rather than deleting rows. Ethiopian privacy and financial retention regulations must be reviewed before designing the anonymizer.

39. **Sprint 36: Tier Gate View Flag Contract and Entitlement Boundaries (November 4, 2026)**
    - **Question/Context:** How do we guarantee that future views or refactors cannot bypass tier gating (trainer module, AI plans, analytics, freeze, group classes), and what are the strict boundaries for Owner vs. Super Admin entitlement modification?
    - **Chosen Solution & Policy:**
      - **Contract Test (`test_all_tier_gated_views_declare_required_flag`):** Walks the project's URL resolver and inspects all view classes in tier-gated modules (`classes`, `trainers`, `memberships` metrics and freeze views, `tenants` analytics view). Asserts that every view explicitly declares `required_flag` with its corresponding flag name (`has_group_classes`, `has_trainer_module`, `has_ai_plans`, `has_analytics`, `freeze`), and that views enforcing API-level 403 gates declare the corresponding permission class (`HasGroupClassesEnabled`, `HasTrainerModule`, `HasAIPlansEnabled`).
      - **Entitlement Modification Boundaries:** Enforced fail-closed in `GymSettingsUpdateSerializer` and `update_gym_settings`. Any Owner attempt to modify `tier`, feature flags (`has_*`), `freeze_days_cap`, `payment_grace_days`, or `subscription_reminder_days` returns HTTP 403 Forbidden. Owner may configure `freeze_days_allowed` (up to `freeze_days_cap`; Starter tier barred from setting > 0), Chapa online payments switch (`is_enabled`), equipment completeness setting (`is_equipment_list_complete`), and receipt verification settings.
    - **Reason for choice:** Eliminates accidental permission bypasses through contract assertion and ensures tenant-tier monetization boundaries are strictly respected.

40. **Sprint 36 Correction: Notice Board, Telegram Bridge, and Expenses Realignment to Growth with Capabilities-Based Frontend Render Gating (November 5, 2026)**
    - **Question/Context:** Which tier includes gym notices, Telegram channel bridge, and expenses and reports, and how does the frontend coordinate dynamic feature gating without visual flicker or manual reloads?
    - **Chosen Solution & Policy:**
      - Notice Board & Telegram bridge (`has_notices`) and Expenses & Reports (`has_expenses`) are assigned exclusively to Growth and Pro tiers. Starter tier remains focused on core operations.
      - The server transmits a unified `capabilities` object (`has_trainer_module`, `has_ai_plans`, `has_freeze`, `has_group_classes`, `has_analytics`, `has_notices`, `has_expenses`) across session and tenant configuration.
      - Frontend re-syncs capabilities on login and on `visibilitychange` (whenever the browser tab regains focus), allowing tier changes made by Super Admin to reflect instantly without a manual page reload.
      - Role navigation, screen widgets, action cards, and forms strictly check capabilities. Unauthorized direct URLs (e.g. `/trainers`, `/classes`, `/notices`, `/expenses`, `/assignments`, `/freezes`) automatically redirect to the user's Home without showing an error page.
      - Trainer-inclusive plans on gyms without the trainer module are barred from listing or sale across all channels (cash, bank transfer, Chapa, upgrade quote); Owners see them flagged 'Not available on your tier'; active member subscriptions continue until their expiration date.
    - **Reason for choice:** Establishes a single source of truth for gym capabilities, cleanly seals tier monetization boundaries across both client and server, and prevents broken UI states.

41. **Sprint 37: PWA Caching Boundaries, Offline Check-in Queue & Safari Fallback (November 6, 2026)**
    - **Question/Context:** How does the PWA guarantee zero offline caching of sensitive API data or photos, how are offline scans stored and synchronized safely, and how do we handle browsers lacking Background Sync API (iOS Safari)?
    - **Chosen Solution & Policy:**
      - **Strict Cache Boundary:** Workbox / service worker intercepts `fetch` events and applies `NetworkOnly` with zero caching to `/api/*` and `/media/*`. Only static frontend app shell assets (HTML, CSS, JS, bundled icons/fonts) are cached via Cache API (`fitgate-app-shell-v1`). Navigation requests when offline fall back to the cached `index.html`.
      - **IndexedDB Security & Clean-up:** Offline scans are buffered in IndexedDB (`fitgate_offline_db`, store `checkin_queue`). A member or staff logging out triggers `clearOfflineQueue()`, purging pending local entries so distinct users cannot replay prior session scans.
      - **Sync & Safari Fallback:** When online, scans submit immediately to `/api/attendance/scan/` which runs the single shared `execute_check_in` engine. If offline, the token signature and expiration are verified locally and saved to IndexedDB. Upon detecting network restoration (`online` event) or tab focus (`visibilitychange` / `focus`), the queue replays sequentially within 5 seconds. Rejections (frozen, suspended, pending, superseded, expired, pending-review) return clear refusal messages to staff, and duplicate scans on the same day resolve idempotently to 1 `Attendance` record.
      - **Install Flow:** Android/Chromium uses `beforeinstallprompt` to surface a "Download App" button on the Member Dashboard. iOS Safari displays a step-by-step "Add to Home Screen" guide modal/card.
    - **Reason for choice:** Complies with privacy and security mandates (no sensitive member or financial data in browser cache), ensures reliable entrance operations during network dropouts, and supports iOS Safari without relying on unsupported Background Sync APIs.
