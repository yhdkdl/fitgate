import { apiFetch } from "./client";

export interface MembershipPlan {
  id: string;
  name: string;
  description: string;
  duration_value: number;
  duration_unit: "days" | "months";
  price_etb: string;
  trainer_inclusive: boolean;
  is_active: boolean;
  warning?: string;
  has_no_trainers_warning?: boolean;
  created_at: string;
  updated_at: string;
}

export interface PublicMembershipPlan {
  id: string;
  name: string;
  description: string;
  duration_value: number;
  duration_unit: "days" | "months";
  price_etb: string;
  trainer_inclusive: boolean;
}

export interface CreatePlanInput {
  name: string;
  description?: string;
  duration_value: number;
  duration_unit: "days" | "months";
  price_etb: string;
  trainer_inclusive?: boolean;
}

export interface UpdatePlanInput {
  name?: string;
  description?: string;
  duration_value?: number;
  duration_unit?: "days" | "months";
  price_etb?: string;
  trainer_inclusive?: boolean;
  is_active?: boolean;
}

/**
 * Fetch all membership plans for the authenticated gym staff's tenant.
 */
export async function getMembershipPlans(): Promise<MembershipPlan[]> {
  return apiFetch<MembershipPlan[]>("/api/gym/plans/");
}

/**
 * Create a new membership plan (Owner/Manager).
 */
export async function createMembershipPlan(
  data: CreatePlanInput
): Promise<MembershipPlan> {
  return apiFetch<MembershipPlan>("/api/gym/plans/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/**
 * Update an existing membership plan (Owner/Manager).
 */
export async function updateMembershipPlan(
  id: string,
  data: UpdatePlanInput
): Promise<MembershipPlan> {
  return apiFetch<MembershipPlan>(`/api/gym/plans/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

/**
 * Deactivate a membership plan (Owner/Manager).
 */
export async function deactivateMembershipPlan(id: string): Promise<{ detail: string }> {
  return apiFetch<{ detail: string }>(`/api/gym/plans/${id}/`, {
    method: "DELETE",
  });
}

/**
 * Fetch public active plans for the current gym subdomain.
 */
export async function getPublicPlans(): Promise<PublicMembershipPlan[]> {
  return apiFetch<PublicMembershipPlan[]>("/api/public/plans/");
}
