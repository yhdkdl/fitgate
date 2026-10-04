# FitGate — Sprint Plan

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done (PR merged to `develop`)

> **⚠️ Not yet confirmed.** Increments 1–5 and 7 are derived from §1.7.2's prose, not transcribed from Figure 1.1 (which is a caption with no image data in the source docx) — confirm or correct that grouping before Sprint 1 starts. **Increment 6 (multi-branch) is not in the source document at all** — it was added by direct decision with the project owner; see `docs/SPEC.md` §3.
>
> **⚠️ Production hosting changed.** The project moved from an unmanaged VPS (Docker + Caddy) to Yegara Host **Premium** (shared/managed cPanel, no root). Sprints 4, 14, 22, and 38 below already reflect this; Sprints 1–13, 15–21, and 23–37 are unaffected since they describe app-level behavior, not deployment mechanics. See `docs/SPEC.md` §10 for the remaining open items (underlying AI model, file storage, Redis availability) that some sprints below depend on.
>
> Every sprint below now carries **acceptance criteria** — concrete, testable statements a diff should satisfy before it's considered done. These are in addition to, not instead of, the general Definition of Done checklist in `AGENT.md` (migrations clean, tests passing, lint clean, etc.) — that checklist is process hygiene applied identically to every sprint; the criteria below are what "correct" actually means for that specific sprint's logic.

---

## Sprint 0 — Project scaffolding

Docker Compose (Django + Postgres + Redis + **pgAdmin**), Django project skeleton, Vite+React skeleton, repo/branch structure (`main`/`develop`), base settings split (local/prod), `.env.example`, pre-commit hooks (ruff/black, eslint/prettier), pytest-django wired up and runnable, drf-spectacular installed.

pgAdmin is a local-development convenience only — a GUI client connected to the same live `postgres` container, not a separate data store. It must not be part of the production deployment (cPanel hosting has no Docker to run it on anyway — see Sprint 38); keep it isolated to a dev-only Compose override or profile so it never gets mistaken for something that needs to exist in production.

**Acceptance criteria:**

