# FitGate — Project Scope Decisions & Modifications

_Date: October 25, 2026_
_Purpose: A dated record of every scope decision, modification, and addition made since the original project document, formatted for updating the university project document._

---

## 1. Deferred to Future Work

- **Trainer availability schedule (Sprint 18):** Deferred to a future release; gym trainers coordinate availability directly with gym management in v1, reducing scheduling interface complexity.
- **Trainer-to-member direct in-app messaging (Sprint 19):** Deferred to a future release; trainer-client communication takes place in person or via standard communication channels, avoiding the overhead of real-time messaging on shared hosting.
- **Group class scheduling and booking (Sprint 26):** Deferred to a future release; target pilot gyms operate primarily on open floor and general access memberships rather than structured group studio bookings.
- **Milestone badges and member progress charts (Sprint 28a):** Deferred to a future release; gamification badges and historical chart visualizations deferred to prioritize core membership, attendance, and payment workflows.
- **Advanced analytics (peak-hours heatmap, cohort retention, referral analytics):** Deferred to a future release; heavy analytical aggregations deferred to preserve performance on shared cPanel hosting; revenue by plan is retained as the sole premium analytics metric.

---

## 2. Changed

- **Revenue by plan designated as the sole premium analytics feature:** In this version, the premium analytics module (Growth and Pro tiers) includes only revenue by plan; heatmap, cohort retention, and referral analytics are deferred, while the basic dashboard remains available on all tiers.
- **Subscription tier structure restated with Pro hidden until release:** Starter provides core operations (registration, plans, payments, QR check-in, notice board, basic dashboard, audit logs); Growth adds the trainer module, AI plans, membership freeze, and revenue by plan; Pro adds multi-branch. Pro is hidden from the landing page and Create Gym forms until multi-branch ships.
- **Multi-branch management (Increment 6) reordered to an optional final phase:** Multi-branch is scheduled after Increment 7 as an optional stretch increment (decision date set by project owner), ensuring the core single-branch product deploys cleanly first.
- **Body measurements recorded exclusively by Trainers (Sprint 7b):** Removed member self-reported measurements during registration; measurements (height, weight, circumferences) are captured exclusively by professional trainers to guarantee data integrity for BMI, body composition, and AI planning.
- **Assisted onboarding replaces open gym self-registration (Sprints 4, 4a):** Prospective gyms submit a "Request a Demo" inquiry and pay platform fees via bank transfer; Super Admin provisions the gym and owner account, avoiding unpaid or unverified tenant sprawl.
- **Database compatibility adjusted for PostgreSQL 13:** Adapted production deployment settings and verified test suites against Yegara cPanel's managed PostgreSQL 13.23 environment, replacing the earlier unmanaged VPS/Docker requirement.
- **Member status model gains a fifth `pending` state:** New member registrations without an active subscription start as `pending`; `MemberSubscription` acts as the single source of truth, and check-in verifies subscription validity directly rather than trusting static status flags.

---

## 3. Added

- **Credential-agnostic check-in pipeline (v1 QR only):** Unified check-in engine routes all entrance attempts through one internal pipeline with attendance method tracking (`qr` or `manual_override`), laying the architectural foundation for future signed NFC tags or biometric hardware without altering business logic.
- **Notice board Telegram channel bridge (Sprint 28):** Gym announcements can optionally broadcast to the gym's public Telegram channel via a platform bot, matching common Ethiopian member communication practices without collecting private member contact IDs.
- **Dedicated entrance kiosk scanner and live check-in monitoring (Sprints 8b, 8c):** Added a full-screen, hands-free tablet camera scanner for front-desk entry and a live ~5-second polling attendance feed on staff dashboards, replacing manual desk check-in registers.
- **Added: bank transfer as a member payment method, with reconciliation and reversal (Sprint 12b):** Direct bank transfer enabled for members at front desk (Owner, Manager, Reception) with unique bank reference enforcement, Owner reconciliation workflow, 7-day unattended flagging cron, and immutable reversal with previous subscription state restoration.
