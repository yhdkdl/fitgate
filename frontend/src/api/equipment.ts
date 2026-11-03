import { apiFetch } from "./client";
import type {
  EquipmentItem,
  EquipmentCreatePayload,
  EquipmentUpdatePayload,
  ReportIssuePayload,
  UpdateConditionPayload,
  MaintenanceLog,
} from "../types/equipment";

export async function listEquipment(): Promise<EquipmentItem[]> {
  return apiFetch<EquipmentItem[]>("/api/gym/equipment/");
}

export async function getEquipment(id: string): Promise<EquipmentItem> {
  return apiFetch<EquipmentItem>(`/api/gym/equipment/${id}/`);
}

export async function createEquipment(
  payload: EquipmentCreatePayload
): Promise<EquipmentItem> {
  return apiFetch<EquipmentItem>("/api/gym/equipment/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateEquipment(
  id: string,
  payload: EquipmentUpdatePayload
): Promise<EquipmentItem> {
  return apiFetch<EquipmentItem>(`/api/gym/equipment/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteEquipment(id: string): Promise<void> {
  return apiFetch<void>(`/api/gym/equipment/${id}/`, {
    method: "DELETE",
  });
}

export async function reportEquipmentIssue(
  id: string,
  payload: ReportIssuePayload
): Promise<MaintenanceLog> {
  return apiFetch<MaintenanceLog>(`/api/gym/equipment/${id}/report-issue/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateEquipmentCondition(
  id: string,
  payload: UpdateConditionPayload
): Promise<EquipmentItem> {
  return apiFetch<EquipmentItem>(`/api/gym/equipment/${id}/condition/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
