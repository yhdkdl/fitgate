# FitGate — Sprint Plan

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done (PR merged to `develop`). Only the project owner marks a sprint `[x]`, after merging.

> **Grouping.** Increments 1–5 and 7 are derived from §1.7.2 of the source document's prose (Figure 1.1 is a caption with no image data). **Increment 6 (multi-branch) is not in the source document** — it was added by direct decision with the project owner; see `docs/SPEC.md` §3. The seven-increment grouping is final.
>
> **Numbering.** Sprints added after the original plan use letter suffixes (`2a`, `4a`, …) so existing numbers and cross-references (Sprints 4, 14, 22, 38) never shift. Sprints run in the order shown, not by number alone.
>
> **Production hosting.** Yegara Host **Premium** (shared/managed cPanel, no root). Scheduled work uses cPanel Cron Jobs calling Django management commands; no Celery worker. See `AGENT.md` Deployment.
>
> **Scope of this version.** Gyms are onboarded by Super Admin (assisted onboarding), after payment. Everything deferred is listed in "Deferred to a future version" at the end; every difference from the source document is in `docs/SPEC.md` §11.
>
> Every sprint carries **acceptance criteria** — concrete, testable statements a diff must satisfy. These are in addition to the Definition of Done in `AGENT.md`. The numeric targets (2 s check-in, 3 s dashboards, 5 s offline sync, 320 px screens) are test criteria in the sprints that build them, not aspirations.

---

## Sprint 0 — Project scaffolding

Docker Compose (Django + Postgres + Redis + **pgAdmin**), Django project skeleton, Vite+React skeleton, repo/branch structure (`main`/`develop`), base settings split (local/prod), `.env.example`, pre-commit hooks (ruff/black, eslint/prettier), pytest-django wired up and runnable, drf-spectacular installed. Pinned to Python 3.11.16 and Django 5.2 LTS (see `AGENT.md`).

pgAdmin is a local-development convenience only — a GUI client connected to the same live `postgres` container, not a separate data store. It must not be part of the production deployment (cPanel hosting has no Docker to run it on — see Sprint 38); keep it isolated to a dev-only Compose override or profile.

**Acceptance criteria:**

- `docker compose up` brings up Django, Postgres, Redis, and pgAdmin cleanly from a fresh checkout with no manual steps beyond copying `.env.example` to `.env`.
- pgAdmin is reachable at its exposed port and can connect to the `postgres` service using credentials from `.env` (pre-configured, not entered by hand every restart).
- A row changed through Django (e.g., via `manage.py shell` or the admin) is visible in pgAdmin after a refresh — confirms it is pointed at the live container.
- `pytest` runs successfully with zero tests collected (proves the harness works).
- A deliberately malformatted commit is blocked by the pre-commit hook, not silently allowed through.
- `.env.example` lists every variable the settings files actually reference, with no real secret values in it.

Two minor items were deliberately deferred when Sprint 0 was merged: the zero-tests `conftest.py` hook and the `0.0.0.0` port binding. Neither blocks anything; revisit when convenient.

- [x] Status: done

## Increment 1 — Platform foundation (multi-tenancy, auth, access control, onboarding, attendance)

1. **Core tenant models + subdomain middleware** — `GymTenant`, `GymConfig`, tenant-scoping base manager/mixin, subdomain-resolution middleware.
   - A request to a known gym's subdomain resolves `request.tenant` to that `GymTenant`; an unknown subdomain fails clearly (404), not silently with no tenant.
   - `DOMAIN` is tested as a two-label value. With `DOMAIN="fitgate.tebebtech.com"` set explicitly in the test: (a) `gymname.fitgate.tebebtech.com` resolves to that gym, and (b) `fitgate.tebebtech.com` itself (the apex) sets `request.tenant = None` rather than 404ing. Implementation uses suffix-matching against the full `DOMAIN`, never "everything before the first dot."
   - Host handling: port stripped, lowercased, trailing dot removed. A host that is neither the apex nor under `.{DOMAIN}` is rejected (404), never treated as the apex. A dot-boundary case (`evil` + `{DOMAIN}`, e.g. `evilfitgate.tebebtech.com`) is rejected. A nested label (`a.b.{DOMAIN}`) is rejected. The production middleware contains no environment-specific host literals; any extra platform hosts needed by Docker or the test client come from a settings value that is empty by default and set only in local/test settings.
   - `DOMAIN` has no default in code; settings fail fast when it is unset, and `.env.example` lists it.
   - `ALLOWED_HOSTS` always contains `DOMAIN` and `.{DOMAIN}`, env hosts are additive, no wildcard.
   - A query through the tenant-scoped manager, with no caller-side `gym_id` filter, returns only the current tenant's rows — proven with two seeded tenants.
   - **Fail closed:** with no tenant context the scoped manager returns an empty queryset; `save()` raises when there is no tenant context and no gym, or when the instance's gym differs from the active tenant; `bulk_create` enforces the same rules. Unscoped access exists only as `all_objects` / the manager's explicit `unscoped()`; no queryset-level `unscoped()` that silently does nothing.
   - `GymTenant.subdomain` is Not Null, unique, a single valid DNS label (`^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$`), with reserved names rejected by a field validator (so it applies outside `full_clean()`). Field lengths follow SPEC §8.
   - Creating a `GymTenant` auto-creates its `GymConfig` with all feature flags `false`.
   - `DummyTenantModel` used by tests exists only in test code, never in a production migration.

   - [~] Status: in progress — PR #3 open on `feature/sprint-1-core-tenant-models`. First revision (multi-label `DOMAIN`, fail-closed, Python 3.11.16 / Django 5.2) is in; a second revision for the criteria above is requested. Not done until the owner merges.

