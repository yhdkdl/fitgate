# FitGate — Spec Reference

Condensed from `FitGate_Documentation_Corrected.docx`. That `.docx` is **not** in this repo — a coding agent can't read it directly — so its plain-text conversion lives at `docs/source/FitGate_Documentation_Full.md`. That file, not the `.docx`, is what this reference is checked against.

**This file is a working reference, not the source of truth.** If it and `docs/source/FitGate_Documentation_Full.md` disagree, the full version wins unless the difference is listed in §11 (Deviations), which records every deliberate departure from the source and why. Day-to-day sprint work uses this file; fall back to the full version when a sprint needs detail this summary leaves out (full use-case flows, exact table wording).

**Coverage rule.** Every functional requirement, use case, and in-scope item in the source document must appear in this file, or be listed in §11 or §10's deferred list with a reason. A better implementation than the source's is fine _if it is recorded in §11_. A source feature that is neither here nor in §11 is a gap, and gaps are bugs in this file — fix them before the feature's sprint starts.

## 1. Overview

FitGate is a multi-tenant gym management platform for the Ethiopian market (developed with Dire Dawa gyms as the initial context). It replaces paper attendance, unverified member access, opaque cash payment handling, unstructured trainer-member relationships, and the absence of personalized training guidance with a single Client-Server platform: React frontend, Django REST Framework backend, PostgreSQL, deployed per-tenant under subdomains of one shared installation.

**Scope of this version.** Gyms are onboarded by the platform owner (Super Admin) after they have paid — there is no public self-registration of gyms yet (§5, §10).

## 2. Actors / Roles and Account Provisioning

- **Super Admin** — platform-level, not tied to a gym (`gym_id` is null). Creates gyms, records subscription payments, suspends/reinstates gyms, sets tiers and feature flags, enables/disables roles per gym, handles demo requests, views platform-wide analytics, posts platform notices.
- **Owner** — one per gym tenant, created by Super Admin when the gym is created. Full control of their gym's operations and settings (not its entitlements).
- **Manager** — staff role, scoped permission subset of Owner (see the matrix below).
- **Trainer** — manages assigned members, reviews/approves AI-generated training plans, publishes availability, messages clients.
- **Reception** — front-desk role: check-in assistance (including manual override), manual cash payment recording, member registration assistance.
- **Member** — end user of a specific gym; registers, checks in via QR, views their subscription/plan, messages their trainer.

**Provisioning chain** (no single open signup for every role):

- **Super Admin:** no public registration route. The first account is created once, at deployment, by a one-time management command that reads its email and initial password from environment configuration, is idempotent, and forces a password change at first login; it is never exposed through an HTTP endpoint. An existing Super Admin can create more Super Admins from their dashboard (audit-logged, requires re-entering their own password). The last active Super Admin cannot be deactivated.
- **Gym Owner:** created by Super Admin as part of "Create gym" (§5). The Owner receives a set-password link, never an emailed password.
- **Manager, Trainer, Reception:** created from inside the gym's own subdomain: Owner creates Managers, Trainers and Reception; Manager creates Trainers and Reception only. Invite email with a set-password link; no public signup form.
- **Member:** registers at the gym's own subdomain (self-service → email verification → plan selection → payment) or is registered at the front desk by Reception/Manager.

**Permission matrix** (source Table 3.1a, with entitlements separated from settings):

| Action                                                                                         | Super Admin      | Owner | Manager |
| ---------------------------------------------------------------------------------------------- | ---------------- | ----- | ------- |
| Edit entitlements: tier, `has_*` flags, freeze allowance, grace and subscription-reminder days | Yes              | No    | No      |
| Edit gym settings: branding, member reminder days, payment credentials                         | —                | Yes   | No      |
| Create or deactivate Manager accounts                                                          | —                | Yes   | No      |
| Create or deactivate Trainer/Reception accounts                                                | —                | Yes   | Yes     |
| Create/edit membership plans and pricing                                                       | —                | Yes   | Yes     |
| Suspend or reactivate a member                                                                 | —                | Yes   | Yes     |
| Approve or reject a freeze request                                                             | —                | Yes   | Yes     |
| Manually reassign a trainer                                                                    | —                | Yes   | Yes     |
| View analytics dashboard, audit log, and payment history                                       | All gyms         | Yes   | Yes     |
| Confirm a manual cash payment                                                                  | —                | Yes   | Yes     |
| Post a notice board announcement                                                               | Platform notices | Yes   | Yes     |

**Deactivation (any staff role):** blocks login and invalidates existing tokens immediately, without deleting or hiding that user's history (audit entries, messages, approvals) from users who could see it before. There is no user hard-delete; the email stays reserved and an account can be reactivated. Deactivating a Trainer with active clients requires reassigning every one of them in the same action (§5).

## 3. Subscription Tiers & Feature Gating

Tiers: **starter / growth / pro** (per `GymTenant.tier`). Gating is enforced via `GymConfig` boolean flags per gym, not hardcoded by tier name, so an individual gym's flags can diverge from its tier's default set — but the default mapping is:

| Feature                                                                                      | Starter | Growth | Pro |
| -------------------------------------------------------------------------------------------- | ------- | ------ | --- |
| Core (multi-tenant, auth, member mgmt, QR attendance, payments incl. Chapa, basic dashboard) | ✅      | ✅     | ✅  |
| `has_trainer_module`                                                                         | ❌      | ✅     | ✅  |
| `has_ai_plans`                                                                               | ❌      | ✅     | ✅  |
| `has_analytics` (heatmap, cohort retention, revenue trends, referrals)                       | ❌      | ✅     | ✅  |
| `has_group_classes`                                                                          | ❌      | ✅     | ✅  |
| Membership freeze (`freeze_days_allowed` > 0)                                                | ❌      | ✅     | ✅  |
| Multi-branch management (`has_multi_branch`)                                                 | ❌      | ❌     | ✅  |

**Who changes flags:** only Super Admin. Entitlements are what a gym pays for; an Owner cannot switch on their own premium features. Owners edit settings only (§2). A request for more (an upgrade) goes to Super Admin.

**Pricing (yearly only, ETB — placeholders; the project owner sets the real prices):** Starter 12,000 · Growth 30,000 · Pro 60,000. The yearly price includes hosting, backups, security updates, bug fixes, new features within the gym's tier, and support, and the first year includes setup. It does not include custom development or large data imports. Billing is yearly only (§5, §11).

**Multi-branch management is not in the original source document** — it is a Pro-tier addition decided directly with the project owner. Design: a `Branch` belongs to exactly one `GymTenant` (nested under the existing `gym_id` tenancy boundary, not a new isolation mechanism). One subdomain per gym regardless of branch count — branch selection happens in-app — because a subdomain per branch would effectively make each branch a separate tenant. Member branch access is a `MembershipPlan` attribute (`all_branches_access`), so a Pro gym can sell both single-branch and all-access plans. Staff are branch-scoped via a nullable `branch_id` (null = all branches, matching Owner).

Gating is enforced at **both** the backend (a Starter gym's API rejects trainer/AI/analytics/class endpoints, not just hides the UI) and the frontend (ungated features aren't rendered).

## 4. Multi-tenancy

