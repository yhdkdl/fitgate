# FitGate — Spec Reference

Condensed from `FitGate_Documentation_Corrected.docx` (the full document remains the legal source of truth; this file is a working reference derived from it for day-to-day development). If this file and the original docx ever disagree, the docx wins and this file should be corrected — flag it rather than silently trusting whichever one is more convenient.

## 1. Overview

FitGate is a multi-tenant gym management platform for the Ethiopian market (developed with Dire Dawa gyms as the initial context). It replaces paper attendance, unverified member access, opaque cash payment handling, unstructured trainer-member relationships, and the absence of personalized training guidance with a single Client-Server platform: React frontend, Django REST Framework backend, PostgreSQL, deployed per-tenant under subdomains of one shared installation.

## 2. Actors / Roles

- **Super Admin** — platform-level, not tied to a gym (`gym_id` is null). Approves/rejects/suspends gym tenants, manages tier changes, views platform-wide analytics, posts platform notices.
- **Owner** — one per gym tenant (created at approval). Full control of their gym: staff, plans, config, tier-gated features.
- **Manager** — staff role, scoped permission subset of Owner.
- **Trainer** — manages assigned members, reviews/approves AI-generated training plans, publishes availability, messages clients.
- **Reception** — front-desk role: check-in assistance, manual payment recording, member registration assistance.
- **Member** — end user of a specific gym; registers, checks in via QR, views their subscription/plan, messages their trainer.

## 3. Subscription Tiers & Feature Gating

Tiers: **starter / growth / pro** (per `GymTenant.tier`). Gating is enforced via `GymConfig` boolean flags per gym, not hardcoded by tier name, so an individual gym's flags can in principle diverge from its tier's default set — but the default mapping is:

| Feature                                                         | Starter | Growth | Pro |
| --------------------------------------------------------------- | ------- | ------ | --- |
| Core (multi-tenant, auth, member mgmt, QR attendance, payments) | ✅      | ✅     | ✅  |
| `has_trainer_module`                                            | ❌      | ✅     | ✅  |
| `has_ai_plans`                                                  | ❌      | ✅     | ✅  |
| `has_analytics`                                                 | ❌      | ✅     | ✅  |
| `has_group_classes`                                             | ❌      | ✅     | ✅  |
| Membership freeze (`freeze_days_allowed` > 0)                   | ❌      | ✅     | ✅  |
| Multi-branch management (`has_multi_branch`)                    | ❌      | ❌     | ✅  |

**Multi-branch management is not in the original source document** — it's a Pro-tier addition decided directly with the project owner, documented here and in `docs/SPRINTS.md` going forward as if it were part of the spec from the start. Design: a `Branch` belongs to exactly one `GymTenant` (nested under the existing `gym_id` tenancy boundary, not a new isolation mechanism). One subdomain per gym regardless of branch count — branch selection happens in-app, not via subdomain — because giving each branch its own subdomain would effectively make it a separate tenant and defeat the point of branches being sub-units of one Pro subscription. Member branch access is a `MembershipPlan` attribute (`all_branches_access`), not a fixed gym-wide rule, so a Pro gym can sell both single-branch and all-access plans. Staff are branch-scoped via a nullable `branch_id` (null = all branches, matching how Owner already has no scoping).

Gating must be enforced at **both** the backend (permission/serializer level — a Starter gym's API must reject trainer/AI/analytics/class endpoints, not just hide the UI) and the frontend (don't render nav/UI for ungated features).

## 4. Multi-tenancy

Row-level scoping: every gym-scoped table carries a `gym_id` foreign key to `GymTenant`. Tenant resolution is via subdomain (middleware resolves `{subdomain}.{DOMAIN}` → `GymTenant`, attaches to the request). Every query touching gym data must be filtered by `gym_id`; cross-tenant access must be architecturally impossible at the query layer (not just convention) — enforce via a base manager/queryset mixin, not per-view discipline. The middleware's resolution logic itself is unaffected by hosting constraints — it just needs the subdomain to exist and resolve in DNS, which is true regardless of how the subdomain was provisioned.

The apex domain (DOMAIN itself — e.g. fitgate.org or fitgate.tebebtech.com) is the public platform site, not any gym's app. A request to the apex sets request.tenant = None and is routed to: the public marketing/tier-info page, Gym Owner self-registration ("Subscribe to Platform"), and the Super Admin dashboard. A gym's actual app — where its Owner, staff, and members log in and operate — only exists at {subdomain}.{DOMAIN}, and that subdomain does not exist at all until Super Admin approves the gym (§5, §7). This split holds regardless of which candidate domain DOMAIN is set to, and switching between candidate domains (e.g. from the tebebtech.com subdomain to fitgate.org once finalized) is a DOMAIN env var change, not a code change — see AGENT.md rule 14.