2. **Custom User model + JWT auth + platform-level base class** — login, logout, token refresh; Super Admin bootstrap.
   - Valid credentials return access + refresh tokens; invalid credentials return 401 with no information about which field was wrong. Token lifetimes are configurable settings.
   - Refresh issues a new access token without the password; a request without a token to a protected endpoint returns 401.
   - **Lockout:** five consecutive failed logins temporarily lock the account (duration is a setting) and notify the gym's Owner; a successful login resets the counter; during a lock, even the correct password is refused.
   - **Session validity:** every authenticated request checks the user is still active and that the token was issued after `password_changed_at`; a deactivated user's existing token is rejected immediately.
   - **Super Admin bootstrap:** a management command reads `SUPERADMIN_EMAIL` and `SUPERADMIN_PASSWORD` from the environment and creates the first Super Admin (`gym_id` null). It is idempotent (a second run changes nothing), the account must change its password at first login, and no HTTP endpoint can create the first Super Admin (test that no such route exists).
   - An existing Super Admin can create further Super Admins; the action is audit-logged and requires re-entering the creator's password; every other role gets 403. The last remaining active Super Admin cannot be deactivated.
   - **Platform-level base class:** `User`, `Notification` and `AuditLog` (nullable `gym_id`) use a second base class. Inside a gym, its manager shows only that gym's rows; at the apex (no tenant) it shows only platform rows (`gym_id` null). A test proves gym rows never appear at the apex and platform rows never appear inside a gym.
   - **Factory pattern:** login returns a role-specific dashboard configuration built by a factory; each role gets its own, an unknown role fails.

2a. **Profile and password management** — account settings for every role.

- A user can view and edit their own name and phone (a Trainer also specialization) without approval.
- Changing the password requires the current password, and invalidates all of that user's existing sessions including refresh tokens.
- Attempts to change `role`, `gym_id`, account status, membership status or `max_clients` through the profile endpoint are rejected or ignored — tested for each field.

3. **Password reset** — single-use, time-expiring link.
   - A reset link works once; a second use fails. An expired link fails with a clear error.
   - The response is identical whether or not the email exists (no account enumeration).
   - A successful reset invalidates all existing sessions of that user.

4. **Super Admin "Create gym"** — gym creation after payment, subdomain provisioning via cPanel UAPI, Owner creation, welcome message.
   - Only Super Admin can create a gym; every other role gets 403.
   - Creation goes through one service function, `create_gym(...)`; the endpoint is a thin wrapper and the tests call the function directly.
   - Inputs: gym name, location, contact name/phone/email, tier, subdomain (proposed from the name, editable, validated unique/DNS-label/not reserved), Owner name and email, and the payment record (amount, method must be `bank_transfer`, reference, verified by = the acting Super Admin). Optional `demo_request_id` links a demo request (Sprint 4a).
   - Atomically: creates the `GymTenant` as `active`, its `GymConfig` with flags set to the chosen tier's defaults, the `Payment` (`payer_type = gym_subscription`, `method = bank_transfer`, status confirmed), the Owner `User` (pre-verified, no password set), a single-use expiring set-password invite, and provisions the subdomain via cPanel's UAPI. A failure at any step (including the UAPI call) leaves nothing half-created. In local development the UAPI call is mocked, not skipped; the atomicity test still covers it.
   - The welcome message contains the set-password link, never a password.
   - A `chapa` method is rejected for `gym_subscription` payments; a duplicate or reserved subdomain is rejected.
   - No code path produces a `pending` gym in this version.
   - **Certificate safeguard (see `docs/SPEC.md` §4):** until the subdomain's TLS certificate is confirmed valid, the app does not force an HTTPS redirect on it and refuses login and registration specifically, showing a "still being secured" state. Login is refused while `tls_confirmed_at` is null and allowed once it is set. When it is set for the first time, `subscription_expires_at` is set to one year later.
   - A migration adds the `GymTenant` columns listed in SPEC §8 and the `GymConfig` fields `payment_grace_days` (default 7), `subscription_reminder_days` (default 14 and 7) and `member_reminder_days` (default 7 and 2).

