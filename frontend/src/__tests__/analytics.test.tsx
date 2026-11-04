import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AnalyticsOverviewSection } from "../components/analytics/AnalyticsOverviewSection";
import * as analyticsApi from "../api/analytics";

vi.mock("../api/analytics");

const mockStarterAnalytics: analyticsApi.GymAnalyticsOverview = {
  active_members: 42,
  frozen_members: 3,
  today_checkins: 15,
  monthly_net_revenue: "45000.00",
  currency: "ETB",
  expiring_memberships_count: 2,
  expiring_memberships: [
    {
      member_id: "m-1",
      member_name: "Dawit Haile",
      member_phone: "+251911223344",
      plan_name: "Standard Monthly",
      end_date: "2026-11-05",
      days_remaining: 2,
    },
    {
      member_id: "m-2",
      member_name: "Sara Bekele",
      member_phone: "+251922334455",
      plan_name: "VIP Monthly",
      end_date: "2026-11-08",
      days_remaining: 5,
    },
  ],
  has_analytics: false,
  upgrade_prompt:
    "Upgrade to Growth or Pro to unlock revenue by plan breakdowns.",
  revenue_by_plan: null,
  server_date: "2026-11-03",
};

const mockProAnalytics: analyticsApi.GymAnalyticsOverview = {
  ...mockStarterAnalytics,
  has_analytics: true,
  upgrade_prompt: null,
  revenue_by_plan: [
    {
      plan_id: "p-vip",
      plan_name: "VIP Monthly",
      revenue: "35000.00",
      payment_count: 10,
    },
    {
      plan_id: "p-std",
      plan_name: "Standard Monthly",
      revenue: "10000.00",
      payment_count: 7,
    },
  ],
};

describe("Sprint 27: AnalyticsOverviewSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders 4 core operational metric cards correctly", async () => {
    vi.spyOn(analyticsApi, "getGymAnalyticsOverview").mockResolvedValue(
      mockStarterAnalytics
    );

    render(<AnalyticsOverviewSection />);

    await waitFor(() => {
      expect(screen.getByTestId("stat-active-members")).toHaveTextContent("42");
    });

    expect(screen.getByText("(3 frozen)")).toBeInTheDocument();
    expect(screen.getByTestId("stat-today-checkins")).toHaveTextContent("15");
    expect(screen.getByTestId("stat-monthly-revenue")).toHaveTextContent(
      "45,000.00"
    );
    expect(screen.getByTestId("stat-expiring-count")).toHaveTextContent("2");
  });

  it("displays upgrade prompt for Starter tier when has_analytics is false", async () => {
    vi.spyOn(analyticsApi, "getGymAnalyticsOverview").mockResolvedValue(
      mockStarterAnalytics
    );

    render(<AnalyticsOverviewSection />);

    await waitFor(() => {
      expect(screen.getByText(/Revenue by Plan Locked/i)).toBeInTheDocument();
    });

    expect(
      screen.getByText(
        /Upgrade to Growth or Pro to unlock revenue by plan breakdowns/i
      )
    ).toBeInTheDocument();
  });

  it("renders plan revenue breakdown table for Growth/Pro tier", async () => {
    vi.spyOn(analyticsApi, "getGymAnalyticsOverview").mockResolvedValue(
      mockProAnalytics
    );

    render(<AnalyticsOverviewSection />);

    await waitFor(() => {
      expect(screen.getByText("VIP Monthly")).toBeInTheDocument();
    });

    expect(screen.getByText("Standard Monthly")).toBeInTheDocument();
    expect(screen.getByText(/35,000.00 ETB/)).toBeInTheDocument();
    expect(screen.getByText(/10,000.00 ETB/)).toBeInTheDocument();
  });

  it("opens expiring members modal and displays expiring membership list", async () => {
    vi.spyOn(analyticsApi, "getGymAnalyticsOverview").mockResolvedValue(
      mockStarterAnalytics
    );

    render(<AnalyticsOverviewSection />);

    await waitFor(() => {
      expect(screen.getByText("View list →")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("View list →"));

    expect(
      screen.getByText("Memberships Expiring Within 7 Days")
    ).toBeInTheDocument();
    expect(screen.getByText("Dawit Haile")).toBeInTheDocument();
    expect(screen.getByText("+251911223344")).toBeInTheDocument();
    expect(screen.getByText("Sara Bekele")).toBeInTheDocument();
    expect(screen.getByText("+251922334455")).toBeInTheDocument();
  });
});