Subdomain provisioning (hosting-constrained): the production host (Yegara Premium, shared/managed cPanel, no root) does not support wildcard DNS, so a gym's subdomain cannot simply "match anything automatically" the way an unmanaged VPS with wildcard DNS would allow. Instead, Super Admin approval (§5, §7) triggers a call to cPanel's UAPI to provision that specific subdomain at creation time. The subdomain is reachable over plain HTTP immediately, but cPanel's AutoSSL issues the certificate on its own periodic scan — not instantly — so there is a window (potentially up to roughly a day) where the subdomain exists without valid HTTPS. During that window, login and any credential-submitting action must be blocked with a clear "still being secured" state rather than forced through a broken HTTPS redirect or allowed over plain HTTP. See Sprint 4's acceptance criteria in docs/SPRINTS.md.

**Known internal conflict, resolved in favor of the option below:** §1.7.3.2 and §1.8.2 of the source document describe "PostgreSQL schema-based isolation, one schema per tenant" (i.e., actual Postgres `CREATE SCHEMA` per gym). This contradicts §3.2.1, §3.2.2, and every table in the data model (§4.8.1), which describe single-schema, row-level `gym_id` scoping. The project owner's confirmed decision is row-level `gym_id` scoping — build to that.

## 5. Functional Requirements (summary)

- Gym owners self-register ("subscribe to platform"); a gym is `pending` until Super Admin approval, then `active` with a subdomain provisioned via cPanel's UAPI (see §4) — the subdomain works over HTTP immediately, but HTTPS (and therefore login) may not be available for up to roughly a day until AutoSSL issues the certificate. This interim state must be surfaced clearly to the Owner, not hidden.
- Members register either self-service (public gym page) or staff-assisted (Reception/Owner/Manager entry).
- Every check-in uses a rotating QR token: server issues a token valid for a short window (see `QRToken.expires_at`, 90 seconds after issue), scanned at the gym to record `Attendance`. Duplicate/expired scans must be rejected, not silently accepted.
- Membership plans (`MembershipPlan`) are gym-defined templates; a member's actual enrollment over time is tracked separately (`MemberSubscription`) so historical plan membership is answerable.
- Payments support Chapa online checkout (covers telebirr, CBE Birr, bank cards) and manual cash entry with a staff confirmer. Chapa payments must be verified via webhook, and webhook handling must be idempotent (a redelivered webhook must not double-credit).
- Membership can be frozen (Growth/Pro only), pausing the expiry clock; freeze usage is tracked against `freeze_days_allowed`.
- Expired memberships must auto-deactivate QR check-in access; this is a scheduled job (implemented as a cPanel Cron Job calling a Django management command, not a persistent task-queue worker — see Deployment in `AGENT.md`), not something checked only at login.
- Trainer assignment: automatic algorithm balances by current client load with a "least recently assigned" tie-break (requires assignment history, not just a current-trainer pointer); manual reassignment by Owner/Manager must also be possible.
- AI Personal Training Engine is explicitly two-layer: a **rules-based Python engine** (not an ML model) computes phase (foundation/build/peak), intensity, equipment constraints, and session structure from the member's `FitnessProfile`; that computed context is then passed through **LiteLLM** (self-hosted integration layer, running inside the Django backend) to an external AI model, which generates the actual exercise/nutrition content. LiteLLM is the swap point: which underlying model it calls is a config change, not a code change. Nutrition guidance should reference locally available Ethiopian foods.
- Every AI-generated `TrainingPlan` is `pending_review` until a trainer approves or rejects it — a member must never see an unapproved plan.
- Weekly check-in (nominally Monday) captures energy/recovery/motivation (1–5 scale each) and feeds back into intensity adjustment for the next plan iteration.
- Equipment has a maintenance/condition lifecycle (`good` / `needs_maintenance` / `under_maintenance` / `out_of_service`) with issue reporting (`MaintenanceLog`) and low-quantity alerting; equipment condition should be usable to filter what the AI engine is allowed to prescribe.
- Group classes (`ClassSession` + `ClassBooking`) enforce capacity and are Growth/Pro gated.
- Analytics (attendance trends, inactivity detection, peak hours, cohort retention, revenue) are Growth/Pro gated.
- Every sensitive action is audit-logged (`AuditLog`), and the audit log itself must be tamper-evident: the application's DB role should have INSERT/SELECT only on that table, no UPDATE/DELETE, so tamper-resistance is enforced by the database, not only application code.
- Pro-tier gyms may manage multiple branches under one subscription (`has_multi_branch`). A branch is a sub-unit of the gym tenant, not a separate tenant. See §3 for the full design decision.
- Two design patterns are called out explicitly in the source document and should be reflected in the implementation: a **Factory pattern** for role-specific interface/dashboard generation at login, and a **Strategy pattern** for swappable intensity-calculation logic inside the rules engine.