4a. **Demo requests** — public "Request a Demo" form and Super Admin lead list.

- The public endpoint exists on the apex only and is rejected on a gym subdomain. Required: gym name, contact name, phone; optional: city, email, message.
- Rate limiting is enforced and tested; a filled honeypot field returns success but stores nothing. The throttle uses the database cache backend (Redis is not assumed).
- A stored request has status `new` and creates a platform-level notification for Super Admin.
- Only Super Admin can list requests, filter by status, add notes, and move a request through new → contacted → demo done → converted / lost; other roles get 403.
- "Convert to gym" returns the data that pre-fills Sprint 4's form; creating the gym with that `demo_request_id` marks the request `converted` and links the new gym.

4b. **File storage layer** — Cloudinary (Free plan) behind Django's storage interface.

- Member photos are stored as `authenticated` assets in per-gym folders (`gyms/<gym_id>/…`). They are served only through a backend view that checks the requester is logged in and belongs to that gym; the browser never receives a Cloudinary URL. Requesting another gym's photo returns 403/404 — tested.
- Gym logos are stored as public assets.
- Uploads are validated server-side before storage: image type only, maximum size (2 MB), random file names; an invalid upload is rejected with a clear error. Images are resized on upload.
- Credentials come from the environment; local development and tests use a local folder through the same interface (a fake storage in tests). The Cloudinary `authenticated` type is verified once against a real account before release (see "External checks").

4c. **Gym branding, entry page, first-run checklist**

- `GymConfig` gains optional `brand_color` (hex) and a logo reference. Both are Owner-editable settings; when empty, a default theme and the gym name are shown.
- A public entry page endpoint on the gym subdomain returns the gym name, brand color, logo, phone and location. The page offers Log in and Register; the plan list is added in Sprint 10. Before the certificate is confirmed it shows the "still being secured" state.
- A first-run checklist is shown to the Owner only: add branding, create a first plan, add a staff account, register a first member. Items tick automatically from real data (no manual flags), and the checklist can be dismissed; dismissal persists.

5. **RBAC framework** — permission classes + Owner/Manager permission matrix enforcement.
   - For every role in the permission matrix (SPEC §2), both an allowed action (succeeds) and a denied action (403, not 200) are covered by a test.
   - **Entitlements vs. settings:** an Owner's attempt to change `tier`, any `has_*` flag, `freeze_days_allowed`, `payment_grace_days` or `subscription_reminder_days` is rejected (403) at the API level; the same Owner can change `brand_color`, `member_reminder_days` and their payment credentials; a Manager can change none of them. Super Admin can change the entitlements.

6. **Staff provisioning** — Manager/Trainer/Reception invite-and-set-password flow, deactivation.
   - An invited user cannot authenticate until they complete the set-password step; the invite link is single-use and expires; invited accounts count as email-verified.
   - Owner can create Managers, Trainers and Reception; Manager can create only Trainers and Reception — a Manager creating a Manager gets 403, enforced at the API.
   - **Deactivation** blocks login and invalidates existing tokens immediately, never deletes, and keeps that user's history (audit entries, messages, approvals) visible to everyone who could see it before. No foreign key to a user cascades a delete, and there is no user hard-delete route. The email stays reserved; reactivation is possible instead of creating a duplicate.

7. **Member registration** — self-service + staff-assisted, `Member` + `BodyMetrics`, waiver, verification, photo.
   - Self-service and staff-assisted registration produce an identical `Member` + `BodyMetrics` structure.
   - A duplicate registration (same identifying field) within one gym is rejected.
   - Accepting the health waiver is required (`waiver_accepted_at` stored); registration without it is rejected.
   - A self-registered member must verify their email by single-use, expiring link before first login; staff-registered members receive a set-password link and count as verified. Public registration is rate-limited.
   - A profile photo uploads through Sprint 4b's storage layer.
   - Body composition: BMI is computed from the latest height and weight; an estimated body-fat percentage (US Navy circumference method) is computed only when the needed measurements are recorded. Both are labeled estimates, computed on read, and covered by unit tests.

