import { apiFetch } from "./client";

export interface PlanPrerequisites {
  eligible: boolean;
  can_generate_this_week: boolean;
  can_generate_next_week: boolean;
  missing_requirements: string[];
  this_week_draft_count: number;
  next_week_draft_count: number;
  has_open_draft_this_week: boolean;
  has_open_draft_next_week: boolean;
  open_draft_id_this_week: string | null;
  open_draft_id_next_week: string | null;
}

export interface ExerciseItem {
  name: string;
  target_muscle: string;
  sets: number;
  reps: string;
  rpe: number;
  rest_seconds: number;
  notes?: string;
}

export interface SessionPlan {
  session_id: string;
  name: string;
  focus: string;
  exercises: ExerciseItem[];
}

export interface NutritionGuidance {
  daily_principles: string[];
  meal_patterns: {
    breakfast: string[];
    lunch: string[];
    dinner: string[];
    snacks: string[];
  };
  hydration_notes: string;
  fasting_compliance_note?: string;
}

export interface PlanDataStructure {
  training_days_per_week: number;
  target_goal: string;
  fitness_level: string;
  training_phase: string;
  target_intensity: {
    rpe_target: number;
    volume_modifier: string;
  };
  sessions: SessionPlan[];
  nutrition_guidance: NutritionGuidance;
}

export interface TrainingPlan {
  id: string;
  member: string;
  gym: string;
  week_start_date: string;
  draft_number: number;
  status: "pending_review" | "approved" | "rejected";
  generated_by_model: string;
  plan_data: PlanDataStructure;
  focus_this_week: string[];
  other_focus?: string;
  trainer_notes?: string;
  rejection_reasons?: string[];
  other_rejection_reason?: string;
  has_medical_caution: boolean;
  was_edited: boolean;
  approved_by?: string | null;
  approved_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface GeneratePlanPayload {
  week_choice: "this_week" | "next_week";
  focus_this_week?: string[];
  other_focus?: string;
}

export interface RejectPlanPayload {
  rejection_reasons: string[];
  other_rejection_reason?: string;
}

export interface EditPlanPayload {
  plan_data: PlanDataStructure;
}

export async function getPlanPrerequisites(memberId: string): Promise<PlanPrerequisites> {
  return apiFetch<PlanPrerequisites>(`/api/gym/members/${memberId}/plans/status/`);
}

export async function listMemberTrainingPlans(memberId: string): Promise<TrainingPlan[]> {
  return apiFetch<TrainingPlan[]>(`/api/gym/members/${memberId}/plans/`);
}

export async function generateTrainingPlan(
  memberId: string,
  payload: GeneratePlanPayload
): Promise<TrainingPlan> {
  return apiFetch<TrainingPlan>(`/api/gym/members/${memberId}/plans/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getTrainingPlanDetail(planId: string): Promise<TrainingPlan> {
  return apiFetch<TrainingPlan>(`/api/gym/training-plans/${planId}/`);
}

export async function approveTrainingPlan(planId: string): Promise<TrainingPlan> {
  return apiFetch<TrainingPlan>(`/api/gym/training-plans/${planId}/approve/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function rejectTrainingPlan(
  planId: string,
  payload: RejectPlanPayload
): Promise<TrainingPlan> {
  return apiFetch<TrainingPlan>(`/api/gym/training-plans/${planId}/reject/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function editTrainingPlan(
  planId: string,
  payload: EditPlanPayload
): Promise<TrainingPlan> {
  return apiFetch<TrainingPlan>(`/api/gym/training-plans/${planId}/edit/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function listMyApprovedTrainingPlans(): Promise<TrainingPlan[]> {
  return apiFetch<TrainingPlan[]>("/api/members/me/plans/");
}