- `docker compose up` brings up Django, Postgres, Redis, and pgAdmin cleanly from a fresh checkout with no manual steps beyond copying `.env.example` to `.env`.
- pgAdmin is reachable at its exposed port and can connect to the `postgres` service using credentials from `.env` (pre-configured, not something you manually enter via pgAdmin's UI every restart).
- A row changed through Django (e.g., via `manage.py shell` or the admin) is visible in pgAdmin after a refresh — confirms it's pointed at the live container, not a stale/separate instance.
- `pytest` runs successfully with zero tests collected (proves the harness itself works, not just that no tests exist to fail).
- A deliberately malformatted commit (e.g., bad Python formatting) is blocked by the pre-commit hook, not silently allowed through.
- `.env.example` lists every variable the settings files actually reference, with no real secret values in it.

- [x] Status: done

## Increment 1 — Platform foundation (multi-tenancy, auth, access control, attendance)

1. **Core tenant models + subdomain middleware** — GymTenant, GymConfig, tenant-scoping base manager/mixin, subdomain-resolution middleware.
   - A request to a known gym's subdomain resolves `request.tenant` to that `GymTenant`; a request to an unknown subdomain fails clearly (404/error), not silently proceeds with no tenant.
   - `DOMAIN` must be tested as a two-label value, not just single-label ones. One of our actual candidate domains (`fitgate.tebebtech.com`) is already two labels before any gym subdomain is added, making a gym's real host three labels deep (`gymname.fitgate.tebebtech.com`). With `DOMAIN` explicitly set to "fitgate.tebebtech.com" in the test: (a) `gymname.fitgate.tebebtech.com` resolves to that gym tenant, and (b) `fitgate.tebebtech.com` itself (the apex, no gym) sets `request.tenant = None` rather than being misread as a subdomain lookup and 404ing. Implementation must use suffix-matching against the full `DOMAIN` value, not "everything before the first dot."
   - A query made through the tenant-scoped base manager, without the caller explicitly adding a `gym_id` filter, still only returns the current tenant's rows — proven with a test seeding two tenants' data and asserting no cross-tenant leakage.
   - Creating a `GymTenant` auto-creates its `GymConfig` with all feature flags defaulting to `false`.

   - [x] Status: done

2. **Custom User model + JWT auth** — login, logout, token refresh.
   - Valid credentials return access + refresh tokens; invalid credentials return 401 with no stack trace or information about which field was wrong.
   - Refresh issues a new access token without requiring the password again.
   - A request without a token to a protected endpoint returns 401, not a 500 or an empty 200.

3. **Password reset** — single-use, time-expiring link.
   - A reset link works once; a second use of the same link fails.
   - An expired link fails with a clear error rather than silently succeeding.
   - The response is identical whether or not the submitted email exists in the system (no account-enumeration leak).

4. **Gym Owner self-registration + Super Admin approval** — pending → active, subdomain provisioning via cPanel UAPI, Owner `User` creation, welcome notification.
   - A new registration creates a `GymTenant` in `pending` status with its subdomain not yet reachable.
   - Approval atomically: sets status to `active`, provisions the subdomain via cPanel's UAPI, creates the Owner `User`, and triggers a welcome notification — test that a failure partway through doesn't leave a half-created gym (in local dev, where there's no real cPanel to call, this step should be mocked/stubbed, not skipped — the atomicity test still needs to cover it).
   - Rejection is terminal — a rejected application cannot later be approved without a fresh registration.
   - A `pending` gym's subdomain returns a clear "not yet active" response, not a 500 or silently empty data.
   - **Hosting-constrained safeguard (see `docs/SPEC.md` §4):** until the subdomain's TLS certificate is confirmed valid (AutoSSL runs on its own periodic schedule, not instantly), the app must not force an HTTPS redirect on it and must block login specifically — not just general browsing — showing a "still being secured" state instead. Test that login is refused while the stored cert-status flag is unconfirmed, and allowed once it flips to valid.

5. **RBAC framework** — permission classes + Owner/Manager permission matrix enforcement.
   - For each role in the permission matrix (Table 3.1a), both an allowed action (succeeds) and a denied action (403, not 200) are covered by a test — not just the allowed side.

6. **Staff provisioning** — Manager/Trainer/Reception invite-and-set-password flow.
   - An invited user cannot authenticate until they've completed the set-password step via their invite link.
   - The invite link is single-use and expires.
   - Only Owner/Manager can issue invites — enforced at the API level, not just hidden in the UI.

7. **Member registration** — self-service + staff-assisted, `Member` + `BodyMetrics`.
   - Self-service and staff-assisted registration both produce an identical `Member` + `BodyMetrics` structure — no field divergence between the two paths.
   - A duplicate registration (same identifying field) within one gym is rejected, per whatever uniqueness rule is defined.

8. **QR check-in** — token issuance/rotation (90s window), scan endpoint, `Attendance`, duplicate/expired-scan rejection.
   - A token is valid at 89 seconds after issue and rejected at 91 seconds — tested with a mocked/frozen clock, not real sleeps.
   - Reusing an already-consumed token on a second scan is rejected.
   - A scan for a member without an active subscription is rejected with a distinguishable reason (expired vs. frozen vs. suspended), not a generic failure.
   - A legitimate single scan produces exactly one `Attendance` row — no duplicates.

9. **Audit log foundation** — `AuditLog` model + logging utility wired into 1–8; restricted DB role (INSERT/SELECT only) for this table.
   - Every action from sprints 1–8 produces exactly one `AuditLog` row with the correct `actor_id`, `action_type`, and affected record.
   - An `UPDATE` or `DELETE` attempted directly against the audit log table, using the application's own DB role, fails at the database level — test this directly rather than trusting the grant was applied correctly.

- [ ] All sprints in this increment complete

## Increment 2 — Membership & payments

10. **Membership plans & subscription lifecycle** — `MembershipPlan` CRUD, `MemberSubscription` state machine.
    - Creating a subscription against an inactive (`is_active=false`) plan is rejected.
    - Every disallowed state transition is explicitly tested and rejected (e.g., `expired → active` without a new payment) — not just the happy path through the state machine.
    - A gym's plans are not visible or usable from another gym's context.

11. **Chapa payment integration** — checkout, webhook verification, idempotency.
    - A redelivered webhook (same event twice) does not double-credit the subscription or create a duplicate `Payment` — this is the core test for this sprint.
    - A webhook with an invalid/unverifiable signature is rejected, not processed.
    - A successful payment correctly extends/activates the related `MemberSubscription`; a failed payment does not.

12. **Manual cash payment fallback** — staff-confirmed, digital receipt.
    - A manual `Payment` cannot be created with `confirmed_by` null.
    - A digital receipt is generated and retrievable, matching the actual amount and plan recorded.

13. **Freeze workflow** — Growth/Pro gated, tracked against `freeze_days_allowed`.
    - A freeze request on a gym with `freeze_days_allowed = 0` is rejected at the API level, not just hidden in the UI.
    - Freezing measurably pauses the subscription's expiry clock — test that `end_date` shifts by the frozen duration once unfrozen.
    - A freeze request exceeding the gym's remaining allowance is rejected.

14. **Expiry automation** — a Django management command (`expire_subscriptions` or similar), scheduled via a **cPanel Cron Job** in production (not Celery Beat — see `AGENT.md` Deployment); runnable manually or via a Compose-scheduled equivalent in local dev. Covers the nightly sweep, renewal reminders, and QR auto-deactivation.
    - Running the command against a seeded mix of subscriptions flips only the ones past `end_date` to `expired`, leaving others untouched.
    - An expired subscription's member is rejected at QR check-in going forward (ties to Sprint 8's rejection logic).
    - A renewal reminder is created once per subscription ahead of expiry — running the command twice in a row doesn't duplicate it (this matters more without Celery Beat's built-in single-run guarantee — cron can double-fire if a run overlaps, so the command itself must be idempotent, not just scheduled once).