8. **QR check-in** — token issuance/rotation (90 s window), scan endpoint, `Attendance`, duplicate/expired-scan handling, manual override.
   - The token is a signed JWT (asymmetric signature, private key in the environment, public key exposed so a scanner can verify offline). A tampered token is rejected; a token is valid at 89 seconds after issue and rejected at 91 — tested with a frozen clock.
   - Reusing an already-consumed token is rejected. A new token is issued after each valid use.
   - A scan for a member without an active subscription is rejected with a distinguishable reason (expired vs. frozen vs. suspended), and the screen shows the member's photo, name and status on success.
   - A legitimate single scan produces exactly one `Attendance` row. A second scan the same day is denied, produces no second row, and notifies staff.
   - **Manual override** by Reception: requires an active subscription and a reason, produces exactly one `Attendance` row and an audit entry, and is refused for expired, frozen or suspended members.
   - `Attendance` rows exist only for actual check-ins. An attendance-log endpoint returns ✓/✗ per day for a date range, derived from check-ins and the subscription period (days outside the period are blank).
   - Performance: scan validation plus attendance recording completes in under 2 seconds against a seeded dataset of 10,000 members.

9. **Audit log foundation** — `AuditLog` model + logging utility wired into 1–8; restricted DB role (INSERT/SELECT only).
   - Every action from sprints 1–8 produces exactly one `AuditLog` row with the correct `actor_id`, `action_type` and affected record, including logout, Super Admin creation, and gym creation (platform-level rows have `gym_id` null).
   - An `UPDATE` or `DELETE` against the audit table using the application's own DB role fails at the database level — tested directly.

9a. **Audit log viewer**

- Owner and Manager see their own gym's entries; Super Admin sees all; every other role gets 403.
- Entries are paginated, newest first, filterable by date range, action type and actor, and the endpoint is read-only (no update or delete verbs).

- [ ] All sprints in this increment complete

## Increment 2 — Membership & payments

10. **Membership plans & subscription lifecycle** — `MembershipPlan` CRUD, `MemberSubscription` state machine.
    - A plan's duration is a number plus a unit (days or months). End dates are correct for both, including month-end cases (31 January + 1 month).
    - Creating a subscription against an inactive plan is rejected. Deactivating a plan hides it from new members but leaves existing subscriptions untouched. Editing a plan's price never changes recorded payments.
    - Saving a trainer-inclusive plan in a gym with no trainers succeeds but returns a clear warning.
    - Every disallowed state transition is tested and rejected (e.g. `expired → active` without a new payment). Allowed transitions include `expired → pending` on a new payment, and `active/frozen → suspended` by Owner or Manager only, lifted only by Owner or Manager.
    - A gym's plans are not visible or usable from another gym's context.
    - The public entry page (Sprint 4c) lists the gym's active plans with prices, without authentication, and never lists another gym's plans.

11. **Chapa payment integration (one account per gym)** — credentials, checkout, webhook verification, idempotency.
    - Each gym stores its own Chapa secret key and webhook secret in a separate payment-config record. They are encrypted at rest (the raw database value is not the plaintext; decrypting needs the environment key), never returned by any API (the response shows a masked value only), and never written to logs — each tested. A missing encryption key fails fast. `GymConfig.chapa_merchant_id` is removed by migration.
    - Only Owner and Super Admin can set or replace credentials; Manager and all others get 403.
    - A verify-connection action tests the keys with a harmless authenticated call (mocked in tests) and records the result. "Pay Now" is refused for a gym with no verified configuration, and the member is offered cash.
    - The webhook path includes the gym id. It looks up that gym's secret, verifies the signature, then re-verifies the transaction with Chapa and compares the amount with what was expected; a mismatch is not activated and is flagged. A webhook for gym A signed with gym B's secret is rejected.
    - A redelivered webhook (same event twice) does not double-credit the subscription or create a duplicate `Payment` — the core test for this sprint. An invalid signature is rejected.
    - A successful payment activates or extends the related `MemberSubscription`; a failed or abandoned one does not and notifies the member, who can retry or pay cash.
    - A payment still `pending` after the review window (default 30 minutes, a setting) is flagged for manual review by the scheduled command from Sprint 14.
    - A gym in test mode (the demo gym) holds Chapa test keys; the stored mode is visible to Super Admin.
    - Chapa is rejected as the method for `gym_subscription` payments.

12. **Manual cash payment, payment history, and the registration-to-payment flow**
    - A cash `Payment` cannot be created with `confirmed_by` null. `bank_transfer` is rejected for member payments.
    - A digital receipt is generated and retrievable, matching the recorded amount and plan.
    - A member sees their own payment history (method, amount, date, reference); Owner/Manager can list payments filtered by date, method and status, with a revenue total that counts confirmed payments only.
    - End to end: a new member registers on the gym's subdomain, picks an active plan, and either pays online (gym with verified Chapa) or leaves the subscription `pending` until Reception confirms cash — then it activates and a QR token is issued. Both paths are tested.

