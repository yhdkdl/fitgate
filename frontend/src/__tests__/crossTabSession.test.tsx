import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  render,
  screen,
  waitFor,
  fireEvent,
  act,
} from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../context/AuthContext";
import { ProtectedRoute } from "../components/auth/ProtectedRoute";
import * as client from "../api/client";
import {
  AUTH_SYNC_STORAGE_KEY,
  AUTH_BROADCAST_CHANNEL,
} from "../utils/authSync";

describe("Cross-Tab Session Synchronization", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("handles remote logout via storage event and redirects out-of-sync tab to /login with notice", async () => {
    client.setRefreshToken("initial-refresh-token");

    vi.spyOn(global, "fetch").mockImplementation(async (url) => {
      const u = String(url);
      if (u.includes("/api/auth/refresh/")) {
        return new Response(
          JSON.stringify({ access: "initial-access-token" }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }
        );
      }
      if (u.includes("/api/auth/me/")) {
        return new Response(
          JSON.stringify({
            id: "user-1",
            email: "alice@fitgate.org",
            role: "member",
            full_name: "Alice Member",
            phone: "+251911111111",
            gym_id: "gym-1",
            gym_name: "Bole Gym",
            gym_subdomain: "bole",
            date_joined: "2026-01-01T00:00:00Z",
            must_change_password: false,
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
                  <div>Alice Dashboard Active</div>
                </ProtectedRoute>
              }
            />
            <Route path="/login" element={<div>Login Page Target</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    // Initial load: Alice is authenticated and on dashboard
    await waitFor(() => {
      expect(screen.getByText("Alice Dashboard Active")).toBeInTheDocument();
    });

    // Simulate another tab logging out (removing fitgate_refresh_token)
    await act(async () => {
      localStorage.removeItem("fitgate_refresh_token");
      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "fitgate_refresh_token",
          newValue: null,
          oldValue: "initial-refresh-token",
        })
      );
    });

    // Out-of-sync tab should redirect to /login and show notice
    await waitFor(() => {
      expect(screen.getByText("Login Page Target")).toBeInTheDocument();
      expect(
        screen.getByText("You were signed out from another tab.")
      ).toBeInTheDocument();
    });
  });

  it("handles remote login / user switch via storage event, updates auth and redirects to dashboard with notice", async () => {
    client.setRefreshToken("alice-token");

    vi.spyOn(global, "fetch").mockImplementation(async (url) => {
      const u = String(url);
      if (u.includes("/api/auth/refresh/")) {
        return new Response(JSON.stringify({ access: "refreshed-token" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (u.includes("/api/auth/me/")) {
        return new Response(
          JSON.stringify({
            id: "user-1",
            email: "alice@fitgate.org",
            role: "member",
            full_name: "Alice Member",
            phone: "+251911111111",
            gym_id: "gym-1",
            gym_name: "Bole Gym",
            gym_subdomain: "bole",
            date_joined: "2026-01-01T00:00:00Z",
            must_change_password: false,
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
                  <div>Dashboard View</div>
                </ProtectedRoute>
              }
            />
            <Route path="/login" element={<div>Login Page Target</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Dashboard View")).toBeInTheDocument();
    });

    // In Tab A, user Bob logs in with owner role
    const bobPayload = {
      type: "LOGIN" as const,
      user: {
        id: "user-2",
        email: "bob@fitgate.org",
        role: "owner",
        full_name: "Bob Owner",
        phone: "+251922222222",
        gym_id: "gym-1",
        gym_name: "Bole Gym",
        gym_subdomain: "bole",
        date_joined: "2026-01-01T00:00:00Z",
        must_change_password: false,
      },
      dashboard: {
        role: "owner",
        title: "Owner Dashboard",
        widgets: [{ id: "metrics", title: "Metrics" }],
        navigation: [{ label: "Staff", path: "/staff" }],
      },
      refreshToken: "bob-new-token",
      timestamp: Date.now(),
    };

    // Update fetch mock to return Bob
    vi.spyOn(global, "fetch").mockImplementation(async (url) => {
      const u = String(url);
      if (u.includes("/api/auth/refresh/")) {
        return new Response(JSON.stringify({ access: "bob-access-token" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (u.includes("/api/auth/me/")) {
        return new Response(JSON.stringify(bobPayload.user), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response("Not found", { status: 404 });
    });

    await act(async () => {
      localStorage.setItem("fitgate_refresh_token", "bob-new-token");
      localStorage.setItem(AUTH_SYNC_STORAGE_KEY, JSON.stringify(bobPayload));
      window.dispatchEvent(
        new StorageEvent("storage", {
          key: AUTH_SYNC_STORAGE_KEY,
          newValue: JSON.stringify(bobPayload),
        })
      );
    });

    // Tab B detects account switch, updates user to Bob Owner, and shows notice
    await waitFor(() => {
      expect(
        screen.getByText(
          "You signed in as Bob Owner in another tab; this tab now shows that account."
        )
      ).toBeInTheDocument();
    });

    // Test dismiss button removes the notice
    const dismissBtn = screen.getByRole("button", { name: /dismiss notice/i });
    fireEvent.click(dismissBtn);

    await waitFor(() => {
      expect(
        screen.queryByText(
          "You signed in as Bob Owner in another tab; this tab now shows that account."
        )
      ).not.toBeInTheDocument();
    });
  });

  it("handles visibilitychange sync when returning to a tab after remote logout", async () => {
    client.setRefreshToken("existing-refresh-token");

    vi.spyOn(global, "fetch").mockImplementation(async (url) => {
      const u = String(url);
      if (u.includes("/api/auth/refresh/")) {
        return new Response(JSON.stringify({ access: "existing-access" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (u.includes("/api/auth/me/")) {
        return new Response(
          JSON.stringify({
            id: "user-alice",
            email: "alice@fitgate.org",
            role: "reception",
            full_name: "Alice Reception",
            phone: "",
            gym_id: "gym-1",
            gym_name: "Bole Gym",
            gym_subdomain: "bole",
            date_joined: "2026-01-01T00:00:00Z",
            must_change_password: false,
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
                  <div>Reception Dashboard</div>
                </ProtectedRoute>
              }
            />
            <Route path="/login" element={<div>Login Page Target</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Reception Dashboard")).toBeInTheDocument();
    });

    // While tab was hidden, token was removed in storage
    localStorage.removeItem("fitgate_refresh_token");

    // Tab becomes visible again
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "visible",
    });

    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });

    await waitFor(() => {
      expect(screen.getByText("Login Page Target")).toBeInTheDocument();
      expect(
        screen.getByText("You were signed out from another tab.")
      ).toBeInTheDocument();
    });
  });

  it("handles remote broadcast via BroadcastChannel when supported", async () => {
    client.setRefreshToken("user-token");

    vi.spyOn(global, "fetch").mockImplementation(async (url) => {
      const u = String(url);
      if (u.includes("/api/auth/refresh/")) {
        return new Response(JSON.stringify({ access: "acc-1" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (u.includes("/api/auth/me/")) {
        return new Response(
          JSON.stringify({
            id: "user-initial",
            email: "init@fitgate.org",
            role: "member",
            full_name: "Initial User",
            phone: "",
            gym_id: "gym-1",
            gym_name: "Bole Gym",
            gym_subdomain: "bole",
            date_joined: "2026-01-01T00:00:00Z",
            must_change_password: false,
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
                  <div>Initial User Dashboard</div>
                </ProtectedRoute>
              }
            />
            <Route path="/login" element={<div>Login Page Target</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Initial User Dashboard")).toBeInTheDocument();
    });

    // Simulate logout broadcast via a BroadcastChannel message if BroadcastChannel exists
    if (typeof BroadcastChannel !== "undefined") {
      const channel = new BroadcastChannel(AUTH_BROADCAST_CHANNEL);
      await act(async () => {
        channel.postMessage({ type: "LOGOUT", timestamp: Date.now() });
      });
      channel.close();

      await waitFor(() => {
        expect(screen.getByText("Login Page Target")).toBeInTheDocument();
      });
    }
  });
});
