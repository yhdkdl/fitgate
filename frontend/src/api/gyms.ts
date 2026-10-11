/**
 * Typed API clients for gym tenant provisioning, TLS confirmation, and invite password setting.
 */

import { apiFetch } from "./client";
import type { components } from "../types/api";

export type CreateGymRequest = components["schemas"]["CreateGymRequestRequest"];
export type CreateGymResponse = components["schemas"]["CreateGymResponse"];
export type GymTenantSummary = components["schemas"]["GymTenantSummary"];
export type ConfirmTLSResponse = components["schemas"]["ConfirmTLSResponse"];

export async function createGym(
  data: CreateGymRequest
): Promise<CreateGymResponse> {
  return await apiFetch<CreateGymResponse>("/api/platform/gyms/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listGyms(): Promise<GymTenantSummary[]> {
  return await apiFetch<GymTenantSummary[]>("/api/platform/gyms/");
}

export async function proposeSubdomain(name: string): Promise<string> {
  const result = await apiFetch<{ subdomain: string }>(
    `/api/platform/gyms/propose-subdomain/?name=${encodeURIComponent(name)}`
  );
  return result.subdomain;
}

export async function confirmGymTls(
  gymId: string
): Promise<ConfirmTLSResponse> {
  return await apiFetch<ConfirmTLSResponse>(
    `/api/platform/gyms/${gymId}/confirm-tls/`,
    {
      method: "POST",
    }
  );
}

export async function setPasswordFromInvite(
  token: string,
  newPassword: string
): Promise<{ detail: string }> {
  return await apiFetch<{ detail: string }>("/api/auth/set-password/", {
    method: "POST",
    body: JSON.stringify({
      token,
      new_password: newPassword,
    }),
  });
}