13. **Freeze workflow** — Growth/Pro gated, tracked against `freeze_days_allowed`.
    - A member submits a freeze request (days and reason) stored as a `FreezeRequest`; Owner/Manager approve or reject (a rejection stores a reason).
    - A request on a gym with `freeze_days_allowed = 0` is rejected at the API level; a request exceeding the remaining allowance is rejected.
    - Approval freezes the subscription, deactivates the QR token, and extends `end_date` by the frozen duration; reactivation at the end date is performed by Sprint 14's command.

14. **Scheduled jobs** — one idempotent management command (e.g. `run_scheduled_jobs`) run by a **cPanel Cron Job** in production (not Celery Beat — see `AGENT.md`); runnable manually or on a Compose schedule in local dev.
    - Member subscriptions: only those past `end_date` become `expired`; others are untouched. An expired member is rejected at check-in (ties to Sprint 8). QR tokens deactivate at expiry. Frozen subscriptions reactivate at the end of the freeze.
    - Member renewal reminders go to the member and to Reception on each day listed in the gym's `member_reminder_days` (default 7 and 2), once per subscription per threshold.
    - Gym subscriptions: the Owner is reminded at each day in `subscription_reminder_days` (default 14 and 7) before `subscription_expires_at`. After expiry, the gym keeps working during `payment_grace_days` (default 7). When the grace period ends unpaid, `lapse_flagged_at` is set and Super Admin is notified; the command never suspends a gym by itself.
    - Payments pending beyond the review window are flagged for manual review.
    - Running the command twice in a row creates no duplicate reminders, flags or notifications — cron can double-fire, so idempotency lives in the command.

15. **Notification center** — `Notification` model, in-app read/unread.
    - A notification created for one gym/member is not visible to another gym's recipient. Platform-level notifications (`gym_id` null) are visible only to Super Admin.
    - Notifications list unread first, then in chronological order; marking one read is idempotent and persists.

- [ ] All sprints in this increment complete

## Increment 3 — Trainer module (non-AI)

16. **Trainer profile & capacity** — `Trainer` model, `max_clients` config.
    - A trainer's current client count is correctly derived from active `TrainerAssignment` rows, exposed accurately for Sprint 17.

17. **Trainer assignment** — automatic (load-balance + least-recently-assigned tie-break) + manual reassignment.
    - Automatic assignment selects the eligible trainer with the lowest current client count; on a tie, the least-recently-assigned trainer wins — both rules tested against a seeded scenario.
    - A trainer at `max_clients` is never selected by automatic assignment. If every trainer is at capacity, no assignment is made and Owner/Manager are notified.
    - Assignment happens only for members on trainer-inclusive plans. The trainer and the member are both notified of a new or changed assignment.
    - Manual reassignment closes the prior `TrainerAssignment` (`ended_at`) and opens a new one; a member never has two open assignments. Manual reassignment may exceed capacity after an explicit confirmation, and is audit-logged.
    - Deactivating a trainer who has active clients is rejected unless the same action reassigns every one of them; a deactivated trainer's clients are never left silently unassigned.

18. **Trainer availability schedule.**
    - Availability reflects added and removed slots when queried per trainer (a trainer maintains their own weekly availability).

19. **Trainer↔member messaging.**
    - One thread per member–trainer pair; a member can only message their currently assigned trainer. After reassignment the member can no longer message the previous trainer, and old messages stay readable by the two participants.
    - Each message notifies the recipient. Messages are not visible to any third party, and a deactivated trainer's history remains.

- [ ] All sprints in this increment complete

## Increment 4 — AI Personal Training Engine

20. **FitnessProfile intake** — self + staff-captured, trainer-editable.
    - The profile is editable by the member's assigned trainer (including from the plan review screen), and rejected for an unrelated trainer or another member.
    - Required fields (`goal`, `fitness_level`, `training_days_per_week`) reject submission when missing, rather than silently defaulting.

21. **Rules engine** — phase/intensity/equipment-filter computation (pure Python, test-heavy; implement the Strategy pattern here for swappable intensity logic).
    - Phase is derived from the elapsed proportion of the member's active plan; intensity is derived from the phase, adjusted by the recent weekly check-in trend (progressive overload).
    - Deterministic output is covered by unit tests across at minimum: a beginner/foundation case, an advanced/peak case, and a case where `equipment_prefs`/limitations measurably exclude equipment.
    - Equipment in `out_of_service` or `under_maintenance` is never prescribed.
    - History context (prior exercises and loads) is read from the member's earlier approved plans' content; no new table.
    - The engine refuses members who are not on a trainer-inclusive plan in a gym with `has_ai_plans`.
    - Two different intensity strategies can be plugged in and produce different outputs from the same input with no change to the calling code — tested directly.

