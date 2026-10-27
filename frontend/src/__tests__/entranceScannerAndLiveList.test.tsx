import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as attendanceApi from "../api/attendance";
import * as gymsApi from "../api/gyms";
import { TodayCheckinsList } from "../components/attendance/TodayCheckinsList";
import { EntranceScannerScreen } from "../screens/EntranceScannerScreen";

vi.mock("../api/attendance", () => ({
  scanQrToken: vi.fn(),
  getTodayCheckins: vi.fn(),
}));

vi.mock("../api/gyms", () => ({
  getPublicGymEntry: vi.fn(),
}));

describe("Sprint 8c: Entrance Scanner & Today's Check-ins List", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("TodayCheckinsList (Reception / Staff Dashboard)", () => {
    it("renders today's count badge and check-in items with photo, name, time, and badge", async () => {
      vi.mocked(attendanceApi.getTodayCheckins).mockResolvedValue({
        total_count: 2,
        results: [
          {
            id: "att-1",
            member_id: "mem-1",
            member_name: "Dawit Bekele",
            member_photo_url: "https://example.com/photos/dawit.webp",
            checked_in_at: "2026-10-17T09:15:00Z",
            is_override: false,
            override_reason: "",
            recorded_by_name: null,
          },
          {
            id: "att-2",
            member_id: "mem-2",
            member_name: "Sara Haile",
            member_photo_url: null,
            checked_in_at: "2026-10-17T08:30:00Z",
            is_override: true,
            override_reason: "Card reader battery dead",
            recorded_by_name: "Reception Staff",
          },
        ],
      });

      render(<TodayCheckinsList />);

      expect(await screen.findByText("Today's Check-ins")).toBeInTheDocument();
      expect(await screen.findByText("2 check-ins")).toBeInTheDocument();

      // Check member Dawit (QR scan)
      expect(screen.getByText("Dawit Bekele")).toBeInTheDocument();
      expect(screen.getByText("QR Scan")).toBeInTheDocument();
      expect(await screen.findByAltText("Dawit Bekele")).toBeInTheDocument();

      // Check member Sara (Manual Override with reason)
      expect(screen.getByText("Sara Haile")).toBeInTheDocument();
      expect(screen.getByText("Manual Override")).toBeInTheDocument();
      expect(
        screen.getByText("Reason: Card reader battery dead")
      ).toBeInTheDocument();
      expect(screen.getByText("S")).toBeInTheDocument(); // initial avatar
    });

    it("displays friendly empty state when no check-ins have occurred today", async () => {
      vi.mocked(attendanceApi.getTodayCheckins).mockResolvedValue({
        total_count: 0,
        results: [],
      });

      render(<TodayCheckinsList />);

      expect(
        await screen.findByText("No check-ins recorded yet today")
      ).toBeInTheDocument();
      expect(screen.getByText("0 check-ins")).toBeInTheDocument();
    });
  });

  describe("EntranceScannerScreen (Tablet at Entrance Door)", () => {
    it("renders gym name, logo, instruction line, and camera preview", async () => {
      vi.mocked(gymsApi.getPublicGymEntry).mockResolvedValue({
        still_securing: false,
        name: "Bole Elite Fitness",
        logo: "https://example.com/logo.webp",
      } as unknown as gymsApi.GymPublicEntryResponse);

      render(
        <MemoryRouter>
          <EntranceScannerScreen />
        </MemoryRouter>
      );

      expect(await screen.findByText("Bole Elite Fitness")).toBeInTheDocument();
      expect(
        screen.getByText("Hold your QR code up to the camera")
      ).toBeInTheDocument();
      expect(
        screen.getByAltText("Bole Elite Fitness Logo")
      ).toBeInTheDocument();
      expect(
        screen.getByRole("region", { name: "Camera QR Scanner" })
      ).toBeInTheDocument();
    });

    it("displays large green screen on successful check-in with name, photo, and time (no phone/email)", async () => {
      const user = userEvent.setup();
      vi.mocked(gymsApi.getPublicGymEntry).mockResolvedValue({
        still_securing: false,
        name: "Bole Elite Fitness",
      } as unknown as gymsApi.GymPublicEntryResponse);

      vi.mocked(attendanceApi.scanQrToken).mockResolvedValue({
        status: "success",
        message: "Welcome, Dawit Bekele!",
        member: {
          id: "mem-dawit",
          full_name: "Dawit Bekele",
          photo_url: "https://example.com/photos/dawit.webp",
          status: "active",
          phone: "+251911002233", // Backend returns phone, but entrance screen must NOT show it
        },
        attendance: {
          id: "att-333",
          date: "2026-10-17",
          checked_in_at: "2026-10-17T09:45:00Z",
          is_override: false,
        },
        next_token: "next-token-jwt",
      });

      render(
        <MemoryRouter>
          <EntranceScannerScreen />
        </MemoryRouter>
      );

      // Open manual entry modal to simulate scan token input
      const enterCodeLink = await screen.findByText("Enter code manually");
      await user.click(enterCodeLink);

      const input = screen.getByPlaceholderText("Paste member token...");
      await user.type(input, "valid-dawit-qr-jwt");
      await user.click(
        screen.getByRole("button", { name: /verify & check in/i })
      );

      // Verify large green success screen appears
      expect(
        await screen.findByRole("dialog", { name: "Check-in Successful" })
      ).toBeInTheDocument();
      expect(screen.getByText("Welcome, Dawit Bekele!")).toBeInTheDocument();
      expect(screen.getByText("Check-in Confirmed")).toBeInTheDocument();
      expect(screen.getByAltText("Dawit Bekele")).toBeInTheDocument();

      // Criterion 5: Screen NEVER shows phone number, email, or any other personal data
      expect(screen.queryByText("+251911002233")).not.toBeInTheDocument();
      expect(screen.queryByText(/@/)).not.toBeInTheDocument();
    });

    it("displays amber refusal screen for already_checked_in with clear plain words and icon", async () => {
      const user = userEvent.setup();
      vi.mocked(gymsApi.getPublicGymEntry).mockResolvedValue({
        still_securing: false,
        name: "Bole Elite Fitness",
      } as unknown as gymsApi.GymPublicEntryResponse);

      vi.mocked(attendanceApi.scanQrToken).mockRejectedValue({
        data: {
          detail: "Member Dawit Bekele has already checked in today.",
          reason: "already_checked_in",
          member: {
            id: "mem-dawit",
            full_name: "Dawit Bekele",
            status: "active",
            phone: "+251911002233",
          },
        },
      });

      render(
        <MemoryRouter>
          <EntranceScannerScreen />
        </MemoryRouter>
      );

      const enterCodeLink = await screen.findByText("Enter code manually");
      await user.click(enterCodeLink);

      const input = screen.getByPlaceholderText("Paste member token...");
      await user.type(input, "already-scanned-jwt");
      await user.click(
        screen.getByRole("button", { name: /verify & check in/i })
      );

      // Verify large amber screen with explanation
      expect(
        await screen.findByRole("dialog", { name: "Check-in Refused" })
      ).toBeInTheDocument();
      expect(screen.getByText("Already Checked In Today")).toBeInTheDocument();
      expect(
        screen.getByText(
          "You have already checked in today. Please speak with reception if you need assistance."
        )
      ).toBeInTheDocument();
      expect(screen.getByText("Dawit Bekele")).toBeInTheDocument();

      // No phone number shown
      expect(screen.queryByText("+251911002233")).not.toBeInTheDocument();
    });

    it("displays red refusal screen for expired membership with plain explanation", async () => {
      const user = userEvent.setup();
      vi.mocked(gymsApi.getPublicGymEntry).mockResolvedValue({
        still_securing: false,
        name: "Bole Elite Fitness",
      } as unknown as gymsApi.GymPublicEntryResponse);

      vi.mocked(attendanceApi.scanQrToken).mockRejectedValue({
        data: {
          detail: "Member subscription is expired.",
          reason: "expired",
          member: {
            id: "mem-chala",
            full_name: "Chala Tafa",
            status: "expired",
          },
        },
      });

      render(
        <MemoryRouter>
          <EntranceScannerScreen />
        </MemoryRouter>
      );

      const enterCodeLink = await screen.findByText("Enter code manually");
      await user.click(enterCodeLink);

      const input = screen.getByPlaceholderText("Paste member token...");
      await user.type(input, "expired-plan-jwt");
      await user.click(
        screen.getByRole("button", { name: /verify & check in/i })
      );

      expect(
        await screen.findByRole("dialog", { name: "Check-in Refused" })
      ).toBeInTheDocument();
      expect(screen.getByText("Membership Expired")).toBeInTheDocument();
      expect(
        screen.getByText(
          "Your membership plan has expired. Please visit reception or renew online."
        )
      ).toBeInTheDocument();
    });
  });
});
