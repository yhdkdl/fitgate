import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthContext, type AuthContextType } from "../context/AuthContext";
import { DashboardScreen } from "../screens/DashboardScreen";
import type { GymCapabilities, UserProfile } from "../types/api";

const STARTER_CAPABILITIES: GymCapabilities = {
  has_trainer_module: false,
  has_ai_plans: false,
  has_freeze: false,
  has_group_classes: false,
  has_analytics: false,
  has_notices: false,
  has_expenses: false,
};

const GROWTH_CAPABILITIES: GymCapabilities = {
  has_trainer_module: true,
  has_ai_plans: true,
  has_freeze: true,
  has_group_classes: true,
  has_analytics: true,
  has_notices: true,
  has_expenses: true,
};

function makeAuthContext(user: Partial<UserProfile>, capabilities: GymCapabilities): AuthContextType {
  const fullUser: UserProfile = {
    id: "test-user-id",
    email: "test@fitgate.org",
    full_name: "Test User",
    role: user.role || "owner",
    phone: "+251911223344",
    gym_id: "test-gym-id",
    gym_name: "Test Gym",
    is_active: true,
    created_at: new Date().toISOString(),
    ...user,
  };

  return {
    user: fullUser,
    isAuthenticated: true,
    isLoading: false,
    mustChangePassword: false,
    capabilities,
    dashboardConfig: {
      user: fullUser,
      capabilities,
      navigation: [],
      branding: {
        name: "Test Gym",
        logo: null,
        brand_color: "#2563EB",
      },
    },
    login: async () => {},
    logout: async () => {},
    updateUser: async () => fullUser,
    changeUserPassword: async () => {},
    refreshProfile: async () => {},
    syncSession: async () => {},
  };
}

