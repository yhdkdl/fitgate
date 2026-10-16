import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ForgotPasswordScreen } from "../screens/ForgotPasswordScreen";
import { ResetPasswordScreen } from "../screens/ResetPasswordScreen";

describe("Password Reset Screens", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("ForgotPasswordScreen sends request and displays uniform success message", async () => {
    vi.spyOn(global, "fetch").mockImplementationOnce(async (url) => {
      if (String(url).includes("/api/auth/password-reset/")) {
        return new Response(
          JSON.stringify({
            detail: "If the account exists, a reset link has been sent.",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      return new Response("Not found", { status: 404 });
    });

    render(
      <MemoryRouter initialEntries={["/forgot-password"]}>
        <ForgotPasswordScreen />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: "user@fitgate.org" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send reset link/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/if the account exists, a reset link has been sent/i)
      ).toBeInTheDocument();
    });
  });

  it("ResetPasswordScreen immediately removes token from address bar via history.replaceState", async () => {
    // Setup window.location with search param
    Object.defineProperty(window, "location", {
      value: new URL(
        "http://localhost:5173/reset-password?token=secret-token-123"
      ),
      writable: true,
      configurable: true,
    });

    const replaceStateSpy = vi.spyOn(window.history, "replaceState");

    render(
      <MemoryRouter initialEntries={["/reset-password?token=secret-token-123"]}>
        <ResetPasswordScreen />
      </MemoryRouter>
    );

    // Verify history.replaceState was called immediately on mount to strip the token from URL
    expect(replaceStateSpy).toHaveBeenCalledWith(
      {},
      document.title,
      "/reset-password"
    );

    // Form inputs should be visible and enabled
    expect(screen.getByLabelText(/^new password/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm new password/i)).toBeInTheDocument();
  });

  it("ResetPasswordScreen successfully submits new password with the stripped token", async () => {
    Object.defineProperty(window, "location", {
      value: new URL(
        "http://localhost:5173/reset-password?token=valid-secret-token"
      ),
      writable: true,
      configurable: true,
    });

    let submittedBody: Record<string, unknown> | null = null;

    vi.spyOn(global, "fetch").mockImplementationOnce(async (url, init) => {
      if (String(url).includes("/api/auth/password-reset/confirm/")) {
        submittedBody = JSON.parse(init?.body as string);
        return new Response(
          JSON.stringify({ detail: "password_reset_complete" }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      return new Response("Not found", { status: 404 });
    });

    render(
      <MemoryRouter
        initialEntries={["/reset-password?token=valid-secret-token"]}
      >
        <Routes>
          <Route path="/reset-password" element={<ResetPasswordScreen />} />
          <Route path="/login" element={<div>Sign In Screen</div>} />
        </Routes>
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText(/^new password/i), {
      target: { value: "NewStrongPassword123!" },
    });
    fireEvent.change(screen.getByLabelText(/confirm new password/i), {
      target: { value: "NewStrongPassword123!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /reset password/i }));

    await waitFor(() => {
      expect(screen.getByText(/password reset complete!/i)).toBeInTheDocument();
    });

    expect(submittedBody).toEqual({
      token: "valid-secret-token",
      new_password: "NewStrongPassword123!",
    });
  });
});
