import { apiFetch } from "./client";

export type SupportCategory =
  | "system_problem"
  | "question"
  | "feature_request"
  | "billing"
  | "other";

export type SupportStatus = "open" | "in_progress" | "resolved";

export interface SupportMessage {
  id: string;
  sender_type: "gym" | "platform";
  sender_name: string;
  body: string;
  created_at: string;
}

export interface SupportRequest {
  id: string;
  gym_id: string;
  gym_name: string;
  category: SupportCategory;
  request_type?: SupportCategory;
  request_type_display?: string;
  subject: string;
  status: SupportStatus;
  created_by_name: string;
  created_at: string;
  updated_at: string;
  messages: SupportMessage[];
}

export async function listGymSupportRequests(): Promise<SupportRequest[]> {
  return await apiFetch<SupportRequest[]>("/api/gym/support-requests/");
}

export async function createGymSupportRequest(payload: {
  category?: SupportCategory;
  request_type?: SupportCategory;
  subject: string;
  message: string;
}): Promise<SupportRequest> {
  const reqType = payload.category || payload.request_type || "system_problem";
  return await apiFetch<SupportRequest>("/api/gym/support-requests/", {
    method: "POST",
    body: JSON.stringify({
      ...payload,
      request_type: reqType,
      category: reqType,
    }),
  });
}

export async function getGymSupportRequestDetail(
  id: string
): Promise<SupportRequest> {
  return await apiFetch<SupportRequest>(`/api/gym/support-requests/${id}/`);
}

export async function replyGymSupportRequest(
  id: string,
  body: string
): Promise<SupportRequest> {
  return await apiFetch<SupportRequest>(`/api/gym/support-requests/${id}/reply/`, {
    method: "POST",
    body: JSON.stringify({ body, message: body }),
  });
}

export async function listPlatformSupportRequests(params?: {
  status?: string;
  gym_id?: string;
  category?: string;
}): Promise<SupportRequest[]> {
  const query = new URLSearchParams();
  if (params?.status && params.status !== "all") query.set("status", params.status);
  if (params?.gym_id && params.gym_id !== "all") query.set("gym_id", params.gym_id);
  if (params?.category && params.category !== "all") query.set("category", params.category);
  const qs = query.toString();
  return await apiFetch<SupportRequest[]>(
    `/api/platform/support-requests/${qs ? `?${qs}` : ""}`
  );
}

export async function getPlatformSupportRequestDetail(
  id: string
): Promise<SupportRequest> {
  return await apiFetch<SupportRequest>(
    `/api/platform/support-requests/${id}/`
  );
}

export async function replyPlatformSupportRequest(
  id: string,
  body: string
): Promise<SupportRequest> {
  return await apiFetch<SupportRequest>(
    `/api/platform/support-requests/${id}/reply/`,
    {
      method: "POST",
      body: JSON.stringify({ body, message: body }),
    }
  );
}

export async function updatePlatformSupportRequestStatus(
  id: string,
  status: SupportStatus
): Promise<SupportRequest> {
  return await apiFetch<SupportRequest>(
    `/api/platform/support-requests/${id}/status/`,
    {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }
  );
}
