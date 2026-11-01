# FitGate — Increment 4 End-to-End Test Script

This document is a comprehensive, numbered click-through guide for project owners, QA testers, and non-developers to verify all features built across **Increment 4: AI Personal Training** (Sprints 20 through 24, selectable profile lists, provider fallback chain, trainer review/approval lifecycle, approval notifications, and trainer dashboard tracking).

---

## Prerequisites & Environment Setup

1. **Verify Services are Running**:
   In your terminal at the project root, ensure Docker Compose containers are running:

   ```powershell
   docker compose ps
   ```

   All containers (`fitgate_backend`, `fitgate_frontend`, `fitgate_postgres`, `fitgate_redis`, `fitgate_pgadmin`) should be running and healthy.

2. **Frontend URLs**:
   - Platform Apex: `http://localhost:5173`
   - Tenant Gym Subdomain: `http://<gym-subdomain>.localhost:5173`

3. **AI Provider Configuration**:
   The plan generation system uses an ordered fallback chain:
   1. **Google AI Studio (Gemini Flash)**: Used if `GEMINI_API_KEY` is present in `backend/.env`.
   2. **OpenRouter**: Used if `OPENROUTER_API_KEY` is present in `backend/.env`.
   3. **Mock AI Provider**: Automatic offline fallback if no external keys are configured or if external providers are unavailable.

   Verify provider status via the management command:

   ```powershell
   docker compose exec backend python manage.py check_ai_provider
   ```

---

## 1. Fitness Profile Intake with Selectable Lists & Medical Caution (Sprint 20)

### 1.1 Trainer-Only Entry & Selectable Lists

1. Sign in as **Trainer** at `http://<gym-subdomain>.localhost:5173`.
2. Navigate to **My Clients** (`/trainers/clients` or Trainer Dashboard) and select an assigned member (e.g. `yoyo`).
3. Open the **Fitness Profile** tab.
4. Verify that free-text inputs for limitations and equipment have been replaced with standard selectable lists:
   - **Health limitations and injuries** (multi-select, "None" is mutually exclusive):
     - `lower_back`, `knee`, `shoulder`, `neck`, `hip`, `ankle_foot`, `wrist_elbow`, `high_blood_pressure`, `heart_condition`, `diabetes`, `asthma`, `pregnancy_postpartum`, `recent_surgery`, `other`.
   - **Equipment access** (multi-select, default "Full gym equipment"):
     - `full_gym`, `free_weights`, `machines`, `cables`, `kettlebells`, `resistance_bands`, `cardio_machines`, `bodyweight_only`, `other`.
   - **Dietary notes** (multi-select, "No restrictions" is mutually exclusive):
     - `vegetarian`, `vegan`, `no_dairy`, `no_eggs`, `no_nuts`, `no_fish`, `no_gluten`, `halal`, `orthodox_fasting`, `ramadan_fasting`, `other`.
5. Select "other" for any category; verify a single-line text input appears (maximum 200 characters) and is required when "other" is checked.

### 1.2 Medical Caution Banner

1. In the **Health limitations and injuries** list, select a high-risk medical condition:
   - `heart_condition`, `high_blood_pressure`, `diabetes`, `asthma`, `pregnancy_postpartum`, or `recent_surgery`.
2. Notice the amber **Medical Caution** banner immediately appears below the field:
   - _"Medical clearance recommended before high-intensity exercise."_
3. Save the profile. Verify the banner remains visible when viewing the saved profile.
4. Deselect the high-risk condition and save; verify the medical caution banner disappears.

### 1.3 RBAC Permissions Enforcement

1. Sign out and sign in as the **Member**.
2. Open the Member Dashboard / Profile. Verify the member can view their fitness profile details in read-only mode, with no editing controls.
3. Attempting to directly call `PUT /api/gym/members/<id>/fitness-profile/` as Member, Reception, or an unrelated Trainer returns HTTP 403 Forbidden.

---

## 2. Client Overview, Measurements & Phase Derivation (Sprint 21)

### 2.1 Trainer Client Overview & Metrics

1. Sign in as **Trainer**.
2. Open **Client Overview** (`/measurements`).
3. Select an assigned client.
4. Record new body measurements:
   - Weight (kg), Height (cm), Waist circumference (cm), Neck (cm), Hip (cm for females).
5. Verify automatic calculations:
   - BMI calculation and classification.
   - Body fat percentage estimation using the US Navy formula.
   - Previous measurements comparison graph/table showing trend delta.

### 2.2 Subscription Phase Derivation

1. Check the client's current training phase displayed at the top of their profile:
   - **Foundation Phase**: Client is in the first third (0% - 33%) of their subscription period.
   - **Build Phase**: Client is in the middle third (34% - 66%) of their subscription period.
   - **Peak / Maintenance Phase**: Client is in the final third (67% - 100%) of their subscription period.
2. Verify that this phase is automatically fed into the AI plan prompt payload to govern training intensity.

