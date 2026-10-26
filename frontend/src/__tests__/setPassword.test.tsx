import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as gymsApi from "../api/gyms";
import { SetPasswordScreen } from "../screens/SetPasswordScreen";

vi.mock("../api/gyms", () => ({
  setPasswordFromInvite: vi.fn(),
}));

describe("SetPasswordScreen", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("reads invite token from URL and immediately removes it from address bar", () => {
    window.history.pushState(
      {},
      "",
      "/set-password?token=secretInviteToken999"
    );
    const replaceStateSpy = vi.spyOn(window.history, "replaceState");

    render(
      <BrowserRouter>
        <SetPasswordScreen />
      </BrowserRouter>
    );

    expect(replaceStateSpy).toHaveBeenCalledWith(
      {},
      expect.any(String),
      "/set-password"
    );
  });

  it("validates password length and match before calling API", async () => {
    window.history.pushState(
      {},
      "",
      "/set-password?token=secretInviteToken999"
    );

    render(
      <BrowserRouter>
        <SetPasswordScreen />
      </BrowserRouter>
    );

    const submitBtn = screen.getByRole("button", {
      name: /activate account & set password/i,
    });

    // Too short
    await userEvent.type(screen.getByLabelText(/^new password/i), "short1");
    await userEvent.type(screen.getByLabelText(/^confirm password/i), "short1");
    fireEvent.click(submitBtn);

    expect(
      await screen.findByText(/password must be at least 10 characters long/i)
    ).toBeInTheDocument();
    expect(gymsApi.setPasswordFromInvite).not.toHaveBeenCalled();

    // Mismatched passwords
    await userEvent.clear(screen.getByLabelText(/^new password/i));
    await userEvent.clear(screen.getByLabelText(/^confirm password/i));
    await userEvent.type(
      screen.getByLabelText(/^new password/i),
      "SecretPassword123!"
    );
    await userEvent.type(
      screen.getByLabelText(/^confirm password/i),
      "DifferentPassword123!"
    );
    fireEvent.click(submitBtn);

    const mismatchErrors = await screen.findAllByText(
      /passwords do not match/i
    );
    expect(mismatchErrors.length).toBeGreaterThan(0);
    expect(gymsApi.setPasswordFromInvite).not.toHaveBeenCalled();
  });

  it("submits valid password and displays success confirmation with link to sign in", async () => {
    window.history.pushState(
      {},
      "",
      "/set-password?token=secretInviteToken999"
    );
    vi.mocked(gymsApi.setPasswordFromInvite).mockResolvedValue({
      detail: "password_set_complete",
    });

    render(
      <BrowserRouter>
        <SetPasswordScreen />
      </BrowserRouter>
    );

    await userEvent.type(
      screen.getByLabelText(/^new password/i),
      "ValidStrongPassword123!"
    );
    await userEvent.type(
      screen.getByLabelText(/^confirm password/i),
      "ValidStrongPassword123!"
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: /activate account & set password/i,
      })
    );

    await waitFor(() => {
      expect(gymsApi.setPasswordFromInvite).toHaveBeenCalledWith(
        "secretInviteToken999",
        "ValidStrongPassword123!"
      );
    });

    expect(
      await screen.findByText(/your password has been successfully set/i)
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /proceed to sign in/i })
    ).toBeInTheDocument();
  });

  it("displays clear security verification message when backend returns 503 still_securing", async () => {
    window.history.pushState(
      {},
      "",
      "/set-password?token=secretInviteToken999"
    );
    vi.mocked(gymsApi.setPasswordFromInvite).mockRejectedValue({
      status: 503,
      data: { detail: "still_securing" },
    });

    render(
      <BrowserRouter>
        <SetPasswordScreen />
      </BrowserRouter>
    );

    await userEvent.type(
      screen.getByLabelText(/^new password/i),
      "ValidStrongPassword123!"
    );
    await userEvent.type(
      screen.getByLabelText(/^confirm password/i),
      "ValidStrongPassword123!"
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: /activate account & set password/i,
      })
    );

    expect(
      await screen.findByText(
        /currently being secured with an SSL certificate/i
      )
    ).toBeInTheDocument();
  });

  it("displays expired message when invite token has expired", async () => {
    window.history.pushState(
      {},
      "",
      "/set-password?token=secretInviteToken999"
    );
    vi.mocked(gymsApi.setPasswordFromInvite).mockRejectedValue({
      status: 400,
      data: { detail: "token_expired" },
    });

    render(
      <BrowserRouter>
        <SetPasswordScreen />
      </BrowserRouter>
    );

    await userEvent.type(
      screen.getByLabelText(/^new password/i),
      "ValidStrongPassword123!"
    );
    await userEvent.type(
      screen.getByLabelText(/^confirm password/i),
      "ValidStrongPassword123!"
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: /activate account & set password/i,
      })
    );

    expect(
      await screen.findByText(/this invitation link has expired/i)
    ).toBeInTheDocument();
  });
});
