import { apiFetch } from "./client";

export interface MemberQrTokenResponse {
  token: string;
  expires_at: string;
  valid_seconds: number;
  member_id: string;
}

export interface AttendanceRecord {
  id: string;
  date: string;
  checked_in_at: string;
  is_override: boolean;
  override_reason?: string;
}

export interface ScanResultMember {
  id: string;
  full_name: string;
  photo_url?: string;
  status: "active" | "expired" | "frozen" | "suspended" | string;
  phone?: string;
}

export interface ScanResultResponse {
  status: "success";
  message: string;
  member: ScanResultMember;
  attendance: AttendanceRecord;
  next_token: string;
}

export interface ScanErrorResponse {
  detail: string;
  reason:
    | "expired"
    | "frozen"
    | "suspended"
    | "already_checked_in"
    | "token_expired"
    | "token_consumed"
    | "invalid_token"
    | "gym_mismatch"
    | string;
  member?: ScanResultMember;
}

export interface ManualOverrideResultResponse {
  status: "success";
  message: string;
  member: ScanResultMember;
  attendance: AttendanceRecord;
}

export interface DailyAttendanceItem {
  date: string;
  status: "present" | "absent" | "blank";
  symbol: string;
  attended: boolean;
  checked_in_at?: string | null;
  is_override?: boolean;
}

export interface AttendanceLogResponse {
  member_id: string;
  member_name: string;
  start_date: string;
  end_date: string;
  subscription_period: {
    start_date: string | null;
    end_date: string | null;
  };
  days: DailyAttendanceItem[];
}

/**
 * Fetch RSA public key for offline QR verification.
 */
export async function getAttendancePublicKey(): Promise<{
  public_key: string;
  algorithm: string;
}> {
  return apiFetch<{ public_key: string; algorithm: string }>(
    "/api/attendance/public-key/"
  );
}

/**
 * Generate or fetch active member's 90-second QR check-in token.
 */
export async function getMemberQrToken(): Promise<MemberQrTokenResponse> {
  return apiFetch<MemberQrTokenResponse>("/api/members/me/qr-token/");
}

/**
 * Scan a member's QR token and record attendance.
 */
export async function scanQrToken(payload: {
  token: string;
  branch_id?: string | null;
}): Promise<ScanResultResponse> {
  return apiFetch<ScanResultResponse>("/api/gym/attendance/scan/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * Perform manual attendance check-in override by reception staff.
 */
export async function manualAttendanceOverride(payload: {
  member_id: string;
  reason: string;
  branch_id?: string | null;
}): Promise<ManualOverrideResultResponse> {
  return apiFetch<ManualOverrideResultResponse>(
    "/api/gym/attendance/manual-override/",
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

/**
 * Fetch member's daily attendance calendar log (✓/✗/blank).
 * If memberId is omitted, requests the authenticated member's own attendance log.
 */
export async function getAttendanceLog(params?: {
  memberId?: string;
  startDate?: string;
  endDate?: string;
}): Promise<AttendanceLogResponse> {
  const query = new URLSearchParams();
  if (params?.startDate) query.set("start_date", params.startDate);
  if (params?.endDate) query.set("end_date", params.endDate);
  const queryString = query.toString() ? `?${query.toString()}` : "";

  if (params?.memberId) {
    return apiFetch<AttendanceLogResponse>(
      `/api/gym/members/${params.memberId}/attendance/${queryString}`
    );
  }
  return apiFetch<AttendanceLogResponse>(
    `/api/members/me/attendance/${queryString}`
  );
}