## 6. Non-Functional Requirements (summary)

- **Tenant isolation:** every gym-data query must include a `gym_id` filter; cross-tenant access architecturally impossible at the query layer, not just application discipline.
- **Offline-first PWA:** core member/staff operations (at minimum, check-in) must remain functional during internet outages, syncing once connectivity returns. Workbox service worker + a local queue for actions taken offline.
- **Security:** password hashing, JWT auth, audit logging of sensitive actions, tamper-evident audit log at the DB-grant level.
- **Localization/context:** ETB currency by default, Ethiopian-context nutrition data, subdomain-based multi-tenancy suited to per-gym branding.
- **Configurability:** the deployment domain is not fixed at build time and must be a single settings/env value, never hardcoded.

## 7. Use Cases (condensed)

Grouped roughly in dependency order. Each entry: goal — key business rule(s).

**Platform / tenancy**

- Gym Owner subscribes to platform — creates `GymTenant` in `pending` status; no subdomain access until approved.
- Super Admin approves/rejects a gym — approval generates subdomain, creates the Owner `User`, sends a welcome notification; rejection is terminal for that application.
- Super Admin suspends/reinstates a gym — suspension should block staff/member access without deleting data.

**Auth & staff**

- User login (role-aware) — JWT issued; response/redirect should be role-appropriate (Factory pattern reference above).
- Password reset — single-use, time-expiring link.
- Owner/Manager invites staff (Manager/Trainer/Reception) — invite-and-set-password flow, not admin-set passwords.

**Members & attendance**

- Member self-registration vs staff-assisted registration — same underlying `Member` + `BodyMetrics` creation, different actor.
- QR check-in — token issued with a short validity window, scanned once, `Attendance` recorded; expired/reused tokens rejected.

**Membership & payment**

- Plan management — Owner/Manager CRUD on `MembershipPlan`.
- Member subscribes/renews to a plan — creates/extends `MemberSubscription`.
- Online payment (Chapa) — checkout session, webhook confirms, idempotent processing.
- Manual cash payment — staff-recorded, `confirmed_by` set, receipt generated.
- Freeze membership — Growth/Pro only; pauses subscription clock, tracked against `freeze_days_allowed`.
- Membership expiry — scheduled job deactivates QR access and notifies the member ahead of expiry.

**Trainer module**

- Automatic trainer assignment — load-balance + least-recently-assigned tie-break.
- Manual trainer reassignment — Owner/Manager override, closes prior `TrainerAssignment`, opens a new one.
- Trainer sets availability.
- Trainer↔member messaging.

**AI training engine**

- Member fitness intake — `FitnessProfile` captured at registration or later, editable by the assigned trainer.
- Plan generation — rules engine computes phase/intensity/equipment context, LiteLLM calls an external AI model to generate content, plan created as `pending_review`. Because production runs Django via Passenger WSGI with a request timeout (not a container with no such limit), a slow AI response risks timing out an inline request — if LiteLLM's response time proves unreliable under Passenger's timeout, generation should run through the same DB-backed job table + cron-poll mechanism used for other async work, rather than assuming it can always complete within one request.
- Trainer review — approve (member can now see it) or reject (regenerate / trainer edits).
- Weekly check-in — member submits energy/recovery/motivation; feeds the next intensity computation.

**Equipment, classes, analytics, communication**

- Report equipment issue — creates `MaintenanceLog`, may change `Equipment.condition`.
- Low-quantity/maintenance alerting to Owner/Manager.
- Group class scheduling and booking — capacity enforced at booking time.
- Analytics dashboards — Growth/Pro gated, per-gym scoped.
- Notice board / broadcast communication.
- Data export (CSV) — members, payments, attendance.

