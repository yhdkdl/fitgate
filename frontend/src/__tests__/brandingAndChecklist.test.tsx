import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as gymsApi from "../api/gyms";
import { FirstRunChecklistCard } from "../components/owner/FirstRunChecklistCard";
import { GymBrandingSection } from "../components/owner/GymBrandingSection";
import { GymEntryScreen } from "../screens/GymEntryScreen";

vi.mock("../api/gyms", () => ({
  getPublicGymEntry: vi.fn(),
  getFirstRunChecklist: vi.fn(),
  dismissFirstRunChecklist: vi.fn(),
  getGymSettings: vi.fn(),
  updateGymSettings: vi.fn(),
  uploadGymLogo: vi.fn(),
}));

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    user: null,
    dashboardConfig: null,
    logout: vi.fn(),
  }),
}));

vi.mock("../utils/tenant", () => ({
  getTenantFromHostname: vi.fn().mockReturnValue("bole-fitness"),
}));

describe("Sprint 4c: Gym branding, entry page, first-run checklist", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("GymEntryScreen", () => {
    it("renders 503 still being secured state when certificate is unconfirmed", async () => {
      vi.mocked(gymsApi.getPublicGymEntry).mockResolvedValue({
        still_securing: true,
        name: "Bole Power Fitness",
        online_payment_verified: false,
        message:
          "This gym portal is still being secured. Please check back shortly.",
      });

      render(
        <MemoryRouter>
          <GymEntryScreen />
        </MemoryRouter>
      );

      expect(
        await screen.findByText("Still Being Secured")
      ).toBeInTheDocument();
      expect(screen.getByText("Bole Power Fitness")).toBeInTheDocument();
      expect(
        screen.getByText(
          "This gym portal is still being secured. Please check back shortly."
        )
      ).toBeInTheDocument();
      expect(
        screen.getByText("Notice for Members and Staff:")
      ).toBeInTheDocument();
    });

    it("renders 200 public entry portal with gym branding and sign in button", async () => {
      vi.mocked(gymsApi.getPublicGymEntry).mockResolvedValue({
        still_securing: false,
        gym_id: "gym-123",
        name: "Bole Power Fitness",
        subdomain: "bole-fitness",
        brand_color: "#FF5733",
        logo: "https://storage.fitgate.com/logo.webp",
        phone: "+251911223344",
        location: "Bole Atlas, Addis Ababa",
        currency: "ETB",
        online_payment_verified: true,
      });

      render(
        <MemoryRouter>
          <GymEntryScreen />
        </MemoryRouter>
      );

      expect(await screen.findByText("Bole Power Fitness")).toBeInTheDocument();
      expect(
        screen.getByText("Welcome to Bole Power Fitness")
      ).toBeInTheDocument();
      expect(
        screen.getAllByText("Bole Atlas, Addis Ababa")[0]
      ).toBeInTheDocument();
      expect(screen.getByText("+251911223344")).toBeInTheDocument();
      expect(screen.getAllByText("Log in")[0]).toBeInTheDocument();
      expect(screen.getAllByText("Register")[0]).toBeInTheDocument();
      expect(screen.getByText("Membership Plans")).toBeInTheDocument();
    });
  });

  describe("FirstRunChecklistCard", () => {
    const mockChecklist: gymsApi.FirstRunChecklistResponse = {
      is_dismissed: false,
      dismissed_at: null,
      all_completed: false,
      items: {
        add_branding: {
          label: "Add gym branding & logo",
          completed: true,
        },
        create_first_plan: {
          label: "Create your first membership plan",
          completed: false,
        },
        add_staff: {
          label: "Add a staff account",
          completed: false,
        },
        register_first_member: {
          label: "Register your first member",
          completed: false,
        },
      },
    };

    it("renders onboarding items with automatic completion progress", async () => {
      vi.mocked(gymsApi.getFirstRunChecklist).mockResolvedValue(mockChecklist);

      render(<FirstRunChecklistCard />);

      expect(
        await screen.findByText("First-Run Onboarding Checklist")
      ).toBeInTheDocument();
      expect(screen.getByText("1/4 Completed")).toBeInTheDocument();
      expect(screen.getByText("Add gym branding & logo")).toBeInTheDocument();
      expect(
        screen.getByText("Create your first membership plan")
      ).toBeInTheDocument();
      expect(screen.getByText("Add a staff account")).toBeInTheDocument();
      expect(
        screen.getByText("Register your first member")
      ).toBeInTheDocument();
    });

    it("calls dismiss API and hides card when dismiss is clicked", async () => {
      vi.mocked(gymsApi.getFirstRunChecklist).mockResolvedValue(mockChecklist);
      vi.mocked(gymsApi.dismissFirstRunChecklist).mockResolvedValue({
        is_dismissed: true,
        dismissed_at: "2026-10-11T12:00:00Z",
      });

      render(<FirstRunChecklistCard />);

      const dismissBtn = await screen.findByRole("button", {
        name: "Dismiss Checklist",
      });
      fireEvent.click(dismissBtn);

      await waitFor(() => {
        expect(gymsApi.dismissFirstRunChecklist).toHaveBeenCalledTimes(1);
      });

      await waitFor(() => {
        expect(
          screen.queryByText("First-Run Onboarding Checklist")
        ).not.toBeInTheDocument();
      });
    });
  });

  describe("GymBrandingSection", () => {
    const mockConfig: gymsApi.GymConfig = {
      tier: "pro",
        has_trainer_module: false,
      has_ai_plans: false,
      has_analytics: false,
      has_group_classes: false,
      has_multi_branch: false,
      freeze_days_cap: 30,
      freeze_days_allowed: 0,
      payment_grace_days: 7,
      subscription_reminder_days: [14, 7],
      member_reminder_days: [7, 2],
      brand_color: "#1E40AF",
      logo: "https://storage.fitgate.com/logo.webp",
      show_unavailable_equipment: false,
      first_run_dismissed_at: null,
    };

    it("loads current branding settings into inputs", async () => {
      vi.mocked(gymsApi.getGymSettings).mockResolvedValue(mockConfig);

      render(<GymBrandingSection gymId="gym-123" />);

      expect(
        await screen.findByText("Gym Branding & Operational Settings")
      ).toBeInTheDocument();
      expect(screen.getByDisplayValue("#1E40AF")).toBeInTheDocument();
      expect(
        screen.getByDisplayValue("https://storage.fitgate.com/logo.webp")
      ).toBeInTheDocument();
      expect(screen.getByDisplayValue("7, 2")).toBeInTheDocument();
    });

    it("validates hex color and prevents submission if invalid", async () => {
      vi.mocked(gymsApi.getGymSettings).mockResolvedValue(mockConfig);

      render(<GymBrandingSection gymId="gym-123" />);

      const colorInput = await screen.findByDisplayValue("#1E40AF");
      await userEvent.clear(colorInput);
      await userEvent.type(colorInput, "invalid-hex");

      const submitBtn = screen.getByRole("button", {
        name: "Save Branding Settings",
      });
      fireEvent.click(submitBtn);

      expect(
        await screen.findByText(
          "Brand color must be a valid 6-character hex code (e.g. #2563EB)."
        )
      ).toBeInTheDocument();
      expect(gymsApi.updateGymSettings).not.toHaveBeenCalled();
    });

    it("submits updated branding settings and shows success alert", async () => {
      vi.mocked(gymsApi.getGymSettings).mockResolvedValue(mockConfig);
      vi.mocked(gymsApi.updateGymSettings).mockResolvedValue({
        ...mockConfig,
        brand_color: "#10B981",
      });

      render(<GymBrandingSection gymId="gym-123" />);

      const colorInput = await screen.findByDisplayValue("#1E40AF");
      await userEvent.clear(colorInput);
      await userEvent.type(colorInput, "#10B981");

      const submitBtn = screen.getByRole("button", {
        name: "Save Branding Settings",
      });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(gymsApi.updateGymSettings).toHaveBeenCalledWith(
          expect.objectContaining({
            brand_color: "#10B981",
          }),
          "gym-123"
        );
      });

      expect(
        await screen.findByText(
          "Gym settings and branding updated successfully."
        )
      ).toBeInTheDocument();
    });
  });
});
