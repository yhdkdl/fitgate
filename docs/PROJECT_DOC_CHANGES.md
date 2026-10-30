# FitGate — Project Scope Decisions & Modifications

_Date: October 25, 2026_
_Purpose: A dated record of every scope decision, modification, and addition made since the original project document, formatted for updating the university project document._

---

## 1. Deferred to Future Work

- **Blood pressure, heart-rate zones, and posture screening checklist (October 30, 2026):** Deferred to a future release; standard physical circumferences, body composition metrics, and resting heart rate cover baseline trainer assessment needs without requiring specialized clinical diagnostics or complex postural assessment tools.
- **Trainer availability schedule (Sprint 18):** Deferred to a future release; gym trainers coordinate availability directly with gym management in v1, reducing scheduling interface complexity.
- **Trainer-to-member direct in-app messaging (Sprint 19):** Deferred to a future release; trainer-client communication takes place in person or via standard communication channels, avoiding the overhead of real-time messaging on shared hosting.
- **Group class scheduling and booking (Sprint 26):** Deferred to a future release; target pilot gyms operate primarily on open floor and general access memberships rather than structured group studio bookings.
- **Milestone badges and member progress charts (Sprint 28a):** Deferred to a future release; gamification badges and historical chart visualizations deferred to prioritize core membership, attendance, and payment workflows.
- **Advanced analytics (peak-hours heatmap, cohort retention, referral analytics):** Deferred to a future release; heavy analytical aggregations deferred to preserve performance on shared cPanel hosting; revenue by plan is retained as the sole premium analytics metric.

---

## 2. Changed

- **Trainer capacity configuration range and active client safety guard (October 30, 2026):** Gym Owner and Manager can configure a trainer's maximum client capacity between 1 and 100 (narrowed from 200). Lowering capacity below the trainer's current number of active clients is refused with an instruction to reassign clients first, preventing accidental orphan states. The change is audit-logged with previous and new values.
- **Strict trainer client scoping on server for measurements and photos (October 30, 2026):** Trainers are restricted on the server to view, search, record measurements for, and access profile photos of only gym members currently assigned to them. Access attempts for non-assigned members, former clients, members of other gyms, or standard plan members are denied with HTTP 403.
- **Revenue by plan designated as the sole premium analytics feature:** In this version, the premium analytics module (Growth and Pro tiers) includes only revenue by plan; heatmap, cohort retention, and referral analytics are deferred, while the basic dashboard remains available on all tiers.
- **Subscription tier structure restated with Pro hidden until release:** Starter provides core operations (registration, plans, payments, QR check-in, notice board, basic dashboard, audit logs); Growth adds the trainer module, AI plans, membership freeze, and revenue by plan; Pro adds multi-branch. Pro is hidden from the landing page and Create Gym forms until multi-branch ships.
- **Multi-branch management (Increment 6) reordered to an optional final phase:** Multi-branch is scheduled after Increment 7 as an optional stretch increment (decision date set by project owner), ensuring the core single-branch product deploys cleanly first.
- **Body measurements recorded exclusively by Trainers (Sprint 7b):** Removed member self-reported measurements during registration; measurements (height, weight, circumferences) are captured exclusively by professional trainers to guarantee data integrity for BMI, body composition, and AI planning.
- **Assisted onboarding replaces open gym self-registration (Sprints 4, 4a):** Prospective gyms submit a "Request a Demo" inquiry and pay platform fees via bank transfer; Super Admin provisions the gym and owner account, avoiding unpaid or unverified tenant sprawl.
- **Database compatibility adjusted for PostgreSQL 13:** Adapted production deployment settings and verified test suites against Yegara cPanel's managed PostgreSQL 13.23 environment, replacing the earlier unmanaged VPS/Docker requirement.
- **Member status model gains a fifth `pending` state:** New member registrations without an active subscription start as `pending`; `MemberSubscription` acts as the single source of truth, and check-in verifies subscription validity directly rather than trusting static status flags.
- **Owner freeze days allowed setting capped by Super Admin entitlement cap (Item 12):** `GymConfig.freeze_days_allowed` is configurable by gym Owner up to `freeze_days_cap`, which is controlled exclusively by Super Admin.
- **Member registration requires binary gender selection Female or Male (Item 13):** Replaced non-binary and optional gender choices with mandatory Female or Male selection.
- **Member self-profile lockdown restricts member accounts to password changes only (Item 14):** Members cannot self-edit name, phone, email, or photo, which are managed exclusively by gym staff.

---

## 3. Added

- **Trainer profile photo and member "My trainer" card (October 30, 2026):** Trainers can upload and replace an optional profile photo via account settings (JPEG, PNG, WebP up to 2 MB), visible to gym Owner/Manager on the Trainers management screen. Members on trainer-inclusive plans see a "My trainer" card on Home and Membership screens with trainer photo, name, and specialization (showing initials if no photo, "Trainer not assigned yet" if unassigned, and hidden on standard plans). Private photo routes strictly enforce that members can only view their own current assigned trainer's photo.
- **Extended body measurement fields and automated derived composition metrics (October 30, 2026):** Added optional circumference fields (chest 50–200 cm, bicep L/R 15–80 cm, thigh L/R 30–120 cm, calf L/R 20–80 cm) and vitals (resting heart rate 30–220 bpm integer, trainer-measured body fat % 2–70%) stored within flexible measurements data without schema changes. Automatically derives waist-to-hip ratio (waist / hip) and lean body mass (`weight * (1 - body fat % / 100)`, labeled "measured" when trainer-measured body fat % is present or "estimate" via formula).
- **Latest measurement entry correction workflow (October 30, 2026):** The assigned trainer can correct errors on only the latest measurement entry for their client. The correction is audit-logged with before-and-after values and flagged as "corrected" in history, while older historical records remain permanently immutable.
- **Credential-agnostic check-in pipeline (v1 QR only):** Unified check-in engine routes all entrance attempts through one internal pipeline with attendance method tracking (`qr` or `manual_override`), laying the architectural foundation for future signed NFC tags or biometric hardware without altering business logic.
- **Notice board Telegram channel bridge (Sprint 28):** Gym announcements can optionally broadcast to the gym's public Telegram channel via a platform bot, matching common Ethiopian member communication practices without collecting private member contact IDs.
- **Dedicated entrance kiosk scanner and live check-in monitoring (Sprints 8b, 8c):** Added a full-screen, hands-free tablet camera scanner for front-desk entry and a live ~5-second polling attendance feed on staff dashboards, replacing manual desk check-in registers.
- **Added: bank transfer as a member payment method, with reconciliation and reversal (Sprint 12b):** Direct bank transfer enabled for members at front desk (Owner, Manager, Reception) with unique bank reference enforcement, Owner reconciliation workflow, 7-day unattended flagging cron, and immutable reversal with previous subscription state restoration.
- **Staff-assisted member registration supports atomic upfront plan payment (Item 16):** Staff can optionally collect cash or bank transfer payment and activate a plan during walk-in registration in a single atomic transaction.
- **Public gym payment configuration status endpoint exposed for unauthenticated client discovery (Item 17):** Public endpoint exposes payment acceptance flags without authentication or credentials to support registration and checkout workflows.
- **Bank transfer payments support payment proof screenshot upload (Item 21):** Staff and members can upload transaction confirmation screenshots for bank transfer payments, stored securely in tenant storage for owner reconciliation.
