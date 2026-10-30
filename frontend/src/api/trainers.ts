import { apiFetch } from "./client";
import type { components } from "../types/api";

export type Trainer = components["schemas"]["Trainer"];
export type TrainerUser = components["schemas"]["TrainerUser"];
export type TrainerCapacityUpdatePayload =
  components["schemas"]["PatchedTrainerCapacityUpdateRequest"];
export type TrainerCapacityUpdateResponse =
  components["schemas"]["TrainerCapacityUpdateResponse"];

export async function listTrainers(): Promise<Trainer[]> {
  return apiFetch<Trainer[]>("/api/gym/trainers/");
}

export async function getTrainer(id: string): Promise<Trainer> {
  return apiFetch<Trainer>(`/api/gym/trainers/${id}/`);
}

export async function updateTrainerCapacity(
  id: string,
  payload: TrainerCapacityUpdatePayload
): Promise<TrainerCapacityUpdateResponse> {
  return apiFetch<TrainerCapacityUpdateResponse>(`/api/gym/trainers/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function getTrainerProfileMe(): Promise<Trainer> {
  return apiFetch<Trainer>("/api/trainers/me/");
}