**Multi-branch (Pro) — not in source document, see §3**

- Owner creates/manages branches under their gym — CRUD, `has_multi_branch` gated.
- Owner assigns staff to a branch, or leaves unscoped for all-branch access.
- QR check-in validates branch access against the member's `MembershipPlan.all_branches_access`, not just subscription status.
- Branch-scoped staff see only their branch's equipment, class sessions, and attendance; Owner and unscoped staff see all branches, individually and aggregated.

**Platform admin**

- Super Admin platform-wide analytics and tenant management (tier changes, suspension).

_(This is a condensed index, not a replacement for the full use-case tables (actors, preconditions, main/alternate flows) in the original document — consult the docx for the full flow of any specific use case before implementing it.)_

## 8. Data Model

All tables carry `id` (uuid, PK) unless noted. Every gym-scoped table carries `gym_id` (FK → `GymTenant`), nullable only where explicitly noted for platform-level records.

**User** — `gym_id` (null for Super Admin), `branch_id` (nullable — null means unscoped/all-branch access; only meaningful for staff roles at a `has_multi_branch` gym, Owner is always effectively unscoped; _new field, not in source document_), `email` (unique), `password_hash`, `role` (super_admin/owner/manager/trainer/reception/member), `is_active`, `created_at`, `last_login`

**GymTenant** — `name`, `subdomain` (unique), `status` (pending/active/suspended/terminated), `tier` (starter/growth/pro), `currency` (default ETB), `created_at`

**GymConfig** — `gym_id` (PK+FK, 1:1 with GymTenant), `has_trainer_module`, `has_ai_plans`, `has_analytics`, `has_group_classes`, `has_multi_branch` (all boolean, default false), `chapa_merchant_id` (nullable, set once Chapa onboarding completes), `freeze_days_allowed` (default 0)

**Branch** _(new — not in source document, see §3)_ — `gym_id`, `name`, `address` (nullable), `is_primary` (boolean, default false), `created_at`

**Member** — `gym_id`, `user_id` (FK → User), `full_name`, `phone`, `date_of_birth`, `gender`, `emergency_contact`, `referral_source`, `photo_url`, `status` (active/expired/frozen/suspended), `joined_at`

**BodyMetrics** — `member_id`, `gym_id`, `weight_kg`, `height_cm`, `measurements` (jsonb, free-form), `recorded_at`

**MembershipPlan** — `gym_id`, `name`, `duration_months`, `price_etb`, `trainer_inclusive` (boolean), `is_active` (default true), `all_branches_access` (boolean, default true — only meaningful for gyms with `has_multi_branch`; _new field, not in source document_)

**MemberSubscription** — `member_id`, `gym_id`, `plan_id` (FK → MembershipPlan), `start_date`, `end_date`, `status` (pending/active/frozen/suspended/expired), `freeze_start_date` (nullable), `frozen_days_total` (default 0)

**QRToken** — `member_id`, `gym_id`, `token_hash`, `issued_at`, `expires_at` (issued_at + 90s), `is_active` (default true)

**Attendance** — `member_id`, `gym_id`, `branch_id` (nullable — set for gyms with `has_multi_branch`; _new field, not in source document_), `date`, `status` (checked_in/missed/blank), `checked_in_at` (time, nullable)

**Payment** — `gym_id`, `payer_type` (gym_subscription/member), `member_id` (nullable — null for gym-subscription payments), `subscription_id` (FK → MemberSubscription, nullable), `method` (chapa/cash), `amount_etb`, `chapa_ref` (nullable), `status` (pending/confirmed/failed), `confirmed_by` (FK → User, nullable — set for manual cash payments), `created_at`

**Trainer** — `gym_id`, `user_id` (FK → User), `specialization` (nullable), `max_clients` (default set by owner)

**TrainerAssignment** — `member_id`, `trainer_id`, `gym_id`, `assigned_at`, `ended_at` (nullable, set on reassignment), `assigned_by` (FK → User, nullable — null for automatic assignment)

**FitnessProfile** — `member_id` (PK+FK), `gym_id`, `goal`, `fitness_level`, `limitations` (text), `equipment_prefs` (text), `training_days_per_week`, `updated_at`

**TrainingPlan** — `member_id`, `trainer_id`, `gym_id`, `phase` (foundation/build/peak), `intensity` (integer), `status` (pending_review/approved/rejected), `content` (jsonb — AI-generated exercise/nutrition content), `trainer_notes` (nullable), `generated_at`, `approved_at` (nullable)

