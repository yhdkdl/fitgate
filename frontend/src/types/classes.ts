export type ClassTitle =
  | "yoga"
  | "zumba"
  | "spinning"
  | "boxing"
  | "aerobics"
  | "crossfit"
  | "strength_circuit"
  | "stretching_mobility"
  | "other";

export const CLASS_TITLE_OPTIONS: Array<{ value: ClassTitle; label: string }> =
  [
    { value: "yoga", label: "Yoga" },
    { value: "zumba", label: "Zumba" },
    { value: "spinning", label: "Spinning" },
    { value: "boxing", label: "Boxing" },
    { value: "aerobics", label: "Aerobics" },
    { value: "crossfit", label: "CrossFit" },
    { value: "strength_circuit", label: "Strength Circuit" },
    { value: "stretching_mobility", label: "Stretching & Mobility" },
    { value: "other", label: "Other" },
  ];

export const CLASS_DURATION_OPTIONS: Array<{ value: number; label: string }> = [
  { value: 30, label: "30 minutes" },
  { value: 45, label: "45 minutes" },
  { value: 60, label: "60 minutes" },
  { value: 90, label: "90 minutes" },
];

export interface ClassSession {
  id: string;
  title: ClassTitle;
  display_title: string;
  other_title: string;
  trainer: string;
  trainer_name: string;
  trainer_photo_url: string;
  start_time: string;
  duration_minutes: number;
  end_time: string;
  capacity: number;
  status: "scheduled" | "cancelled";
  booked_count: number;
  spots_remaining: number;
  is_full: boolean;
  is_past: boolean;
  user_booking: {
    id: string;
    status: string;
    attended: boolean;
    created_at: string;
  } | null;
}

export interface ClassRosterMember {
  id: string;
  full_name: string;
  phone: string;
  email: string;
  photo_url: string;
  status: string;
}

export interface ClassBooking {
  id: string;
  session: string;
  session_title: string;
  session_start_time: string;
  session_end_time: string;
  session_duration_minutes: number;
  session_status: string;
  trainer_name: string;
  member: ClassRosterMember;
  status: "booked" | "cancelled";
  attended: boolean;
  marked_at: string | null;
  created_at: string;
}

export interface ClassRosterResponse {
  session: ClassSession;
  bookings: ClassBooking[];
}

export interface ClassSessionCreatePayload {
  title: ClassTitle;
  other_title?: string;
  trainer_id: string;
  start_time: string; // ISO datetime
  duration_minutes: number;
  capacity: number;
  repeat_weeks?: number;
}

export interface ClassSessionUpdatePayload {
  title?: ClassTitle;
  other_title?: string;
  trainer_id?: string;
  start_time?: string;
  duration_minutes?: number;
  capacity?: number;
}

export interface MarkAttendancePayload {
  member_id: string;
  attended: boolean;
}
