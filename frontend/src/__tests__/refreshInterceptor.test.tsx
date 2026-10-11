import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  apiFetch,
  getAccessToken,
  getRefreshToken,
  onAuthFailure,
  setAccessToken,
  setRefreshToken,
  clearTokens,
} from "../api/client";

describe("API Client & Refresh Interceptor", () => {
  beforeEach(() => {
    clearTokens();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("transparently refreshes access token on 401 and retries original request", async () => {
    setAccessToken("expired-access-token");
    setRefreshToken("valid-refresh-token");

    let callCount = 0;
    let refreshCount = 0;

    vi.spyOn(global, "fetch").mockImplementation(async (url, init) => {
      const u = String(url);
      if (u.includes("/api/auth/refresh/")) {
        refreshCount++;
        return new Response(JSON.stringify({ access: "fresh-new-token" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (u.includes("/api/test-data/")) {
        callCount++;
        const authHeader = (init?.headers as Headers)?.get("Authorization");
        if (callCount === 1) {
          expect(authHeader).toBe("Bearer expired-access-token");
          return new Response(JSON.stringify({ detail: "Token expired" }), {
            status: 401,
            headers: { "Content-Type": "application/json" },
          });
        }
        // Second call after refresh
        expect(authHeader).toBe("Bearer fresh-new-token");
        return new Response(JSON.stringify({ result: "success" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response("Not found", { status: 404 });
    });

    const data = await apiFetch<{ result: string }>("/api/test-data/");
    expect(data.result).toBe("success");
    expect(refreshCount).toBe(1);
    expect(callCount).toBe(2);
    expect(getAccessToken()).toBe("fresh-new-token");
  });

  it("deduplicates concurrent 401s so only one in-flight refresh request is executed", async () => {
    setAccessToken("expired-access-token");
    setRefreshToken("valid-refresh-token");

    let refreshCount = 0;

    vi.spyOn(global, "fetch").mockImplementation(async (url, init) => {
      const u = String(url);
      if (u.includes("/api/auth/refresh/")) {
        refreshCount++;
        // Simulate small network delay
        await new Promise((resolve) => setTimeout(resolve, 20));
        return new Response(
          JSON.stringify({ access: "shared-refreshed-token" }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }
        );
      }

      if (u.includes("/api/endpoint-")) {
        const authHeader = (init?.headers as Headers)?.get("Authorization");
        if (authHeader === "Bearer expired-access-token") {
          return new Response(JSON.stringify({ detail: "Token expired" }), {
            status: 401,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(JSON.stringify({ source: u }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }

      return new Response("Not found", { status: 404 });
    });

    // Fire two concurrent requests that both receive 401
    const [res1, res2] = await Promise.all([
      apiFetch<{ source: string }>("/api/endpoint-1/"),
      apiFetch<{ source: string }>("/api/endpoint-2/"),
    ]);

    expect(res1.source).toBe("/api/endpoint-1/");
    expect(res2.source).toBe("/api/endpoint-2/");
    // Crucial requirement: exactly ONE refresh request dispatched for multiple in-flight 401s
    expect(refreshCount).toBe(1);
    expect(getAccessToken()).toBe("shared-refreshed-token");
  });

  it("clears tokens and notifies listeners on refresh failure", async () => {
    setAccessToken("bad-access-token");
    setRefreshToken("expired-refresh-token");

    let failureNotified = false;
    const unsubscribe = onAuthFailure(() => {
      failureNotified = true;
    });

    vi.spyOn(global, "fetch").mockImplementation(async (url) => {
      const u = String(url);
      if (u.includes("/api/auth/refresh/")) {
        return new Response(JSON.stringify({ detail: "Token is invalid" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify({ detail: "Unauthorized" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      });
    });

    await expect(apiFetch("/api/protected/")).rejects.toThrow();

    expect(failureNotified).toBe(true);
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();

    unsubscribe();
  });
});
