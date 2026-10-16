import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../context/AuthContext";
import { LoginScreen } from "../screens/LoginScreen";

describe("LoginScreen", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders login form with 320px support and shows apex platform context by default", () => {
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <AuthProvider>
          <LoginScreen />
        </AuthProvider>
      </MemoryRouter>
    );

    expect(screen.getByText("FitGate")).toBeInTheDocument();
    expect(screen.getByText("Platform Administration")).toBeInTheDocument();
    expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /sign in/i })
    ).toBeInTheDocument();
  });

  it("handles successful login and stores tokens", async () => {
    const mockLoginResponse = {
      access: "mock-access-token",
      refresh: "mock-refresh-token",
      user: {
        id: "user-123",
        email: "admin@fitgate.org",
        role: "super_admin",
        full_name: "Super Admin",
        phone: "+251911223344",
        must_change_password: false,
        gym_id: null,
      },
      dashboard: {
        role: "super_admin",
        title: "Platform Administration",
        widgets: [{ id: "w1", title: "Overview" }],
        navigation: [{ label: "Gyms", path: "/platform/gyms" }],
      },
    };

    vi.spyOn(global, "fetch").mockImplementationOnce(async (url) => {
      if (String(url).includes("/api/auth/login/")) {
        return new Response(JSON.stringify(mockLoginResponse), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response("Not found", { status: 404 });
    });

    render(
      <MemoryRouter initialEntries={["/login"]}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginScreen />} />
            <Route path="/dashboard" element={<div>Dashboard Screen</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: "admin@fitgate.org" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "SuperPassword123!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText("Dashboard Screen")).toBeInTheDocument();
    });

    expect(localStorage.getItem("fitgate_refresh_token")).toBe(
      "mock-refresh-token"
    );
  });

  it("shows uniform generic error on failed login without field hints", async () => {
    vi.spyOn(global, "fetch").mockImplementationOnce(async () => {
      return new Response(JSON.stringify({ detail: "Invalid credentials." }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      });
    });

    render(
      <MemoryRouter initialEntries={["/login"]}>
        <AuthProvider>
          <LoginScreen />
        </AuthProvider>
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: "wrong@fitgate.org" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "WrongPassword123!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(
        screen.getByText(
          "Invalid email or password. Please check your credentials and try again."
        )
      ).toBeInTheDocument();
    });
  });

  it("shows server error message when API returns 5xx or network error", async () => {
    vi.spyOn(global, "fetch").mockImplementationOnce(async () => {
      return new Response("Internal Server Error", {
        status: 500,
        headers: { "Content-Type": "text/plain" },
      });
    });

    render(
      <MemoryRouter initialEntries={["/login"]}>
        <AuthProvider>
          <LoginScreen />
        </AuthProvider>
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: "user@fitgate.org" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "AnyPassword123!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Server error, please try again")
      ).toBeInTheDocument();
    });
  });
});
