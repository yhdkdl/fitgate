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
