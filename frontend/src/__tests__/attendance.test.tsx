import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as attendanceApi from "../api/attendance";
import { MemberQrCard } from "../components/attendance/MemberQrCard";
import { AttendanceScannerSection } from "../components/attendance/AttendanceScannerSection";
import { AttendanceLogCard } from "../components/attendance/AttendanceLogCard";

vi.mock("../api/attendance", () => ({
  getMemberQrToken: vi.fn(),
  scanQrToken: vi.fn(),
  manualAttendanceOverride: vi.fn(),
  getAttendanceLog: vi.fn(),
  getAttendancePublicKey: vi.fn(),
}));

describe("Sprint 8: QR Check-in & Attendance Components", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("MemberQrCard", () => {
    it("renders QR pass, status badge, and countdown timer", async () => {
      const expiresAt = new Date(Date.now() + 85 * 1000).toISOString();
      vi.mocked(attendanceApi.getMemberQrToken).mockResolvedValue({
        token: "mock-rs256-jwt-token-string",
        expires_at: expiresAt,
        valid_seconds: 90,
        member_id: "3cd1c4f9-704d-4d1e-af75-76e8fa2ba5de",
      });

      render(<MemberQrCard memberStatus="active" />);

      expect(await screen.findByText("Check-in QR Pass")).toBeInTheDocument();
      expect(screen.getByText("ACTIVE")).toBeInTheDocument();
      expect(await screen.findByText("Refresh")).toBeInTheDocument();
      expect(await screen.findByText("Copy code")).toBeInTheDocument();

      await waitFor(() => {
        expect(
          screen.getByAltText("Personal Member Check-in QR Code")
        ).toBeInTheDocument();
      });
    });

    it("copies token to clipboard when Copy code button is clicked", async () => {
      const user = userEvent.setup();
      const expiresAt = new Date(Date.now() + 85 * 1000).toISOString();
      vi.mocked(attendanceApi.getMemberQrToken).mockResolvedValue({
        token: "mock-rs256-jwt-token-string",
        expires_at: expiresAt,
        valid_seconds: 90,
        member_id: "3cd1c4f9-704d-4d1e-af75-76e8fa2ba5de",
      });

      const writeTextMock = vi.fn().mockResolvedValue(undefined);
      Object.defineProperty(navigator, "clipboard", {
        value: {
          writeText: writeTextMock,
        },
        configurable: true,
      });

      render(<MemberQrCard memberStatus="active" />);

      const copyBtn = await screen.findByRole("button", { name: /copy code/i });
      expect(copyBtn).toBeInTheDocument();
      await user.click(copyBtn);

      expect(writeTextMock).toHaveBeenCalledWith("mock-rs256-jwt-token-string");
      expect(await screen.findByText("Copied!")).toBeInTheDocument();
    });

    it("displays error state when token generation is rejected", async () => {
      vi.mocked(attendanceApi.getMemberQrToken).mockRejectedValue({
        data: {
          detail: "Member subscription is expired.",
          reason: "expired",
        },
      });

      render(<MemberQrCard memberStatus="expired" />);

      expect(
        await screen.findByText("Pass Unavailable (expired)")
      ).toBeInTheDocument();
      expect(
        screen.getByText("Member subscription is expired.")
      ).toBeInTheDocument();
      expect(screen.getByText("Try Again")).toBeInTheDocument();
    });
  });

  describe("AttendanceScannerSection", () => {
    it("scans valid token, displays member details, photo, and check-in result", async () => {
      const user = userEvent.setup();
      vi.mocked(attendanceApi.scanQrToken).mockResolvedValue({
        status: "success",
        message: "Welcome, Abebe Bikila!",
        member: {
          id: "3cd1c4f9-704d-4d1e-af75-76e8fa2ba5de",
          full_name: "Abebe Bikila",
          photo_url: "https://example.com/photos/abebe.webp",
          status: "active",
        },
        attendance: {
          id: "att-12345",
          date: "2026-10-15",
          checked_in_at: "2026-10-15T08:30:00Z",
          is_override: false,
        },
        next_token: "mock-next-token-jwt",
      });

      render(<AttendanceScannerSection userRole="reception" />);

      const input = screen.getByPlaceholderText(
        "Scan QR token or paste token JWT..."
      );
      await user.type(input, "valid-token-jwt-string");

      const submitBtn = screen.getByRole("button", {
        name: /verify & check in/i,
      });
      await user.click(submitBtn);

      expect(await screen.findByText("Abebe Bikila")).toBeInTheDocument();
      expect(screen.getByText("ACTIVE")).toBeInTheDocument();
      expect(screen.getByText("2026-10-15")).toBeInTheDocument();
      expect(screen.getByAltText("Abebe Bikila")).toBeInTheDocument();
    });

    it("displays duplicate check-in warning and informs that staff were notified", async () => {
      const user = userEvent.setup();
      vi.mocked(attendanceApi.scanQrToken).mockRejectedValue({
        data: {
          detail: "Member Abebe Bikila has already checked in today.",
          reason: "already_checked_in",
          member: {
            full_name: "Abebe Bikila",
            status: "active",
          },
        },
      });

      render(<AttendanceScannerSection userRole="reception" />);

      const input = screen.getByPlaceholderText(
        "Scan QR token or paste token JWT..."
      );
      await user.type(input, "already-checked-in-jwt");
      await user.click(
        screen.getByRole("button", { name: /verify & check in/i })
      );

      expect(
        await screen.findByText("Check-in Rejected (already_checked_in)")
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          "Duplicate check-in detected today. Staff have been notified."
        )
      ).toBeInTheDocument();
    });

    it("displays distinguishable reason when subscription is expired", async () => {
      const user = userEvent.setup();
      vi.mocked(attendanceApi.scanQrToken).mockRejectedValue({
        data: {
          detail: "Member subscription has expired.",
          reason: "expired",
          member: {
            full_name: "Chala Tafa",
            status: "expired",
          },
        },
      });

      render(<AttendanceScannerSection userRole="reception" />);

      const input = screen.getByPlaceholderText(
        "Scan QR token or paste token JWT..."
      );
      await user.type(input, "expired-member-jwt");
      await user.click(
        screen.getByRole("button", { name: /verify & check in/i })
      );

      expect(
        await screen.findByText("Check-in Rejected (expired)")
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          "Membership expired. Member must renew plan before check-in."
        )
      ).toBeInTheDocument();
    });

    it("executes manual override modal flow with required reason", async () => {
      const user = userEvent.setup();
      vi.mocked(attendanceApi.manualAttendanceOverride).mockResolvedValue({
        status: "success",
        message: "Manual check-in recorded for Abebe Bikila.",
        member: {
          id: "3cd1c4f9-704d-4d1e-af75-76e8fa2ba5de",
          full_name: "Abebe Bikila",
          status: "active",
        },
        attendance: {
          id: "att-manual-1",
          date: "2026-10-15",
          checked_in_at: "2026-10-15T09:00:00Z",
          is_override: true,
          override_reason: "Member phone battery died at gate",
        },
      });

      render(<AttendanceScannerSection userRole="reception" />);

      // Open override modal
      const overrideBtn = screen.getByRole("button", {
        name: /manual override/i,
      });
      await user.click(overrideBtn);

      expect(
        screen.getByText("Manual Attendance Override")
      ).toBeInTheDocument();

      // Enter member ID and reason
      const memberInput = screen.getByPlaceholderText(
        "e.g. 3cd1c4f9-704d-4d1e-af75-76e8fa2ba5de"
      );
      const reasonInput = screen.getByPlaceholderText(
        "Explain why manual override was needed (e.g. phone died, camera broken)..."
      );

      await user.type(memberInput, "3cd1c4f9-704d-4d1e-af75-76e8fa2ba5de");
      await user.type(reasonInput, "Member phone battery died at gate");

      const confirmBtn = screen.getByRole("button", {
        name: /confirm override/i,
      });
      await user.click(confirmBtn);

      await waitFor(() => {
        expect(attendanceApi.manualAttendanceOverride).toHaveBeenCalledWith({
          member_id: "3cd1c4f9-704d-4d1e-af75-76e8fa2ba5de",
          reason: "Member phone battery died at gate",
        });
      });

      expect(await screen.findByText("OVERRIDE")).toBeInTheDocument();
      expect(
        screen.getByText("Reason: Member phone battery died at gate")
      ).toBeInTheDocument();
    });
  });

  describe("AttendanceLogCard", () => {
    it("renders calendar items with present (✓), absent (✗), and blank symbols", async () => {
      vi.mocked(attendanceApi.getAttendanceLog).mockResolvedValue({
        member_id: "3cd1c4f9-704d-4d1e-af75-76e8fa2ba5de",
        member_name: "Abebe Bikila",
        start_date: "2026-10-12",
        end_date: "2026-10-14",
        subscription_period: {
          start_date: "2026-10-13",
          end_date: "2026-10-25",
        },
        days: [
          {
            date: "2026-10-12",
            status: "blank",
            symbol: "",
            attended: false,
          },
          {
            date: "2026-10-13",
            status: "absent",
            symbol: "✗",
            attended: false,
          },
          {
            date: "2026-10-14",
            status: "present",
            symbol: "✓",
            attended: true,
            checked_in_at: "2026-10-14T10:00:00Z",
            is_override: false,
          },
        ],
      });

      render(
        <AttendanceLogCard memberId="3cd1c4f9-704d-4d1e-af75-76e8fa2ba5de" />
      );

      expect(await screen.findByText("Check-ins:")).toBeInTheDocument();
      expect(screen.getByText("1")).toBeInTheDocument(); // 1 check-in
      expect(screen.getByText("2")).toBeInTheDocument(); // 2 active days (13 and 14)

      // Symbols
      expect(screen.getByText("blank")).toBeInTheDocument();
      expect(screen.getByText("✗")).toBeInTheDocument();
      expect(screen.getByText("✓")).toBeInTheDocument();
    });
  });
});
