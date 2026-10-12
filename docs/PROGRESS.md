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

## Current

- Sprint 5: RBAC framework (GATE)

## Next

- Sprint 6: Staff provisioning

## Open manual steps

- Sprint 4: cPanel UAPI token & subdomain provisioning (fallback: mock UAPI client; not verified against real service)
- Sprints 4, 6, 7: Production SMTP mailbox (fallback: console email backend; not verified against real service)
- Sprints 4b, 7: Cloudinary credentials (fallback: local filesystem storage; not verified against real service)
- Sprint 8: QR asymmetric signing key pair (fallback: dev key generator / test fixture; not verified against real service)

## Deviations

- none

## Docs Note — Sprint 4 Strict Security & Path Coverage Report (for review at Sprint 5 Gate)

- **Sprint 4 Data Entities & Primary Write Paths:**
  - `GymTenant`, `GymConfig`, `User` (Owner), `Payment` (`payer_type='gym_subscription'`).
  - Primary path: `POST /api/platform/gyms/create/` executed via atomic `create_gym(...)` service.
  - Secondary paths: `POST /api/platform/gyms/<gym_id>/confirm-tls/` (TLS confirmation and 1-year subscription activation), `POST /api/auth/set-password/` (Owner invite token redemption).
- **Other Paths Reaching the Same Data:**
  - **Bulk operations:** No bulk create/update endpoints exist for gyms, configs, or owner provisioning. Database constraints (`GymTenant.subdomain` unique, `GymConfig.gym_id` 1:1 PK/FK) enforce integrity at the schema layer.
  - **Generators / Seeders:** No automated demo/test gym generators run outside test suites.
  - **Django Admin:** Restricted to platform superusers (`is_staff` / `is_superuser`); not accessible by tenant users or API tokens.
  - **Serializers:** `CreateGymRequestSerializer` strictly validates RFC 1123 DNS labels, reserved names (`admin`, `api`, `apex`, etc.), payment method (`bank_transfer` required, `chapa` rejected), and owner fields.
  - **Management commands:** `bootstrap_super_admin` creates platform superuser only; does not provision gyms or bypass tenant logic.
  - **Unscoped managers:** `User.all_objects` is used exclusively for platform user queries (email uniqueness, cross-tenant resolution) and audited login lookups. `GymTenant.objects` is inherently platform-level.
- **Tenant Isolation & Permission Tests:**
  - `IsSuperAdmin` and `RequirePasswordChanged` enforced on all `/api/platform/gyms/*` endpoints. Tested: Owner, Manager, Trainer, Reception, Member receive 403; unauthenticated receives 401.
  - Certificate safeguard: `LoginView` checks `tls_confirmed_at`; unconfirmed subdomains return HTTP 503 `still_securing` (tested).
  - Transaction atomicity: Provisioning failure with cPanel UAPI triggers complete database rollback of GymTenant, GymConfig, Payment, and User records (tested).
