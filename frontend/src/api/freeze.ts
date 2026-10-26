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
    let detail = fallbackMessage;
    if (typeof errorData === "object" && errorData !== null) {
      if ("detail" in errorData) {
        detail = String((errorData as { detail: unknown }).detail);
      } else if ("rejection_reason" in errorData) {
        detail = String((errorData as { rejection_reason: unknown }).rejection_reason);
      } else if ("reason" in errorData) {
        detail = String((errorData as { reason: unknown }).reason);
      }
    } else if (typeof errorData === "string" && errorData.trim() !== "") {
      detail = errorData;
    }
    throw new ApiError(res.status, detail, errorData);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  const data = await parseResponseBody(res);
  return data as T;
}

export interface MemberFreeze {
  id: string;
  member: {
    id: string;
    full_name: string;
    phone?: string;
  };
  subscription_id: string;
  start_date: string;
  end_date: string;
  days: number;
  reason: string;
  status: "pending" | "approved" | "rejected" | "completed";
  rejection_reason?: string;
  approved_by?: {
    id: string;
    email: string;
    role: string;
  };
  reviewed_at?: string;
  unfrozen_at?: string;
  created_at: string;
}

export interface MemberFreezeAllowance {
  total_allowed: number;
  used_days: number;
  remaining_days: number;
  has_active_subscription: boolean;
  freeze_allowed: boolean;
  subscription_id?: string;
}

export interface FreezeRequestPayload {
  start_date: string;
  end_date: string;
  reason: string;
}

/**
 * Member requests a freeze on their active membership subscription.
 */
export async function requestFreeze(
  payload: FreezeRequestPayload
): Promise<MemberFreeze> {
  const res = await fetch("/api/memberships/freezes/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeader(),
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<MemberFreeze>(res, "Failed to submit freeze request");
}

/**
 * Member retrieves their own freeze requests.
 */
export async function getMyFreezes(): Promise<MemberFreeze[]> {
  const res = await fetch("/api/memberships/freezes/mine/", {
    headers: {
      ...getAuthHeader(),
    },
  });
  return handleResponse<MemberFreeze[]>(res, "Failed to fetch your freeze history");
}

/**
 * Member retrieves their freeze allowance and remaining days.
 */
export async function getMemberFreezeAllowance(): Promise<MemberFreezeAllowance> {
  const res = await fetch("/api/memberships/freezes/allowance/", {
    headers: {
      ...getAuthHeader(),
    },
  });
  return handleResponse<MemberFreezeAllowance>(res, "Failed to fetch freeze allowance");
}

/**
 * Staff (Owner, Manager) lists freeze requests for their gym.
 */
export async function getGymFreezes(
  statusFilter?: string
): Promise<MemberFreeze[]> {
  const query = statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : "";
  const res = await fetch(`/api/gym/freezes/${query}`, {
    headers: {
      ...getAuthHeader(),
    },
  });
  return handleResponse<MemberFreeze[]>(res, "Failed to fetch gym freeze requests");
}

/**
 * Staff (Owner, Manager) approves a pending freeze request.
 */
export async function approveFreeze(
  freezeId: string
): Promise<{ detail: string; freeze: MemberFreeze }> {
  const res = await fetch(`/api/gym/freezes/${freezeId}/approve/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeader(),
    },
  });
  return handleResponse<{ detail: string; freeze: MemberFreeze }>(
    res,
    "Failed to approve freeze request"
  );
}

/**
 * Staff (Owner, Manager) rejects a pending freeze request with reason.
 */
export async function rejectFreeze(
  freezeId: string,
  rejectionReason: string
): Promise<{ detail: string; freeze: MemberFreeze }> {
  const res = await fetch(`/api/gym/freezes/${freezeId}/reject/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeader(),
    },
    body: JSON.stringify({ rejection_reason: rejectionReason }),
  });
  return handleResponse<{ detail: string; freeze: MemberFreeze }>(
    res,
    "Failed to reject freeze request"
  );
}
