import { apiFetch } from "./client";
import type { components } from "../types/api";

export type FitnessProfile = components["schemas"]["FitnessProfile"];

export interface FitnessProfilePayload {
  goal: string;
  fitness_level: string;
  training_days_per_week: number;
  session_length_minutes: number;
  dietary_notes?: string;
  health_limitations?: string;
  equipment_access?: string;
}

export async function getMemberFitnessProfile(
  memberId: string
): Promise<FitnessProfile> {
  return apiFetch<FitnessProfile>(
    `/api/gym/members/${memberId}/fitness-profile/`
  );
}

export async function saveMemberFitnessProfile(
  memberId: string,
  payload: FitnessProfilePayload
): Promise<FitnessProfile> {
  return apiFetch<FitnessProfile>(
    `/api/gym/members/${memberId}/fitness-profile/`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function getMemberSelfFitnessProfile(): Promise<FitnessProfile> {
  return apiFetch<FitnessProfile>("/api/members/me/fitness-profile/");
}
