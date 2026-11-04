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
  const res = await apiFetch<ClassSession[] | ClassSessionListResponse>(
    `/api/gym/classes/${qs ? `?${qs}` : ""}`
  );
  if (Array.isArray(res)) {
    return res;
  }
  if (res && Array.isArray(res.sessions)) {
    return res.sessions;
  }
  return [];
}

export async function createClasses(
  payload: ClassSessionCreatePayload
): Promise<{ message: string; sessions: ClassSession[] }> {
  const res = await apiFetch<
    ClassSession[] | { message?: string; sessions?: ClassSession[] }
  >("/api/gym/classes/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (Array.isArray(res)) {
    return {
      message: `Successfully scheduled ${res.length} class session(s).`,
      sessions: res,
    };
  }
  return {
    message: res.message || "Class session(s) scheduled.",
    sessions: res.sessions || [],
  };
}

export async function updateClass(
  id: string,
  payload: ClassSessionUpdatePayload
): Promise<{ message: string; session: ClassSession }> {
  const res = await apiFetch<
    ClassSession | { message?: string; session?: ClassSession }
  >(`/api/gym/classes/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  if (res && "id" in res) {
    return {
      message: "Class session updated successfully.",
      session: res as ClassSession,
    };
  }
  return {
    message: (res as { message?: string }).message || "Class session updated.",
    session: (res as { session: ClassSession }).session,
  };
}

export async function cancelClass(
  id: string
): Promise<{ message: string; session: ClassSession }> {
  const res = await apiFetch<
    ClassSession | { message?: string; session?: ClassSession }
  >(`/api/gym/classes/${id}/cancel/`, {
    method: "POST",
  });
  if (res && "id" in res) {
    return {
      message: "Class session cancelled successfully.",
      session: res as ClassSession,
    };
  }
  return {
    message:
      (res as { message?: string }).message || "Class session cancelled.",
    session: (res as { session: ClassSession }).session,
  };
}

export async function getClassRoster(id: string): Promise<ClassRosterResponse> {
  return apiFetch<ClassRosterResponse>(`/api/gym/classes/${id}/roster/`);
}

export async function bookClass(
  id: string,
  memberId?: string
): Promise<{ message: string; booking: ClassBooking }> {
  const res = await apiFetch<
    ClassBooking | { message?: string; booking?: ClassBooking }
  >(`/api/gym/classes/${id}/book/`, {
    method: "POST",
    body: JSON.stringify(memberId ? { member_id: memberId } : {}),
  });
  if (res && "id" in res) {
    return {
      message: "Session booked successfully!",
      booking: res as ClassBooking,
    };
  }
  return {
    message:
      (res as { message?: string }).message || "Session booked successfully!",
    booking: (res as { booking: ClassBooking }).booking,
  };
}

export async function cancelClassBooking(
  id: string,
  bookingId?: string
): Promise<{ message: string; booking: ClassBooking }> {
  const res = await apiFetch<
    ClassBooking | { message?: string; booking?: ClassBooking }
  >(`/api/gym/classes/${id}/cancel-booking/`, {
    method: "POST",
    body: JSON.stringify(bookingId ? { booking_id: bookingId } : {}),
  });
  if (res && "id" in res) {
    return {
      message: "Booking cancelled successfully.",
      booking: res as ClassBooking,
    };
  }
  return {
    message:
      (res as { message?: string }).message || "Booking cancelled successfully.",
    booking: (res as { booking: ClassBooking }).booking,
  };
}

export async function markClassAttendance(
  id: string,
  payload: MarkAttendancePayload
): Promise<{ message: string; booking: ClassBooking }> {
  const res = await apiFetch<
    ClassBooking | { message?: string; booking?: ClassBooking }
  >(`/api/gym/classes/${id}/attendance/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (res && "id" in res) {
    return {
      message: "Attendance marked successfully.",
      booking: res as ClassBooking,
    };
  }
  return {
    message:
      (res as { message?: string }).message ||
      "Attendance marked successfully.",
    booking: (res as { booking: ClassBooking }).booking,
  };
}

export async function getMyBookings(): Promise<ClassBooking[]> {
  const res = await apiFetch<ClassBooking[] | ClassBookingListResponse>(
    "/api/gym/classes/my-bookings/"
  );
  if (Array.isArray(res)) {
    return res;
  }
  if (res && Array.isArray(res.bookings)) {
    return res.bookings;
  }
  return [];
}

export async function getTrainerSessions(): Promise<ClassSession[]> {
  const res = await apiFetch<
    | ClassSession[]
    | { sessions?: ClassSession[]; upcoming?: ClassSession[]; past?: ClassSession[] }
  >("/api/gym/classes/trainer-sessions/");
  if (Array.isArray(res)) {
    return res;
  }
  if (res && "sessions" in res && Array.isArray(res.sessions)) {
    return res.sessions;
  }
  if (res && ("upcoming" in res || "past" in res)) {
    const obj = res as { upcoming?: ClassSession[]; past?: ClassSession[] };
    return [...(obj.upcoming || []), ...(obj.past || [])];
  }
  return [];
}
