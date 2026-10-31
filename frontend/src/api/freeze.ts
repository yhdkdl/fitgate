import { ApiError, getAccessToken, parseResponseBody } from "./client";
export { ApiError } from "./client";

function getAuthHeader(): Record<string, string> {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function formatApiErrorMessage(
  errorData: unknown,
  fallbackMessage: string
): string {
  if (typeof errorData === "string" && errorData.trim() !== "") {
    return errorData;
  }
  if (typeof errorData === "object" && errorData !== null) {
    const dataObj = errorData as Record<string, unknown>;
    if ("detail" in dataObj) {
      const d = dataObj.detail;
      if (typeof d === "string" && d.trim() !== "") {
        return d;
      }
      if (Array.isArray(d)) {
        return d.map(String).join(" ");
      }
      if (typeof d === "object" && d !== null) {
        const nested = Object.values(d as Record<string, unknown>)
          .flatMap((v) => (Array.isArray(v) ? v : [v]))
          .map(String)
          .filter(Boolean);
        if (nested.length > 0) return nested.join(" ");
      }
    }
    if ("rejection_reason" in dataObj && dataObj.rejection_reason) {
      return String(dataObj.rejection_reason);
    }
    if ("reason" in dataObj && dataObj.reason) {
      if (typeof dataObj.reason === "string") return dataObj.reason;
      if (Array.isArray(dataObj.reason)) return dataObj.reason.map(String).join(" ");
    }
    const messages: string[] = [];
    for (const [key, val] of Object.entries(dataObj)) {
      if (key === "detail" || key === "reason" || key === "rejection_reason") continue;
      if (Array.isArray(val)) {
        messages.push(...val.map(String));
      } else if (typeof val === "string") {
        messages.push(val);
      }
    }
    if (messages.length > 0) {
      return messages.join(" ");
    }
  }
  return fallbackMessage;
}

async function handleResponse<T>(
  res: Response,
  fallbackMessage: string
): Promise<T> {
  if (!res.ok) {
    const errorData = await parseResponseBody(res);
    const detail = formatApiErrorMessage(errorData, fallbackMessage);
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

/**
 * Staff (Owner, Manager, Reception) ends an approved freeze early.
 */
export async function endFreezeEarly(
  freezeId: string
): Promise<{ detail: string; freeze?: MemberFreeze }> {
  const res = await fetch(`/api/gym/freezes/${freezeId}/end-early/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeader(),
    },
  });
  return handleResponse<{ detail: string; freeze?: MemberFreeze }>(
    res,
    "Failed to end freeze early"
  );
}

/**
 * Staff (Owner, Manager, Reception) ends a member's active approved freeze early.
 */
export async function endMemberFreezeEarly(
  memberId: string
): Promise<{ detail: string; freeze?: MemberFreeze }> {
  const res = await fetch(`/api/gym/members/${memberId}/end-freeze-early/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeader(),
    },
  });
  return handleResponse<{ detail: string; freeze?: MemberFreeze }>(
    res,
    "Failed to end member freeze early"
  );
}