**WeeklyCheckIn** — `member_id`, `gym_id`, `week_start_date`, `energy` (1–5), `recovery` (1–5), `motivation` (1–5), `submitted_at`

**Equipment** — `gym_id`, `branch_id` (nullable — set for gyms with `has_multi_branch`; _new field, not in source document_), `name`, `category` (nullable), `quantity`, `min_qty_threshold` (nullable), `condition` (good/needs_maintenance/under_maintenance/out_of_service)

**MaintenanceLog** — `equipment_id`, `gym_id`, `reported_by` (FK → User), `issue_text` (nullable), `reported_at`, `resolved_at` (nullable)

**ClassSession** — `gym_id`, `branch_id` (nullable — set for gyms with `has_multi_branch`; _new field, not in source document_), `trainer_id`, `name`, `scheduled_at`, `max_capacity`

**ClassBooking** — `session_id` (FK → ClassSession), `member_id`, `gym_id`, `booked_at`, `attended` (nullable boolean)

**Notification** — `recipient_id` (FK → User), `gym_id` (nullable — null for platform-level notifications), `type`, `message`, `is_read` (default false), `created_at`

**AuditLog** — `gym_id` (nullable — null for platform-level actions), `actor_id` (FK → User), `action_type`, `affected_record_type`, `affected_record_id`, `timestamp`, `metadata` (jsonb, nullable). **DB-level constraint: the application's Postgres role must be granted INSERT and SELECT only on this table — no UPDATE, no DELETE.**

## 9. State Machines

**MemberSubscription.status:** `pending → active → {frozen, suspended, expired}`. `frozen` only reachable if `GymConfig.freeze_days_allowed > 0` for the gym. `frozen → active` on unfreeze/expiry of freeze window.

**TrainingPlan.status:** `pending_review → {approved, rejected}`. Only `approved` plans are visible to the member.

**Equipment.condition:** `good → needs_maintenance → under_maintenance → {good, out_of_service}`.

**GymTenant.status:** `pending → active → {suspended, terminated}`; `suspended → active` reinstatement possible.

## 10. Known Conflicts / Open Items

- **Tenancy isolation mechanism:** source document contradicts itself (schema-per-tenant in §1.7.3.2/§1.8.2 vs. row-level `gym_id` scoping in §3.2.1/§3.2.2/§4.8.1). Resolved: build row-level `gym_id` scoping, per the project owner's explicit decision.
- **Figure 1.1 (six development increments):** referenced in §1.7.2 but the source docx contains no embedded image data for any figure. The grouping in `docs/SPRINTS.md` is a derived approximation from the surrounding text, not a transcription — treat as provisional until confirmed against the actual diagram.
- **Production hosting environment — resolved, and this reversed an earlier decision:** originally planned as an unmanaged VPS with Docker Compose + Caddy in production. Confirmed instead: Yegara Host **Premium** plan — shared/managed cPanel hosting, no root/SSH access. This changes production deployment substantially: Django via cPanel's Python App Manager (Passenger WSGI, not Docker), PostgreSQL via cPanel (confirmed available), TLS via cPanel AutoSSL (periodic, not instant — see §4 and §5), subdomains provisioned via cPanel's UAPI (API token access confirmed available) rather than wildcard DNS. See `AGENT.md`'s Deployment entry for the full detail and Sprint 38 in `docs/SPRINTS.md` for the rebuilt production-hardening sprint.
- **Task queue — resolved as a consequence of the above:** Celery's persistent worker model is not assumed viable on shared hosting without root. Scheduled jobs use cPanel Cron Jobs calling Django management commands; async work that can't safely run inline (e.g., a slow AI call — see §5) uses a DB-backed job table polled by a cron-triggered command, not a live queue. Whether Redis is available at all in production (for this or for caching) is unconfirmed — check if cPanel offers it as an add-on.
- **AI integration layer:** resolved — LiteLLM, self-hosted in the Django backend. **Underlying model:** not yet chosen; plan is to trial candidates via OpenRouter's free tier for output-quality comparison, then point LiteLLM at the winner directly (see Sprint 22).
- **File storage:** local volume vs. S3-compatible object storage for photos/branding — not yet chosen, and now constrained by the same no-root limitation (self-hosted S3-compatible storage like MinIO isn't viable on shared hosting the way it would be on a Docker-based VPS).