---

## 3. AI Workout & Nutrition Plan Generation (Sprint 22)

### 3.1 Generating a Weekly Plan

1. As **Trainer**, navigate to **Client Overview** -> **AI Workout Plan** tab for an assigned client.
2. Select the target week:
   - **This week** (starts current week Monday).
   - **Next week** (starts next week Monday).
3. Select a **Weekly Focus**:
   - `hypertrophy` (Muscle growth)
   - `strength` (Strength building)
   - `endurance` (Cardiovascular conditioning)
   - `fat_loss` (Fat loss & circuit training)
   - `mobility` (Flexibility & joint mobility)
   - `general_fitness` (Balanced full-body)
4. Click **Generate Plan**.
5. Verify the loading spinner appears while the request completes.
6. Verify generation completes and displays Draft 1 for review.

### 3.2 Safety Exclusions & Prompt Rules

1. Set the client's fitness profile to include `shoulder` injury.
2. Generate a plan.
3. Review the generated exercise list:
   - Verify all overhead pressing (barbell overhead press, dumbbell shoulder press, Arnold press) and lateral/front raises at shoulder height are excluded.
4. Review the nutrition guidance:
   - Verify authentic Ethiopian foods are recommended (e.g. injera with shiro, lentils, shimbra chickpeas, teff porridge) without unrealistic Western foods or strict calorie gram precision.
   - If fasting is marked (`orthodox_fasting` or `ramadan_fasting`), verify fasting dietary rules are strictly respected.

### 3.3 Missing Date of Birth Guard

1. If a member record has no `date_of_birth` set, attempt to generate a plan.
2. Verify the server refuses generation with the exact error:
   - _"Member date of birth is missing"_

### 3.4 Rate Limit Enforcement

1. Each gym is limited to 20 plan generations per hour.
2. When the 20/hr limit is reached:
   - The generation button returns a clean message: _"Gym hourly generation limit reached. Please try again later."_
   - The Gym Owner receives a notification about the rate cap.
   - Failed attempts do not create draft records and do not increment the generation counter.

---

## 4. Trainer Plan Review, Editing & Rejection Lifecycle (Sprints 23 & 24)

### 4.1 Plan Review Screen & AI Source Line

1. In the **AI Workout Plan** tab, locate the freshly generated Draft 1.
2. Verify the review header shows:
   - Week starting date (Monday).
   - Draft badge: `Draft 1 (Pending Review)`.
   - **Source line**: Names the model and provider that generated the plan (e.g. `Source: Gemini 1.5 Flash via Google AI Studio`, `Source: Mistral 7B via OpenRouter`, or `Source: Mock AI Provider`).

### 4.2 Editing a Draft

1. Click **Edit Plan**.
2. Modify an exercise name, adjust the sets/reps (e.g. change `3 sets of 10` to `4 sets of 8`), and adjust rest times.
3. Add a personalized trainer note to the nutrition recommendations.
4. Click **Save Changes**.
5. Verify the saved changes are reflected immediately in the review view without altering the draft number or status.

### 4.3 Rejection Flow & Three-Draft Rule

1. Click **Reject Draft**.
2. A rejection modal opens with a required reasons checklist:
   - `too_hard` (Exercises too advanced)
   - `too_easy` (Insufficient intensity)
   - `lacks_equipment` (Exercises require unavailable equipment)
   - `injury_concern` (Safety or injury conflict)
   - `nutrition_unsuitable` (Dietary preferences not matched)
   - `other` (Requires explanatory text)
3. Select a reason and click **Confirm Rejection**.
4. Verify the system automatically generates **Draft 2**, incorporating feedback from the rejection reason.
5. Reject Draft 2 with another reason; verify **Draft 3** is generated.
6. On **Draft 3**, verify the **Reject** button is disabled with the notice:
   - _"Maximum AI drafts reached. Please edit this draft yourself to finalize the plan."_

---

## 5. Plan Approval & In-App Notification (Sprint 23 & 24)

### 5.1 Plan Approval

1. On Draft 1, 2, or 3, click **Approve Plan**.
2. Confirm the approval dialog.
3. Verify:
   - Plan status changes to `Approved`.
   - The Edit and Reject buttons are hidden.
   - The plan is marked locked and immutable for that week.

### 5.2 Member In-App Notification

1. Immediately upon approval, sign out and sign in as the **Member** whose plan was approved.
2. Look at the notification bell icon in the top navigation header:
   - Verify the unread badge count has incremented.
3. Click the notification bell to open the notification list.
4. Verify the new notification is present with the exact text:
   - _"Your training plan for the week of <YYYY-MM-DD> is ready."_
5. Verify that editing or rejecting drafts previously sent **no** notification to the member.
6. Verify other members in the gym received **no** notification.

---

## 6. Member Dashboard Experience (Sprint 24)

### 6.1 "Waiting for your trainer" State

