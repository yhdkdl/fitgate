import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../context/AuthContext";
import { ProfileScreen } from "../screens/ProfileScreen";
import * as client from "../api/client";

describe("ProfileScreen", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    client.clearTokens();
    client.setRefreshToken("mock-refresh");
    vi.restoreAllMocks();
  });

  it("loads and displays user profile and allows editing name and phone", async () => {
    let patchPayload: Record<string, unknown> | null = null;

    vi.spyOn(global, "fetch").mockImplementation(async (url, init) => {
      const u = String(url);
      if (u.includes("/api/auth/refresh/")) {
        return new Response(JSON.stringify({ access: "refreshed-access" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (u.includes("/api/auth/me/") && (!init || init.method === "GET")) {
        return new Response(
          JSON.stringify({
            id: "user-1",
            email: "trainer@fitgate.org",
            role: "trainer",
            full_name: "Original Name",
            phone: "+251911111111",
            must_change_password: false,
            gym_id: "gym-1",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      if (u.includes("/api/auth/me/") && init?.method === "PATCH") {
        patchPayload = JSON.parse(init.body as string);
        return new Response(
          JSON.stringify({
            id: "user-1",
            email: "trainer@fitgate.org",
            role: "trainer",
            full_name: "Updated Name",
            phone: "+251922222222",
            must_change_password: false,
            gym_id: "gym-1",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      return new Response("Not found", { status: 404 });
    });

    render(
      <MemoryRouter initialEntries={["/profile"]}>
        <AuthProvider>
          <ProfileScreen />
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByDisplayValue("Original Name")).toBeInTheDocument();
      expect(screen.getByDisplayValue("+251911111111")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/full name/i), {
      target: { value: "Updated Name" },
    });
    fireEvent.change(screen.getByLabelText(/phone number/i), {
      target: { value: "+251922222222" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save profile/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Profile details updated successfully.")
      ).toBeInTheDocument();
    });

    expect(patchPayload).toEqual({
      full_name: "Updated Name",
      phone: "+251922222222",
    });
  });

  it("allows changing password with current and new passwords", async () => {
    let changePayload: Record<string, unknown> | null = null;

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
            email: "owner@fitgate.org",
            role: "owner",
            full_name: "Gym Owner",
            phone: "",
            must_change_password: false,
            gym_id: "gym-1",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      if (u.includes("/api/auth/change-password/")) {
        changePayload = JSON.parse(init?.body as string);
        return new Response(
          JSON.stringify({
            access: "brand-new-access",
            refresh: "brand-new-refresh",
            user: {
              id: "user-1",
              email: "owner@fitgate.org",
              role: "owner",
              full_name: "Gym Owner",
              phone: "",
              must_change_password: false,
              gym_id: "gym-1",
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      return new Response("Not found", { status: 404 });
    });

    render(
      <MemoryRouter initialEntries={["/profile"]}>
        <AuthProvider>
          <ProfileScreen />
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Change Password")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/current password/i), {
      target: { value: "CurrentSecretPassword123!" },
    });
    fireEvent.change(screen.getByLabelText(/^new password/i), {
      target: { value: "BrandNewSecretPassword123!" },
    });
    fireEvent.change(screen.getByLabelText(/confirm new password/i), {
      target: { value: "BrandNewSecretPassword123!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /update password/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Password updated successfully.")
      ).toBeInTheDocument();
    });

    expect(changePayload).toEqual({
      current_password: "CurrentSecretPassword123!",
      new_password: "BrandNewSecretPassword123!",
    });
    expect(client.getAccessToken()).toBe("brand-new-access");
  });
});