15. **Notification center** — `Notification` model, in-app read/unread.
    - A notification created for one gym/member is not visible to another gym's recipient.
    - Marking a notification read is idempotent and persists across requests.

- [ ] All sprints in this increment complete

## Increment 3 — Trainer module (non-AI)

16. **Trainer profile & capacity** — `Trainer` model, `max_clients` config.
    - A trainer's current client count is correctly derived from active `TrainerAssignment` rows, exposed accurately for Sprint 17 to consume.

17. **Trainer assignment** — automatic (load-balance + least-recently-assigned tie-break) + manual reassignment.
    - Automatic assignment selects the eligible trainer with the lowest current client count; on a tie, the least-recently-assigned trainer wins — both rules tested explicitly against a seeded scenario, not just one or the other.
    - A trainer at `max_clients` capacity is never selected by automatic assignment.
    - Manual reassignment closes the prior `TrainerAssignment` (sets `ended_at`) and opens a new one — no member ever has two simultaneously-open assignments.

18. **Trainer availability schedule.**
    - Availability correctly reflects added and removed slots when queried per trainer.

19. **Trainer↔member messaging.**
    - A member can only message their currently assigned trainer, not an arbitrary trainer at the gym.
    - Messages are not visible to any third party outside the conversation.

- [ ] All sprints in this increment complete

## Increment 4 — AI Personal Training Engine

20. **FitnessProfile intake** — self + staff-captured, trainer-editable.
    - The profile is editable by the member's assigned trainer, and rejected for an unrelated trainer or another member.
    - Required fields (`goal`, `fitness_level`, `training_days_per_week`) reject submission when missing, rather than silently defaulting.

21. **Rules engine** — phase/intensity/equipment-filter computation (pure Python, test-heavy; implement the Strategy pattern here for swappable intensity logic).
    - Deterministic output is covered by unit tests across at minimum: a beginner/foundation case, an advanced/peak case, and a case where `equipment_prefs`/limitations measurably exclude equipment from the computed output.
    - Two different intensity-calculation strategies can be plugged in and produce different outputs from the same input without any change to the calling code — test the Strategy-pattern swap directly.

