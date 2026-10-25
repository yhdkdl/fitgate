import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MembershipPlansSection } from "../components/owner/MembershipPlansSection";
import * as plansApi from "../api/plans";

vi.mock("../api/plans");

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    user: {
      id: "owner-1",
      email: "owner@gym.com",
      role: "owner",
      full_name: "Owner User",
    },
    dashboardConfig: null,
    logout: vi.fn(),
  }),
}));

const mockPlans: plansApi.MembershipPlan[] = [
  {
    id: "plan-1",
    gym: "gym-1",
    name: "Monthly Standard",
    duration_value: 1,
    duration_unit: "months",
    duration_in_days: 30,
    price_etb: "1500.00",
    trainer_inclusive: false,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "plan-2",
    gym: "gym-1",
    name: "Pro Training VIP",
    duration_value: 3,
    duration_unit: "months",
    duration_in_days: 90,
    price_etb: "4500.00",
    trainer_inclusive: true,
    is_active: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

describe("MembershipPlansSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(plansApi.getMembershipPlans).mockResolvedValue(mockPlans);
  });

  it("renders list of membership plans and duration/price details", async () => {
    render(<MembershipPlansSection />);

    expect(screen.getByText("Loading membership plans...")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Monthly Standard")).toBeInTheDocument();
      expect(screen.getByText("Pro Training VIP")).toBeInTheDocument();
    });

    expect(screen.getByText("1,500")).toBeInTheDocument();
    expect(screen.getByText("4,500")).toBeInTheDocument();
  });

  it("allows opening create plan modal and creating a new plan", async () => {
    const user = userEvent.setup();
    const createdPlan: plansApi.MembershipPlan = {
      id: "plan-3",
      gym: "gym-1",
      name: "Annual Unlimited",
      duration_value: 12,
      duration_unit: "months",
      duration_in_days: 365,
      price_etb: "12000.00",
      trainer_inclusive: false,
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };

    vi.mocked(plansApi.createMembershipPlan).mockResolvedValue(createdPlan);

    render(<MembershipPlansSection />);

    await waitFor(() => {
      expect(screen.getByText("Monthly Standard")).toBeInTheDocument();
    });

    const addBtn = screen.getByRole("button", { name: /\+ Add New Plan/i });
    await user.click(addBtn);

    expect(screen.getByText("Create New Membership Plan")).toBeInTheDocument();

    // Fill form
    const nameInput = screen.getByLabelText(/Plan Name/i);
    await user.type(nameInput, "Annual Unlimited");

    const durationInput = screen.getByLabelText(/Duration Value/i);
    await user.clear(durationInput);
    await user.type(durationInput, "12");

    const priceInput = screen.getByLabelText(/Price in ETB/i);
    await user.clear(priceInput);
    await user.type(priceInput, "12000");

    const submitBtn = screen.getByRole("button", { name: /Create Plan/i });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(plansApi.createMembershipPlan).toHaveBeenCalledWith({
        name: "Annual Unlimited",
        description: "",
        duration_value: 12,
        duration_unit: "months",
        price_etb: "12000",
        trainer_inclusive: false,
      });
    });
  });

  it("allows deactivating an active plan", async () => {
    const user = userEvent.setup();
    vi.mocked(plansApi.deactivateMembershipPlan).mockResolvedValue({
      ...mockPlans[0],
      is_active: false,
    });

    render(<MembershipPlansSection />);

    await waitFor(() => {
      expect(screen.getByText("Monthly Standard")).toBeInTheDocument();
    });

    const deactivateBtn = screen.getByRole("button", { name: /^Deactivate$/i });
    await user.click(deactivateBtn);

    // Confirmation modal appears
    expect(screen.getByText(/Are you sure you want to deactivate/i)).toBeInTheDocument();
    const confirmBtn = screen.getByRole("button", { name: /Deactivate Plan/i });
    await user.click(confirmBtn);

    await waitFor(() => {
      expect(plansApi.deactivateMembershipPlan).toHaveBeenCalledWith("plan-1");
    });
  });
});
