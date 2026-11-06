import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LoginScreen } from "../screens/LoginScreen";
import * as tenantUtils from "../utils/tenant";

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    login: vi.fn(),
    user: null,
    isAuthenticated: false,
  }),
}));

vi.mock("../api/gyms", () => ({
  getPublicGymEntry: vi.fn(),
}));

describe("LoginScreen Demo Credentials Panel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders demo credentials panel when tenant is demo", async () => {
    vi.spyOn(tenantUtils, "getTenantFromHostname").mockReturnValue("demo");

    render(
      <BrowserRouter>
        <LoginScreen />
      </BrowserRouter>
    );

    expect(screen.getByTestId("demo-credentials-panel")).toBeInTheDocument();
    expect(screen.getByText("Demo credentials")).toBeInTheDocument();
  });

  it("populates email and password on clicking Fill without auto-submitting", async () => {
    vi.spyOn(tenantUtils, "getTenantFromHostname").mockReturnValue("demo");
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <LoginScreen />
      </BrowserRouter>
    );

    const emailInput = screen.getByLabelText(/Email address/i) as HTMLInputElement;
    const passwordInput = screen.getByLabelText(/Password/i) as HTMLInputElement;

    expect(emailInput.value).toBe("");
    expect(passwordInput.value).toBe("");

    // Find the Fill buttons in the demo panel
    const fillButtons = screen.getAllByRole("button", { name: "Fill" });
    expect(fillButtons.length).toBeGreaterThan(0);

    // Click the first Fill button (Owner: owner@demo.local)
    await user.click(fillButtons[0]);

    expect(emailInput.value).toBe("owner@demo.local");
    expect(passwordInput.value).toBe("FitGateDemo2026!");
  });
});