22. **LiteLLM integration layer** — self-hosted in the Django backend, called from behind the swappable-provider interface. Prompt construction, content storage, retry/fallback. _Underlying model still to be chosen (trial via OpenRouter's free tier first — see open items) — build and test this sprint against whichever model is fastest to trial, then swap via LiteLLM config once a model is picked, without touching this sprint's code._ **Runs synchronously within the request** (no Celery worker available on shared hosting — see `AGENT.md` Deployment); LiteLLM's own retry/fallback happens inline. Confirm the chosen model's response time stays comfortably within the Passenger WSGI request timeout once that's known — if it doesn't, fall back to a DB-backed job table polled by a cron-triggered command instead of blocking the request.
    - A simulated provider failure/rate-limit on the primary deployment correctly falls through to the next configured deployment in the Router's fallback list — tested with a mocked provider error, not a real one.
    - Generated content is stored on the correct `TrainingPlan` row in `pending_review` status, and is not fetchable by the member before trainer approval.
    - Total provider failure (all fallbacks exhausted) produces a clear "generation failed" state, not a silent hang or a plan that's incorrectly marked approved.

23. **Trainer review workflow** — `TrainingPlan` approve/reject state machine, gated member visibility.
    - A member cannot fetch a `pending_review` plan — tested as a direct permission check, not just a UI omission.
    - Rejecting a plan preserves `trainer_notes` and the rejected content; nothing is deleted.
    - Only the assigned trainer (or Owner/Manager) can approve/reject — an unrelated trainer cannot.

24. **Weekly check-in** — energy/recovery/motivation capture, feeds intensity adjustment.
    - A second check-in for the same `week_start_date` and member is rejected.
    - A low-recovery/low-energy check-in measurably changes the next computed intensity versus a high-recovery one, given the same underlying `FitnessProfile` — test the feedback loop actually changes output, not just that the check-in is stored.

- [ ] All sprints in this increment complete

## Increment 5 — Equipment, classes, analytics, communication

25. **Equipment registry & maintenance** — `Equipment`, `MaintenanceLog`, low-quantity alerts, AI exclusion-filter wiring.
    - Reporting an issue creates a `MaintenanceLog` and can transition `Equipment.condition` — test the transition, not just log creation.
    - A quantity exactly at `min_qty_threshold` triggers an alert; one above it does not (boundary test).
    - Equipment marked `under_maintenance` or `out_of_service` is excluded from what Sprint 21's rules engine is allowed to prescribe — test this integration point directly.

26. **Group class scheduling & booking** — `ClassSession`, `ClassBooking`, capacity enforcement, Growth/Pro gated.
    - Booking is accepted for the session's last available slot and rejected on the next attempt once `max_capacity` is reached (boundary test).
    - Booking endpoints reject a Starter-tier gym's request (`has_group_classes = false`) at the API level.

27. **Analytics dashboard** — attendance, inactivity, peak hours, cohort retention, revenue; Growth/Pro gated.
    - Every analytics endpoint rejects a Starter-tier gym's request at the API level, not just omits the UI entry.
    - Figures returned are scoped to the requesting gym only — verified against a seeded multi-tenant dataset where a cross-gym figure appearing would be an obvious tell.

28. **Notice board & broadcast communication.**
    - A broadcast reaches all intended recipients of the issuing gym and is not visible to another gym's users.

29. **CSV export** — members, payments, attendance.
    - Exported rows, headers, and row count match a known seeded dataset exactly, scoped to the requesting gym only.

- [ ] All sprints in this increment complete

## Increment 6 — Multi-branch management (Pro tier)

_Not in the original source document — added by direct decision with the project owner. See `docs/SPEC.md` §3 for the full design rationale. Depends on Increment 1 (tenant/staff models), Increment 2 (`MembershipPlan`), and Increment 5 (`Equipment`, `ClassSession`) all being in place, which is why this sits here rather than earlier._

30. **Branch model + management** — `Branch` CRUD (Owner only), gated by `GymConfig.has_multi_branch`; frontend in-app branch switcher. One subdomain per gym regardless of branch count.
    - Branch CRUD endpoints reject requests on a gym without `has_multi_branch` at the API level.
    - Adding a gym's first branch doesn't break existing single-branch-gym behavior — a regression pass against Increments 1–5's tests still passes with `has_multi_branch=false`.

31. **Branch-scoped staff** — nullable `branch_id` on `User` (null = all-branch, matching Owner's existing unscoped access); RBAC updated so branch-scoped staff only see their branch's operational data.
    - A staff user with a set `branch_id` sees only that branch's data; a `null`-`branch_id` user sees all branches — both cases tested explicitly, including confirming Owner's access is unaffected either way.

32. **Branch-aware check-in & attendance** — `branch_id` on `Attendance`; QR check-in validates the scan's branch against `MembershipPlan.all_branches_access` and the member's subscription, not just subscription status alone.
    - A member whose plan has `all_branches_access=false` is rejected checking in at a branch other than their home branch; a `true`-flag member succeeds at any branch of the gym — both cases tested.
    - Recorded `Attendance.branch_id` matches the actual scan location.

33. **Branch-aware equipment & classes** — `branch_id` on `Equipment` and `ClassSession`; branch-scoped maintenance alerts, class booking, and trainer assignment.
    - Equipment/class queries for a branch-scoped staff member return only that branch's records, mirroring Sprint 31's pattern applied to these two models.

34. **Plan-level branch access** — `MembershipPlan.all_branches_access` flag + plan management UI; lets a Pro gym sell both single-branch and all-access plans.
    - The flag is settable only on gyms with `has_multi_branch`; it has no effect on single-branch gyms regardless of its stored value.

- [ ] All sprints in this increment complete

## Increment 7 — Platform administration, PWA, deployment

35. **Super Admin platform dashboard** — tenant management (approve/reject/suspend/tier change), platform-wide analytics, platform notices.
    - Super-Admin-only actions are rejected for every other role, including an Owner acting on their own gym.
    - Suspending a gym blocks staff/member access while leaving the gym's data intact and still visible to Super Admin — test both halves of that claim.

36. **GymConfig feature-flag enforcement** — backend permission layer + frontend render gating, for every tier-gated feature above, including `has_multi_branch`.
    - Full regression pass: every previously-built tier-gated endpoint (trainer module, AI plans, analytics, group classes, multi-branch) is re-verified to reject a gym missing the corresponding flag. This sprint's specific job is closing any gaps individual earlier sprints missed — treat a clean pass here as the actual proof the gating is complete, not a formality.

37. **Offline-first PWA** — Workbox service worker, local check-in queue, background sync.
    - A check-in performed while offline is queued locally and produces exactly one `Attendance` row once connectivity returns and sync runs — no duplicate on reconnect.
    - The app shell is served correctly while offline, not a browser error page.

38. **Production hardening (cPanel-based — rebuilt from the original Docker/Caddy/VPS plan)** — deploy Django via cPanel's Python App Manager (Passenger WSGI), wire the cPanel UAPI subdomain-provisioning call from Sprint 4 to the real account (not a stub), confirm PostgreSQL connection settings against cPanel's provided database, set up the cPanel Cron Job for Sprint 14's management command, resolve whether Redis is available on this plan and configure the cache backend accordingly (database/filesystem cache as the fallback), DB backups via whatever cPanel/Yegara backup mechanism is available, `DOMAIN` fully parameterized end-to-end.
    - A fresh deploy to the actual Yegara Premium account succeeds end-to-end from documented steps, with every environment-specific value sourced from `.env`, not hardcoded.
    - The cPanel UAPI call in Sprint 4 is confirmed working against the real account — a real subdomain actually gets provisioned on gym approval, not just the local-dev stub.
    - The AutoSSL gap behaves as designed under real conditions: a freshly provisioned subdomain is reachable over HTTP, login is correctly blocked until the cert is confirmed valid, and the app correctly detects the cert becoming valid without a manual flag flip.
    - The cPanel Cron Job actually fires the expiry-sweep command on schedule — verified against real execution, not just that the command works when run manually.
    - Changing `DOMAIN` in `.env` and redeploying requires no code or config changes anywhere else in the project — the final proof of the "never hardcoded" rule from `AGENT.md`.

- [ ] All sprints in this increment complete

---

## Open items to resolve before/along the way (see `docs/SPEC.md` §10)

- [ ] Confirm/correct the six-increment grouping above against the real Figure 1.1
- [x] Production hosting: Yegara Host **Premium** (shared/managed cPanel, no root) — confirmed; Docker/Caddy/VPS assumption reversed throughout Sprints 4, 14, 22, 38
- [x] Task scheduling: cPanel Cron Jobs + Django management commands, replacing Celery — confirmed, no functionality lost (see Sprint 14)
- [x] AI integration layer: LiteLLM, self-hosted, called synchronously (no worker process) — confirmed
- [ ] Trial candidate models via OpenRouter's free tier, then configure LiteLLM to call the chosen one directly (blocks final tuning of Sprint 22, not the sprint's build itself) — also confirm the chosen model's response time fits within Passenger's WSGI request timeout
- [ ] Choose file storage backend (local volume for dev; cPanel shared hosting has no Docker in prod, so self-hosted S3-compatible storage like MinIO isn't viable there either — affects Sprint 0 and Sprints 7/20 photo upload fields)
- [ ] Confirm whether Redis is available on the Yegara Premium plan at all (affects caching only — Celery's removal above means Redis is no longer load-bearing for scheduling)
- [ ] Confirm with Yegara support whether the cPanel API token can trigger an on-demand AutoSSL check, or whether Sprint 4/38's "wait for the periodic scan" assumption is the real behavior to design around