22. **LiteLLM integration layer** — self-hosted in the Django backend, called from behind the swappable-provider interface. Prompt construction, content storage, retry/fallback. **Runs synchronously within the request** (no worker on shared hosting); LiteLLM's retry/fallback happens inline. If the chosen model's response time does not fit comfortably within the Passenger WSGI request timeout, generation moves to a DB-backed job table polled by a cron-triggered command.
    - **Model selection:** candidate models are trialled (OpenRouter free tier) on a fixed set of standard member profiles and scored on valid structured output, exercise safety, and use of locally available Ethiopian foods; the cheapest model that passes is configured in LiteLLM. Swapping models changes configuration only.
    - Generation requires `has_ai_plans`, a trainer-inclusive plan, a complete profile and an assigned trainer; otherwise it is refused.
    - A simulated provider failure on the primary deployment falls through to the next configured deployment (mocked error). After three failed attempts overall, the owner is notified, the failure is logged, no plan is created, and other operations are unaffected.
    - Generated content is stored on a `TrainingPlan` in `pending_review`, the assigned trainer is notified, and it is not fetchable by the member before approval.
    - The prompt includes an instruction to base nutrition guidance on locally available Ethiopian foods (tested at the prompt-construction level).
    - Total provider failure produces a clear "generation failed" state, never a hang or an incorrectly approved plan.

23. **Trainer review workflow** — `TrainingPlan` approve/reject state machine, gated member visibility.
    - A member cannot fetch a `pending_review` plan — tested as a direct permission check.
    - Rejecting preserves `trainer_notes` and the rejected content, and triggers regeneration of a new `pending_review` plan that incorporates those notes. Approval and rejection are audit-logged, and the member is notified on approval.
    - Only the assigned trainer (or Owner/Manager) can approve/reject.

24. **Weekly check-in** — energy/recovery/motivation capture, feeds intensity adjustment.
    - A second check-in for the same `week_start_date` and member is rejected.
    - A low-recovery/low-energy check-in measurably changes the next computed intensity versus a high one, given the same profile.
    - A completed check-in triggers regeneration of next week's plan.
    - If no check-in is submitted by Monday evening, the scheduled command (Sprint 14) sends a reminder once and applies the default intensity for the phase with the previous load held constant — idempotent.

- [ ] All sprints in this increment complete

## Increment 5 — Equipment, classes, analytics, communication

25. **Equipment registry & maintenance** — `Equipment`, `MaintenanceLog`, low-quantity alerts, AI exclusion-filter wiring.
    - Equipment records include `purchase_date`. Reporting an issue creates a `MaintenanceLog`, transitions `Equipment.condition` to `needs_maintenance`, and notifies the Owner; reporting on an item already `under_maintenance` creates no duplicate.
    - Owner/Manager update condition and log resolutions (`resolved_at` set, condition returns to `good`) — the transitions are tested, not just log creation.
    - A quantity exactly at `min_qty_threshold` triggers an alert; one above it does not (boundary test).
    - Equipment `under_maintenance` or `out_of_service` is excluded from what Sprint 21's engine may prescribe — tested at the integration point.
    - An Owner setting controls whether members see unavailable equipment (default off).

26. **Group class scheduling & booking** — `ClassSession`, `ClassBooking`, capacity enforcement, Growth/Pro gated.
    - Booking is accepted for the last available slot and rejected on the next attempt once `max_capacity` is reached (boundary test); booking closes automatically at capacity.
    - Booking endpoints reject a gym with `has_group_classes = false` at the API level.
    - The class's trainer marks attendance on the booking (`attended`); this creates no daily `Attendance` row.

27. **Dashboards and analytics**
    - A basic dashboard endpoint is available to Owner/Manager on every tier: active members, today's check-ins, monthly revenue, and memberships expiring within seven days. It responds in under 3 seconds against a seeded dataset (1,000 members, a year of attendance).
    - Premium analytics — peak-hours heatmap (day of week × hour), cohort retention by joining month, revenue trends (monthly and by plan), referral analytics — are Growth/Pro only; every such endpoint rejects a gym with `has_analytics = false` at the API level, and the Starter response carries an upgrade prompt.
    - Figures are scoped to the requesting gym only — verified against a seeded multi-tenant dataset.

28. **Notice board & broadcast communication.**
    - A notice reaches all members of the issuing gym (Owner/Manager can post) and is not visible to another gym's users.

