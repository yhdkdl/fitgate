import { apiFetch } from "./client";
import type { components } from "../types/api";

export type AuditLogEntry = components["schemas"]["AuditLog"];

export interface PaginatedAuditLogResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: AuditLogEntry[];
}

export interface AuditLogFilters {
  date_from?: string;
  date_to?: string;
  action_type?: string;
  actor_id?: string;
  gym_id?: string;
  search?: string;
  page?: number;
  page_size?: number;
}

export async function fetchGymAuditLogs(
  filters?: AuditLogFilters
): Promise<PaginatedAuditLogResponse> {
  const params = new URLSearchParams();
  if (filters?.date_from) params.set("date_from", filters.date_from);
  if (filters?.date_to) params.set("date_to", filters.date_to);
  if (filters?.action_type) params.set("action_type", filters.action_type);
  if (filters?.actor_id) params.set("actor_id", filters.actor_id);
  if (filters?.search) params.set("search", filters.search);
  if (filters?.page) params.set("page", String(filters.page));
  if (filters?.page_size) params.set("page_size", String(filters.page_size));

  const queryStr = params.toString() ? `?${params.toString()}` : "";
  return apiFetch<PaginatedAuditLogResponse>(`/api/gym/audit-logs/${queryStr}`);
}

export async function fetchPlatformAuditLogs(
  filters?: AuditLogFilters
): Promise<PaginatedAuditLogResponse> {
  const params = new URLSearchParams();
  if (filters?.gym_id) params.set("gym_id", filters.gym_id);
  if (filters?.date_from) params.set("date_from", filters.date_from);
  if (filters?.date_to) params.set("date_to", filters.date_to);
  if (filters?.action_type) params.set("action_type", filters.action_type);
  if (filters?.actor_id) params.set("actor_id", filters.actor_id);
  if (filters?.search) params.set("search", filters.search);
  if (filters?.page) params.set("page", String(filters.page));
  if (filters?.page_size) params.set("page_size", String(filters.page_size));

  const queryStr = params.toString() ? `?${params.toString()}` : "";
  return apiFetch<PaginatedAuditLogResponse>(
    `/api/platform/audit-logs/${queryStr}`
  );
}
