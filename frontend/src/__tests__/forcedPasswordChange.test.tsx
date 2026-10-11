import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../context/AuthContext";
import { ProtectedRoute } from "../components/auth/ProtectedRoute";
import { ForcedChangePasswordScreen } from "../screens/ForcedChangePasswordScreen";
import { DashboardScreen } from "../screens/DashboardScreen";
import * as client from "../api/client";

describe("ForcedChangePassword", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it("blocks routes and redirects to /force-change-password when must_change_password is true", async () => {
    client.setRefreshToken("mock-refresh");

    vi.spyOn(global, "fetch").mockImplementation(async (url) => {
      const u = String(url);
      if (u.includes("/api/auth/refresh/")) {
        return new Response(JSON.stringify({ access: "refreshed-access" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (u.includes("/api/auth/me/")) {
        return new Response(
          JSON.stringify({
            id: "user-1",
            email: "admin@fitgate.org",
            role: "super_admin",
            full_name: "Admin",
            phone: "",
            must_change_password: true,
            gym_id: null,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      return new Response("Not found", { status: 404 });
    });

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AuthProvider>
          <Routes>
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <DashboardScreen />
                </ProtectedRoute>
              }
            />
            <Route
              path="/force-change-password"
              element={
                <ProtectedRoute allowForcedPasswordChangeOnly={true}>
                  <ForcedChangePasswordScreen />
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    // Should redirect to ForcedChangePasswordScreen
    await waitFor(() => {
      expect(screen.getByText("Password Change Required")).toBeInTheDocument();
    });
  });

  it("validates password length and match, then updates password successfully", async () => {
    client.setRefreshToken("mock-refresh");

    vi.spyOn(global, "fetch").mockImplementation(async (url, init) => {
      const u = String(url);
      if (u.includes("/api/auth/refresh/")) {
        return new Response(JSON.stringify({ access: "refreshed-access" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (u.includes("/api/auth/me/")) {
        return new Response(
          JSON.stringify({
            id: "user-1",
            email: "admin@fitgate.org",
            role: "super_admin",
            full_name: "Admin",
            phone: "",
            must_change_password: true,
            gym_id: null,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      if (u.includes("/api/auth/change-password/") && init?.method === "POST") {
        return new Response(
          JSON.stringify({
            access: "new-access-token",
            refresh: "new-refresh-token",
            user: {
              id: "user-1",
              email: "admin@fitgate.org",
              role: "super_admin",
              full_name: "Admin",
              phone: "",
              must_change_password: false,
              gym_id: null,
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      return new Response("Not found", { status: 404 });
    });

    render(
      <MemoryRouter initialEntries={["/force-change-password"]}>
        <AuthProvider>
          <Routes>
            <Route
              path="/force-change-password"
              element={
                <ProtectedRoute allowForcedPasswordChangeOnly={true}>
                  <ForcedChangePasswordScreen />
                </ProtectedRoute>
              }
            />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <div>Welcome to Dashboard</div>
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Password Change Required")).toBeInTheDocument();
    });

    // Test password too short
    fireEvent.change(screen.getByLabelText(/current password/i), {
      target: { value: "InitialPassword123!" },
    });
    fireEvent.change(screen.getByLabelText(/^new password/i), {
      target: { value: "short" },
    });
    fireEvent.change(screen.getByLabelText(/confirm new password/i), {
      target: { value: "short" },
    });
    fireEvent.click(screen.getByRole("button", { name: /update password/i }));

    await waitFor(() => {
      expect(
        screen.getByText("New password must be at least 10 characters long.")
      ).toBeInTheDocument();
    });

    // Test password mismatch
    fireEvent.change(screen.getByLabelText(/^new password/i), {
      target: { value: "BrandNewPassword123!" },
    });
    fireEvent.change(screen.getByLabelText(/confirm new password/i), {
      target: { value: "DifferentPassword123!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /update password/i }));

    await waitFor(() => {
      expect(
        screen.getByText("New passwords do not match.")
      ).toBeInTheDocument();
    });

    // Test successful update
    fireEvent.change(screen.getByLabelText(/confirm new password/i), {
      target: { value: "BrandNewPassword123!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /update password/i }));

    await waitFor(() => {
      expect(screen.getByText("Welcome to Dashboard")).toBeInTheDocument();
    });
  });
});