28a. **Badges and member progress** - Badges are awarded for a first check-in, a 30-day streak, and plan completion — each at most once per member, idempotent. - The member progress view returns body-metric history (and the Sprint 7 estimates) as chart data, scoped to that member.

29. **CSV export** — members, payments, attendance.
    - Exported rows, headers and row count match a known seeded dataset exactly, scoped to the requesting gym.
    - For 7 days after a gym is suspended (Sprint 35) its Owner can still log in and export, and nothing else; after that window the export is refused.

29a. **Expenses and reports** - Owner/Manager can log expenses (amount, category, note, date) and view revenue vs. expenses for a period; revenue counts confirmed payments only. - Reports: attendance summary and revenue report, scoped to the gym.

- [ ] All sprints in this increment complete

## Increment 6 — Multi-branch management (Pro tier)

_Not in the original source document — added by direct decision with the project owner. See `docs/SPEC.md` §3 for the full design rationale. Depends on Increment 1 (tenant/staff models), Increment 2 (`MembershipPlan`), and Increment 5 (`Equipment`, `ClassSession`) all being in place, which is why this sits here rather than earlier._

30. **Branch model + management** — `Branch` CRUD (Owner only), gated by `GymConfig.has_multi_branch`; frontend in-app branch switcher. One subdomain per gym regardless of branch count.
    - Branch CRUD endpoints reject requests on a gym without `has_multi_branch` at the API level.
    - Adding a gym's first branch doesn't break existing single-branch-gym behavior — a regression pass against Increments 1–5's tests still passes with `has_multi_branch=false`.

