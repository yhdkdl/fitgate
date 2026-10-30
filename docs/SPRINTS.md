# FitGate — Sprint Plan

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done (PR merged to `develop`). Only the project owner marks a sprint `[x]`, after merging.
GATE = the agent stops after this sprint and waits for the owner's review before continuing.

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

Docker Compose (Django + Postgres + Redis + **pgAdmin**), Django project skeleton, Vite+React skeleton, repo/branch structure (`main`/`develop`), base settings split (local/prod), `.env.example`, pre-commit hooks (ruff/black, eslint/prettier), pytest-django wired up and runnable, drf-spectacular installed. Pinned to Python 3.11.17 and Django 5.2 LTS (see `AGENT.md`).

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

**Preflight (external items):**

- Sprint 4 (cPanel UAPI token; fallback: mocked UAPI locally)
- Sprint 4b (Cloudinary Free account and keys; fallback: local folder through the storage interface)
- Real email (SMTP mailbox; fallback: console backend)

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

   - [x] Status: done — merged to develop (PR #5)

2. **Custom User model + JWT auth + platform-level base class** — login, logout, token refresh; Super Admin bootstrap.
   - Valid credentials return access + refresh tokens; invalid credentials return 401 with no information about which field was wrong. Token lifetimes are configurable settings.
   - Refresh issues a new access token without the password; a request without a token to a protected endpoint returns 401.
   - **Lockout:** five consecutive failed logins temporarily lock the account (duration is a setting) and notify the gym's Owner; a successful login resets the counter; during a lock, even the correct password is refused.
   - **Session validity:** every authenticated request checks the user is still active and that the token was issued after `password_changed_at`; a deactivated user's existing token is rejected immediately.
   - **Super Admin bootstrap:** a management command reads `SUPERADMIN_EMAIL` and `SUPERADMIN_PASSWORD` from the environment and creates the first Super Admin (`gym_id` null). It is idempotent (a second run changes nothing), the account must change its password at first login, and no HTTP endpoint can create the first Super Admin (test that no such route exists).
   - An existing Super Admin can create further Super Admins; the action is audit-logged and requires re-entering the creator's password; every other role gets 403. The last remaining active Super Admin cannot be deactivated.
   - **Platform-level base class:** `User`, `Notification` and `AuditLog` (nullable `gym_id`) use a second base class. Inside a gym, its manager shows only that gym's rows; at the apex (no tenant) it shows only platform rows (`gym_id` null). A test proves gym rows never appear at the apex and platform rows never appear inside a gym.
   - **Factory pattern:** login returns a role-specific dashboard configuration built by a factory; each role gets its own, an unknown role fails.

   Decisions made in review:
   - Super Admin logs in only at the apex; gym users only at their own subdomain. Every login failure (unknown email, wrong password, wrong host, locked, inactive) returns the same generic 401 (status and body); an unknown email still runs a dummy password hash.
   - The lockout counter resets when an expired lock is found, so after expiry one typo does not re-lock. Gym users' Owner is emailed; Super Admin lockouts are logged only. A failed email never changes the login response.
   - Tokens carry role, gym_id and password_changed_at (integer microseconds), checked on every request and on refresh.
   - is_staff and is_superuser are derived from role, not stored.
   - Public auth views declare authentication_classes = [] and AllowAny; the DRF default permission is deny; a contract test enforces explicit permission declarations.
   - must_change_password: RequirePasswordChanged is in the DRF default permissions and must be listed explicitly by any view that overrides permission_classes (a contract test for this arrives in Sprint 2a).
   - Django admin is served on the apex only (404 on gym subdomains).

   - [x] Status: done — merged to develop (PR #6)

2a. **Profile and password management** — account settings for every role.

- A user can view and edit their own name and phone (a Trainer also specialization) without approval.
- Changing the password requires the current password, and invalidates all of that user's existing sessions including refresh tokens.
- Attempts to change `role`, `gym_id`, account status, membership status or `max_clients` through the profile endpoint are rejected or ignored — tested for each field.
- Password-strength validation with Django's validators (minimum length 10, common-password, numeric-only, user-attribute similarity), applied to the change-password endpoint and also to Super Admin creation and the create_super_admin command.
- Make the lockout counter update atomic (select_for_update or F()) if time allows.
- A contract test: every project view that is not AllowAny and not an auth endpoint must include RequirePasswordChanged, and every AllowAny project view must declare authentication_classes explicitly.

Trainer specialization and photo are delivered in the Trainer and storage sprints (see SPEC §11).

- [x] Status: done — merged to develop (PR #8)

3. **Password reset** — single-use, time-expiring link.
   - A reset link works once; a second use fails. An expired link fails with a clear error.
   - The response is identical whether or not the email exists (no account enumeration).
   - A successful reset invalidates all existing sessions of that user.

   Decisions:
   - Reset is host-scoped like login: Super Admin at the apex, gym users at their own subdomain. A request on the wrong host behaves exactly like an unknown email.
   - The reset link is built from the user's own gym subdomain and settings.DOMAIN, never from request headers.
   - A successful reset also clears failed_login_count and locked_until, and does not log the user in (they must re-authenticate).
   - At most one reset email per user per PASSWORD_RESET_COOLDOWN_SECONDS (silent).
   - Known follow-up: the request endpoint's response time differs slightly when an email is sent (no job queue yet).

   - [x] Status: done — merged to develop (PR #9)

3a. **Frontend shell and auth screens** - Vite React app shell with Tailwind and the tokens from docs/DESIGN.md, React Router, TanStack Query, API client built on the generated TypeScript types. - Dev proxy forwards the ORIGINAL Host header so tenant resolution works at `<gym>.localhost:5173` as well as `localhost:5173`; Vite allows `*.localhost` hosts. - Login screen (apex for Super Admin, gym subdomain for gym users); every failure shows the same generic message; no field-level hints about what was wrong. - Token handling: access token in memory, refresh token handling chosen and documented (explain the choice and the risk in the PR); one in-flight refresh at a time; on refresh failure the user is sent to login; logout calls the logout endpoint. - Forced change-password screen when `must_change_password` is true; every other route is blocked until done. - Forgot-password and reset-password screens; the reset page reads the token from the URL and removes it from the address bar immediately (`history.replaceState`). - Profile page: edit name and phone, change password. - Role dashboard shell: navigation and placeholder cards driven by the login response's dashboard config; protected-route guard by role. - Tests (Vitest + React Testing Library): login success and failure, forced password change, route guard, refresh interceptor, reset-token removal from the URL. Lint and prettier clean. Usable at 320px. - "You can now test": log in as Super Admin at localhost, change the forced password, edit profile, log out, run the forgot-password flow reading the link from the backend logs.

    - [x] Status: done — merged to develop (PR #11)

4. **Super Admin "Create gym"** — gym creation after payment, subdomain provisioning via cPanel UAPI, Owner creation, welcome message.

- Only Super Admin can create a gym; every other role gets 403.
- Creation goes through one service function, `create_gym(...)`; the endpoint is a thin wrapper and the tests call the function directly.
- Inputs: gym name, location, contact name/phone/email, tier, subdomain (proposed from the name, editable, validated unique/DNS-label/not reserved), Owner name and email, and the payment record (amount, method must be `bank_transfer`, reference, verified by = the acting Super Admin). Optional `demo_request_id` links a demo request (Sprint 4a). Create Gym tier choices offer Starter and Growth only (Pro is hidden and not selectable until multi-branch ships in Increment 6; if set in DB, Pro defaults equal Growth with `has_multi_branch=false`; `has_group_classes` is false across all tiers).
- Atomically: creates the `GymTenant` as `active`, its `GymConfig` with flags set to the chosen tier's defaults (Starter or Growth; Pro is hidden until Increment 6; `has_group_classes` is false), the `Payment` (`payer_type = gym_subscription`, `method = bank_transfer`, status confirmed), the Owner `User` (pre-verified, no password set), a single-use expiring set-password invite, and provisions the subdomain via cPanel's UAPI. A failure at any step (including the UAPI call) leaves nothing half-created. In local development the UAPI call is mocked, not skipped; the atomicity test still covers it.
- The welcome message contains the set-password link, never a password.
- A `chapa` method is rejected for `gym_subscription` payments; a duplicate or reserved subdomain is rejected.
- No code path produces a `pending` gym in this version.
- **Certificate safeguard (see `docs/SPEC.md` §4):** until the subdomain's TLS certificate is confirmed valid, the app does not force an HTTPS redirect on it and refuses login and registration specifically, showing a "still being secured" state. Login is refused while `tls_confirmed_at` is null and allowed once it is set. When it is set for the first time, `subscription_expires_at` is set to one year later.
- A migration adds the `GymTenant` columns listed in SPEC §8 and the `GymConfig` fields `payment_grace_days` (default 7), `subscription_reminder_days` (default 14 and 7) and `member_reminder_days` (default 7 and 2).

- [x] Status: done — merged to develop (PR #12)

4a. **Demo requests** — public "Request a Demo" form and Super Admin lead list.

- The public endpoint exists on the apex only and is rejected on a gym subdomain. Required: gym name, contact name, phone; optional: city, email, message.
- Rate limiting is enforced and tested; a filled honeypot field returns success but stores nothing. The throttle uses the database cache backend (Redis is not assumed).
- A stored request has status `new` and creates a platform-level notification for Super Admin.
- Only Super Admin can list requests, filter by status, add notes, and move a request through new → contacted → demo done → converted / lost; other roles get 403.
- "Convert to gym" returns the data that pre-fills Sprint 4's form; creating the gym with that `demo_request_id` marks the request `converted` and links the new gym.

- [x] Status: done — merged to develop (PR #13)

4b. **File storage layer** — Cloudinary (Free plan) behind Django's storage interface.

- Member photos are stored as `authenticated` assets in per-gym folders (`gyms/<gym_id>/…`). They are served only through a backend view that checks the requester is logged in and belongs to that gym; the browser never receives a Cloudinary URL. Requesting another gym's photo returns 403/404 — tested.
- Gym logos are stored as public assets.
- Uploads are validated server-side before storage: image type only, maximum size (2 MB), random file names; an invalid upload is rejected with a clear error. Images are resized on upload.
- Credentials come from the environment; local development and tests use a local folder through the same interface (a fake storage in tests). The Cloudinary `authenticated` type is verified once against a real account before release (see "External checks").

- [x] Status: done — merged to develop (PR #14)

4c. **Gym branding, entry page, first-run checklist**

- `GymConfig` gains optional `brand_color` (hex) and a logo reference. Both are Owner-editable settings; when empty, a default theme and the gym name are shown. Branding and entry pages operate within the gym's assigned tier (Starter or Growth; Pro is hidden until Increment 6 ships; `has_group_classes` is false across all tiers).
- A public entry page endpoint on the gym subdomain returns the gym name, brand color, logo, phone and location. The page offers Log in and Register; the plan list is added in Sprint 10. Before the certificate is confirmed it shows the "still being secured" state.
- A first-run checklist is shown to the Owner only: add branding, create a first plan, add a staff account, register a first member. Items tick automatically from real data (no manual flags), and the checklist can be dismissed; dismissal persists.

- [x] Status: done — merged to develop (PR #15)

4d. **Public platform landing page** (non-GATE, built after Sprint 9a by owner decision)

1. Opening the platform's main address (http://localhost:5173 locally; the apex in production) shows a public FitGate landing page. No login is needed.
2. The page explains what FitGate does for a gym, using only features that are in docs/SPEC.md (membership management, QR check-in, attendance, trainer tools, AI personal training plans, payments, multi-branch).
3. It shows Starter and Growth with a placeholder price per year (12,000 / 30,000 ETB per year) and what each tier includes, taken from the tier table in docs/SPEC.md. Pro is hidden and not offered, advertised or selectable until multi-branch ships in Increment 6, and shows no price until it ships. The prices live in ONE place in the code so changing a price is a one-line edit.
4. A clear "Request a Demo" button takes the visitor to the existing form; submitting it shows the existing confirmation.
5. A short "How it works" section: request a demo, we set up your gym after payment, your gym gets its own address.
6. A "Go to my gym" box: the visitor types their gym's name (subdomain) and is taken to that gym's own address; an invalid name shows a clear message. A small "Platform sign in" link in the footer goes to the existing Super Admin login.
7. It looks right on a phone (320px) and on a desktop, in the dark theme from docs/DESIGN.md, is readable, and works with the keyboard. It uses no external fonts, images or scripts.
8. On a gym's own address the root page still shows that gym's entry page (unchanged).
9. The page has a proper title and description for search engines.

- [x] Status: done — merged to develop (commit fa095ed, tag sprint-4d-done)

5. **RBAC framework (GATE)** — permission classes + Owner/Manager permission matrix enforcement.
   - For every role in the permission matrix (SPEC §2), both an allowed action (succeeds) and a denied action (403, not 200) are covered by a test.
   - **Entitlements vs. settings:** an Owner's attempt to change `tier`, any `has_*` flag, `freeze_days_allowed`, `payment_grace_days` or `subscription_reminder_days` is rejected (403) at the API level; the same Owner can change `brand_color`, `member_reminder_days` and their payment credentials; a Manager can change none of them. Super Admin can change the entitlements.
   - **Super Admin vs. gym settings:** Per SPEC §2 Table 3.1a, Super Admin modifies entitlements only (`/api/platform/gyms/<id>/config/`) and cannot edit gym operational settings (`brand_color`, reminder days, logo) or access the Owner checklist on gym subdomains.

- [x] Status: done — merged to develop (tag sprint-5-done)

6. **Staff provisioning** — Manager/Trainer/Reception invite-and-set-password flow, deactivation.
   - An invited user cannot authenticate until they complete the set-password step; the invite link is single-use and expires; invited accounts count as email-verified.
   - Owner can create Managers, Trainers and Reception; Manager can create only Trainers and Reception — a Manager creating a Manager gets 403, enforced at the API.
   - **Deactivation** blocks login and invalidates existing tokens immediately, never deletes, and keeps that user's history (audit entries, messages, approvals) visible to everyone who could see it before. No foreign key to a user cascades a delete, and there is no user hard-delete route. The email stays reserved; reactivation is possible instead of creating a duplicate.

- [x] Status: done — merged to develop (tag sprint-6-done)

7. **Member registration** — self-service + staff-assisted, `Member`, waiver, verification, photo.
   - Self-service and staff-assisted registration produce an identical `Member` structure (registration captures no body measurements; body measurements are recorded exclusively by Trainers in Sprint 7b).
   - A duplicate registration (same identifying field) within one gym is rejected.
   - Accepting the health waiver is required (`waiver_accepted_at` stored); registration without it is rejected.
   - A self-registered member must verify their email by single-use, expiring link before first login; staff-registered members receive a set-password link and count as verified. Public registration is rate-limited.
   - A profile photo uploads through Sprint 4b's storage layer; member self-service photo ownership is wired there, with an exact-match check against the Member record (Members read their own photo only through the exact-match check).
   - Member photo read access for Trainers must narrow to their assigned members (Sprint 17 wires assignment).
   - **Profile photo policy (owner decision):** Staff-assisted registration provides an optional profile photo picker with preview (JPEG, PNG, WebP up to 2 MB). Public self-service registration accepts NO file uploads to protect against storage abuse; members add or change their own photo from their profile screen after signing in. Owner, Manager and Reception can upload or change a member's photo from the member detail modal/profile; Trainers and staff of other gyms cannot. Photos remain private and load exclusively through the authenticated, permission-checked backend route (`/api/media/member-photos/{gym_id}/{filename}/`).

- [x] Status: done — merged to develop (tag sprint-7-done)

7b. **Trainer-only body measurements** (non-GATE, built out of order by owner decision, before Increment 2)

1.  Registering a member, through the public Register page and as staff, no longer asks for height, weight, waist, neck or hip. Both forms still ask for name, email, phone, date of birth, gender, emergency contact, photo and the waiver.
2.  A Trainer can open a "Member measurements" screen, search members of their own gym by name, email or phone, and see a member's latest measurements and history.
3.  A Trainer can record a new set of measurements (weight kg and height cm required; waist, neck and hip cm optional). It appears in the member's history with the date and the trainer's name.
4.  After a Trainer records them, the member's profile shows BMI and estimated body fat as labeled estimates. Before that it says "Not measured yet. A trainer records measurements."
5.  Reception sees no measurements anywhere and cannot enter any. Owner and Manager can view but not enter. A Member can view their own measurements and history but cannot enter or edit them. Super Admin sees none.
6.  Anyone who is not a Trainer who tries to record measurements directly through the API is refused, and a Trainer cannot record for a member of another gym.
7.  Every recording is written to the audit log with the trainer as the actor.
8.  Until Sprint 17, any Trainer of the gym can record for any member of that gym (assignment-based narrowing comes in Sprint 17).
9.  Measurements already saved stay.

- [x] Status: done — merged to develop (`fa06902`, tag sprint-7b-done)

8. **QR check-in (GATE)** — token issuance/rotation (90 s window), scan endpoint, `Attendance`, duplicate/expired-scan handling, manual override.
   - The token is a signed JWT (asymmetric signature, private key in the environment, public key exposed so a scanner can verify offline). A tampered token is rejected; a token is valid at 89 seconds after issue and rejected at 91 — tested with a frozen clock.
   - Reusing an already-consumed token is rejected. A new token is issued after each valid use.
   - A scan for a member without an active subscription is rejected with a distinguishable reason (expired vs. frozen vs. suspended), and the screen shows the member's photo, name and status on success.
   - A legitimate single scan produces exactly one `Attendance` row. A second scan the same day is denied, produces no second row, and notifies staff.
   - **Manual override** by Reception: requires an active subscription and a reason, produces exactly one `Attendance` row and an audit entry, and is refused for expired, frozen or suspended members.
   - `Attendance` rows exist only for actual check-ins. An attendance-log endpoint returns ✓/✗ per day for a date range, derived from check-ins and the subscription period (days outside the period are blank).
   - Performance: scan validation plus attendance recording completes in under 2 seconds against a seeded dataset of 10,000 members.
   - _Note:_ changed from RS256 to EdDSA so the QR is small enough for webcams and tablets.

- [x] Status: done — merged to develop (tag sprint-8-done)

8b. **Camera QR scanner** — browser-based camera scan for reception, owner and manager. - A receptionist (or Owner or Manager) can tap "Scan with camera" on the scanner screen and see a live camera view. - Holding a member's QR code in front of the camera checks them in: the same result card appears (name, photo, status, green pass), exactly as when the code is pasted. - A rejected scan (expired, frozen, suspended, duplicate, replayed code) shows the same clear message as the paste field. - Holding the code in view does not scan it again and again: after one read the camera pauses reading for about 3 seconds, so staff are not spammed with duplicate notifications. - The paste field still works as before. - If camera permission is denied, no camera exists, the camera is busy, or the page is not secure (not HTTPS and not localhost), the screen says so in plain words and the paste field stays usable. - The camera turns off when the scanner is closed, when staff leave the screen, or when the browser tab is hidden. - It works at 320px width, with 44px buttons and a visible focus ring, and the result never relies on color alone (docs/DESIGN.md). - No camera image or video ever leaves the device (decoding happens in the browser).

    - [x] Status: done — merged to develop (`fdc63bc`, tag sprint-8b-done)

8c. **Entrance scanner page and live check-in list** (builds on Sprint 8b)

1. Reception, Owner and Manager can open "Entrance scanner" from their dashboard. It opens a full-screen page for a tablet with only the camera view and one line of instructions (gym name and logo on top).
2. A member holds the QR code on their phone up to the tablet's camera and is checked in without staff touching anything.
3. On success a large green screen shows the member's name, photo and check-in time for about 3 seconds, then returns to scanning.
4. When a member cannot enter, a large red or amber screen says why in plain words with an icon and what to do: membership expired, frozen, suspended, already checked in today (amber), code expired (refresh your pass), code already used (refresh your pass).
5. The tablet screen never shows phone number, email or any other personal data beyond name and photo.
6. A code held in view is not read again and again (the 3-second pause from Sprint 8b).
7. The camera can be switched front/back and the choice is remembered on that device. A small "Enter code manually" link keeps the paste field. Clear messages for camera permission denied, no camera, camera in use, and page not secure (not HTTPS and not localhost).
8. The screen stays awake while scanning (use the Screen Wake Lock when the browser has it). The camera turns off when staff leave the page or the tab is hidden.
9. If the staff session expires, the page says "Staff must sign in again" instead of failing silently. Otherwise it keeps working all day (the normal session refresh keeps running).
10. It works at 320px and at tablet sizes, with large text, 44px buttons, and no meaning carried by color alone (text and icon on every result), per docs/DESIGN.md.
11. No camera image or video leaves the device.
12. Reception, Owner and Manager see a "Today's check-ins" list on their dashboard: each entry shows photo, name, time and whether it was a scan or a manual override, newest first, with today's count.
13. When someone scans at the entrance tablet, their entry appears on that list within about 5 seconds without refreshing the page (the page checks for new entries about every 5 seconds; no websockets, because the hosting has no permanent worker process).
14. Trainers, Members and other gyms cannot see this list.
15. Repeated scans by the same member on the same day send staff ONE notification, not many.

- [x] Status: done — merged to develop (`7d2120c`, tag sprint-8c-done)

9. **Audit log foundation** — `AuditLog` model + logging utility wired into 1–8; database triggers for immutability (BEFORE UPDATE, DELETE, TRUNCATE raise exception).

- _Note (Sprint 8 Gate decision):_ extend the existing AuditLog model with a NEW migration (never edit 0005) that adds the triggers; do NOT create a second model or recreate the table.
- Every action from sprints 1–8 produces exactly one `AuditLog` row with the correct `actor_id`, `action_type` and affected record, including logout, Super Admin creation, and gym creation (platform-level rows have `gym_id` null).
- An `UPDATE`, `DELETE`, or `TRUNCATE` against the audit table fails at the database level via PostgreSQL triggers — tested directly with raw SQL through the application connection.

- [x] Status: done — merged to develop (tag sprint-9-done)

9a. **Audit log viewer**

- Owner and Manager see their own gym's entries; Super Admin sees all; every other role gets 403.
- Entries are paginated, newest first, filterable by date range, action type and actor, and the endpoint is read-only (no update or delete verbs).

- [x] Status: done — merged to develop (tag sprint-9a-done)

9b. **Email safety (Brevo bounce protection & delivery safeguard)** (Non-gate)

1. Local development never sends real mail (console only); fake addresses keep working.
2. In staging and production ("strict mode", an explicit EMAIL_STRICT_MODE setting, no default in production) the system never sends to reserved test domains (example.com/.org/.net, .test, .invalid, .localhost, .local); forms refuse them with "Use a real email address"; sends are skipped and logged.
3. In strict mode the domain must exist and accept mail (DNS lookup, short timeout); a definite "no such domain / no mail server" is refused; if the lookup itself fails, accept and log (never block people because of our DNS).
4. Throw-away email domains are refused for public self-registration (one bundled list; documented how to update it).
5. Brevo webhook (hard bounce, blocked, invalid, spam complaint): read Brevo's official documentation for event names and authentication; do not guess; list in docs/MANUAL_STEPS.md which pages you used. The address goes on our suppression list and is never emailed again; the person who typed it sees "Email not delivered" with "Fix the address and resend". Public endpoint on the apex that accepts only requests carrying the secret (BREVO_WEBHOOK_SECRET, required in production, no default, constant-time compare); a wrong or missing secret returns the same response as an unknown event.
6. The Super Admin types an owner's email twice; staff invitations and front-desk registration show the address back before sending.
7. Invitations show a status (sent, not delivered, activated); resend limited to 3 per address per day.
8. Owners, Super Admin and invited staff: strict. Front-desk members: lenient: registration is never blocked by an email problem; the member exists and manual check-in works; the invitation shows "not delivered" until fixed.
9. Public self-registration: per-IP and per-gym rate limits, only the single verification email until verified, unverified accounts older than 7 days marked expired (management command cleanup_unverified_members plus cron line in MANUAL_STEPS).
10. Safety caps: a configurable maximum of emails per hour per gym and per platform; beyond it mails are skipped and the user sees "email limit reached".
11. Optional staging allow-list EMAIL_ALLOWED_RECIPIENTS (addresses or domains): only those get real mail.
12. "Email not delivered" is visible only to staff of the same gym (Super Admin for owners).

- [ ] Status: in progress — branch feature/sprint-9b-email-safety

- [x] All sprints in this increment complete

---

## Staging deploy prep (between Increment 1 and Increment 2)

Preparation for deploying the Increment 1 milestone to the real Yegara cPanel staging environment (`fitgate.tebebtech.com`).

**Acceptance criteria:**

1. Requirements split into `base.txt`, `prod.txt`, `dev.txt`; dev/test packages excluded from prod; exact versions pinned.
2. Production settings fail fast on missing secrets or invalid config (no silent fallbacks to insecure defaults).
3. Automated tests against PostgreSQL 13 pass (or compatibility shim documented and tested).
4. Subdomain creation derives root domain and subdomain hierarchy from `DOMAIN` (no hardcoded domain names).
5. Management commands `check_cpanel_uapi`, `send_test_email`, `generate_secret_key`, `generate_tenant_credentials_key` exist and work.
6. `deploy/passenger_wsgi.py` loads settings, environment, and exposes application correctly.
7. WhiteNoise serves frontend and static files; unknown non-API routes fall through to React `index.html`.
8. Email display name sanitization prevents header injection.
9. `deploy/build_release.sh` and `deploy/build_release.ps1` produce a self-contained release zip.
10. `docs/DEPLOY_STAGING.md` covers every step click-by-click for cPanel.

- [x] Status: done — merged to develop (tag staging-prep-done)

---

## Increment 2 — Membership & payments

**Preflight (external items):**

- Sprint 11: A Chapa TEST merchant account for the gym (test keys). Keys are entered by the gym Owner in that gym's settings screen (per-gym tenant credentials, encrypted at rest), not in `.env`. The staging host is online over HTTPS, so Chapa test webhooks can reach it without a tunnel once deployed to staging; until then signed mocked webhooks are used. Fallback if skipped: signed mocked webhooks plus a documented entry in `docs/MANUAL_STEPS.md`, with the feature marked "not verified against the real service".

10. **Membership plans & subscription lifecycle (STRICT)** — The agent stops and reports for the owner's review before merging, because it changes the shared check-in code and where member status comes from.
    - All check-ins (QR scan and manual override) go through ONE internal function; the QR scan and the manual override are thin callers of it. No behaviour change for staff, and all existing QR and check-in security behaviour stays as approved at the Sprint 8 gate (existing tests stay green).
    - Every attendance record stores how the member got in (a stored `method` field: `qr` or `manual_override`). `method` is the single source of truth. The existing `is_override` column STAYS, is written ONLY by the shared check-in function from `method`, and a database CHECK constraint makes them always agree (`is_override` is true exactly when `method` is `manual_override`). Use ordered migrations, not one combined step: add the field as optional, backfill existing rows (override rows become `manual_override`, the rest `qr`), then make it required and add the constraint. Do not make `is_override` a Python property (it could not be used in database filters). Every query or test that uses `is_override` is UPDATED to stay correct, never deleted or weakened; say in your reply how many places you updated. A later method (NFC card, wristband, fingerprint terminal) must be addable by writing a new caller of the same function, with no change to subscription, duplicate, audit-logging or notification logic (all of that lives inside the shared function).
    - Member status: `MemberSubscription` is the single source of truth. `Member.status` stays a stored, indexed column but is derived: only ONE shared function may write it, it always computes the value from the member's subscription, and it runs in the same transaction as every subscription change (bought, renewed, frozen, unfrozen, expired, suspended). Nothing else may set `Member.status`. Add a fifth value `pending` (registered, no subscription yet) and record this SPEC change in `docs/OPEN_QUESTIONS.md` and SPEC section 2 (member status). A new member starts as `pending`. Check-in refuses pending members with its own plain message ("no active plan yet"), and check-in NEVER trusts `Member.status`: it reads the subscription and its dates directly and refuses when unclear. "Active members" counts and expiry-based lists use the subscription end date, so they stay exact between nightly sweeps. Existing members are backfilled by running the same function once. Add one test that compares stored status against computed status across a seeded set (pending, active, expired, frozen, suspended, renewed). Record the choice and the reason in `docs/OPEN_QUESTIONS.md` when Sprint 10 runs. If the agent sees a reason against this choice, it says so in OPEN_QUESTIONS and in the report; it never silently does something different.
    - The current rule that a second check-in on the same day is refused stays. Do not add a gym setting for multiple daily check-ins in this sprint; note it as a possible later setting in the same sprint entry.
    - Sprint 10 does NOT add any branch fields.
    - The Sprint 10 report must say in plain words how the unchanged check-in behaviour was verified and show each member-status case.
    - What gym users can do after this sprint:
      - Gym staff can create, view, edit, and deactivate membership plans with durations specified in days or months.
      - End dates are accurately calculated for month durations, including month-end days (such as January 31 + 1 month).
      - New subscriptions can only be created for active plans; deactivating a plan hides it from new signups while leaving existing subscriptions intact.
      - Updating a plan's price does not alter past payments or active subscriptions.
      - Creating a plan that includes personal training warns staff if the gym currently has no trainers.
      - Member subscription status moves strictly according to business rules (for example, expired subscriptions cannot become active without payment, and only gym owners or managers can suspend or unsuspend a member).
      - Plans belong strictly to their gym and are never visible or usable by another gym.
      - Visitors on the public gym website can view all active plans with their prices without needing to log in.
    - _Note on multiple daily check-ins:_ A gym setting to allow multiple daily check-ins per member is noted as a possible future setting; it was not added in this sprint (second check-in on the same day remains strictly refused).
    - Status: implemented, full suite green — awaiting owner review (branch `feature/sprint-10-membership-plans`, STRICT sprint)

11. **Chapa payment integration (one account per gym) (GATE)** — Sprint 11 builds the `Notification` record and ONE shared helper function that creates a notification (stored only, no email, scoped to the gym) so notification criteria are immediately verifiable. What gym users can do after this sprint:
    - _Subscription creation rule:_ Subscriptions must never be creatable or renewable by staff without a recorded payment. The ONLY paths that create or renew a subscription are (a) a verified Chapa payment confirmation (this sprint) and (b) a staff-confirmed cash payment (Sprint 12), each executed in the exact same database transaction as its payment record.
    - Gym owners can enter and update their gym's Chapa payment credentials securely in their gym settings, with keys stored encrypted and masked from view.
    - Only the gym owner can view or edit payment credentials; other staff and platform administrators cannot access them.
    - Gym owners can test their Chapa connection to verify their keys before enabling online member checkout.
    - Members can pay for their subscription online with Chapa if the gym has verified credentials; otherwise, the system offers cash payment.
    - When Chapa confirms a payment, the member's subscription is immediately activated or extended without creating duplicates if payment confirmations are repeated, and a notification is recorded for the member.
    - If an online payment fails or is abandoned, a notification is recorded for the member with options to retry or pay cash.
    - Online payments left unfinished beyond 30 minutes are flagged, and a notification is recorded for staff follow-up.
    - Platform administrators can view whether a gym is running in test mode or live mode.
    - Chapa cannot be used to pay platform gym subscription fees.

12. **Manual cash payment, payment history, and the registration-to-payment flow** — What gym users can do after this sprint:
    - _Subscription creation rule:_ Subscriptions are created or renewed via staff-confirmed cash payment in the exact same database transaction as the confirmed payment record; subscriptions are never created without a payment.
    - Reception staff can record and confirm cash payments from members and issue an official digital receipt.
    - Direct bank transfer is introduced in Sprint 12b with owner reconciliation and reversal; cash payments must always record which staff member confirmed them.
    - Members can view their complete payment history with dates, amounts, and receipt references.
    - Gym owners and managers can review payments filtered by date, payment method, and status, and see confirmed revenue totals.
    - A new member can register on the gym site, pick a plan, and either pay online immediately or have reception confirm cash at the desk before receiving their active QR check-in pass.

12b. **Bank transfer payments, reconciliation, and reversal (STRICT)** — The agent builds this on branch feature/sprint-12b-bank-transfer and the owner reviews it in the final report. What gym users can do after this sprint: - _Subscription creation rule:_ Subscriptions are created or renewed via staff-confirmed bank transfer in the exact same database transaction as the payment record, digital receipt, and audit entry. - Reception, Manager, and Owner can record a member's bank-transfer payment using their bank reference, transfer date (not in the future), optional channel (CBE, Telebirr, Awash, Other), and optional note. - The payment amount is locked to the membership plan price at that moment and cannot be typed or discounted. - Submitting a bank-transfer payment uses client idempotency keys created on modal open to prevent double submits. - The bank reference follows the shared rule (3 to 100 characters), is compared case-insensitively, and must be unique per gym forever (even across reversed payments). Duplicate references are refused with a plain message that does not expose another member's information. - Every bank transfer recorded by Reception or Manager starts as "unreconciled". Only the gym Owner can view unreconciled bank transfers and clear them individually or in bulk against their bank statement. If the Owner records the payment, it is cleared automatically with an audit log entry. - A daily scheduled command flags unreconciled bank transfers older than 7 days, setting a flagged time once, sending the Owner a single summary notification, and writing audit log entries naming the staff member who confirmed the payment. - The gym Owner can reverse an unreconciled bank-transfer payment with a required reason (5 to 500 characters). Reversal is recorded in an immutable database record, marks the digital receipt as reversed, excludes the payment from revenue summaries, and restores the member's subscription to its exact state prior to that payment (pending for first purchase; previous end date and status for renewals). - Reversal is refused if the member has had any subsequent payment, freeze, or subscription change. - Members can view their bank-transfer payments in their personal history (including method, bank reference, and reversal status), and receipts display the transfer method and reference. - Super Admin is strictly denied on member bank transfers, receipts, reconciliation, and reversals.

13. **Freeze workflow (Growth/Pro gated, tracked against freeze days allowed)** — What gym users can do after this sprint:
    - Members can submit a freeze request specifying their duration and reason, provided their gym allows freezes and they have days remaining.
    - Freeze requests on gyms with zero allowed freeze days, or requests exceeding the remaining allowance, are blocked with a clear message.
    - Gym owners and managers can review, approve, or reject freeze requests (with an explanation for rejections).
    - Approving a freeze pauses the member's QR pass and extends their membership end date by the frozen days, and a notification is recorded for the member.
    - Rejecting a freeze request leaves the pass active with an explanation, and a notification is recorded for the member.

14. **Scheduled jobs (automated daily maintenance tasks)** — Requires Sprint 9b (email safety) to be built first, because Sprint 14 sends the first automatic emails. What gym users can do after this sprint:
    - Subscriptions past their end date automatically expire, deactivating check-in passes, and frozen memberships automatically reactivate when the freeze ends.
    - Members and reception staff receive renewal reminder notices before a membership expires according to gym reminder settings.
    - Gym owners receive reminder notices before their gym platform subscription expires, and gyms continue operating during the payment grace period.
    - If a gym's grace period ends unpaid, the platform administrator is alerted without abruptly shutting off gym access mid-day.
    - Unconfirmed payments lingering past the review window are flagged for staff review.
    - Running the maintenance job multiple times in a row never produces duplicate notifications, flags, or updates.

- [x] Status: done — merged to develop (tag sprint-14-done)

15. **Notification center (in-app screens)** — Notification records and the shared creation helper were built in Sprint 11; Sprint 15 delivers the user-facing screens and mark-as-read interaction. What gym users can do after this sprint:
    - Members and staff can view their own in-app notifications in a dropdown or panel (bell with unread count), organized with unread notices first.
    - Notifications are strictly separated so gym members and staff only see messages for their gym, while platform alerts go exclusively to Super Admin.
    - Users can mark notifications as read, and the read status remains saved when returning.

- [x] Status: done — merged to develop (tag sprint-15-done)

- [x] All sprints in this increment complete

## Increment 3 — Trainer module (non-AI)

_Increment 3 = Sprints 16 and 17 only; Sprints 18 and 19 are deferred to a future version (see docs/SPEC.md §10)._

**Preflight (external items):** None

16. **Trainer profile & capacity** — `Trainer` model, `max_clients` config.
    - A trainer's current client count is correctly derived from active `TrainerAssignment` rows, exposed accurately for Sprint 17.

- [x] Status: done — merged to develop (tag sprint-16-done)

17. **Trainer assignment (GATE)** — automatic (load-balance + least-recently-assigned tie-break) + manual reassignment.
    - Automatic assignment selects the eligible trainer with the lowest current client count; on a tie, the least-recently-assigned trainer wins — both rules tested against a seeded scenario.
    - A trainer at `max_clients` is never selected by automatic assignment. If every trainer is at capacity, no assignment is made and Owner/Manager are notified.
    - Assignment happens only for members on trainer-inclusive plans. The trainer and the member are both notified of a new or changed assignment.
    - Manual reassignment closes the prior `TrainerAssignment` (`ended_at`) and opens a new one; a member never has two open assignments. Manual reassignment may exceed capacity after an explicit confirmation, and is audit-logged.
    - Deactivating a trainer who has active clients is rejected unless the same action reassigns every one of them; a deactivated trainer's clients are never left silently unassigned.

18. **Trainer availability schedule.** (Deferred to a future version, see docs/SPEC.md §10)
    - Availability reflects added and removed slots when queried per trainer (a trainer maintains their own weekly availability).

19. **Trainer↔member messaging.** (Deferred to a future version, see docs/SPEC.md §10)
    - One thread per member–trainer pair; a member can only message their currently assigned trainer. After reassignment the member can no longer message the previous trainer, and old messages stay readable by the two participants.
    - Each message notifies the recipient. Messages are not visible to any third party, and a deactivated trainer's history remains.

- [ ] All sprints in this increment complete

## Increment 4 — AI Personal Training Engine

**Preflight (external items):**

- Sprint 22 (OpenRouter free API key; fallback: mock AI provider)

20. **FitnessProfile intake** — self + staff-captured, trainer-editable.
    - The profile is editable by the member's assigned trainer (including from the plan review screen), and rejected for an unrelated trainer or another member.
    - Required fields (`goal`, `fitness_level`, `training_days_per_week`) reject submission when missing, rather than silently defaulting.
    - Height and weight come from the latest Trainer-recorded measurements; if none exist the intake says a trainer must record them first.

21. **Rules engine** — phase/intensity/equipment-filter computation (pure Python, test-heavy; implement the Strategy pattern here for swappable intensity logic).
    - Phase is derived from the elapsed proportion of the member's active plan; intensity is derived from the phase, adjusted by the recent weekly check-in trend (progressive overload).
    - Deterministic output is covered by unit tests across at minimum: a beginner/foundation case, an advanced/peak case, and a case where `equipment_prefs`/limitations measurably exclude equipment.
    - Equipment in `out_of_service` or `under_maintenance` is never prescribed. Note: this equipment status exclusion rule is wired up when the equipment registry lands in Sprint 25 (see Sprint 25).
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

## Increment 5 — Equipment, analytics, communication

_Increment 5 = Sprints 25, 27, 28, 29, 29a; Sprints 26 and 28a are deferred to a future version (see docs/SPEC.md §10)._

**Preflight (external items):** None (Note: Sprint 28 platform Telegram bot token will be requested at Increment 5 preflight)

25. **Equipment registry & maintenance** — `Equipment`, `MaintenanceLog`, low-quantity alerts, AI exclusion-filter wiring.
    - Equipment records include `purchase_date`. Reporting an issue creates a `MaintenanceLog`, transitions `Equipment.condition` to `needs_maintenance`, and notifies the Owner; reporting on an item already `under_maintenance` creates no duplicate.
    - Owner/Manager update condition and log resolutions (`resolved_at` set, condition returns to `good`) — the transitions are tested, not just log creation.
    - A quantity exactly at `min_qty_threshold` triggers an alert; one above it does not (boundary test).
    - Equipment `under_maintenance` or `out_of_service` is excluded from what Sprint 21's engine may prescribe — tested at the integration point.
    - An Owner setting controls whether members see unavailable equipment (default off).

26. **Group class scheduling & booking** (Deferred to a future version, see docs/SPEC.md §10) — `ClassSession`, `ClassBooking`, capacity enforcement, Growth/Pro gated.
    - Booking is accepted for the last available slot and rejected on the next attempt once `max_capacity` is reached (boundary test); booking closes automatically at capacity.
    - Booking endpoints reject a gym with `has_group_classes = false` at the API level.
    - The class's trainer marks attendance on the booking (`attended`); this creates no daily `Attendance` row.

27. **Dashboards and analytics** — What gym owners and managers can see after this sprint:
    - A basic dashboard endpoint is available to Owner/Manager on every tier: active members, today's check-ins, monthly revenue, and memberships expiring within seven days. It responds in under 3 seconds against a seeded dataset (1,000 members, a year of attendance).
    - Premium analytics contains only revenue by plan in this version (peak-hours heatmap, cohort retention by joining month, and referral analytics are deferred to a future version, see docs/SPEC.md §10). Revenue by plan is available on Growth and Pro tiers only (`has_analytics = true`). Starter tier users see an upgrade prompt where the premium block would be.
    - Figures are scoped to the requesting gym only — verified against a seeded multi-tenant dataset.

28. **Notice board & broadcast communication**
    - A notice reaches all members of the issuing gym (Owner/Manager can post) and is not visible to another gym's users.
    - If the gym has set a Telegram channel in its settings, posting a notice also sends it to that channel; if Telegram is not configured or the send fails, the in-app notice still succeeds. It is a public noticeboard for the gym's channel, not a per-member direct message. No member Telegram IDs are collected. Note: the platform bot's token is a platform secret (host env file, requested at Increment 5's preflight); the gym Owner enters only the channel in the gym's settings and must add the platform bot to that channel as an administrator; whether the host can reach Telegram's API is untested and will be checked at that preflight.

28a. **Badges and member progress** (Deferred to a future version, see docs/SPEC.md §10) - Badges are awarded for a first check-in, a 30-day streak, and plan completion — each at most once per member, idempotent. - The member progress view returns body-metric history (and the Sprint 7b estimates) as chart data, scoped to that member.

29. **CSV export** — members, payments, attendance.
    - Exported rows, headers and row count match a known seeded dataset exactly, scoped to the requesting gym.
    - For 7 days after a gym is suspended, its Owner can still log in and export, and nothing else; after that window the export is refused. Note: this post-suspension export rule is wired up when gym suspension lands in Sprint 35 (see Sprint 35).

29a. **Expenses and reports** - Owner/Manager can log expenses (amount, category, note, date) and view revenue vs. expenses for a period; revenue counts confirmed payments only. - Reports: attendance summary and revenue report, scoped to the gym.

- [ ] All sprints in this increment complete

## Increment 7 — Platform administration, PWA, demo, deployment

**Preflight (external items):**

- Sprint 38 (cPanel deployment steps, cron, AutoSSL, HTTPS for the PWA)

35. **Super Admin platform dashboard** — tenant management, renewals, lapse handling, platform reports.
    - Super-Admin-only actions are rejected for every other role, including an Owner acting on their own gym.
    - Tenant list with tier, status, `subscription_expires_at` and lapse flags; Super Admin can change a gym's tier and flags (the flag editor offers only tiers that exist: Starter and Growth; Pro is hidden until Increment 6 ships; `has_group_classes` is not shown or enabled), enable or disable roles per gym (a disabled role cannot be invited or log in), and every change is audit-logged at platform level.
    - **Renewal:** Super Admin records a `bank_transfer` payment (amount, reference); `subscription_expires_at` extends by one year from the later of the current expiry or today, the lapse flag clears, and a suspended gym is reactivated.
    - **Suspension:** Super Admin confirms suspension of a lapse-flagged gym (it is never automatic). A suspended gym's staff and members cannot log in, while its data stays intact and visible to Super Admin — both halves tested. Its Owner can still log in for 7 days to export (Sprint 29), after which login is refused; nothing is deleted.
    - Platform reports: tenant summary, platform revenue (confirmed `gym_subscription` payments, excluding demo gyms), subscription status overview. Platform-wide notices (an `Announcement` with null gym) appear on every Owner's dashboard.
    - Super Admin can edit a gym's `payment_grace_days` and `subscription_reminder_days`.

36. **GymConfig feature-flag enforcement** — backend permission layer + frontend render gating, for every tier-gated feature above.
    - Full regression pass: every previously-built tier-gated endpoint (trainer module, AI plans, premium analytics [revenue by plan], freeze, and entitlement edits) is re-verified to reject a gym missing the corresponding flag, and every entitlement edit by an Owner is re-verified to be rejected. A clean pass here is the actual proof the gating is complete. Group classes are deferred. Note: multi-branch is verified at the end of Increment 6 if Increment 6 ships (Sprint 36's multi-branch regression check and Sprint 38's final-release re-check are run again after Sprint 34).

37. **Offline-first PWA** — Workbox service worker, local check-in queue, sync.
    - The member dashboard offers a "Download App" button that installs the PWA on Android (it appears only when the browser reports the app can be installed, which needs the gym's valid HTTPS certificate); on iPhone the app shows short "Add to Home Screen" instructions; an installed app opens without the browser address bar.
    - A check-in performed while offline is queued locally and produces exactly one `Attendance` row once connectivity returns — no duplicate on reconnect. Sync completes within 5 seconds of connectivity returning. Note: queued check-ins carry the branch once Increment 6 exists.
    - Where background sync is unsupported (iOS Safari), the app replays the queue itself when it detects connectivity or regains focus; this path is tested separately.
    - Offline, a scanned token is checked locally against the public key (signature and expiry); membership status is verified on sync, and a rejected queued check-in is surfaced to staff.
    - The app shell is served while offline, not a browser error page; all screens work at 320 px width without sideways scrolling. Staff keep a manual fallback register for the case where browser data is cleared offline.

37a. **Demo gym** - A management command seeds a gym on the `demo` subdomain (flagged `is_demo`) with sample members, plans, attendance, trainers, and equipment (classes removed/deferred), Growth flags on, and Chapa test keys read from the environment. Multi-branch sample data is added only if Increment 6 has shipped. Re-running it resets only that gym's data, never any other gym's — tested with a second seeded gym. Demo gyms are excluded from platform revenue.

38. **Production hardening (cPanel-based)** — Note in plain words that the cPanel provisioning, the AutoSSL behavior, the cron run and the DOMAIN change were already proven on the staging deploy, so this sprint is a re-check of the final release, not new work. Deploy Django via cPanel's Python App Manager (Passenger WSGI), wire the cPanel UAPI subdomain-provisioning call from Sprint 4 to the real account (not a stub), confirm PostgreSQL connection settings against cPanel's database, set up the cPanel Cron Job for Sprint 14's command, configure the cache backend (database cache unless Redis is confirmed), DB backups via whatever cPanel/Yegara provides, `DOMAIN` fully parameterized end-to-end. `.env` carries every environment-specific value: `DOMAIN`, database credentials, JWT and QR signing keys, `TENANT_CREDENTIALS_KEY`, Cloudinary credentials, Super Admin bootstrap values, demo Chapa test keys.
    - A fresh deploy to the actual Yegara Premium account succeeds end-to-end from documented steps, with every environment-specific value sourced from `.env`.
    - The cPanel UAPI call is confirmed against the real account — a real subdomain is actually provisioned when a gym is created.
    - The AutoSSL gap behaves as designed under real conditions: a freshly provisioned subdomain is reachable over HTTP, login is blocked until the certificate is confirmed valid, and the app detects the certificate becoming valid without a manual flag flip.
    - The cPanel Cron Job fires Sprint 14's command on schedule — verified against real execution.
    - Changing `DOMAIN` in `.env` and redeploying requires no other code or configuration change.

- [ ] All sprints in this increment complete

## Increment 6 — Multi-branch management (Pro tier)

**Preflight (external items):** None

_Increment 6 runs after Increment 7; go/no-go decision date: to be set by the owner. Note that it adds schema changes to gyms that already hold real data, so its migrations must be tested against a copy of staging data first. Built LAST as an optional stretch if time remains. Keeps sprint numbers 30 to 34._

30. **Branch model + management** — `Branch` CRUD (Owner only), gated by `GymConfig.has_multi_branch`; frontend in-app branch switcher. One subdomain per gym regardless of branch count. Also creates the `MembershipPlan.all_branches_access` field in the database (default `false`), so it exists before Sprint 32 check-in needs it.
    - Branch CRUD endpoints reject requests on a gym without `has_multi_branch` at the API level.
    - Adding a gym's first branch doesn't break existing single-branch-gym behavior — a regression pass against Increments 1–5 and 7's tests still passes with `has_multi_branch=false`.

31. **Branch-scoped staff (STRICT)** — The agent stops and reports for the owner's review before merging it (data from another branch must never leak; missing branch data must reject, never allow). Nullable `branch_id` on `User` (null = all-branch, matching Owner's existing unscoped access); RBAC updated so branch-scoped staff only see their branch's operational data.
    - A staff user with a set `branch_id` sees only that branch's data; a `null`-`branch_id` user sees all branches — both tested, including confirming Owner's access is unaffected either way.

32. **Branch-aware check-in & attendance** — `branch_id` on `Attendance`; QR check-in validates the scan's branch against `MembershipPlan.all_branches_access` and the member's subscription, not just subscription status. This branch check is placed inside the single shared check-in function from Sprint 10.
    - A member whose plan has `all_branches_access=false` is rejected at a branch other than their home branch; a `true`-flag member succeeds at any branch — both tested.
    - Recorded `Attendance.branch_id` matches the actual scan location.

33. **Branch-aware equipment & trainer assignment** — `branch_id` on `Equipment`; branch-scoped maintenance alerts and trainer assignment (classes are deferred).
    - Equipment queries for a branch-scoped staff member return only that branch's records, mirroring Sprint 31.

34. **Plan-level branch access management** — Plan management UI for `MembershipPlan.all_branches_access` (created in Sprint 30); lets a Pro gym sell both single-branch and all-access plans.
    - The flag is settable only on gyms with `has_multi_branch`; it has no effect on single-branch gyms regardless of its stored value.
    - Note: If Increment 6 ships, Sprint 36's multi-branch regression check and Sprint 38's final-release re-check are run again after Sprint 34.

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

## Before final deployment (and before the next release to the host)

1. Member QR pass stretched on desktop and wanted as its own "My QR pass" navigation item with a perfectly square QR (max about 420px) — deferred by owner decision.
2. Request a Demo redirects to the landing page after about 5 seconds with a Back to home button and no Sign in link — deferred by owner decision.
3. Subdomain suggestion joined letters and digits ("mtfitness") instead of hyphenated — deferred by owner decision.
4. Build scripts: forward-slash zip paths and LF line endings (.gitattributes, build fails on CR in .sh) — deferred by owner decision.
5. PostgreSQL socket DATABASE_URL (postgres://user:pass@/dbname?host=/var/run/postgresql) in .env.production.example and the guide (including pg_dump and .pgpass) — deferred by owner decision.
6. Pip install in Web Terminal as the primary method — deferred by owner decision.
7. A check_env command that compares env-file variable NAMES with .env.production.example and never prints values — deferred by owner decision.
8. Ask cPanel to start AutoSSL right after creating a gym subdomain (uapi SSL start_autossl_check works in Web Terminal) as a best-effort step — deferred by owner decision.
9. Brevo: confirm "Authenticated" in the dashboard and DKIM PASS with d=fitgate.tebebtech.com in Gmail's "Show original" — deferred by owner decision.
10. "Lessons from the first deploy" section in docs/DEPLOY_STAGING.md — deferred by owner decision.
11. The earlier small follow-ups already in Known follow-ups — deferred by owner decision.
12. [x] Tier cards on the landing page, the Create Gym tier choices, the default flags set at gym creation, and the Super Admin flag editor must offer only the tiers that exist; Pro appears only after Increment 6 ships; has_group_classes must not be shown or enabled.

## Deferred to a future version

- Public self-serve gym registration and approval (the source's FG-UC-00-GYM) and its rejection handling
- Inactivity flags, escalation and the inactive-member report (attendance data is already kept, so these can be added later)
- Chapa subaccount mode; Chapa-paid platform fees
- Monthly billing and auto-renewal; plan upgrades and downgrades mid-subscription
- Phone-number login; member discounts and promotions
- A full public landing page per gym
- A Starter member cap and a setup fee
- A data deletion/archival policy for lapsed gyms
- Trainer availability schedule (Sprint 18)
- Trainer-to-member messaging (Sprint 19)
- Group class scheduling and booking (Sprint 26)
- Badges and member progress charts (Sprint 28a)
- Premium analytics: peak-hours heatmap, cohort retention, and referral analytics (Sprint 27)

## Known follow-ups (not scheduled)

- Dedicated scanner device account instead of a staff login on the entrance tablet.
- Rejected scans are shown only on the tablet, not on the reception list.
- User.bulk_create skips email normalization (no current caller; any future bulk user import must normalize emails).
- The tenant check in the JWT authentication reads token claims, not the database user.
- Dead code in accounts/tokens.py (claims set on a throwaway access_token object).
- A Super Admin account can be locked by anyone guessing passwords at the apex; mitigation later: per-IP throttling.
- Access tokens stay valid until expiry after logout; the token blacklist table needs a periodic cleanup (flushexpiredtokens) in the Sprint 38 cron setup.
- Purge expired AuthToken rows with a management command in the Sprint 38 cron setup.
- Sprint 1a (GitHub Actions CI) was proposed and skipped to save time; revisit before final submission. (The "every view declares permissions" contract test already exists from Sprint 2.)
- Real Super Admin JWT test at gym and apex hosts.
- Parametrized tests for the Member.status path.
- Move freezegun to a dev/test requirements file and check @types/qrcode.react is needed with qrcode.react v4.
- Alert close button min 44px per DESIGN.md.
- [x] Before the staging deploy: pin exact versions and split dev/test packages (pytest, freezegun) from production requirements.txt. The Sprint 8 and Increment 1 reports gave different versions for cryptography and freezegun, and different QR libraries (qrcode vs qrcode.react), so regenerate the list from pip freeze / npm ls. (Done in Staging deploy prep).
