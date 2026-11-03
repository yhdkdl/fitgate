import { apiFetch } from "./client";
import type {
  ClassBooking,
  ClassRosterResponse,
  ClassSession,
  ClassSessionCreatePayload,
  ClassSessionUpdatePayload,
  MarkAttendancePayload,
} from "../types/classes";

interface ClassSessionListResponse {
  sessions?: ClassSession[];
}

interface ClassBookingListResponse {
  bookings?: ClassBooking[];
}

export async function listClasses(params?: {
  start_date?: string;
  end_date?: string;
  trainer_id?: string;
  status?: string;
}): Promise<ClassSession[]> {
  const query = new URLSearchParams();
  if (params?.start_date) query.set("start_date", params.start_date);
  if (params?.end_date) query.set("end_date", params.end_date);
  if (params?.trainer_id) query.set("trainer_id", params.trainer_id);
  if (params?.status) query.set("status", params.status);

  const qs = query.toString();
  const res = await apiFetch<ClassSessionListResponse>(
    `/api/gym/classes/${qs ? `?${qs}` : ""}`
  );
  return res.sessions || [];
}

export async function createClasses(
  payload: ClassSessionCreatePayload
): Promise<{ message: string; sessions: ClassSession[] }> {
  return apiFetch<{ message: string; sessions: ClassSession[] }>(
    "/api/gym/classes/",
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function updateClass(
  id: string,
  payload: ClassSessionUpdatePayload
): Promise<{ message: string; session: ClassSession }> {
  return apiFetch<{ message: string; session: ClassSession }>(
    `/api/gym/classes/${id}/`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    }
  );
}

export async function cancelClass(
  id: string
): Promise<{ message: string; session: ClassSession }> {
  return apiFetch<{ message: string; session: ClassSession }>(
    `/api/gym/classes/${id}/cancel/`,
    {
      method: "POST",
    }
  );
}

export async function getClassRoster(id: string): Promise<ClassRosterResponse> {
  return apiFetch<ClassRosterResponse>(`/api/gym/classes/${id}/roster/`);
}

export async function bookClass(
  id: string,
  memberId?: string
): Promise<{ message: string; booking: ClassBooking }> {
  return apiFetch<{ message: string; booking: ClassBooking }>(
    `/api/gym/classes/${id}/book/`,
    {
      method: "POST",
      body: JSON.stringify(memberId ? { member_id: memberId } : {}),
    }
  );
}

export async function cancelClassBooking(
  id: string,
  bookingId?: string
): Promise<{ message: string; booking: ClassBooking }> {
  return apiFetch<{ message: string; booking: ClassBooking }>(
    `/api/gym/classes/${id}/cancel-booking/`,
    {
      method: "POST",
      body: JSON.stringify(bookingId ? { booking_id: bookingId } : {}),
    }
  );
}

export async function markClassAttendance(
  id: string,
  payload: MarkAttendancePayload
): Promise<{ message: string; booking: ClassBooking }> {
  return apiFetch<{ message: string; booking: ClassBooking }>(
    `/api/gym/classes/${id}/attendance/`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function getMyBookings(): Promise<ClassBooking[]> {
  const res = await apiFetch<ClassBookingListResponse>(
    "/api/gym/classes/my-bookings/"
  );
  return res.bookings || [];
}

export async function getTrainerSessions(): Promise<ClassSession[]> {
  const res = await apiFetch<ClassSessionListResponse>(
    "/api/gym/classes/trainer-sessions/"
  );
  return res.sessions || [];
}
