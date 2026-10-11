/**
 * API client methods for Public Demo Requests and Super Admin lead management.
 */

import { apiFetch } from "./client";
import type { components } from "../types/api";

export type PublicDemoRequestRequest =
  components["schemas"]["PublicDemoRequestRequest"];
export type PublicDemoRequestResponse =
  components["schemas"]["PublicDemoRequestResponse"];
export type DemoRequest = components["schemas"]["DemoRequest"];
export type DemoRequestStatus = components["schemas"]["DemoRequestStatusEnum"];
export type DemoRequestUpdateRequest =
  components["schemas"]["PatchedDemoRequestUpdateRequest"];
export type DemoRequestConvertResponse =
  components["schemas"]["DemoRequestConvertResponse"];

export async function submitPublicDemoRequest(
  data: PublicDemoRequestRequest
): Promise<PublicDemoRequestResponse> {
  return await apiFetch<PublicDemoRequestResponse>(
    "/api/platform/demo-requests/public/",
    {
      method: "POST",
      body: JSON.stringify(data),
    }
  );
}

export async function listDemoRequests(
  status?: string
): Promise<DemoRequest[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return await apiFetch<DemoRequest[]>(`/api/platform/demo-requests/${query}`);
}

export async function getDemoRequest(id: string): Promise<DemoRequest> {
  return await apiFetch<DemoRequest>(`/api/platform/demo-requests/${id}/`);
}

export async function updateDemoRequest(
  id: string,
  data: DemoRequestUpdateRequest
): Promise<DemoRequest> {
  return await apiFetch<DemoRequest>(`/api/platform/demo-requests/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function getDemoRequestConvertData(
  id: string
): Promise<DemoRequestConvertResponse> {
  return await apiFetch<DemoRequestConvertResponse>(
    `/api/platform/demo-requests/${id}/convert/`
  );
}
