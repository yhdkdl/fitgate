import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch, ApiError } from "../api/client";
import { MemberQrCard } from "../components/attendance/MemberQrCard";

describe("apiFetch & ApiError handling", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("exercises real apiFetch with mocked global fetch returning 400 JSON and preserves detail and reason", async () => {
    const errorBody = {
      detail: "Member subscription has expired.",
      reason: "expired",
    };

    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(errorBody), {
        status: 400,
        statusText: "Bad Request",
        headers: { "Content-Type": "application/json" },
      })
    );

    let caughtError: unknown;
    try {
      await apiFetch("/api/members/me/qr-token/");
    } catch (err) {
      caughtError = err;
    }

    expect(caughtError).toBeInstanceOf(ApiError);
    const apiError = caughtError as ApiError;
    expect(apiError.status).toBe(400);
    expect(apiError.reason).toBe("expired");
    expect(apiError.detail).toBe("Member subscription has expired.");
    expect(apiError.message).toBe("Member subscription has expired.");
    expect(apiError.data).toEqual(errorBody);
  });

  it("handles non-JSON error bodies (plain text / HTML) without throwing body stream already read", async () => {
    const htmlBody = "<html><body>502 Bad Gateway</body></html>";

    global.fetch = vi.fn().mockResolvedValue(
      new Response(htmlBody, {
        status: 502,
        statusText: "Bad Gateway",
        headers: { "Content-Type": "text/html" },
      })
    );

    let caughtError: unknown;
    try {
      await apiFetch("/api/some-endpoint/");
    } catch (err) {
      caughtError = err;
    }

    expect(caughtError).toBeInstanceOf(ApiError);
    const apiError = caughtError as ApiError;
    expect(apiError.status).toBe(502);
    expect(apiError.message).toBe(htmlBody);
    expect(apiError.data).toBe(htmlBody);
    expect(apiError.message).not.toContain("body stream already read");
  });

  it("handles empty error bodies gracefully without throwing body stream already read", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response("", {
        status: 404,
        statusText: "Not Found",
      })
    );

    let caughtError: unknown;
    try {
      await apiFetch("/api/non-existent/");
    } catch (err) {
      caughtError = err;
    }

    expect(caughtError).toBeInstanceOf(ApiError);
    const apiError = caughtError as ApiError;
    expect(apiError.status).toBe(404);
    expect(apiError.message).toBe("HTTP 404");
    expect(apiError.data).toBeNull();
    expect(apiError.message).not.toContain("body stream already read");
  });

  it("renders QR pass card using real api layer (mock only fetch) and displays Pass Unavailable (expired)", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: "Member subscription has expired.",
          reason: "expired",
        }),
        {
          status: 400,
          statusText: "Bad Request",
          headers: { "Content-Type": "application/json" },
        }
      )
    );

    render(<MemberQrCard memberStatus="expired" />);

    expect(
      await screen.findByText("Pass Unavailable (expired)")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Member subscription has expired.")
    ).toBeInTheDocument();
    expect(screen.queryByText(/body stream already read/i)).not.toBeInTheDocument();
  });
});
