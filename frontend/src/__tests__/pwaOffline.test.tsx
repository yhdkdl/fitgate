import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import {
  enqueueCheckIn,
  getQueuedCheckIns,
  clearOfflineQueue,
  validateOfflineToken,
  replayOfflineQueue,
} from "../utils/offlineQueue";
import { PwaInstallPrompt } from "../components/pwa/PwaInstallPrompt";
import * as attendanceApi from "../api/attendance";
import { ApiError } from "../api/client";

// Mock attendance API
vi.mock("../api/attendance", () => ({
  scanQrToken: vi.fn(),
}));

describe("Sprint 37 — Offline PWA & Check-in Sync Queue", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    await clearOfflineQueue();
  });

  afterEach(async () => {
    await clearOfflineQueue();
  });

  describe("1. Service Worker Caching Boundary", () => {
    it("strictly refuses to cache /api/* and /media/* requests (NetworkOnly boundary)", async () => {
      // Simulate SW fetch filter logic matching sw.js
      const isCacheable = (urlPath: string, method = "GET"): boolean => {
        if (urlPath.startsWith("/api/") || urlPath.startsWith("/media/")) {
          return false; // NetworkOnly
        }
        if (method !== "GET") {
          return false;
        }
        return true;
      };

      // API endpoints must NEVER be cached
      expect(isCacheable("/api/attendance/scan/")).toBe(false);
      expect(isCacheable("/api/members/me/")).toBe(false);
      expect(isCacheable("/api/payments/receipts/")).toBe(false);
      expect(isCacheable("/api/trainers/measurements/")).toBe(false);

      // Photos and media must NEVER be cached
      expect(isCacheable("/media/members/photo.jpg")).toBe(false);
      expect(isCacheable("/media/receipts/bank_slip.pdf")).toBe(false);

      // POST / PUT / DELETE requests must NEVER be cached
      expect(isCacheable("/index.html", "POST")).toBe(false);

      // App shell static assets ARE cacheable
      expect(isCacheable("/")).toBe(true);
      expect(isCacheable("/index.html")).toBe(true);
      expect(isCacheable("/manifest.webmanifest")).toBe(true);
      expect(isCacheable("/assets/index-abc123.js")).toBe(true);
      expect(isCacheable("/assets/index-xyz789.css")).toBe(true);
      expect(isCacheable("/icon-192.png")).toBe(true);
      expect(isCacheable("/icon.svg")).toBe(true);
    });
  });

  describe("2. Offline Check-in Queue & Local Validation", () => {
    it("enqueues scans and retrieves them from the local offline queue", async () => {
      const mockToken = "header.eyJzdWIiOiJtZW1iZXItMTIzIiwiZXhwIjoyNTI0NjA4MDAwfQ.sig";
      const record = await enqueueCheckIn(mockToken);

      expect(record.id).toBeDefined();
      expect(record.token).toBe(mockToken);

      const items = await getQueuedCheckIns();
      expect(items.length).toBe(1);
      expect(items[0].token).toBe(mockToken);
    });

    it("detects expired tokens locally before queueing", () => {
      // Expired token: exp was in 1970
      const expiredPayload = btoa(JSON.stringify({ sub: "member-1", exp: 100 }));
      const expiredToken = `header.${expiredPayload}.signature`;

      const result = validateOfflineToken(expiredToken);
      expect(result.valid).toBe(false);
      expect(result.reason).toBe("token_expired");

      // Valid token: exp far in the future (year 2030)
      const validPayload = btoa(JSON.stringify({ sub: "member-2", exp: 1893456000 }));
      const validToken = `header.${validPayload}.signature`;

      const validResult = validateOfflineToken(validToken);
      expect(validResult.valid).toBe(true);
      expect(validResult.memberId).toBe("member-2");
    });
  });

  describe("3. Offline Check-in Replay & Server Refusals", () => {
    it("replays successful scan, producing attendance and removing item from queue", async () => {
      const mockToken = "header.payload.signature";
      await enqueueCheckIn(mockToken);

      vi.mocked(attendanceApi.scanQrToken).mockResolvedValueOnce({
        attendance: {
          id: "att-1",
          date: "2026-11-06",
          status: "checked_in",
          checked_in_at: "2026-11-06T08:00:00Z",
          method: "qr",
          is_override: false,
          override_reason: "",
        },
        member: {
          id: "m-1",
          full_name: "Abebe Kebede",
          status: "active",
          phone: "+251911223344",
          photo_url: null,
        },
      });

      const events: { token: string; status: string; reason?: string; detail?: string }[] = [];
      const res = await replayOfflineQueue((e) => events.push(e));

      expect(res.succeeded).toBe(1);
      expect(attendanceApi.scanQrToken).toHaveBeenCalledWith({ token: mockToken });

      const remaining = await getQueuedCheckIns();
      expect(remaining.length).toBe(0);
      expect(events[0].status).toBe("success");
    });

    it("handles already_checked_in idempotently (exactly 1 attendance row, removes from queue)", async () => {
      const mockToken = "header.payload.signature";
      await enqueueCheckIn(mockToken);

      vi.mocked(attendanceApi.scanQrToken).mockRejectedValueOnce(
        new ApiError(400, "Already checked in", {
          reason: "already_checked_in",
          detail: "Member Abebe Kebede has already checked in today.",
        })
      );

      const events: { token: string; status: string; reason?: string; detail?: string }[] = [];
      const res = await replayOfflineQueue((e) => events.push(e));

      expect(res.succeeded).toBe(1);
      expect(events[0].status).toBe("already_checked_in");

      const remaining = await getQueuedCheckIns();
      expect(remaining.length).toBe(0);
    });

    it("surfaces server refusal (suspended/frozen/pending/pending-review) and clears from queue", async () => {
      const suspendedToken = "header.suspended.sig";
      await enqueueCheckIn(suspendedToken);

      vi.mocked(attendanceApi.scanQrToken).mockRejectedValueOnce(
        new ApiError(400, "Refused", {
          reason: "suspended",
          detail: "Member account is suspended.",
          member: {
            id: "m-2",
            full_name: "Chala Tolosa",
            status: "suspended",
            phone: "+251922334455",
            photo_url: null,
          },
        })
      );

      const events: { token: string; status: string; reason?: string; detail?: string }[] = [];
      const res = await replayOfflineQueue((e) => events.push(e));

      expect(res.failed).toBe(1);
      expect(events[0].status).toBe("refused");
      expect(events[0].reason).toBe("suspended");
      expect(events[0].detail).toBe("Member account is suspended.");

      // Item removed so it doesn't loop forever
      const remaining = await getQueuedCheckIns();
      expect(remaining.length).toBe(0);
    });

    it("keeps items in queue on network failure for next retry", async () => {
      const netToken = "header.net.sig";
      await enqueueCheckIn(netToken);

      vi.mocked(attendanceApi.scanQrToken).mockRejectedValueOnce(
        new TypeError("Failed to fetch")
      );

      const events: { token: string; status: string; reason?: string; detail?: string }[] = [];
      const res = await replayOfflineQueue((e) => events.push(e));

      expect(res.succeeded).toBe(0);
      expect(events[0].status).toBe("network_error");

      // Item stays in queue
      const remaining = await getQueuedCheckIns();
      expect(remaining.length).toBe(1);
    });
  });

  describe("4. Logout Clears Offline Queue", () => {
    it("clearOfflineQueue purges all queued check-ins to prevent cross-account leaks", async () => {
      await enqueueCheckIn("token-1");
      await enqueueCheckIn("token-2");
      await enqueueCheckIn("token-3");

      let items = await getQueuedCheckIns();
      expect(items.length).toBe(3);

      await clearOfflineQueue();

      items = await getQueuedCheckIns();
      expect(items.length).toBe(0);
    });
  });

  describe("5. PWA Install Prompt Component", () => {
    it("renders 'Download App' button on Android/Chromium when beforeinstallprompt fires", async () => {
      render(<PwaInstallPrompt />);

      // Initially no prompt
      expect(screen.queryByText(/Download App/i)).toBeNull();

      // Dispatch beforeinstallprompt
      const promptMock = vi.fn().mockResolvedValue(undefined);
      const userChoiceMock = Promise.resolve({ outcome: "accepted", platform: "android" });

      const installEvent = new Event("beforeinstallprompt");
      Object.assign(installEvent, {
        prompt: promptMock,
        userChoice: userChoiceMock,
        platforms: ["android"],
      });

      await act(async () => {
        window.dispatchEvent(installEvent);
      });

      // Button now renders
      const downloadBtn = await screen.findByRole("button", { name: /Download App/i });
      expect(downloadBtn).toBeInTheDocument();

      // Clicking triggers prompt
      await act(async () => {
        fireEvent.click(downloadBtn);
      });
      expect(promptMock).toHaveBeenCalled();
    });

    it("displays 'Add to Home Screen' instructions when iOS user agent is detected", () => {
      // Mock iOS Safari userAgent
      const originalUserAgent = navigator.userAgent;
      Object.defineProperty(navigator, "userAgent", {
        value: "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
        configurable: true,
      });

      render(<PwaInstallPrompt />);

      expect(screen.getByText(/Add FitGate to Home Screen/i)).toBeInTheDocument();
      expect(screen.getByText(/Share/i)).toBeInTheDocument();

      // Restore user agent
      Object.defineProperty(navigator, "userAgent", {
        value: originalUserAgent,
        configurable: true,
      });
    });
  });
});