31. **Branch-scoped staff** — nullable `branch_id` on `User` (null = all-branch, matching Owner's existing unscoped access); RBAC updated so branch-scoped staff only see their branch's operational data.
    - A staff user with a set `branch_id` sees only that branch's data; a `null`-`branch_id` user sees all branches — both tested, including confirming Owner's access is unaffected either way.

32. **Branch-aware check-in & attendance** — `branch_id` on `Attendance`; QR check-in validates the scan's branch against `MembershipPlan.all_branches_access` and the member's subscription, not just subscription status.
    - A member whose plan has `all_branches_access=false` is rejected at a branch other than their home branch; a `true`-flag member succeeds at any branch — both tested.
    - Recorded `Attendance.branch_id` matches the actual scan location.

33. **Branch-aware equipment & classes** — `branch_id` on `Equipment` and `ClassSession`; branch-scoped maintenance alerts, class booking, and trainer assignment.
    - Equipment/class queries for a branch-scoped staff member return only that branch's records, mirroring Sprint 31.

34. **Plan-level branch access** — `MembershipPlan.all_branches_access` flag + plan management UI; lets a Pro gym sell both single-branch and all-access plans.
    - The flag is settable only on gyms with `has_multi_branch`; it has no effect on single-branch gyms regardless of its stored value.

- [ ] All sprints in this increment complete

## Increment 7 — Platform administration, PWA, demo, deployment

35. **Super Admin platform dashboard** — tenant management, renewals, lapse handling, platform reports.
    - Super-Admin-only actions are rejected for every other role, including an Owner acting on their own gym.
    - Tenant list with tier, status, `subscription_expires_at` and lapse flags; Super Admin can change a gym's tier and flags, enable or disable roles per gym (a disabled role cannot be invited or log in), and every change is audit-logged at platform level.
    - **Renewal:** Super Admin records a `bank_transfer` payment (amount, reference); `subscription_expires_at` extends by one year from the later of the current expiry or today, the lapse flag clears, and a suspended gym is reactivated.
    - **Suspension:** Super Admin confirms suspension of a lapse-flagged gym (it is never automatic). A suspended gym's staff and members cannot log in, while its data stays intact and visible to Super Admin — both halves tested. Its Owner can still log in for 7 days to export (Sprint 29), after which login is refused; nothing is deleted.
    - Platform reports: tenant summary, platform revenue (confirmed `gym_subscription` payments, excluding demo gyms), subscription status overview. Platform-wide notices (an `Announcement` with null gym) appear on every Owner's dashboard.
    - Super Admin can edit a gym's `payment_grace_days` and `subscription_reminder_days`.

36. **GymConfig feature-flag enforcement** — backend permission layer + frontend render gating, for every tier-gated feature above, including `has_multi_branch`.
    - Full regression pass: every previously-built tier-gated endpoint (trainer module, AI plans, premium analytics, group classes, freeze, multi-branch) is re-verified to reject a gym missing the corresponding flag, and every entitlement edit by an Owner is re-verified to be rejected. A clean pass here is the actual proof the gating is complete.

37. **Offline-first PWA** — Workbox service worker, local check-in queue, sync.
    - A check-in performed while offline is queued locally and produces exactly one `Attendance` row once connectivity returns — no duplicate on reconnect. Sync completes within 5 seconds of connectivity returning.
    - Where background sync is unsupported (iOS Safari), the app replays the queue itself when it detects connectivity or regains focus; this path is tested separately.
    - Offline, a scanned token is checked locally against the public key (signature and expiry); membership status is verified on sync, and a rejected queued check-in is surfaced to staff.
    - The app shell is served while offline, not a browser error page; all screens work at 320 px width without sideways scrolling. Staff keep a manual fallback register for the case where browser data is cleared offline.

37a. **Demo gym** - A management command seeds a gym on the `demo` subdomain (flagged `is_demo`) with sample members, plans, attendance, trainers, equipment and classes, Growth/Pro flags on, and Chapa test keys read from the environment. - Re-running it resets only that gym's data, never any other gym's — tested with a second seeded gym. Demo gyms are excluded from platform revenue.

38. **Production hardening (cPanel-based)** — deploy Django via cPanel's Python App Manager (Passenger WSGI), wire the cPanel UAPI subdomain-provisioning call from Sprint 4 to the real account (not a stub), confirm PostgreSQL connection settings against cPanel's database, set up the cPanel Cron Job for Sprint 14's command, configure the cache backend (database cache unless Redis is confirmed), DB backups via whatever cPanel/Yegara provides, `DOMAIN` fully parameterized end-to-end. `.env` carries every environment-specific value: `DOMAIN`, database credentials, JWT and QR signing keys, `TENANT_CREDENTIALS_KEY`, Cloudinary credentials, Super Admin bootstrap values, demo Chapa test keys.
    - A fresh deploy to the actual Yegara Premium account succeeds end-to-end from documented steps, with every environment-specific value sourced from `.env`.
    - The cPanel UAPI call is confirmed against the real account — a real subdomain is actually provisioned when a gym is created.
    - The AutoSSL gap behaves as designed under real conditions: a freshly provisioned subdomain is reachable over HTTP, login is blocked until the certificate is confirmed valid, and the app detects the certificate becoming valid without a manual flag flip.
    - The cPanel Cron Job fires Sprint 14's command on schedule — verified against real execution.
    - Changing `DOMAIN` in `.env` and redeploying requires no other code or configuration change.

- [ ] All sprints in this increment complete

---

## Decided

- [x] Production hosting: Yegara Host **Premium** (shared cPanel, no root); Docker/Caddy/VPS reversed
- [x] Task scheduling: cPanel Cron Jobs + Django management commands, no Celery
- [x] AI integration layer: LiteLLM, self-hosted, called synchronously; model chosen by the Sprint 22 trial procedure
- [x] Onboarding: assisted only (Request a Demo → Super Admin creates the gym after payment)
- [x] Billing: yearly only, paid by bank transfer, 7-day configurable grace period
- [x] Payments: one Chapa account per gym with encrypted credentials; platform fees by bank transfer
- [x] Storage: Cloudinary Free plan, member photos private and served through the backend
- [x] Seven-increment grouping is final

## External checks (each has a fallback; none blocks a sprint)

- [ ] Confirm with Yegara that `SubDomain::addsubdomain` is enabled for the API token. _Fallback:_ the subdomain is created by hand in cPanel and recorded as provisioned in Sprint 4.
- [ ] Confirm whether the API token can trigger an on-demand AutoSSL check. _Fallback:_ wait for the periodic scan; the login gate already covers the wait.
- [ ] Confirm how a one-time management command (Super Admin bootstrap, migrations) can be run on the host. _Fallback:_ a one-time cron entry.
- [ ] Confirm whether Redis is available. _Fallback:_ database cache and database job table.
- [ ] Ask Chapa what a small gym needs to open a merchant account. _Fallback:_ a gym without one runs cash-only until it has one.
- [ ] Test Cloudinary: sign-up and uploads work from your network, and an `authenticated` asset is inaccessible without a signature. _Fallback:_ host disk through the same storage interface.

## Deferred to a future version

- Public self-serve gym registration and approval (the source's FG-UC-00-GYM) and its rejection handling
- Inactivity flags, escalation and the inactive-member report (attendance data is already kept, so these can be added later)
- Chapa subaccount mode; Chapa-paid platform fees
- Monthly billing and auto-renewal; plan upgrades and downgrades mid-subscription
- Phone-number login; member discounts and promotions
- A full public landing page per gym
- A Starter member cap and a setup fee
- A data deletion/archival policy for lapsed gyms