Row-level scoping: every gym-scoped table carries a `gym_id` foreign key to `GymTenant`. Tenant resolution is via subdomain (middleware resolves `{subdomain}.{DOMAIN}` → `GymTenant`, attaches to the request). Cross-tenant access must be architecturally impossible at the query layer: a base manager/queryset enforces it, with no per-view discipline. With no tenant in context the scoped manager returns nothing (fail closed); saving a record with no tenant context and no gym, or with a gym other than the active tenant, raises; bulk creation follows the same rules. Unscoped access is explicit (`all_objects`, the manager's `unscoped()`).

**Platform-level records.** Three tables — `User` (Super Admin), `Notification` and `AuditLog` — and platform `Announcement`s may have a null `gym_id`. They use a second base class: inside a gym it shows only that gym's rows; at the apex it shows only platform rows. The two never mix.

The apex domain (`DOMAIN` itself — e.g. `fitgate.org` or `fitgate.tebebtech.com`) is the public platform site, not any gym's app. A request to the apex sets `request.tenant = None` and is routed to: the public marketing/tier-info page, the "Request a Demo" form, and the Super Admin dashboard. A gym's actual app only exists at `{subdomain}.{DOMAIN}`, and that subdomain does not exist until Super Admin creates the gym. Switching candidate domains is a `DOMAIN` env change, not a code change (`AGENT.md` rule 14). A host that is neither the apex nor under `.{DOMAIN}` is rejected, not treated as the apex. A gym subdomain is a single DNS label.

**Subdomain provisioning (hosting-constrained):** the production host (Yegara Premium, shared cPanel, no root) has no wildcard DNS, so creating a gym calls cPanel's UAPI to provision that subdomain. The subdomain is reachable over plain HTTP immediately, but AutoSSL issues the certificate on its own periodic scan (potentially up to about a day). During that window login and registration are blocked with a "still being secured" state, and no HTTPS redirect is forced. See Sprint 4.

**Known internal conflict, resolved:** §1.7.3.2 and §1.8.2 of the source describe schema-per-tenant isolation, contradicting §3.2.1, §3.2.2 and the whole data model (§4.8.1), which use row-level `gym_id` scoping. The confirmed decision is row-level scoping.

**Gym entry page.** `{subdomain}.{DOMAIN}` shows the gym's name, optional logo and brand color (a default theme otherwise), phone and location, Log in and Register buttons, and the gym's active plans with prices. Owner, staff and members all log in there with email and password, and each role lands on its own dashboard.

## 5. Functional Requirements

Grouped as in the source document's §3.2.1.

**Platform level (Super Admin)**

- Dashboard: create gyms, record subscription payments, suspend/reinstate, handle demo requests, monitor platform-wide analytics.
- Assign a tier to each gym; set premium flags (Trainer, AI Engine, Analytics, classes, multi-branch); enable/disable user roles per gym. Online payment via Chapa is available to every tier.
- A unique subdomain is proposed (editable) for each new gym at creation.
- Platform reports (tenant summary, platform revenue, subscription status overview) and platform-wide notices published to all Owner dashboards.

**Gym onboarding and platform subscription (assisted, pay-first)**

- **Request a Demo:** a public form on the marketing site collects gym name, contact name, phone (required) and optionally city, email and a message. It is rate-limited and has a honeypot. Each request appears in a Super Admin lead list with a status (new, contacted, demo done, converted, lost) and notes, and notifies Super Admin. "Convert to gym" pre-fills the Create-gym form. A Telegram/phone contact is shown beside the form.
- **Create gym** (Super Admin, after the gym has paid by bank transfer): in one atomic action, record the payment (amount, reference, who verified it), create the gym as `active` with flags set to its tier's defaults, provision the subdomain, and create the Owner with a set-password link. Gym details captured: name, location, contact name/phone/email.
- **Certificate gate:** until the certificate is valid, login and registration are blocked; the yearly subscription period starts when login first becomes possible.
- **Yearly subscription:** billing is yearly only. A renewal is a bank-transfer payment recorded by Super Admin, extending the expiry by one year (from the later of the current expiry or today).
- **Reminders, grace, lapse:** the Owner is reminded 14 and 7 days before expiry (Super Admin can change these days per gym). After expiry the gym keeps working for a grace period of 7 days (configurable per gym, default 7). When it ends unpaid, the gym is flagged and Super Admin is notified; Super Admin confirms the suspension — it is never automatic. A suspended gym's staff and members cannot log in. The Owner can log in for 7 days after suspension to export CSV data, then access closes. Nothing is deleted; reinstatement restores everything.
- **First-run checklist** for the Owner: add branding, create a first plan, add a staff account, register a first member. Items tick automatically from real data; it can be dismissed. At handover, plans can be entered together with the Owner.
- **Branding:** optional brand color and logo, set by Super Admin at creation or by the Owner later.
- Gym subscription payments are never taken through Chapa; platform fees are paid by bank transfer.

**Authentication and access control**

- Unique email + password for every user; role-based access control; all queries scoped by `gym_id`.
- JWT session management with configurable token expiry; all API endpoints require a valid token, and every request also checks that the user is still active and that the token was issued after the last password change.
- Password reset by single-use, time-expiring emailed link. **Any password change (reset or in-app) invalidates all of that user's sessions**; the user must re-authenticate.
- Logout discards the session token and is recorded in the audit log.
- **Login lockout:** five consecutive failed attempts temporarily lock the account and notify the gym's Owner.
- **Email verification:** a self-registering Member must confirm by link before first login; invite-created accounts (Owner, staff) and staff-registered members are pre-verified.
- Deactivation rules: see §2. Deactivating a Trainer requires reassigning every active client in the same action; a trainer's clients are never left silently unassigned.

**Profile management**

- Users view/edit their own profile fields (name, phone, photo; Trainer: specialization) and change their own password (current + new) from an account settings screen, without approval.
- No role may self-edit role, `gym_id`, account status, membership status or trainer client capacity.

**Member management**

- Reception/Manager register members capturing full name, date of birth, phone, gender, emergency contact, optional referral source, profile photo, body metrics, and acceptance of the health waiver (required). Members can also self-register through the gym's subdomain, then choose a plan and pay.
- Members update body metrics over time with full history. A progress view charts the history. **Body composition estimation:** BMI is computed from the latest height and weight; an estimated body-fat percentage (US Navy circumference method) is shown when the needed measurements exist. Both are labeled estimates.
- Member status: active, expired, frozen, suspended. Referral source data appears in owner analytics.

**Membership plans**

- Owner/Manager create plans: name, duration (a number of **days or months**), price, optional trainer-inclusive flag. Trainer-inclusive plans cost more and trigger automatic trainer assignment on activation. A deactivated plan stays linked to existing subscriptions but is hidden from new members. Saving a trainer-inclusive plan when the gym has no trainers shows a warning. Editing a price never changes recorded payments.
- Start date and expiry are calculated and stored on activation.
- **Freeze:** a member requests a freeze (days + reason); Owner/Manager approve or reject; approval freezes, deactivates the QR token, records the start, and extends expiry by the frozen days; membership and QR reactivate automatically at the freeze end date. Growth/Pro only.
- **Member renewal reminders** go to the member and to Reception on the days set in the gym's `member_reminder_days` (an Owner setting, default 7 and 2). The QR token deactivates at expiry.

**QR check-in and attendance**

- A unique, time-expiring QR token for each active member, regenerated on each valid use. The token is a **signed JWT with a 90-second window**, signed asymmetrically so a scanner can verify it offline from the public key alone. Known limitation: device clock skew can cause false rejections.
- Browser-based scanner for reception, no dedicated hardware. Validation checks token expiry, `gym_id` match and active membership. On success, show the member's photo, name and status, and record the attendance.
- A second scan for the same member on the same day is denied and staff are notified. Frozen or suspended members are denied with a distinct status message.
- **Manual override** by Reception when the QR flow can't be used: requires an active subscription and a reason, and is audit-logged.
- **Offline grace mode:** check-ins keep working during outages (§6).
- Attendance rows exist only for check-ins; the daily attendance log shows ✓/✗ per day, derived from check-ins and the subscription period.

**Payments**

- **Payment methods:** `chapa`, `cash`, `bank_transfer`. Members pay by `chapa` or `cash`; gyms pay the platform by `bank_transfer`.
- **Each gym uses its own Chapa merchant account.** The gym's secret key and webhook secret are stored encrypted, never returned by any API, never logged; only Owner and Super Admin can set them; a verify-connection check tests them. "Pay Now" opens Chapa's hosted checkout (telebirr, CBE Birr, bank cards) only once a gym's configuration is verified; otherwise members are offered cash. The platform stores no card data. A demo gym uses Chapa test keys.
- Chapa webhooks go to a per-gym URL, are verified by signature (with that gym's secret) **and amount** (re-verified with Chapa), and duplicate deliveries are treated as already processed. A successful webhook activates the membership with no staff involvement. A payment with no webhook after a configurable window (default 30 minutes) is flagged for manual review. A failed or abandoned checkout notifies the member, who may retry or pay cash.
- Manual cash payment by Reception/Manager: amount and optional reference note; activates immediately and generates a digital receipt.
- Per-member payment history (method, amount, date, reference). Owners log **expenses** and view revenue vs. expenses for a period. Financial summaries count confirmed payments only.

**Trainer management**

- Trainer profile: name, specialization, configurable maximum client capacity.
- Automatic assignment on trainer-inclusive activation: lowest current client count among trainers below capacity; ties go to the least recently assigned. If all trainers are at capacity, nothing is assigned and Owner/Manager are notified.
- Owner/Manager can reassign at any time (audit-logged; manual reassignment may exceed capacity after explicit confirmation). The trainer and the member are notified of a new or changed assignment. A trainer's client list shows only their assigned members.
- Trainers set and update weekly availability.
- In-app messaging between a trainer and their assigned members only: one thread per member-trainer pair, timestamped, each message notifies the recipient. After reassignment the member can no longer message the previous trainer.

**AI Personal Training Engine** (Growth/Pro, trainer-inclusive plans only)

- Initial fitness profile collected at registration (by the member or by reception): goal, self-reported fitness level, health limitations, equipment access, preferred training days. The assigned trainer can review and correct it from the plan review screen.
- The rules engine determines phase (Foundation/Build/Peak) from the elapsed proportion of the member's active plan; computes intensity from the phase, adjusted by the recent weekly check-in trend (progressive overload); excludes `out_of_service` and `under_maintenance` equipment; reads history (prior exercises and loads) from the member's earlier approved plans; builds a structured prompt; and calls LiteLLM.
- Returned exercise and nutrition content is stored. Nutrition guidance is based on locally available Ethiopian foods; the trainer can adapt it during review (the source ships no validated food database).
- Every new plan is `pending_review` and notifies the assigned trainer. The member cannot view it until the trainer approves. Rejection stores the trainer's notes and regenerates a new plan that incorporates them. Approval and rejection are audit-logged.
- Monday check-in form (energy, recovery, motivation, 1–5). If missed by Monday evening: default intensity for the phase, previous load held, and a reminder notification. A completed check-in triggers regeneration of next week's plan.
- If the AI call fails after three attempts, the owner is notified and the failure is logged, with no disruption to other operations.
- Known limitation: not validated for edge-case profiles (disabilities, chronic conditions); trainer review is the safeguard.

**Equipment management**

- Per-gym registry: name, category, quantity, purchase date, condition (Good / Needs Maintenance / Under Maintenance / Out of Service).
- Staff can report an issue, setting Needs Maintenance and notifying the Owner (no duplicate report if already Under Maintenance). Owner/Manager update condition and log resolutions. An Owner setting controls whether members see unavailable equipment (default off).
- Owner sets a minimum quantity per item; a low-quantity alert fires when the count falls below it. Out-of-service and under-maintenance items are excluded from AI plans and update automatically when resolved.

**Classes and group scheduling**

- Owner/Manager create sessions (name, trainer, date, time, max capacity). Members view and book; booking closes automatically at capacity. The trainer marks class attendance, recorded separately from daily check-in. Growth/Pro only.

**Dashboards, analytics and reporting**

- **Basic dashboard (every tier):** total active members, today's check-ins, monthly revenue, memberships expiring within seven days.
- **Premium analytics (Growth/Pro):** peak-hours heatmap (day of week × hour), cohort retention by joining month, revenue trends (monthly and by plan), referral analytics. A Starter gym sees an upgrade prompt.
- Reports (Owner/Manager): attendance summary and revenue report. Super Admin: tenant summary, platform revenue, subscription status overview.

**Communication and engagement**

- Notification centre per role (unread first, chronological, mark as read). Owner/Manager notice-board announcements visible to all members of the gym.
- Milestone badges: first check-in, 30-day streak, plan completion.

**Audit log**

- Permanent entries for every significant action: member registration, plan creation/activation, payment confirmation, trainer assignment/reassignment, plan approval/rejection, equipment status changes, role/config changes, gym creation, Super Admin creation, logout. Each captures actor, action type, timestamp and affected record.
- Write-only at the database level (INSERT/SELECT only for the application role). Visible to Owner, Manager (own gym) and Super Admin (all), filterable by date range, action type and actor; read-only for every role.

**Data export**

- CSV export of members, confirmed payments and attendance for the Owner's own tenant, including during the 7-day export window after suspension.

**Design patterns** called out in the source: a **Factory pattern** for role-specific dashboard generation at login, and a **Strategy pattern** for swappable intensity-calculation logic in the rules engine.

## 6. Non-Functional Requirements

The numeric targets are **test criteria** in the sprint that builds each feature, measured against seeded data.

| Category        | Requirement                                                                                                                                                                                                                                                                                                                                                                                                           |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Usability       | Mobile-first; responsive from 320 px up with no sideways scrolling; operable by staff with minimal training                                                                                                                                                                                                                                                                                                           |
| Performance     | QR scan validation + attendance recording within 2 s; Owner/Manager dashboards within 3 s (normal network)                                                                                                                                                                                                                                                                                                            |
| Offline         | Check-ins queue locally when offline and sync within 5 s of connectivity returning (Workbox + IndexedDB). Where background sync is unsupported (iOS Safari), the app replays the queue itself on reconnect or focus. Offline scans are verified locally by token signature; membership is verified on sync. Limitation: clearing browser data while offline loses the queue, so staff keep a manual fallback register |
| Security        | JWT on all endpoints; tenant isolation at the query layer; per-gym Chapa credentials encrypted at rest and never exposed; webhook signature + amount + idempotency; input validation on frontend and backend; password hashing; tamper-evident audit log; member photos private and served only through the backend                                                                                                   |
| Reliability     | 99% uptime target during gym operating hours; AI failure after three attempts notifies the owner without disrupting other operations                                                                                                                                                                                                                                                                                  |
| Maintainability | Modular architecture (payments, trainer, AI, equipment independently updatable); documented API (OpenAPI + docstrings, which also satisfies `AGENT.md` rule 6)                                                                                                                                                                                                                                                        |
| Compatibility   | Chrome, Firefox, Safari, Edge — last two major versions; PWA installs on Android and iOS                                                                                                                                                                                                                                                                                                                              |
| Scalability     | New tenants added without schema changes or interruption to existing tenants                                                                                                                                                                                                                                                                                                                                          |
| Localization    | ETB default; telebirr and CBE Birr; Ethiopian-context nutrition guidance                                                                                                                                                                                                                                                                                                                                              |
| Configurability | The deployment domain is a single env value, never hardcoded; grace, reminder and review-window values are configuration, not code constants                                                                                                                                                                                                                                                                          |

## 7. Use Cases (condensed)

Each entry: goal — key business rule(s).

**Platform / tenancy**

- Request a demo — public form on the apex; stored as a lead; Super Admin contacts the gym.
- Create gym (replaces the source's FG-UC-00-GYM "Subscribe to Platform" and approval for this version) — Super Admin records payment, creates the active gym, subdomain and Owner in one atomic step.
- Renew subscription — Super Admin records a bank-transfer payment; expiry extends one year.
- Suspend / reinstate a gym — suspension needs Super Admin confirmation after the grace period; blocks staff/member access without deleting data; Owner can export for 7 days.
- Change tier, flags and roles per gym — Super Admin only; audit-logged.

**Auth & staff**

- Login (FG-UC-00) — JWT scoped to role and `gym_id`; role-appropriate dashboard (Factory pattern); five failures lock the account.
- Password reset (FG-UC-00-PWD) — single-use, time-expiring; identical response whether or not the email exists; invalidates all sessions.
- Logout (FG-UC-00-OUT) — discards the token, audit-logged.
- Owner/Manager invites staff — invite-and-set-password, per the permission matrix.
- Profile and change password — every role.

**Members & attendance**

- Register member (FG-UC-01) — self-registration vs staff-assisted share the same `Member` + `BodyMetrics` creation; waiver required; both end in plan selection and payment; QR issued on activation.
- QR check-in (FG-UC-02) — token validated for expiry, gym and status; duplicate and expired scans denied with staff notified; frozen/suspended shown distinctly; manual override for Reception.

**Membership & payment**

- Submit payment (FG-UC-03) — Chapa or cash; failed checkout may retry or fall back to cash; missing webhook flagged for manual review.
- Plan management — Owner/Manager CRUD; edits don't affect existing subscriptions.
- Member subscribes/renews — creates/extends `MemberSubscription`.
- Request freeze / approve-reject freeze — Growth/Pro only.
- Membership expiry — scheduled job deactivates QR access and sends reminders.
- View payments — Owner/Manager filter by date, method, status, with a revenue summary.

**Trainer module**

- Assign trainer (FG-UC-05) — automatic (load-balance + least-recently-assigned) or manual; capacity-exhausted notifies Owner/Manager.
- Trainer availability; trainer↔member messaging.

**AI training engine**

- Member fitness intake — at registration or later, editable by the assigned trainer.
- Generate AI plan (FG-UC-06) — rules engine → LiteLLM → plan `pending_review`. Runs synchronously inside the request on Passenger WSGI; if the chosen model is too slow for the request timeout, generation moves to the DB-backed job table + cron-poll.
- Approve/reject plan; view training plan (most recent approved, or "pending trainer review"); weekly check-in.

**Equipment, classes, analytics, communication**

- Report equipment issue; manage equipment registry; low-quantity alerts.
- Book group class; manage group class (capacity enforced; class attendance recorded separately).
- View dashboard / analytics; view audit log; generate reports; notice board; notifications; badges and progress; data export; log expenses.

**Multi-branch (Pro) — not in source document, see §3**

- Owner creates/manages branches; assigns staff to a branch or leaves them unscoped.
- QR check-in validates branch access against `MembershipPlan.all_branches_access`.
- Branch-scoped staff see only their branch's equipment, classes and attendance; Owner and unscoped staff see all branches.

**Platform admin**

- Manage gym tenants; generate platform report; publish platform notice; handle demo requests; create further Super Admins.

_(This is a condensed index, not a replacement for the full use-case tables in the source — consult `docs/source/FitGate_Documentation_Full.md` for the full flow of any use case before implementing it.)_

## 8. Data Model

All tables carry `id` (uuid, PK) unless noted. Every gym-scoped table carries `gym_id` (FK → `GymTenant`); a nullable `gym_id` is allowed only where marked and uses the platform-level base class (§4). Field lengths follow the source's Tables 4.1–4.21 unless noted.

**User** — `gym_id` (null for Super Admin), `branch_id` (nullable — null = all branches; staff at a `has_multi_branch` gym; _new, not in source_), `email` (unique), `password_hash`, `role` (super_admin/owner/manager/trainer/reception/member), `is_active`, `created_at`, `last_login`; _added for §5 (not in Table 4.1):_ `email_verified_at`, `failed_login_count`, `locked_until`, `password_changed_at`, `must_change_password`, `full_name` (150, blank allowed), `phone` (20, blank allowed).

**GymTenant** — `name` (150), `subdomain` (63, unique, **Not Null**, single DNS label, reserved names rejected), `status` (pending/active/suspended/terminated — `pending` is unused in this version), `tier` (starter/growth/pro), `currency` (default ETB), `created_at`; _added (not in Table 4.2):_ `location`, `contact_name`, `contact_phone`, `contact_email`, `subscription_expires_at` (null until login first becomes possible), `tls_confirmed_at`, `lapse_flagged_at`, `suspended_at`, `is_demo` (default false). _Note: `GymTenant.updated_at` is an extra operational timestamp not in the source tables._

**GymConfig** — `gym_id` (PK+FK, 1:1), `has_trainer_module`, `has_ai_plans`, `has_analytics`, `has_group_classes`, `has_multi_branch` (_new_) (booleans, default false), `freeze_days_allowed` (default 0); _added:_ `payment_grace_days` (default 7), `subscription_reminder_days` (list, default 14 and 7), `member_reminder_days` (list, default 7 and 2), `brand_color` (hex, nullable), `logo` (storage reference, nullable), `show_unavailable_equipment` (default false), `first_run_dismissed_at` (nullable). Entitlements (`has_*`, `freeze_days_allowed`, `payment_grace_days`, `subscription_reminder_days`) are Super-Admin-editable; the rest are Owner-editable. _The source's `chapa_merchant_id` is replaced by `GymPaymentConfig` (§11)._

**GymPaymentConfig** _(new)_ — `gym_id` (PK+FK), `provider` (chapa), `mode` (test/live), `secret_key` (encrypted), `webhook_secret` (encrypted), `verified_at` (nullable), `is_enabled`. Never serialized back to any client.

**DemoRequest** _(new, platform-level — no `gym_id`)_ — `gym_name`, `contact_name`, `phone`, `city` (nullable), `email` (nullable), `message` (nullable), `status` (new/contacted/demo_done/converted/lost), `notes`, `handled_by` (FK → User, nullable), `converted_gym_id` (FK → GymTenant, nullable), `created_at`.

**Branch** _(new — Pro tier, see §3)_ — `gym_id`, `name`, `address` (nullable), `is_primary` (default false), `created_at`

**Member** — `gym_id`, `user_id`, `full_name`, `phone`, `date_of_birth`, `gender`, `emergency_contact`, `referral_source`, `photo_url`, `status` (active/expired/frozen/suspended), `joined_at`; _added:_ `waiver_accepted_at`.

**BodyMetrics** — `member_id`, `gym_id`, `weight_kg`, `height_cm`, `measurements` (jsonb, free-form), `recorded_at`

**MembershipPlan** — `gym_id`, `name`, `duration_value`, `duration_unit` (days/months — _the source has `duration_months` only_), `price_etb`, `trainer_inclusive`, `is_active` (default true), `all_branches_access` (default true; _new_)

**MemberSubscription** — `member_id`, `gym_id`, `plan_id`, `start_date`, `end_date`, `status` (pending/active/frozen/suspended/expired), `freeze_start_date` (nullable), `frozen_days_total` (default 0)

**QRToken** — `member_id`, `gym_id`, `token_hash`, `issued_at`, `expires_at` (issued_at + 90 s), `is_active` (default true)

**Attendance** — `member_id`, `gym_id`, `branch_id` (nullable; _new_), `date`, `status` (checked_in — rows are written on check-in only; absence is derived), `checked_in_at`

**Payment** — `gym_id` (the paying gym, including for `gym_subscription` payments), `payer_type` (gym_subscription/member), `member_id` (nullable), `subscription_id` (nullable), `method` (chapa/cash/bank_transfer — `bank_transfer` only for `gym_subscription`; `chapa` and `cash` only for `member`), `amount_etb`, `chapa_ref` (nullable), `bank_reference` (nullable), `status` (pending/confirmed/failed), `confirmed_by` (FK → User, nullable — required for cash and bank_transfer), `created_at`

**Trainer** — `gym_id`, `user_id`, `specialization` (nullable), `max_clients`

**TrainerAssignment** — `member_id`, `trainer_id`, `gym_id`, `assigned_at`, `ended_at` (nullable), `assigned_by` (nullable — null for automatic)

**TrainerAvailability** _(new)_ — `trainer_id`, `gym_id`, `day_of_week`, `start_time`, `end_time`

**Message** _(new)_ — `gym_id`, `member_id`, `trainer_id`, `sender_id`, `body`, `sent_at` (one thread per member-trainer pair)

**FitnessProfile** — `member_id` (PK+FK), `gym_id`, `goal`, `fitness_level`, `limitations`, `equipment_prefs`, `training_days_per_week`, `updated_at`

**TrainingPlan** — `member_id`, `trainer_id`, `gym_id`, `phase` (foundation/build/peak), `intensity`, `status` (pending_review/approved/rejected), `content` (jsonb), `trainer_notes` (nullable), `generated_at`, `approved_at` (nullable)

**WeeklyCheckIn** — `member_id`, `gym_id`, `week_start_date`, `energy` (1–5), `recovery` (1–5), `motivation` (1–5), `submitted_at`

**Equipment** — `gym_id`, `branch_id` (nullable; _new_), `name`, `category` (nullable), `quantity`, `min_qty_threshold` (nullable), `condition` (good/needs_maintenance/under_maintenance/out_of_service), `purchase_date` (nullable; required by the source's FR but missing from its Table 4.16)

**MaintenanceLog** — `equipment_id`, `gym_id`, `reported_by`, `issue_text` (nullable), `reported_at`, `resolved_at` (nullable)

**ClassSession** — `gym_id`, `branch_id` (nullable; _new_), `trainer_id`, `name`, `scheduled_at`, `max_capacity`

**ClassBooking** — `session_id`, `member_id`, `gym_id`, `booked_at`, `attended` (nullable boolean)

**FreezeRequest** _(new)_ — `member_id`, `subscription_id`, `gym_id`, `requested_days`, `reason`, `status` (pending/approved/rejected), `decided_by`, `decided_at`, `rejection_reason`

**Announcement** _(new)_ — `gym_id` (nullable — null = platform notice), `author_id`, `title`, `body`, `created_at`

**Expense** _(new)_ — `gym_id`, `amount_etb`, `category`, `note`, `incurred_on`, `logged_by`

**MemberBadge** _(new)_ — `member_id`, `gym_id`, `badge_type` (first_check_in/thirty_day_streak/plan_completed), `awarded_at`

**AuthToken** _(new)_ — `user_id`, `purpose` (password_reset/invite/email_verification), `token_hash`, `expires_at`, `used_at`

**Notification** — `recipient_id`, `gym_id` (nullable — platform-level), `type`, `message`, `is_read` (default false), `created_at`

**AuditLog** — `gym_id` (nullable — platform-level), `actor_id`, `action_type`, `affected_record_type`, `affected_record_id`, `timestamp`, `metadata` (jsonb, nullable). **DB-level constraint: the application's Postgres role has INSERT and SELECT only — no UPDATE, no DELETE.**

## 9. State Machines

**MemberSubscription.status:**

- `pending → active`: cash payment recorded, or verified Chapa webhook.
- `active → expired`: nightly job when `end_date` has passed; reminders precede expiry.
- `active → frozen`: approved freeze (Growth/Pro, `freeze_days_allowed > 0`); the countdown pauses; on resumption frozen days are added to `end_date`, then `frozen → active`.
- `active/frozen → suspended`: Owner or Manager only; the QR token is invalidated immediately; only Owner/Manager can lift it by returning the subscription to `active`.
- `expired → pending`: when the member submits a new payment; the cycle repeats.

**TrainingPlan.status:** `pending_review → {approved, rejected}`. Only `approved` is visible to the member. A rejection triggers regeneration, creating a new `pending_review` plan with the trainer's notes.

**Equipment.condition:** `good → needs_maintenance → under_maintenance → {good (resolved), out_of_service}`; `out_of_service → good` when resolved. `under_maintenance` and `out_of_service` are both excluded from AI plans.

**GymTenant lifecycle:** created `active` by Super Admin. When `subscription_expires_at` passes, a grace period runs (`payment_grace_days`); if unpaid when it ends, `lapse_flagged_at` is set. Super Admin confirms → `suspended` (`suspended_at` set): staff and members blocked, Owner may export for 7 days, then Owner access closes; data is kept. A recorded renewal payment clears the flag and reinstates a suspended gym → `active`. `pending` and `terminated` are unused in this version.

**DemoRequest.status:** `new → contacted → demo_done → {converted, lost}`; `converted` is set when a gym is created from it.

## 10. Decided items, external checks, deferred features

**Decided**

- **Tenancy:** row-level `gym_id` scoping (the source's schema-per-tenant text is superseded).
- **Authentication:** JWT; Super Admin signs in only at the apex and gym users only at their own subdomain; every login failure returns one identical generic 401; five failed logins lock the account for a configurable time (Owner emailed, Super Admin logged only); tokens are bound to password_changed_at and to the host's tenant; DRF default permission is deny; Django admin only on the apex.
- **Hosting:** Yegara Host **Premium** — shared cPanel, no root/SSH. Django via the cPanel Python App Manager (Passenger WSGI), PostgreSQL via cPanel, TLS via AutoSSL (periodic, not instant), subdomains via cPanel UAPI rather than wildcard DNS. See `AGENT.md` Deployment and Sprint 38.
- **Scheduling:** cPanel Cron Jobs calling one idempotent Django management command; work that can't run inline uses a DB-backed job table. No Celery.
- **AI layer:** LiteLLM, self-hosted, synchronous; the underlying model is chosen by the trial procedure in Sprint 22.
- **Onboarding:** assisted only — Request a Demo, then Super Admin creates the gym after payment.
- **Billing:** yearly only, by bank transfer, with Owner reminders at 14 and 7 days, a 7-day configurable grace period, flag → Super Admin confirms suspension, 7-day export window, no deletion.
- **Payments:** one Chapa account per gym with encrypted credentials; cash stays for members; platform fees by bank transfer.
- **Storage:** Cloudinary Free plan behind Django's storage interface; member photos are `authenticated` assets served only through the backend; logos public; local folder in development.
- **Sprint grouping:** seven increments, final.

**External checks** (each has a fallback; none blocks a sprint — see `docs/SPRINTS.md`): cPanel UAPI `addsubdomain` enabled for the token; on-demand AutoSSL trigger; how to run one-time management commands on the host; Redis availability (fallback: database cache and job table); Chapa's merchant-account requirements for small gyms (fallback: cash-only until configured); Cloudinary sign-up, uploads and `authenticated` access from your network (fallback: host disk through the same storage interface).

**Deferred to a future version:** public self-serve gym registration and approval (with rejection handling); inactivity flags, escalation and the inactive-member report; Chapa subaccount mode and Chapa-paid platform fees; monthly billing and auto-renewal; mid-subscription plan changes; phone-number login; discounts; a full public landing page per gym; a Starter member cap and a setup fee; a data deletion/archival policy.

## 11. Deviations from the source document (deliberate)

| Source says                                                                                                                                                                                           | This project does                                                                                       | Why                                                                                                                            |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Schema-per-tenant (§1.7.3.2, §1.8.2)                                                                                                                                                                  | Row-level `gym_id` scoping                                                                              | Source contradicts itself; owner decision                                                                                      |
| Celery nightly task (§4.5.1)                                                                                                                                                                          | cPanel Cron + management command                                                                        | Shared hosting, no persistent workers                                                                                          |
| Single-instance cloud VPS (§1.4.2)                                                                                                                                                                    | Yegara cPanel shared hosting                                                                            | Owner decision after hosting was confirmed                                                                                     |
| Gym owner self-registers and Super Admin approves; tenant becomes `active` on first Chapa webhook (FG-UC-00-GYM)                                                                                      | Super Admin creates the gym after payment; no self-registration in this version                         | Target owners are non-technical; avoids an unpaid-gym state and the owner-logs-in-to-pay contradiction. Self-serve is deferred |
| Gym-owner onboarding form with custom add-ons                                                                                                                                                         | Request-a-Demo lead form; no add-ons                                                                    | Simplicity; add-ons are undefined in the source                                                                                |
| Monthly and yearly gym billing, auto-renewal                                                                                                                                                          | Yearly only, manual renewal by bank transfer                                                            | Simplicity; fits assisted onboarding                                                                                           |
| Gym subscription payments via Chapa                                                                                                                                                                   | `bank_transfer` for gym-to-platform payments                                                            | Platform has no Chapa account; avoids concentrating risk                                                                       |
| Owner completes Chapa onboarding; `chapa_merchant_id`                                                                                                                                                 | `GymPaymentConfig` with encrypted per-gym keys and a per-gym webhook                                    | Same intent; credentials secured, test mode possible per gym                                                                   |
| Owner edits GymConfig/feature toggles (Table 3.1a)                                                                                                                                                    | Entitlements Super Admin only; Owner edits settings                                                     | Otherwise an Owner could enable their own premium features                                                                     |
| Plan duration in months                                                                                                                                                                               | Duration in days or months                                                                              | Real gyms sell trials and short passes                                                                                         |
| Duplicate scan: notify staff                                                                                                                                                                          | Deny entry and notify staff                                                                             | Superset of the source behavior                                                                                                |
| `missed` attendance written by a nightly job; inactivity flags at 7 and 10 days, escalation, missed-days KPI, inactive-member report                                                                  | Attendance derived from check-ins; inactivity features deferred                                         | Owner decision; data is kept so they can be added later                                                                        |
| AI excludes only out-of-service equipment                                                                                                                                                             | Also excludes under-maintenance equipment                                                               | Unusable equipment shouldn't be prescribed                                                                                     |
| Analytics dashboard gated to Growth/Pro (UC 3.19)                                                                                                                                                     | Basic KPIs on every tier; premium charts Growth/Pro                                                     | A paying Starter gym should see its basics                                                                                     |
| "External AI API"                                                                                                                                                                                     | LiteLLM in-process, swappable model                                                                     | Provider-agnostic; satisfies the source's intent                                                                               |
| Staff accounts as the source describes; session handling                                                                                                                                              | Password change invalidates all sessions; deactivation checked on every request; soft-deactivation only | Security hardening beyond the source                                                                                           |
| QR token with 90-second validity                                                                                                                                                                      | Asymmetric signed JWT, 90 s                                                                             | Enables offline verification without exposing a secret                                                                         |
| `GymTenant.subdomain` varchar, Not Null                                                                                                                                                               | Same, plus DNS-label validation and reserved names                                                      | Required for cPanel provisioning                                                                                               |
| Offline sync via background sync                                                                                                                                                                      | Plus a replay-on-reconnect fallback                                                                     | Background sync is unsupported on iOS Safari                                                                                   |
| Multi-branch management                                                                                                                                                                               | Added (Pro tier)                                                                                        | Owner decision; not in the source                                                                                              |
| `has_multi_branch`, `payment_grace_days`, reminder/branding fields, `Branch`, `DemoRequest`, `FreezeRequest`, `Message`, `TrainerAvailability`, `Announcement`, `Expense`, `MemberBadge`, `AuthToken` | Added                                                                                                   | Required by the features above or by source requirements the source's data model omits                                         |

- Name and phone for every role live on User so profile editing is one code path; the Member table does not duplicate full_name/phone (the Member sprint reads them from User); Trainer specialization and the profile photo are delivered in the sprints that create the Trainer model and the Cloudinary storage layer.
