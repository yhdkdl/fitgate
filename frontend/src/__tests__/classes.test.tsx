import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ClassScheduleSection } from "../components/classes/ClassScheduleSection";
import * as classesApi from "../api/classes";
import * as trainersApi from "../api/trainers";
import * as membersApi from "../api/members";
import type { ClassSession, ClassBooking, ClassRosterResponse } from "../types/classes";

const mockClasses: ClassSession[] = [
  {
    id: "session-1",
    title: "yoga",
    display_title: "Yoga",
    other_title: "",
    trainer: "trainer-1",
    trainer_name: "Dawit Trainer",
    trainer_photo_url: "",
    start_time: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(), // tomorrow
    duration_minutes: 60,
    end_time: new Date(Date.now() + 25 * 60 * 60 * 1000).toISOString(),
    capacity: 20,
    status: "scheduled",
    booked_count: 5,
    spots_remaining: 15,
    is_full: false,
    is_past: false,
    user_booking: null,
  },
  {
    id: "session-2",
    title: "spinning",
    display_title: "Spinning",
    other_title: "",
    trainer: "trainer-1",
    trainer_name: "Dawit Trainer",
    trainer_photo_url: "",
    start_time: new Date(Date.now() + 1 * 60 * 60 * 1000).toISOString(), // 1 hour from now (< 2h)
    duration_minutes: 45,
    end_time: new Date(Date.now() + 1.75 * 60 * 60 * 1000).toISOString(),
    capacity: 10,
    status: "scheduled",
    booked_count: 10,
    spots_remaining: 0,
    is_full: true,
    is_past: false,
    user_booking: {
      id: "booking-2",
      status: "booked",
      attended: false,
      created_at: new Date().toISOString(),
    },
  },
];

const mockBookings: ClassBooking[] = [
  {
    id: "booking-1",
    session: "session-1",
    session_title: "Yoga",
    session_start_time: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(), // > 2h
    session_end_time: new Date(Date.now() + 25 * 60 * 60 * 1000).toISOString(),
    session_duration_minutes: 60,
    session_status: "scheduled",
    trainer_name: "Dawit Trainer",
    member: {
      id: "member-1",
      full_name: "Abebe Bikila",
      phone: "+251911223344",
      email: "abebe@example.com",
      photo_url: "",
      status: "active",
    },
    status: "booked",
    attended: false,
    marked_at: null,
    created_at: new Date().toISOString(),
  },
  {
    id: "booking-2",
    session: "session-2",
    session_title: "Spinning",
    session_start_time: new Date(Date.now() + 1 * 60 * 60 * 1000).toISOString(), // < 2h
    session_end_time: new Date(Date.now() + 1.75 * 60 * 60 * 1000).toISOString(),
    session_duration_minutes: 45,
    session_status: "scheduled",
    trainer_name: "Dawit Trainer",
    member: {
      id: "member-1",
      full_name: "Abebe Bikila",
      phone: "+251911223344",
      email: "abebe@example.com",
      photo_url: "",
      status: "active",
    },
    status: "booked",
    attended: false,
    marked_at: null,
    created_at: new Date().toISOString(),
  },
];

const mockRoster: ClassRosterResponse = {
  session: mockClasses[0],
  bookings: [mockBookings[0]],
};