describe("Tier Navigation & Route Gating", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.restoreAllMocks();

    vi.spyOn(global, "fetch").mockImplementation(async () => {
      return new Response(JSON.stringify({}), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
  });

  it("renders correct navigation for Owner on Starter vs Growth", async () => {
    // 1. Starter Owner
    const starterAuth = makeAuthContext({ role: "owner" }, STARTER_CAPABILITIES);
    const { unmount } = render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AuthContext.Provider value={starterAuth}>
          <Routes>
            <Route path="/*" element={<DashboardScreen />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    );

    // Starter shown
    expect(screen.getAllByText("Overview")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Members")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Check-in")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Equipment")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Payments")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Plans")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Staff")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Audit log")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Settings")[0]).toBeInTheDocument();

    // Starter hidden (tier-gated)
    expect(screen.queryByText("Classes")).not.toBeInTheDocument();
    expect(screen.queryByText("Expenses & Reports")).not.toBeInTheDocument();
    expect(screen.queryByText("Trainers")).not.toBeInTheDocument();
    expect(screen.queryByText("Assignments")).not.toBeInTheDocument();
    expect(screen.queryByText("Freeze requests")).not.toBeInTheDocument();
    expect(screen.queryByText("Notices")).not.toBeInTheDocument();

    unmount();

    // 2. Growth Owner
    const growthAuth = makeAuthContext({ role: "owner" }, GROWTH_CAPABILITIES);
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AuthContext.Provider value={growthAuth}>
          <Routes>
            <Route path="/*" element={<DashboardScreen />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    );

    // Growth includes tier-gated items
    expect(screen.getAllByText("Classes")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Expenses & Reports")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Trainers")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Assignments")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Freeze requests")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Notices")[0]).toBeInTheDocument();
  });

  it("renders correct navigation for Manager on Starter vs Growth", async () => {
    // 1. Starter Manager
    const starterAuth = makeAuthContext({ role: "manager" }, STARTER_CAPABILITIES);
    const { unmount } = render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AuthContext.Provider value={starterAuth}>
          <Routes>
            <Route path="/*" element={<DashboardScreen />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    );

    expect(screen.getAllByText("Receipt reviews")[0]).toBeInTheDocument();
    expect(screen.queryByText("Classes")).not.toBeInTheDocument();
    expect(screen.queryByText("Expenses & Reports")).not.toBeInTheDocument();
    expect(screen.queryByText("Trainers")).not.toBeInTheDocument();
    expect(screen.queryByText("Freeze requests")).not.toBeInTheDocument();
    expect(screen.queryByText("Notices")).not.toBeInTheDocument();

    unmount();

    // 2. Growth Manager
    const growthAuth = makeAuthContext({ role: "manager" }, GROWTH_CAPABILITIES);
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AuthContext.Provider value={growthAuth}>
          <Routes>
            <Route path="/*" element={<DashboardScreen />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    );

    expect(screen.getAllByText("Receipt reviews")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Classes")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Expenses & Reports")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Trainers")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Freeze requests")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Notices")[0]).toBeInTheDocument();
  });

  it("renders correct navigation for Reception and Member on Starter vs Growth", async () => {
    // 1. Reception Starter
    const recStarter = makeAuthContext({ role: "reception" }, STARTER_CAPABILITIES);
    const { unmount: unmount1 } = render(
      <MemoryRouter initialEntries={["/members"]}>
        <AuthContext.Provider value={recStarter}>
          <Routes>
            <Route path="/*" element={<DashboardScreen />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    );

    expect(screen.getAllByText("Members")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Check-in")[0]).toBeInTheDocument();
    expect(screen.queryByText("Classes")).not.toBeInTheDocument();
    expect(screen.queryByText("Notices")).not.toBeInTheDocument();

    unmount1();

    // 2. Member Starter
    const memberStarter = makeAuthContext({ role: "member" }, STARTER_CAPABILITIES);
    const { unmount: unmount2 } = render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AuthContext.Provider value={memberStarter}>
          <Routes>
            <Route path="/*" element={<DashboardScreen />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    );

    expect(screen.getAllByText("Home")[0]).toBeInTheDocument();
    expect(screen.getAllByText("My membership")[0]).toBeInTheDocument();
    expect(screen.getAllByText("My payments")[0]).toBeInTheDocument();
    expect(screen.queryByText("Classes")).not.toBeInTheDocument();
    expect(screen.queryByText("Freeze request")).not.toBeInTheDocument();
    expect(screen.queryByText("Notices")).not.toBeInTheDocument();

    unmount2();

    // 3. Member Growth
    const memberGrowth = makeAuthContext({ role: "member" }, GROWTH_CAPABILITIES);
    const { unmount: unmountGrowth } = render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AuthContext.Provider value={memberGrowth}>
          <Routes>
            <Route path="/*" element={<DashboardScreen />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    );

    expect(screen.getAllByText("Classes")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Freeze request")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Notices")[0]).toBeInTheDocument();

    unmountGrowth();

    // 4. Trainer Starter
    const trainerStarter = makeAuthContext({ role: "trainer" }, STARTER_CAPABILITIES);
    const { unmount: unmount3 } = render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AuthContext.Provider value={trainerStarter}>
          <Routes>
            <Route path="/*" element={<DashboardScreen />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    );
    expect(screen.queryByText("My clients")).not.toBeInTheDocument();
    expect(screen.queryByText("Member measurements")).not.toBeInTheDocument();
    expect(screen.queryByText("My classes")).not.toBeInTheDocument();
    expect(screen.queryByText("Notices")).not.toBeInTheDocument();

    unmount3();

    // 5. Trainer Growth
    const trainerGrowth = makeAuthContext({ role: "trainer" }, GROWTH_CAPABILITIES);
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AuthContext.Provider value={trainerGrowth}>
          <Routes>
            <Route path="/*" element={<DashboardScreen />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    );
    expect(screen.getAllByText("My clients")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Member measurements")[0]).toBeInTheDocument();
    expect(screen.getAllByText("My classes")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Notices")[0]).toBeInTheDocument();
  });

  it("redirects hidden tier-gated routes directly to Home on Starter tier", async () => {
    const starterAuth = makeAuthContext({ role: "owner" }, STARTER_CAPABILITIES);

    // Visiting /expenses on Starter directly
    render(
      <MemoryRouter initialEntries={["/expenses"]}>
        <AuthContext.Provider value={starterAuth}>
          <Routes>
            <Route path="/*" element={<DashboardScreen />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    );

    // Should redirect to /dashboard and render Overview Home without error
    await waitFor(() => {
      expect(screen.getAllByText("Overview")[0]).toBeInTheDocument();
    });
  });
});
