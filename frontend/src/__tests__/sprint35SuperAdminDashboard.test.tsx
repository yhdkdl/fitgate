import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as gymsApi from "../api/gyms";
import { GymManagementSection } from "../components/superadmin/GymManagementSection";
import { NoticeBoardSection } from "../components/notices/NoticeBoardSection";

vi.mock("../api/gyms", () => ({
  listGyms: vi.fn(),
  getPlatformAnalyticsOverview: vi.fn(),
  getGymSettings: vi.fn(),
  updateGymSettings: vi.fn(),
  confirmGymTls: vi.fn(),
  createGym: vi.fn(),
  proposeSubdomain: vi.fn(),
  terminateGym: vi.fn(),
  reinstateGym: vi.fn(),
  getPlatformNotices: vi.fn(),
  createPlatformNotice: vi.fn(),
  deletePlatformNotice: vi.fn(),
}));

vi.mock("../api/notices", () => ({
  getNotices: vi.fn(),
  createNotice: vi.fn(),
  deleteNotice: vi.fn(),
}));

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "admin-1", role: "super_admin", email: "admin@fitgate.com" },
    dashboardConfig: null,
    logout: vi.fn(),
  }),
}));

const mockGyms: gymsApi.GymTenantSummary[] = [
  {
    id: "gym-1",
    name: "Active Fitness",
    subdomain: "active-fit",
    tier: "growth",
    status: "active",
    tls_confirmed_at: "2026-01-01T00:00:00Z",
    owner_email: "owner@active.com",
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "gym-2",
    name: "Suspended Iron",
    subdomain: "suspended-iron",
    tier: "starter",
    status: "suspended",
    tls_confirmed_at: "2026-01-01T00:00:00Z",
    owner_email: "owner@suspended.com",
    suspended_at: "2026-01-01T00:00:00Z",
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "gym-3",
    name: "Terminated Gold",
    subdomain: "terminated-gold",
    tier: "starter",
    status: "terminated",
    tls_confirmed_at: "2026-01-01T00:00:00Z",
    owner_email: "owner@terminated.com",
    created_at: "2026-01-01T00:00:00Z",
  },
];

const mockMetrics: gymsApi.PlatformAnalyticsOverview = {
  active_gyms: 1,
  suspended_gyms: 1,
  terminated_gyms: 1,
  platform_revenue_etb: "42000.00",
};

