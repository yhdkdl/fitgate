import { apiFetch } from "./client";
import type { components } from "../types/api";

export type StaffMember = components["schemas"]["StaffMember"];
export type StaffRole = "manager" | "trainer" | "reception";

export interface InviteStaffPayload {
  email: string;
  role: StaffRole;
  full_name?: string;
  phone?: string;
}

export interface InviteStaffResponse {
  detail: string;
  user: StaffMember;
}

export interface StaffActionResponse {
  detail: string;
  user: StaffMember;
}

export async function listStaff(filters?: {
  role?: string;
  is_active?: boolean;
}): Promise<StaffMember[]> {
  const params = new URLSearchParams();
  if (filters?.role) {
    params.set("role", filters.role);
  }
  if (filters?.is_active !== undefined) {
    params.set("is_active", String(filters.is_active));
  }
  const queryStr = params.toString() ? `?${params.toString()}` : "";
  return apiFetch<StaffMember[]>(`/api/gym/staff/${queryStr}`);
}

export async function inviteStaff(
  payload: InviteStaffPayload
): Promise<InviteStaffResponse> {
  return apiFetch<InviteStaffResponse>("/api/gym/staff/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function deactivateStaff(
  userId: string
): Promise<StaffActionResponse> {
  return apiFetch<StaffActionResponse>(`/api/gym/staff/${userId}/deactivate/`, {
    method: "POST",
  });
}

export async function reactivateStaff(
  userId: string
): Promise<StaffActionResponse> {
  return apiFetch<StaffActionResponse>(`/api/gym/staff/${userId}/reactivate/`, {
    method: "POST",
  });
}
