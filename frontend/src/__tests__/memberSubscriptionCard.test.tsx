import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Member } from "../api/members";
import { MemberSubscriptionCard } from "../components/member/MemberSubscriptionCard";

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    capabilities: { has_trainer_module: true },
  }),
}));

describe("MemberSubscriptionCard", () => {
  const baseMember: Member = {
    id: "mem-card-1",
    full_name: "Yoyo Upgraded",
    email: "yoyo@example.com",
    phone: "+251911223344",
    status: "active",
    joined_at: "2026-10-01T00:00:00Z",
    waiver_accepted_at: "2026-10-01T00:00:00Z",
    is_on_trainer_plan: true,
    active_subscription: {
      id: "sub-1",
      plan_id: "plan-1",
      plan_name: "Pro Trainer Elite",
      plan_price_etb: "3000.00",
      trainer_inclusive: true,
      status: "active",
      start_date: "2026-11-01",
      end_date: "2026-11-30",
      duration_value: 1,
      duration_unit: "months",
      total_days: 30,
      used_days: 2,
      remaining_days: 28,
    },
    queued_subscription: {
      id: "sub-2",
      plan_id: "plan-2",
      plan_name: "Standard Fitness Plan",
      trainer_inclusive: false,
      start_date: "2026-12-01",
      end_date: "2026-12-31",
      status: "active",
    },
  };

  it("renders active plan details with days left and queued next plan", () => {
    render(<MemberSubscriptionCard member={baseMember} />);

    expect(screen.getByText("Pro Trainer Elite")).toBeInTheDocument();
    expect(screen.getByText("Trainer included: yes")).toBeInTheDocument();
    expect(screen.getByText("1 month")).toBeInTheDocument();
    expect(screen.getByText("2026-11-01")).toBeInTheDocument();
    expect(screen.getByText("2026-11-30")).toBeInTheDocument();
    expect(screen.getByText("28 days left")).toBeInTheDocument();
    expect(
      screen.getByText("Next plan: Standard Fitness Plan starts on 2026-12-01")
    ).toBeInTheDocument();
  });

  it("renders non-trainer plan with 'Trainer included: no'", () => {
    const nonTrainerMember: Member = {
      ...baseMember,
      is_on_trainer_plan: false,
      active_subscription: {
        ...baseMember.active_subscription!,
        plan_name: "Basic Gym Pass",
        trainer_inclusive: false,
        duration_value: 30,
        duration_unit: "days",
      },
      queued_subscription: null,
    };

    render(<MemberSubscriptionCard member={nonTrainerMember} />);

    expect(screen.getByText("Basic Gym Pass")).toBeInTheDocument();
    expect(screen.getByText("Trainer included: no")).toBeInTheDocument();
    expect(screen.getByText("30 days")).toBeInTheDocument();
  });

  it("renders frozen state with 'Frozen until <date>'", () => {
    const frozenMember: Member = {
      ...baseMember,
      status: "frozen",
      active_freeze: {
        id: "fr-1",
        start_date: "2026-11-02",
        end_date: "2026-11-15",
      },
    };

    render(<MemberSubscriptionCard member={frozenMember} />);

    expect(screen.getByText("Frozen until 2026-11-15")).toBeInTheDocument();
  });

  it("renders pending state with 'Waiting for payment'", () => {
    const pendingMember: Member = {
      ...baseMember,
      status: "pending",
      active_subscription: null,
      queued_subscription: null,
    };

    render(<MemberSubscriptionCard member={pendingMember} />);

    expect(screen.getByText("Waiting for payment")).toBeInTheDocument();
  });
});