describe("Sprint 35: Super Admin Dashboard, Analytics, Termination, Notices", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(gymsApi.listGyms).mockResolvedValue(mockGyms);
    vi.mocked(gymsApi.getPlatformAnalyticsOverview).mockResolvedValue(mockMetrics);
    vi.mocked(gymsApi.getGymSettings).mockResolvedValue({
      has_trainer_module: true,
      has_ai_plans: true,
      has_analytics: true,
      has_group_classes: true,
      freeze_days_cap: 30,
      payment_grace_days: 7,
      subscription_reminder_days: [14, 7],
    });
  });

  it("renders platform analytics metrics cards", async () => {
    render(<GymManagementSection />);
    await waitFor(() => {
      expect(screen.getByText("Active Gyms")).toBeInTheDocument();
      expect(screen.getByText("ETB 42000.00")).toBeInTheDocument();
      expect(screen.getByText("Suspended")).toBeInTheDocument();
      expect(screen.getByText("Terminated")).toBeInTheDocument();
    });
  });

  it("shows Terminate button only for suspended gyms and Reinstate only for terminated gyms", async () => {
    render(<GymManagementSection />);
    await waitFor(() => {
      expect(screen.getByText("Active Fitness")).toBeInTheDocument();
    });

    const terminateBtns = screen.getAllByRole("button", { name: "Terminate" });
    expect(terminateBtns.length).toBe(1);

    const reinstateBtns = screen.getAllByRole("button", { name: "Reinstate" });
    expect(reinstateBtns.length).toBe(1);
  });

  it("requires exact subdomain confirmation in modal to terminate a gym", async () => {
    const user = userEvent.setup();
    vi.mocked(gymsApi.terminateGym).mockResolvedValue({
      id: "gym-2",
      name: "Suspended Iron",
      subdomain: "suspended-iron",
      status: "terminated",
    } as unknown as gymsApi.GymTenantSummary);

    render(<GymManagementSection />);
    await waitFor(() => {
      expect(screen.getByText("Suspended Iron")).toBeInTheDocument();
    });

    // Click Terminate
    const terminateBtn = screen.getByRole("button", { name: "Terminate" });
    await user.click(terminateBtn);

    expect(screen.getByText("Permanently Terminate")).toBeInTheDocument();

    // Type wrong subdomain
    const input = screen.getByPlaceholderText("suspended-iron");
    await user.type(input, "wrong-name");
    await user.click(screen.getByText("Permanently Terminate"));

    expect(screen.getByText("Subdomain confirmation does not match.")).toBeInTheDocument();
    expect(gymsApi.terminateGym).not.toHaveBeenCalled();

    // Type correct subdomain
    await user.clear(input);
    await user.type(input, "suspended-iron");
    await user.click(screen.getByText("Permanently Terminate"));

    await waitFor(() => {
      expect(gymsApi.terminateGym).toHaveBeenCalledWith("gym-2", "suspended-iron");
    });
  });

  it("requires exact subdomain confirmation in modal to reinstate a gym", async () => {
    const user = userEvent.setup();
    vi.mocked(gymsApi.reinstateGym).mockResolvedValue({
      id: "gym-3",
      name: "Terminated Gold",
      subdomain: "terminated-gold",
      status: "suspended",
    } as unknown as gymsApi.GymTenantSummary);

    render(<GymManagementSection />);
    await waitFor(() => {
      expect(screen.getByText("Terminated Gold")).toBeInTheDocument();
    });

    // Click Reinstate
    const reinstateBtn = screen.getByRole("button", { name: "Reinstate" });
    await user.click(reinstateBtn);

    expect(screen.getByRole("heading", { name: "Reinstate Gym" })).toBeInTheDocument();

    // Type wrong subdomain
    const input = screen.getByPlaceholderText("terminated-gold");
    await user.type(input, "wrong-sub");
    await user.click(screen.getByRole("button", { name: "Reinstate Gym" }));

    expect(screen.getByText("Subdomain confirmation does not match.")).toBeInTheDocument();
    expect(gymsApi.reinstateGym).not.toHaveBeenCalled();

    // Type correct subdomain
    await user.clear(input);
    await user.type(input, "terminated-gold");
    await user.click(screen.getByRole("button", { name: "Reinstate Gym" }));

    await waitFor(() => {
      expect(gymsApi.reinstateGym).toHaveBeenCalledWith("gym-3", "terminated-gold");
    });
  });

  it("includes group classes entitlement checkbox in Super Admin config modal", async () => {
    const user = userEvent.setup();
    render(<GymManagementSection />);
    await waitFor(() => {
      expect(screen.getByText("Active Fitness")).toBeInTheDocument();
    });

    const configBtns = screen.getAllByRole("button", { name: "Config" });
    await user.click(configBtns[0]);

    await waitFor(() => {
      expect(screen.getByText("Group Classes")).toBeInTheDocument();
    });

    const groupClassesCheckbox = screen.getByLabelText("Group Classes");
    expect(groupClassesCheckbox).toBeChecked();

    await user.click(groupClassesCheckbox);
    expect(groupClassesCheckbox).not.toBeChecked();
  });

  it("loads and manages platform notices for super_admin role in NoticeBoardSection", async () => {
    vi.mocked(gymsApi.getPlatformNotices).mockResolvedValue([
      {
        id: "notice-1",
        title: "Platform Maintenance",
        body: "Maintenance on Sunday.",
        posted_by_name: "FitGate Platform",
        is_platform_wide: true,
        created_at: "2026-01-01T00:00:00Z",
      },
    ]);

    render(<NoticeBoardSection userRole="super_admin" />);
    await waitFor(() => {
      expect(screen.getByText("Platform Maintenance")).toBeInTheDocument();
      expect(screen.getByText("Post Notice")).toBeInTheDocument();
      expect(screen.getByText("Platform Announcement")).toBeInTheDocument();
    });
  });
});
