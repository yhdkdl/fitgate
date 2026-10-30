import { apiFetch } from "./client";
import type { components } from "../types/api";

export type Trainer = components["schemas"]["Trainer"];
export type TrainerUser = components["schemas"]["TrainerUser"];
export type TrainerCapacityUpdatePayload =
  components["schemas"]["PatchedTrainerCapacityUpdateRequest"];
export type TrainerCapacityUpdateResponse =
  components["schemas"]["TrainerCapacityUpdateResponse"];

export type AssignmentMemberInfo = {
  id: string;
  full_name: string;
  phone: string;
  status: string;
  plan_name: string;
};

export type TrainerAssignmentDetail = Omit<
  components["schemas"]["TrainerAssignmentDetail"],
  "member"
> & {
  member: AssignmentMemberInfo;
};

export type UnassignedMember = components["schemas"]["UnassignedMember"];
export type ManualReassignRequest =
  components["schemas"]["ManualReassignRequestRequest"];
export type ManualReassignResponse =
  components["schemas"]["ManualReassignResponse"];
export type TrainerMyClient = components["schemas"]["TrainerMyClient"];

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

export async function listAssignments(): Promise<TrainerAssignmentDetail[]> {
  return apiFetch<TrainerAssignmentDetail[]>("/api/gym/assignments/");
}

export async function listUnassignedMembers(): Promise<UnassignedMember[]> {
  return apiFetch<UnassignedMember[]>("/api/gym/unassigned-members/");
}

export async function reassignTrainer(
  payload: ManualReassignRequest
): Promise<ManualReassignResponse> {
  return apiFetch<ManualReassignResponse>("/api/gym/assignments/reassign/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getMyClients(): Promise<TrainerMyClient[]> {
  return apiFetch<TrainerMyClient[]>("/api/trainers/me/clients/");
}

export async function uploadTrainerPhoto(
  gymId: string,
  file: File
): Promise<{ photo_url: string }> {
  const formData = new FormData();
  formData.append("photo", file);
  return apiFetch<{ photo_url: string }>(`/api/media/member-photos/${gymId}/`, {
    method: "POST",
    body: formData,
  });
}
