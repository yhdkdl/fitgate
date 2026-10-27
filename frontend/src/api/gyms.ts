/**
 * Typed API clients for gym tenant provisioning, TLS confirmation, and invite password setting.
 */

import { apiFetch } from "./client";
import type { components } from "../types/api";

export type CreateGymRequest = components["schemas"]["CreateGymRequestRequest"];
export type CreateGymResponse = components["schemas"]["CreateGymResponse"] & {
  gym_url?: string;
  invite_link?: string;
};
export type GymTenantSummary = components["schemas"]["GymTenantSummary"] & {
  url?: string;
};
export type ConfirmTLSResponse = components["schemas"]["ConfirmTLSResponse"];
export type GymPublicEntryResponse =
  components["schemas"]["GymPublicEntryResponse"] & {
    plans?: Array<{
      id: string;
      name: string;
      description?: string;
      duration_value: number;
      duration_unit: string;
      price_etb: string;
      trainer_inclusive: boolean;
    }>;
  };
export type FirstRunChecklistResponse =
  components["schemas"]["FirstRunChecklistResponse"];
export type GymConfig = components["schemas"]["GymConfig"];
export type PatchedGymSettingsUpdateRequest =
  components["schemas"]["PatchedGymSettingsUpdateRequest"];
export type DismissChecklistResponse =
  components["schemas"]["DismissChecklistResponse"];

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

export async function getPublicGymEntry(
  subdomain?: string
): Promise<GymPublicEntryResponse> {
  const query = subdomain ? `?subdomain=${encodeURIComponent(subdomain)}` : "";
  return await apiFetch<GymPublicEntryResponse>(
    `/api/public/gym-entry/${query}`
  );
}

export async function getFirstRunChecklist(
  gymId?: string
): Promise<FirstRunChecklistResponse> {
  const query = gymId ? `?gym_id=${encodeURIComponent(gymId)}` : "";
  return await apiFetch<FirstRunChecklistResponse>(
    `/api/gym/checklist/${query}`
  );
}

export async function dismissFirstRunChecklist(): Promise<DismissChecklistResponse> {
  return await apiFetch<DismissChecklistResponse>(
    "/api/gym/checklist/dismiss/",
    {
      method: "POST",
    }
  );
}

export async function getGymSettings(gymId?: string): Promise<GymConfig> {
  const url = gymId
    ? `/api/platform/gyms/${gymId}/config/`
    : "/api/gym/settings/";
  return await apiFetch<GymConfig>(url);
}

export async function updateGymSettings(
  data: PatchedGymSettingsUpdateRequest,
  gymId?: string
): Promise<GymConfig> {
  const url = gymId
    ? `/api/platform/gyms/${gymId}/config/`
    : "/api/gym/settings/";
  return await apiFetch<GymConfig>(url, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function uploadGymLogo(
  file: File,
  gymId: string
): Promise<{ url: string }> {
  const formData = new FormData();
  formData.append("logo", file);
  return await apiFetch<{ url: string }>(`/api/media/gym-logo/${gymId}/`, {
    method: "POST",
    body: formData,
  });
}
