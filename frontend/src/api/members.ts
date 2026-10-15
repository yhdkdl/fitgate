import { getAccessToken } from "./client";

function getAuthHeader(): Record<string, string> {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export interface ApiError extends Error {
  status?: number;
  data?: unknown;
}

export interface BodyMetrics {
  id?: string;
  weight_kg?: number | string | null;
  height_cm?: number | string | null;
  measurements?: Record<string, unknown>;
  recorded_at?: string;
  estimated_bmi?: number | null;
  estimated_body_fat_percentage?: number | null;
  bmi_label?: string;
  body_fat_label?: string;
}

export interface Member {
  id: string;
  email: string;
  full_name: string;
  phone: string;
  date_of_birth?: string | null;
  gender?: string;
  emergency_contact?: string;
  referral_source?: string;
  photo_url?: string;
  status: "active" | "expired" | "frozen" | "suspended";
  joined_at: string;
  waiver_accepted_at: string;
  latest_metrics?: BodyMetrics | null;
  body_metrics?: BodyMetrics[];
}

export interface PublicMemberRegistrationPayload {
  full_name: string;
  email: string;
  phone: string;
  password?: string;
  waiver_accepted: boolean;
  date_of_birth?: string | null;
  gender?: string;
  emergency_contact?: string;
  referral_source?: string;
  weight_kg?: number | null;
  height_cm?: number | null;
  measurements?: Record<string, unknown>;
}

export interface StaffMemberRegistrationPayload {
  full_name: string;
  email: string;
  phone: string;
  waiver_accepted: boolean;
  date_of_birth?: string | null;
  gender?: string;
  emergency_contact?: string;
  referral_source?: string;
  weight_kg?: number | null;
  height_cm?: number | null;
  measurements?: Record<string, unknown>;
}

export interface MemberRegistrationResponse {
  detail: string;
  member: Member;
}

/**
 * Public self-service member registration on gym subdomain.
 */
export async function registerMemberSelfService(
  payload: PublicMemberRegistrationPayload
): Promise<MemberRegistrationResponse> {
  const res = await fetch("/api/public/members/register/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorData = (await res.json().catch(() => ({}))) as Record<
      string,
      unknown
    >;
    const err = new Error(
      (errorData.detail as string) ||
        "Registration failed. Please check your inputs."
    ) as ApiError;
    err.status = res.status;
    err.data = errorData;
    throw err;
  }

  return res.json();
}

/**
 * Public email verification.
 */
export async function verifyMemberEmail(
  token: string
): Promise<{ detail: string }> {
  const res = await fetch("/api/auth/verify-email/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ token }),
  });

  if (!res.ok) {
    const errorData = (await res.json().catch(() => ({}))) as Record<
      string,
      unknown
    >;
    const err = new Error(
      (errorData.detail as string) ||
        "Email verification failed. The link may have expired."
    ) as ApiError;
    err.status = res.status;
    err.data = errorData;
    throw err;
  }

  return res.json();
}

/**
 * Staff-assisted member list.
 */
export async function listGymMembers(params?: {
  search?: string;
  status?: string;
}): Promise<Member[]> {
  const query = new URLSearchParams();
  if (params?.search) query.set("search", params.search);
  if (params?.status) query.set("status", params.status);

  const url = `/api/gym/members/${query.toString() ? `?${query.toString()}` : ""}`;
  const res = await fetch(url, {
    headers: {
      ...getAuthHeader(),
    },
  });

  if (!res.ok) {
    const errorData = (await res.json().catch(() => ({}))) as Record<
      string,
      unknown
    >;
    const err = new Error(
      (errorData.detail as string) || "Failed to load members."
    ) as ApiError;
    err.status = res.status;
    err.data = errorData;
    throw err;
  }

  return res.json();
}

/**
 * Staff-assisted member registration.
 */
export async function registerMemberStaffAssisted(
  payload: StaffMemberRegistrationPayload
): Promise<MemberRegistrationResponse> {
  const res = await fetch("/api/gym/members/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeader(),
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorData = (await res.json().catch(() => ({}))) as Record<
      string,
      unknown
    >;
    const err = new Error(
      (errorData.detail as string) || "Staff member registration failed."
    ) as ApiError;
    err.status = res.status;
    err.data = errorData;
    throw err;
  }

  return res.json();
}

/**
 * Get detailed member record with metrics history.
 */
export async function getGymMemberDetail(memberId: string): Promise<Member> {
  const res = await fetch(`/api/gym/members/${memberId}/`, {
    headers: {
      ...getAuthHeader(),
    },
  });

  if (!res.ok) {
    const errorData = (await res.json().catch(() => ({}))) as Record<
      string,
      unknown
    >;
    const err = new Error(
      (errorData.detail as string) || "Member not found."
    ) as ApiError;
    err.status = res.status;
    err.data = errorData;
    throw err;
  }

  return res.json();
}

/**
 * Record body metrics for a member by staff.
 */
export async function recordMemberMetrics(
  memberId: string,
  payload: {
    weight_kg?: number | null;
    height_cm?: number | null;
    measurements?: Record<string, unknown>;
  }
): Promise<BodyMetrics> {
  const res = await fetch(`/api/gym/members/${memberId}/metrics/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeader(),
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorData = (await res.json().catch(() => ({}))) as Record<
      string,
      unknown
    >;
    const err = new Error(
      (errorData.detail as string) || "Failed to record body metrics."
    ) as ApiError;
    err.status = res.status;
    err.data = errorData;
    throw err;
  }

  return res.json();
}

/**
 * Member self-service profile.
 */
export async function getMemberProfileMe(): Promise<Member> {
  const res = await fetch("/api/members/me/", {
    headers: {
      ...getAuthHeader(),
    },
  });

  if (!res.ok) {
    const errorData = (await res.json().catch(() => ({}))) as Record<
      string,
      unknown
    >;
    const err = new Error(
      (errorData.detail as string) || "Failed to load profile."
    ) as ApiError;
    err.status = res.status;
    err.data = errorData;
    throw err;
  }

  return res.json();
}

/**
 * Member record own body metrics.
 */
export async function recordMemberMetricsMe(payload: {
  weight_kg?: number | null;
  height_cm?: number | null;
  measurements?: Record<string, unknown>;
}): Promise<BodyMetrics> {
  const res = await fetch("/api/members/me/metrics/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeader(),
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorData = (await res.json().catch(() => ({}))) as Record<
      string,
      unknown
    >;
    const err = new Error(
      (errorData.detail as string) || "Failed to record body metrics."
    ) as ApiError;
    err.status = res.status;
    err.data = errorData;
    throw err;
  }

  return res.json();
}

/**
 * Upload member photo to gym storage.
 */
export async function uploadMemberPhoto(
  file: File,
  gymId: string,
  memberId?: string
): Promise<{ file_path: string; filename: string; url: string }> {
  const formData = new FormData();
  formData.append("photo", file);
  if (memberId) {
    formData.append("member_id", memberId);
  }

  const res = await fetch(`/api/media/member-photos/${gymId}/`, {
    method: "POST",
    headers: {
      ...getAuthHeader(),
    },
    body: formData,
  });

  if (!res.ok) {
    const errorData = (await res.json().catch(() => ({}))) as Record<
      string,
      unknown
    >;
    const err = new Error(
      (errorData.detail as string) || "Failed to upload member photo."
    ) as ApiError;
    err.status = res.status;
    err.data = errorData;
    throw err;
  }

  return res.json();
}