describe("ClassScheduleSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(classesApi, "listClasses").mockResolvedValue(mockClasses);
    vi.spyOn(classesApi, "getMyBookings").mockResolvedValue(mockBookings);
    vi.spyOn(classesApi, "getClassRoster").mockResolvedValue(mockRoster);
    vi.spyOn(classesApi, "bookClass").mockResolvedValue({
      message: "Session booked successfully!",
      booking: mockBookings[0],
    });
    vi.spyOn(classesApi, "cancelClassBooking").mockResolvedValue({
      message: "Booking cancelled successfully.",
      booking: mockBookings[0],
    });
    vi.spyOn(classesApi, "markClassAttendance").mockResolvedValue({
      message: "Attendance marked successfully.",
      booking: { ...mockBookings[0], attended: true },
    });
    vi.spyOn(trainersApi, "listTrainers").mockResolvedValue([
      {
        id: "trainer-1",
        photo_url: "",
        max_clients: 20,
        client_count: 5,
        created_at: "",
        updated_at: "",
        user: {
          id: "user-t1",
          email: "dawit@example.com",
          full_name: "Dawit Trainer",
          phone: "+251911000000",
          is_active: true,
        },
      },
    ]);
  });

  it("renders class sessions and schedule button for Owner/Manager", async () => {
    render(<ClassScheduleSection userRole="owner" />);

    await waitFor(() => {
      expect(screen.getByText("Group Classes")).toBeInTheDocument();
      expect(screen.getByTestId("btn-schedule-class")).toBeInTheDocument();
      expect(screen.getByText("Yoga")).toBeInTheDocument();
      expect(screen.getByText("Spinning")).toBeInTheDocument();
    });

    expect(screen.getByTestId("btn-roster-session-1")).toBeInTheDocument();
    expect(screen.getByTestId("btn-edit-session-1")).toBeInTheDocument();
    expect(screen.getByTestId("btn-cancel-session-1")).toBeInTheDocument();
  });

  it("allows a member to view schedule and book an available class", async () => {
    render(<ClassScheduleSection userRole="member" />);

    await waitFor(() => {
      expect(screen.getByText("Yoga")).toBeInTheDocument();
    });

    const bookBtn = screen.getByTestId("btn-member-book-session-1");
    expect(bookBtn).toBeInTheDocument();
    fireEvent.click(bookBtn);

    await waitFor(() => {
      expect(classesApi.bookClass).toHaveBeenCalledWith("session-1");
    });
  });

  it("enforces the 2-hour cancellation rule on My Bookings tab", async () => {
    render(<ClassScheduleSection userRole="member" />);

    await waitFor(() => {
      expect(screen.getByTestId("tab-my-bookings")).toBeInTheDocument();
    });

    // Switch to My Bookings tab
    fireEvent.click(screen.getByTestId("tab-my-bookings"));

    await waitFor(() => {
      expect(classesApi.getMyBookings).toHaveBeenCalled();
    });

    // Booking 1 is tomorrow (> 2h) -> cancel button enabled
    const cancelBtn1 = screen.getByTestId("btn-cancel-booking-tab-booking-1");
    expect(cancelBtn1).not.toBeDisabled();

    // Booking 2 is in 1 hour (< 2h) -> cancel button disabled
    const cancelBtn2 = screen.getByTestId("btn-cancel-booking-tab-booking-2");
    expect(cancelBtn2).toBeDisabled();
    expect(
      screen.getByText("Bookings can only be cancelled up to 2 hours before the class begins.")
    ).toBeInTheDocument();
  });

  it("opens class roster and allows staff/trainer to toggle attendance", async () => {
    render(<ClassScheduleSection userRole="owner" />);

    await waitFor(() => {
      expect(screen.getByTestId("btn-roster-session-1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("btn-roster-session-1"));

    await waitFor(() => {
      expect(classesApi.getClassRoster).toHaveBeenCalledWith("session-1");
      expect(screen.getByText("Abebe Bikila")).toBeInTheDocument();
    });

    // Attendance toggle checkbox is present
    const checkbox = screen.getByTestId("checkbox-attendance-booking-1");
    expect(checkbox).toBeInTheDocument();
  });

  it("supports receptionist booking on behalf of a member", async () => {
    vi.spyOn(membersApi, "listGymMembers").mockResolvedValue([
      {
        id: "member-abc",
        email: "kebede@example.com",
        full_name: "Kebede Michael",
        phone: "+251911999888",
        status: "active",
        joined_at: "",
        waiver_accepted_at: "",
        photo_url: "",
      },
    ]);

    render(<ClassScheduleSection userRole="reception" />);

    await waitFor(() => {
      expect(screen.getByTestId("btn-reception-book-session-1")).toBeInTheDocument();
    });

    // Open booking modal
    fireEvent.click(screen.getByTestId("btn-reception-book-session-1"));

    await waitFor(() => {
      expect(screen.getByTestId("input-search-member-for-class")).toBeInTheDocument();
    });

    // Type member name
    fireEvent.change(screen.getByTestId("input-search-member-for-class"), {
      target: { value: "Kebede" },
    });

    await waitFor(() => {
      expect(screen.getByTestId("member-search-row-member-abc")).toBeInTheDocument();
    });

    // Select member and confirm booking
    fireEvent.click(screen.getByTestId("member-search-row-member-abc"));
    fireEvent.click(screen.getByTestId("btn-confirm-staff-booking"));

    await waitFor(() => {
      expect(classesApi.bookClass).toHaveBeenCalledWith("session-1", "member-abc");
    });
  });
});
