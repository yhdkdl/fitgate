import type { DashboardConfig, UserProfile, UserSummary } from "../api/auth";

export const AUTH_SYNC_STORAGE_KEY = "fitgate_auth_sync";
export const AUTH_BROADCAST_CHANNEL = "fitgate_auth_channel";

export interface AuthSyncMessage {
  type: "LOGIN" | "LOGOUT" | "UPDATE_PROFILE";
  user?: UserSummary | UserProfile | null;
  dashboard?: DashboardConfig | null;
  refreshToken?: string | null;
  timestamp: number;
}

/**
 * Broadcast an authentication event to other open tabs via BroadcastChannel and localStorage.
 */
export function broadcastAuthSync(
  event: Omit<AuthSyncMessage, "timestamp">
): void {
  const message: AuthSyncMessage = {
    ...event,
    timestamp: Date.now(),
  };

  // 1. BroadcastChannel (supported in modern browsers)
  if (typeof BroadcastChannel !== "undefined") {
    try {
      const channel = new BroadcastChannel(AUTH_BROADCAST_CHANNEL);
      channel.postMessage(message);
      channel.close();
    } catch {
      // Ignore broadcast errors in restricted environments
    }
  }

  // 2. localStorage (fires the 'storage' event across other tabs)
  if (typeof localStorage !== "undefined") {
    try {
      if (event.type === "LOGOUT") {
        localStorage.removeItem(AUTH_SYNC_STORAGE_KEY);
      } else {
        localStorage.setItem(AUTH_SYNC_STORAGE_KEY, JSON.stringify(message));
      }
    } catch {
      // Ignore storage write errors
    }
  }
}

/**
 * Read the current auth sync state from localStorage.
 */
export function getStoredAuthSync(): AuthSyncMessage | null {
  if (typeof localStorage === "undefined") return null;
  try {
    const raw = localStorage.getItem(AUTH_SYNC_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as AuthSyncMessage) : null;
  } catch {
    return null;
  }
}

/**
 * Clear the stored auth sync state from localStorage.
 */
export function clearStoredAuthSync(): void {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.removeItem(AUTH_SYNC_STORAGE_KEY);
  } catch {
    // Ignore storage errors
  }
}
