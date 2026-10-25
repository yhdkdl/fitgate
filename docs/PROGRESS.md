# FitGate — Progress

## Done

- Sprint 0: Scaffolding (`004825e2866605c2f87886c320aba6052d6bf30b`)
- Sprint 1: Core tenant models + subdomain middleware (`ac8d08c5eb567bfc8cdd667cbafd8c39ec5cbd8d`)
- Sprint 2: Custom User model + JWT auth + platform-level base class (`abc0efe2d55aa31d504d70df08cb6f965fe737dd`)
- Sprint 2a: Profile and password management (`107a05d9a0aa249376d9871d7346277fe4d9ed81`)
- Sprint 3: Password reset (`a616d5a5f08fa8e52f338e3cecdf675386009809`)
- Sprint 3a: Frontend shell and auth screens (`f44a10875c75ff33d0277df5003b145803975073`)
- Sprint 4: Super Admin "Create gym" (`d760b36`, PR #12)
- Sprint 4a: Demo requests (`199f1bb`, PR #13)
- Sprint 4b: File storage layer (`3fe54b0`, PR #14)
- Sprint 4c: Gym branding, entry page, first-run checklist (PR #15)
- Sprint 4d: Public platform landing page (`fa095ed`, tag sprint-4d-done)
- Sprint 5: RBAC framework (GATE) (`6e07935`)
- Sprint 6: Staff provisioning (`4d957da`)
- Sprint 7: Member registration (`c7c948cb4114442c53947884cc191c865f05116a`)
- Sprint 7b: Trainer-only body measurements (`fa06902`, tag sprint-7b-done)
- Sprint 8: QR check-in (GATE) (`da91b1546b18e3e0e147934771fce5467b3e0204`)
- Sprint 8b: Camera QR scanner (`fdc63bc`, tag sprint-8b-done)
- Sprint 8c: Entrance scanner page and live check-in list (`7d2120c`, tag sprint-8c-done)
- Sprint 9a: Audit log viewer
- Fix: Unified form validation across frontend and backend (`a99aaf648d4279ab161a273a62040ebed2ea2eba`, tag `fix-form-validation-done`)
- Fix: Member profile photo upload and role enforcement (`2cc9a6802b5f82b22cfdd8f6e858f7b182654e59`, tag `fix-member-photo-upload-done`)
- Fix: Cross-tab session synchronization (`e49b29ec95ccd55e4953526360cc3fef7ce4df23`, tag `fix-cross-tab-session-done`)
- Staging deploy prep: release packaging, cPanel deployment guide, UAPI client hardening, PG 13 compatibility, security settings (`2d981a8`, tag `staging-prep-done`)
- Fix: Private photo authentication, domain normalization, and deferred checklist (`001764e14ea58c33a1628ab19731859ba79cd31d`, tag `fix-private-photos-done`)

## Current

- Increment 2 preparation: documentation updates, scope alignments, and Increment 2 preflight.
- Scope adjustments recorded:
  - Deferred to future versions: Sprint 18 (trainer availability schedule), Sprint 19 (trainer-to-member messaging), Sprint 26 (group class scheduling and booking), Sprint 28a (badges and member progress charts), and advanced analytics (peak-hours heatmap, cohort retention, referral analytics).
  - Premium analytics in v1 narrowed to revenue by plan only (Growth and Pro tiers).
  - Tiers restated: Pro hidden from landing page and gym creation until Increment 6 ships; `has_group_classes` inert across all tiers.
  - Multi-branch ordering: Increment 6 (Sprints 30–34) runs after Increment 7 as an optional final phase; go/no-go decision date: to be set by the owner.
  - Member status model: `pending` added for newly registered members with no active plan; `MemberSubscription` established as single source of truth.
  - Notification architecture: Sprint 11 creates the Notification model and shared helper (stored only, gym-scoped) so criteria in Sprints 11–13 are checkable; Sprint 15 delivers the in-app UI screens.

## Next

- Increment 2 starts with Sprint 10: Membership plans & subscription lifecycle (STRICT sprint).

## Open manual steps

- Sprint 4: cPanel UAPI token & subdomain provisioning (to be verified at staging)
- Sprints 4, 6, 7: Production SMTP mailbox via Brevo (to be verified at staging)
- Sprints 4b, 7: File storage layer (skipped: local filesystem storage in /home/<user>/fitgate_media/ behind protected Django views)
- Sprint 8: QR asymmetric signing key pair (to be verified at staging)
- Sprint 8b/8c: Camera scanning on physical devices (to be verified at staging)
- Sprint 4d: Apex platform address wiring (to be verified at staging)
- Sprint 11: Chapa test keys & online payments (skipped for Increment 2 per preflight answer; mocked webhooks in use; marked not verified against real service)

## Deviations

- (a) Stand-in `AuditLog` model in `apps.accounts` extended in Sprint 9 (migration 0006) with PostgreSQL immutability triggers (preventing UPDATE, DELETE, TRUNCATE), PROTECT on actor, compound indexing, secret redaction, and wired across Sprints 1–8 write operations. Sprint 9a added read-only paginated endpoints (/api/gym/audit-logs/ and /api/platform/audit-logs/) and dashboard audit viewer.
- (b) Stand-in `MemberSubscription` model in `apps.memberships` (migration 0002) introduced in Sprint 8 to track active/expired/frozen/suspended subscription states during check-in — to be extended/confirmed in Sprint 9 / Sprint 10, never recreated.
- (c) 30-day fallback period in `Member.get_subscription_period()` when no subscription exists — to be extended/confirmed in Sprint 10.
- (d) Owner and Manager may also use manual check-in override (SPEC §2 names Reception); accepted by owner.
- (e) Working rules updated: plain-language non-developer acceptance criteria in SPRINTS.md, plain-language sprint reports without diffs or code, new tests written only for security/money/tenancy or silently breakable logic, and clear bug-fix diagnoses.
- (f) Body measurements recorded by Trainers only; registration captures none. A gym with no trainer cannot record measurements, so BMI, body fat and AI plans show 'not measured yet'. Owner decided: no fallback for now.

Until Sprint 10, check-in requires a MemberSubscription row (create via Django shell/tests).

## Docs Note — Sprint 4 Strict Security & Path Coverage Report (for review at Sprint 5 Gate)

- **Sprint 4 Data Entities & Primary Write Paths:**
  - `GymTenant`, `GymConfig`, `User` (Owner), `Payment` (`payer_type='gym_subscription'`).
  - Primary path: `POST /api/platform/gyms/` executed via atomic `create_gym(...)` service.
  - Secondary paths: `POST /api/platform/gyms/<gym_id>/confirm-tls/` (TLS confirmation and 1-year subscription activation), `POST /api/auth/set-password/` (Owner invite token redemption).
- **Other Paths Reaching the Same Data:**
  - **Bulk operations:** No bulk create/update endpoints exist for gyms, configs, or owner provisioning. Database constraints (`GymTenant.subdomain` unique, `GymConfig.gym_id` 1:1 PK/FK) enforce integrity at the schema layer.
  - **Generators / Seeders:** No automated demo/test gym generators run outside test suites.
  - **Django Admin:** Restricted to platform superusers (`is_staff` / `is_superuser`); not accessible by tenant users or API tokens.
  - **Serializers:** `CreateGymRequestSerializer` strictly validates RFC 1123 DNS labels, reserved names (`admin`, `api`, `apex`, etc.), payment method (`bank_transfer` required, `chapa` rejected), and owner fields.
  - **Management commands:** `create_super_admin` creates platform superuser only; does not provision gyms or bypass tenant logic.
  - **Unscoped managers:** `User.all_objects` is used exclusively for platform user queries (email uniqueness, cross-tenant resolution). `GymTenant.objects` is inherently platform-level.
- **Tenant Isolation & Permission Tests:**
  - `IsSuperAdmin` and `RequirePasswordChanged` enforced on all `/api/platform/gyms/*` endpoints. Tested: Owner, Manager, Trainer, Reception, Member receive 403; unauthenticated receives 401.
  - Certificate safeguard: `TenantSubdomainMiddleware` checks `tls_confirmed_at`; unconfirmed subdomains return HTTP 503 `still_securing` for all `/api/` paths except `api/health/` and `api/public/gym-entry/` (tested).
  - Transaction atomicity: Provisioning failure with cPanel UAPI triggers complete database rollback of GymTenant, GymConfig, Payment, and User records (tested).
