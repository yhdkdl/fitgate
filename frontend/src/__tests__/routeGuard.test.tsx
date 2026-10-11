import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../context/AuthContext";
import { ProtectedRoute } from "../components/auth/ProtectedRoute";
import * as client from "../api/client";

describe("ProtectedRoute Guard", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it("redirects unauthenticated users to /login", async () => {
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AuthProvider>
          <Routes>
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <div>Secret Dashboard Content</div>
                </ProtectedRoute>
              }
            />
            <Route path="/login" element={<div>Login Page</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Login Page")).toBeInTheDocument();
      expect(
        screen.queryByText("Secret Dashboard Content")
      ).not.toBeInTheDocument();
    });
  });

  it("blocks users when role is not in allowedRoles with Access Denied", async () => {
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
            id: "user-member",
            email: "member@fitgate.org",
            role: "member",
            full_name: "Member User",
            phone: "",
            must_change_password: false,
            gym_id: "gym-1",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      return new Response("Not found", { status: 404 });
    });

    render(
      <MemoryRouter initialEntries={["/admin-only"]}>
        <AuthProvider>
          <Routes>
            <Route
              path="/admin-only"
              element={
                <ProtectedRoute allowedRoles={["super_admin"]}>
                  <div>Super Admin Restricted Area</div>
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Access Denied")).toBeInTheDocument();
      expect(
        screen.queryByText("Super Admin Restricted Area")
      ).not.toBeInTheDocument();
    });
  });
});