1. Create or identify an active member who:
   - Has an assigned trainer.
   - Is on an active trainer-inclusive membership plan.
   - Has **no** approved training plan for the current week.
2. Sign in as that **Member** and view the Member Dashboard Home screen (`/dashboard`).
3. Verify the **Workout Plan** section displays the card:
   - **"Waiting for your trainer"**
   - Subtext explaining that their assigned trainer is preparing their weekly workout and nutrition plan.
4. Verify that pending AI drafts are **never** displayed, mentioned, or hinted at to the member.
5. Verify that a member _without_ an assigned trainer or on a basic gym pass sees no training plan section at all.

### 6.2 Approved Plan View

1. Sign in as a **Member** whose training plan was approved in Section 5.
2. View the Member Dashboard.
3. Verify the "Waiting for your trainer" card is replaced with the full **Weekly Training & Nutrition Plan**:
   - Day-by-day workout sessions (exercises, sets, reps, rest periods, coaching cues).
   - Weekly focus and trainer guidance notes.
   - Daily nutritional guidelines and hydration tips.
4. Verify all content is read-only for the member.

---

## 7. Trainer Overview Dashboard (Sprint 24)

### 7.1 "Clients with no approved plan this week" Card

1. Sign in as **Trainer** at `http://<gym-subdomain>.localhost:5173`.
2. View the **Trainer Overview** dashboard (`/dashboard`).
3. Locate the summary card:
   - Title: **"Clients with no approved plan this week"**
   - Header badge displaying the total count of assigned clients missing an approved plan for the current Monday-to-Sunday week.
4. Verify each row in the card displays:
   - Client avatar / photo and full name.
   - State badge:
     - **"No draft yet"** (if no plan draft has been generated for this week).
     - **"Draft waiting for your review"** (if Draft 1, 2, or 3 exists in pending review state).
   - **"Open Plan"** button.

### 7.2 Quick Navigation to Client Plan

1. Click **Open Plan** on any client row in the card.
2. Verify the browser navigates directly to `/measurements?memberId=<id>&tab=training_plans`.
3. Verify the client is automatically selected and the **AI Workout Plan** tab is opened, ready for draft generation or review.

### 7.3 Multi-Trainer Scope Isolation

1. Sign in as a **second Trainer** in the same gym.
2. Verify the "Clients with no approved plan this week" card shows **only** clients assigned to Trainer 2.
3. Confirm clients assigned to Trainer 1 never appear on Trainer 2's dashboard card, even if Trainer 1 has generated drafts for them.

---

## 8. Provider Health Check & Offline Fallback Command

### 8.1 Management Command Verification

1. Run the AI health check command from your terminal:

   ```powershell
   docker compose exec backend python manage.py check_ai_provider
   ```

2. Expected output format:
   - Reports the active provider chain in priority order:
     - `Google AI Studio (Gemini Flash)`: Configured / Not configured
     - `OpenRouter`: Configured / Not configured
     - `Mock Provider`: Always available as fallback
   - Tests connectivity to the primary available provider and prints response latency.

---

## Appendix: Time-Dependent Steps (Django Shell Snippets)

To verify behavior across different calendar weeks or simulate time-based logic without waiting for real-world dates, use the following PowerShell Django shell commands:

### A.1 Backdating a Training Plan to Previous Week

Advance or backdate a training plan's `week_start_date` by 7 days to simulate a new calendar week:

```powershell
docker compose exec backend python manage.py shell -c "from datetime import timedelta; from apps.trainers.models import TrainingPlan; p = TrainingPlan.objects.order_by('-created_at').first(); TrainingPlan.objects.filter(id=p.id).update(week_start_date=p.week_start_date - timedelta(days=7)) if p else None; print(f'Plan {p.id} backdated to previous week' if p else 'No plan found')"
```

After running this, revisit the Trainer Overview dashboard and confirm the client immediately returns to the **"Clients with no approved plan this week"** list with state **"No draft yet"**.

### A.2 Resetting Gym Hourly Generation Rate Limits

If you hit the 20 plans/hour limit during testing and need to reset the counter immediately:

```powershell
docker compose exec backend python manage.py shell -c "from apps.trainers.models import TrainingPlanGenerationRateLimit; TrainingPlanGenerationRateLimit.objects.all().delete(); print('Gym rate limit counters reset successfully')"
```

### A.3 Setting a Plan Directly to Draft 3 for Testing the Final Edit Lock

To test the third-draft edit-only rule without generating three times:

```powershell
docker compose exec backend python manage.py shell -c "from apps.trainers.models import TrainingPlan; p = TrainingPlan.objects.filter(status='pending_review').order_by('-created_at').first(); TrainingPlan.objects.filter(id=p.id).update(draft_number=3) if p else None; print(f'Plan {p.id} updated to Draft 3' if p else 'No pending plan found')"
```

Reload the client's AI Workout Plan tab and verify the **Reject** button is disabled with the _"Maximum AI drafts reached. Please edit this draft yourself"_ prompt.
