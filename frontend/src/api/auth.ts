import {
  apiFetch,
  clearTokens,
  getRefreshToken,
  setAccessToken,
  setRefreshToken,
} from "./client";
import type { components } from "../types/api";

export type LoginRequest = components["schemas"]["LoginRequestRequest"];
export type LoginResponse = components["schemas"]["LoginResponse"];
export type UserSummary = components["schemas"]["UserSummary"];
export type UserProfile = components["schemas"]["UserProfile"];
export type ProfileUpdateRequest =
  components["schemas"]["PatchedUserProfileUpdateRequest"];
export type ChangePasswordRequest =
  components["schemas"]["ChangePasswordRequestRequest"];
export type ChangePasswordResponse =
  components["schemas"]["ChangePasswordResponse"];
export type PasswordResetRequest =
  components["schemas"]["PasswordResetRequestRequest"];
export type PasswordResetResponse =
  components["schemas"]["PasswordResetResponse"];
export type PasswordResetConfirmRequest =
  components["schemas"]["PasswordResetConfirmRequestRequest"];
export type PasswordResetConfirmResponse =
  components["schemas"]["PasswordResetConfirmResponse"];

export interface GymCapabilities {
  tier?: string;
  has_trainer_module?: boolean;
  has_ai_plans?: boolean;
  has_analytics?: boolean;
  has_group_classes?: boolean;
  has_notices?: boolean;
  has_expenses?: boolean;
  has_freeze?: boolean;
  freeze_days_allowed?: number;
  freeze_days_cap?: number;
}

export interface DashboardConfig {
  role: string;
  title: string;
  widgets: Array<{ id: string; title: string }>;
  navigation: Array<{ label: string; path: string }>;
  capabilities?: GymCapabilities;
}

export async function login(payload: LoginRequest): Promise<LoginResponse> {
  const data = await apiFetch<LoginResponse>("/api/auth/login/", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  setAccessToken(data.access);
  setRefreshToken(data.refresh);
  return data;
}

export async function logout(): Promise<void> {
  const refresh = getRefreshToken();
  try {
    if (refresh) {
      await apiFetch<void>("/api/auth/logout/", {
        method: "POST",
        body: JSON.stringify({ refresh }),
      });
    }
  } finally {
    clearTokens();
  }
}

export async function getProfile(): Promise<UserProfile> {
  return apiFetch<UserProfile>("/api/auth/me/", {
    method: "GET",
  });
}

export async function updateProfile(
  payload: ProfileUpdateRequest
): Promise<UserProfile> {
  return apiFetch<UserProfile>("/api/auth/me/", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function changePassword(
  payload: ChangePasswordRequest
): Promise<ChangePasswordResponse> {
  const data = await apiFetch<ChangePasswordResponse>(
    "/api/auth/change-password/",
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );

  setAccessToken(data.access);
  setRefreshToken(data.refresh);
  return data;
}

export async function requestPasswordReset(
  payload: PasswordResetRequest
): Promise<PasswordResetResponse> {
  return apiFetch<PasswordResetResponse>("/api/auth/password-reset/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function confirmPasswordReset(
  payload: PasswordResetConfirmRequest
): Promise<PasswordResetConfirmResponse> {
  return apiFetch<PasswordResetConfirmResponse>(
    "/api/auth/password-reset/confirm/",
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}
