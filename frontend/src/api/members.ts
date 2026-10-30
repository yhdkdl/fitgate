import { ApiError, getAccessToken, parseResponseBody } from "./client";
export { ApiError } from "./client";

function getAuthHeader(): Record<string, string> {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function handleResponse<T>(
  res: Response,
  fallbackMessage: string
): Promise<T> {
  if (!res.ok) {
    const errorData = await parseResponseBody(res);
    const detail =
      typeof errorData === "object" &&
      errorData !== null &&
      "detail" in errorData
        ? String((errorData as { detail: unknown }).detail)
        : typeof errorData === "string" && errorData.trim() !== ""
          ? errorData
          : fallbackMessage;
    throw new ApiError(res.status, detail, errorData);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  const data = await parseResponseBody(res);
  return data as T;
}

export interface BodyMetrics {
  id?: string;
  weight_kg?: number | string | null;
  height_cm?: number | string | null;
  measurements?: Record<string, unknown>;
  recorded_at?: string;
  recorded_by?: string | null;
  trainer_name?: string;
  recorded_by_name?: string;
  estimated_bmi?: number | null;
  estimated_body_fat_percentage?: number | null;
  bmi_label?: string;
  body_fat_label?: string;
  waist_to_hip_ratio?: number | null;
  lean_body_mass?: number | null;
  lean_body_mass_label?: string | null;
  is_corrected?: boolean;
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
  status: "pending" | "active" | "expired" | "frozen" | "suspended";
  joined_at: string;
  waiver_accepted_at: string;
  latest_metrics?: BodyMetrics | null;
  body_metrics?: BodyMetrics[];
  assigned_trainer?: {
    id: string;
    name: string;
    specialization?: string;
    photo_url?: string;
  } | null;
  is_on_trainer_plan?: boolean;
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
  photo_url?: string;
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
  photo_url?: string;
  plan_id?: string;
  payment_method?: "none" | "cash" | "bank_transfer";
  idempotency_key?: string;
  notes?: string;
  bank_reference?: string;
  transfer_date?: string;
  channel?: string;
  screenshot?: File;
}

export interface MemberRegistrationResponse {
  detail: string;
  member: Member;
  payment?: unknown;
  receipt?: import("./payments").DigitalReceipt;
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

  return handleResponse<MemberRegistrationResponse>(
    res,
    "Registration failed. Please check your inputs."
  );
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

  return handleResponse<{ detail: string }>(
    res,
    "Email verification failed. The link may have expired."
  );
}

/**
 * Staff-assisted member list.
 */
export async function listGymMembers(params?: {
  search?: string;
  status?: string;
  limit?: number;
}): Promise<Member[]> {
  const query = new URLSearchParams();
  if (params?.search) query.set("search", params.search);
  if (params?.status) query.set("status", params.status);
  if (params?.limit) query.set("limit", String(params.limit));

  const url = `/api/gym/members/${query.toString() ? `?${query.toString()}` : ""}`;
  const res = await fetch(url, {
    headers: {
      ...getAuthHeader(),
    },
  });

  return handleResponse<Member[]>(res, "Failed to load members.");
}

/**
 * Staff-assisted member registration with integrated atomic payment (Item 12).
 */
export async function registerMemberStaffAssisted(
  payload: StaffMemberRegistrationPayload
): Promise<MemberRegistrationResponse> {
  let body: BodyInit;
  const headers: Record<string, string> = { ...getAuthHeader() };

  if (payload.screenshot) {
    const formData = new FormData();
    Object.entries(payload).forEach(([key, val]) => {
      if (val !== undefined && val !== null) {
        if (key === "screenshot" && val instanceof File) {
          formData.append("screenshot", val);
        } else {
          formData.append(key, String(val));
        }
      }
    });
    body = formData;
  } else {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(payload);
  }

  const res = await fetch("/api/gym/members/", {
    method: "POST",
    headers,
    body,
  });

  return handleResponse<MemberRegistrationResponse>(
    res,
    "Staff member registration failed."
  );
}

/**
 * Staff member edit (Owner, Manager, Reception - Item 14).
 */
export async function updateGymMember(
  memberId: string,
  payload: {
    full_name?: string;
    phone?: string;
    emergency_contact?: string;
    gender?: string;
    date_of_birth?: string | null;
    photo_url?: string;
  }
): Promise<Member> {
  const res = await fetch(`/api/gym/members/${memberId}/`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeader(),
    },
    body: JSON.stringify(payload),
  });

  return handleResponse<Member>(res, "Failed to update member profile.");
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

  return handleResponse<Member>(res, "Member not found.");
}

/**
 * Get body metrics history for a gym member (Trainer, Owner, Manager).
 */
export async function getMemberMetrics(
  memberId: string
): Promise<BodyMetrics[]> {
  const res = await fetch(`/api/gym/members/${memberId}/metrics/`, {
    headers: {
      ...getAuthHeader(),
    },
  });

  return handleResponse<BodyMetrics[]>(res, "Failed to load member metrics.");
}

/**
 * Record body metrics for a member by a Trainer.
 */
export interface RecordMetricsPayload {
  weight_kg?: number;
  height_cm?: number;
  waist_cm?: number | null;
  neck_cm?: number | null;
  hip_cm?: number | null;
  chest_cm?: number | null;
  bicep_left_cm?: number | null;
  bicep_right_cm?: number | null;
  thigh_left_cm?: number | null;
  thigh_right_cm?: number | null;
  calf_left_cm?: number | null;
  calf_right_cm?: number | null;
  resting_heart_rate?: number | null;
  body_fat_percentage?: number | null;
  metric_id?: string;
  measurements?: Record<string, unknown>;
}

export async function recordMemberMetrics(
  memberId: string,
  payload: RecordMetricsPayload
): Promise<BodyMetrics> {
  const res = await fetch(`/api/gym/members/${memberId}/metrics/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeader(),
    },
    body: JSON.stringify(payload),
  });

  return handleResponse<BodyMetrics>(res, "Failed to record body metrics.");
}

export async function correctMemberMetrics(
  memberId: string,
  payload: RecordMetricsPayload
): Promise<BodyMetrics> {
  const res = await fetch(`/api/gym/members/${memberId}/metrics/`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeader(),
    },
    body: JSON.stringify(payload),
  });

  return handleResponse<BodyMetrics>(res, "Failed to correct body metrics.");
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

  return handleResponse<Member>(res, "Failed to load profile.");
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

  return handleResponse<BodyMetrics>(res, "Failed to record body metrics.");
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

  return handleResponse<{ file_path: string; filename: string; url: string }>(
    res,
    "Failed to upload member photo."
  );
}

/**
 * Suspend a gym member (Owner/Manager).
 */
export async function suspendMember(
  memberId: string,
  reason: string
): Promise<{ detail: string; status: string; member: Member }> {
  const res = await fetch(`/api/gym/members/${memberId}/suspend/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeader(),
    },
    body: JSON.stringify({ reason }),
  });

  return handleResponse<{ detail: string; status: string; member: Member }>(
    res,
    "Failed to suspend member."
  );
}

/**
 * Reactivate a suspended gym member (Owner/Manager).
 */
export async function reactivateMember(
  memberId: string
): Promise<{ detail: string; status: string; member: Member }> {
  const res = await fetch(`/api/gym/members/${memberId}/reactivate/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeader(),
    },
  });

  return handleResponse<{ detail: string; status: string; member: Member }>(
    res,
    "Failed to reactivate member."
  );
}
