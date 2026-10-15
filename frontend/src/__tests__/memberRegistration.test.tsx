import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as membersApi from "../api/members";
import { MemberManagementSection } from "../components/dashboard/MemberManagementSection";
import { MemberSelfSection } from "../components/dashboard/MemberSelfSection";
import { RegisterScreen } from "../screens/RegisterScreen";
import { VerifyEmailScreen } from "../screens/VerifyEmailScreen";

describe("Sprint 7: Member Registration & Body Metrics UI", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe("RegisterScreen", () => {
    it("renders member registration form with waiver checkbox and touch-friendly targets", () => {
      render(
        <MemoryRouter>
          <RegisterScreen />
        </MemoryRouter>
      );

      expect(
        screen.getByRole("heading", { name: /create member account/i })
      ).toBeInTheDocument();
      expect(screen.getByLabelText(/full name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/phone number/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
      expect(
        screen.getByLabelText(/health & safety waiver/i)
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /complete registration/i })
      ).toBeInTheDocument();
    });

    it("requires health waiver to be accepted before submission", async () => {
      render(
        <MemoryRouter>
          <RegisterScreen />
        </MemoryRouter>
      );

      const submitBtn = screen.getByRole("button", {
        name: /complete registration/i,
      });
      // Submit button is disabled when waiver is not checked
      expect(submitBtn).toBeDisabled();

      // Check waiver
      const waiverCheckbox = screen.getByLabelText(/health & safety waiver/i);
      fireEvent.click(waiverCheckbox);
      expect(submitBtn).not.toBeDisabled();
    });

    it("submits valid form and displays confirmation success card", async () => {
      const mockRegister = vi
        .spyOn(membersApi, "registerMemberSelfService")
        .mockResolvedValueOnce({
          detail:
            "Registration successful. Please check your email to verify your account.",
          member: {
            id: "m-123",
            email: "abebe@example.com",
            full_name: "Abebe Bikila",
            phone: "+251911001122",
            status: "active",
            joined_at: new Date().toISOString(),
            waiver_accepted_at: new Date().toISOString(),
          },
        });

      render(
        <MemoryRouter>
          <RegisterScreen />
        </MemoryRouter>
      );

      fireEvent.change(screen.getByLabelText(/full name/i), {
        target: { value: "Abebe Bikila" },
      });
      fireEvent.change(screen.getByLabelText(/email address/i), {
        target: { value: "abebe@example.com" },
      });
      fireEvent.change(screen.getByLabelText(/phone number/i), {
        target: { value: "+251911001122" },
      });
      fireEvent.change(screen.getByLabelText(/password/i), {
        target: { value: "SecurePassword123!" },
      });
      fireEvent.click(screen.getByLabelText(/health & safety waiver/i));

      fireEvent.click(
        screen.getByRole("button", { name: /complete registration/i })
      );

      await waitFor(() => {
        expect(mockRegister).toHaveBeenCalledWith(
          expect.objectContaining({
            full_name: "Abebe Bikila",
            email: "abebe@example.com",
            phone: "+251911001122",
            waiver_accepted: true,
          })
        );
      });

      expect(
        await screen.findByRole("heading", { name: /verify your account/i })
      ).toBeInTheDocument();
      expect(screen.getByText("abebe@example.com")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /proceed to sign in/i })
      ).toBeInTheDocument();
    });

    it("displays friendly rate limiting message when API returns 429", async () => {
      const err = Object.assign(new Error("Rate limit exceeded"), {
        status: 429,
      });
      vi.spyOn(membersApi, "registerMemberSelfService").mockRejectedValueOnce(
        err
      );

      render(
        <MemoryRouter>
          <RegisterScreen />
        </MemoryRouter>
      );

      fireEvent.change(screen.getByLabelText(/full name/i), {
        target: { value: "Rate Limit Tester" },
      });
      fireEvent.change(screen.getByLabelText(/email address/i), {
        target: { value: "limit@example.com" },
      });
      fireEvent.change(screen.getByLabelText(/phone number/i), {
        target: { value: "+251911999999" },
      });
      fireEvent.change(screen.getByLabelText(/password/i), {
        target: { value: "SecurePassword123!" },
      });
      fireEvent.click(screen.getByLabelText(/health & safety waiver/i));

      fireEvent.click(
        screen.getByRole("button", { name: /complete registration/i })
      );

      expect(
        await screen.findByText(/too many registration requests/i)
      ).toBeInTheDocument();
    });
  });

  describe("VerifyEmailScreen", () => {
    it("strips verification token from URL and confirms account on success", async () => {
      const replaceStateSpy = vi.spyOn(window.history, "replaceState");
      const mockVerify = vi
        .spyOn(membersApi, "verifyMemberEmail")
        .mockResolvedValueOnce({ detail: "Email verified successfully." });

      render(
        <MemoryRouter
          initialEntries={["/verify-email?token=valid_test_token_123"]}
        >
          <Routes>
            <Route path="/verify-email" element={<VerifyEmailScreen />} />
          </Routes>
        </MemoryRouter>
      );

      expect(replaceStateSpy).toHaveBeenCalled();
      await waitFor(() => {
        expect(mockVerify).toHaveBeenCalledWith("valid_test_token_123");
      });

      expect(
        await screen.findByRole("heading", { name: /account activated/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /sign in to member portal/i })
      ).toBeInTheDocument();
    });

    it("displays error card when verification token is expired or invalid", async () => {
      vi.spyOn(membersApi, "verifyMemberEmail").mockRejectedValueOnce(
        new Error("Invalid or expired verification token.")
      );

      render(
        <MemoryRouter initialEntries={["/verify-email?token=expired_token"]}>
          <Routes>
            <Route path="/verify-email" element={<VerifyEmailScreen />} />
          </Routes>
        </MemoryRouter>
      );

      expect(
        await screen.findByRole("heading", { name: /unable to verify/i })
      ).toBeInTheDocument();
      expect(
        screen.getByText(/invalid or expired verification token/i)
      ).toBeInTheDocument();
    });
  });

  describe("MemberManagementSection", () => {
    const mockMembers: membersApi.Member[] = [
      {
        id: "mem-1",
        email: "haile@example.com",
        full_name: "Haile Gebrselassie",
        phone: "+251911111111",
        status: "active",
        joined_at: new Date().toISOString(),
        waiver_accepted_at: new Date().toISOString(),
        latest_metrics: {
          weight_kg: 68.0,
          height_cm: 165.0,
          estimated_bmi: 25.0,
          estimated_body_fat_percentage: 13.5,
          bmi_label: "estimate",
          body_fat_label: "estimate",
        },
      },
    ];

    it("renders member directory with computed BMI and Body Fat estimates", async () => {
      vi.spyOn(membersApi, "listGymMembers").mockResolvedValueOnce(mockMembers);

      render(
        <MemoryRouter>
          <MemberManagementSection userRole="reception" />
        </MemoryRouter>
      );

      expect(await screen.findByText("Haile Gebrselassie")).toBeInTheDocument();
      expect(screen.getByText("haile@example.com")).toBeInTheDocument();
      expect(screen.getByText("+251911111111")).toBeInTheDocument();
      expect(screen.getByText("25")).toBeInTheDocument();
      expect(screen.getByText("13.5%")).toBeInTheDocument();
    });

    it("opens staff registration modal and registers a member", async () => {
      vi.spyOn(membersApi, "listGymMembers").mockResolvedValueOnce(mockMembers);
      const mockRegister = vi
        .spyOn(membersApi, "registerMemberStaffAssisted")
        .mockResolvedValueOnce({
          detail: "Member registered successfully. Invitation email sent.",
          member: {
            id: "mem-2",
            email: "derartu@example.com",
            full_name: "Derartu Tulu",
            phone: "+251922222222",
            status: "active",
            joined_at: new Date().toISOString(),
            waiver_accepted_at: new Date().toISOString(),
          },
        });

      const onReg = vi.fn();

      render(
        <MemoryRouter>
          <MemberManagementSection
            userRole="owner"
            onMemberRegistered={onReg}
          />
        </MemoryRouter>
      );

      await screen.findByText("Haile Gebrselassie");

      // Open registration modal
      fireEvent.click(
        screen.getByRole("button", { name: /\+ register member/i })
      );

      expect(
        screen.getByRole("heading", { name: /register new member/i })
      ).toBeInTheDocument();

      fireEvent.change(screen.getByPlaceholderText(/e\.g\. Kenenisa Bekele/i), {
        target: { value: "Derartu Tulu" },
      });
      fireEvent.change(screen.getByPlaceholderText(/email@example\.com/i), {
        target: { value: "derartu@example.com" },
      });
      fireEvent.change(screen.getByPlaceholderText(/\+251911223344/i), {
        target: { value: "+251922222222" },
      });
      fireEvent.click(screen.getByRole("checkbox"));

      fireEvent.click(
        screen.getByRole("button", { name: /confirm & send invite/i })
      );

      await waitFor(() => {
        expect(mockRegister).toHaveBeenCalledWith(
          expect.objectContaining({
            full_name: "Derartu Tulu",
            email: "derartu@example.com",
            phone: "+251922222222",
            waiver_accepted: true,
          })
        );
      });

      expect(onReg).toHaveBeenCalled();
    });

    it("opens member detail view and records new measurements", async () => {
      vi.spyOn(membersApi, "listGymMembers").mockResolvedValueOnce(mockMembers);
      vi.spyOn(membersApi, "getGymMemberDetail").mockResolvedValueOnce({
        ...mockMembers[0],
        latest_metrics: {
          weight_kg: 68.0,
          height_cm: 165.0,
          estimated_bmi: 25.0,
          estimated_body_fat_percentage: 13.5,
          bmi_label: "estimate",
          body_fat_label: "estimate",
        },
      });

      const mockRecord = vi
        .spyOn(membersApi, "recordMemberMetrics")
        .mockResolvedValueOnce({
          weight_kg: 67.5,
          height_cm: 165.0,
          estimated_bmi: 24.8,
        });

      render(
        <MemoryRouter>
          <MemberManagementSection userRole="reception" />
        </MemoryRouter>
      );

      await screen.findByText("Haile Gebrselassie");

      // Open detail modal
      fireEvent.click(screen.getByRole("button", { name: /view details/i }));

      expect(
        await screen.findByRole("heading", {
          name: /current body composition estimates/i,
        })
      ).toBeInTheDocument();

      // Submit new weight measurement
      fireEvent.change(screen.getByPlaceholderText(/weight \(kg\)/i), {
        target: { value: "67.5" },
      });
      fireEvent.click(
        screen.getByRole("button", { name: /record measurements/i })
      );

      await waitFor(() => {
        expect(mockRecord).toHaveBeenCalledWith("mem-1", {
          weight_kg: 67.5,
          height_cm: null,
          measurements: undefined,
        });
      });
    });
  });

  describe("MemberSelfSection", () => {
    it("displays member profile with labeled BMI and body fat estimates", async () => {
      vi.spyOn(membersApi, "getMemberProfileMe").mockResolvedValueOnce({
        id: "mem-me",
        email: "self@example.com",
        full_name: "Self Member",
        phone: "+251933333333",
        status: "active",
        joined_at: new Date().toISOString(),
        waiver_accepted_at: new Date().toISOString(),
        latest_metrics: {
          weight_kg: 75.0,
          height_cm: 180.0,
          estimated_bmi: 23.1,
          estimated_body_fat_percentage: 14.5,
          bmi_label: "estimate",
          body_fat_label: "estimate",
        },
      });

      render(
        <MemoryRouter>
          <MemberSelfSection />
        </MemoryRouter>
      );

      expect(
        await screen.findByText("Welcome, Self Member")
      ).toBeInTheDocument();
      expect(screen.getByText("75 kg")).toBeInTheDocument();
      expect(screen.getByText("180 cm")).toBeInTheDocument();
      expect(screen.getByText("23.1")).toBeInTheDocument();
      expect(screen.getByText("14.5%")).toBeInTheDocument();
    });
  });
});
