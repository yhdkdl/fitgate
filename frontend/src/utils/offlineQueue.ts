import { scanQrToken, type ScanResultMember } from "../api/attendance";
import { ApiError } from "../api/client";

export interface QueuedCheckIn {
  id: string;
  token: string;
  scanned_at: string;
  client_timestamp: number;
  attempts: number;
}

export interface ReplaySyncEvent {
  id: string;
  token: string;
  status: "success" | "already_checked_in" | "refused" | "network_error";
  reason?: string;
  detail?: string;
  member?: ScanResultMember;
}

const DB_NAME = "fitgate_offline_db";
const DB_VERSION = 1;
const STORE_NAME = "checkin_queue";

// In-memory fallback for environments without IndexedDB (e.g. testing)
const memoryStore: Map<string, QueuedCheckIn> = new Map();

/**
 * Open or initialize IndexedDB
 */
export function openOfflineDb(): Promise<IDBDatabase | null> {
  if (typeof indexedDB === "undefined") {
    return Promise.resolve(null);
  }

  return new Promise((resolve, reject) => {
    try {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME, { keyPath: "id" });
        }
      };

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    } catch {
      reject(err);
    }
  });
}

/**
 * Validate token payload expiration locally without secret.
 */
export function validateOfflineToken(token: string): {
  valid: boolean;
  reason?: string;
  memberId?: string;
} {
  try {
    const parts = token.trim().split(".");
    if (parts.length < 2) {
      return { valid: false, reason: "invalid_token" };
    }
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const jsonStr = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );
    const payload = JSON.parse(jsonStr);

    if (payload.exp && typeof payload.exp === "number") {
      const nowSeconds = Math.floor(Date.now() / 1000);
      if (payload.exp < nowSeconds) {
        return { valid: false, reason: "token_expired" };
      }
    }

    return {
      valid: true,
      memberId: payload.sub || payload.member_id,
    };
  } catch {
    return { valid: false, reason: "invalid_token" };
  }
}

/**
 * Enqueue a scanned check-in into IndexedDB.
 */
export async function enqueueCheckIn(token: string): Promise<QueuedCheckIn> {
  const tokenStr = token.trim();
  const id =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `offline_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;

  const record: QueuedCheckIn = {
    id,
    token: tokenStr,
    scanned_at: new Date().toISOString(),
    client_timestamp: Date.now(),
    attempts: 0,
  };

  const db = await openOfflineDb().catch(() => null);
  if (!db) {
    memoryStore.set(id, record);
    return record;
  }

  return new Promise((resolve, reject) => {
    try {
      const tx = db.transaction(STORE_NAME, "readwrite");
      const store = tx.objectStore(STORE_NAME);
      const req = store.put(record);

      req.onsuccess = () => resolve(record);
      req.onerror = () => reject(req.error);
    } catch {
      memoryStore.set(id, record);
      resolve(record);
    }
  });
}

/**
 * Retrieve all queued check-ins ordered by client_timestamp.
 */
export async function getQueuedCheckIns(): Promise<QueuedCheckIn[]> {
  const db = await openOfflineDb().catch(() => null);
  if (!db) {
    return Array.from(memoryStore.values()).sort(
      (a, b) => a.client_timestamp - b.client_timestamp
    );
  }

  return new Promise((resolve, reject) => {
    try {
      const tx = db.transaction(STORE_NAME, "readonly");
      const store = tx.objectStore(STORE_NAME);
      const req = store.getAll();

      req.onsuccess = () => {
        const results = (req.result as QueuedCheckIn[]) || [];
        results.sort((a, b) => a.client_timestamp - b.client_timestamp);
        resolve(results);
      };
      req.onerror = () => reject(req.error);
    } catch {
      resolve(Array.from(memoryStore.values()));
    }
  });
}

/**
 * Remove a specific queued check-in by id after successful sync or permanent refusal.
 */
export async function removeQueuedCheckIn(id: string): Promise<void> {
  const db = await openOfflineDb().catch(() => null);
  if (!db) {
    memoryStore.delete(id);
    return;
  }

  return new Promise((resolve, reject) => {
    try {
      const tx = db.transaction(STORE_NAME, "readwrite");
      const store = tx.objectStore(STORE_NAME);
      const req = store.delete(id);

      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    } catch {
      memoryStore.delete(id);
      resolve();
    }
  });
}

/**
 * Clear the entire offline check-in queue (called on logout to prevent cross-account leak).
 */
export async function clearOfflineQueue(): Promise<void> {
  memoryStore.clear();

  const db = await openOfflineDb().catch(() => null);
  if (!db) return;

  return new Promise((resolve, reject) => {
    try {
      const tx = db.transaction(STORE_NAME, "readwrite");
      const store = tx.objectStore(STORE_NAME);
      const req = store.clear();

      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    } catch {
      resolve();
    }
  });
}

let isReplaying = false;

/**
 * Replay queued check-ins through the single shared execute_check_in backend engine.
 */
export async function replayOfflineQueue(
  onProgress?: (event: ReplaySyncEvent) => void
): Promise<{ processed: number; succeeded: number; failed: number }> {
  if (isReplaying) {
    return { processed: 0, succeeded: 0, failed: 0 };
  }

  // If browser reports offline, defer sync
  if (typeof navigator !== "undefined" && !navigator.onLine) {
    return { processed: 0, succeeded: 0, failed: 0 };
  }

  isReplaying = true;
  let processed = 0;
  let succeeded = 0;
  let failed = 0;

  try {
    const queue = await getQueuedCheckIns();
    if (queue.length === 0) {
      return { processed: 0, succeeded: 0, failed: 0 };
    }

    for (const item of queue) {
      processed++;
      try {
        await scanQrToken({ token: item.token });
        // Successfully scanned
        await removeQueuedCheckIn(item.id);
        succeeded++;
        onProgress?.({
          id: item.id,
          token: item.token,
          status: "success",
        });
      } catch (err: unknown) {
        if (err instanceof ApiError && err.status === 400) {
          const reason = (err.data?.reason as string) || "checkin_refused";
          const detail = (err.data?.detail as string) || err.message;
          const member = err.data?.member as ScanResultMember | undefined;

          // If already checked in today: remove from queue (ensuring exactly 1 attendance row)
          if (reason === "already_checked_in") {
            await removeQueuedCheckIn(item.id);
            succeeded++;
            onProgress?.({
              id: item.id,
              token: item.token,
              status: "already_checked_in",
              reason,
              detail,
              member,
            });
            continue;
          }

          // Refusals (frozen, suspended, pending, superseded, expired, pending_review, token_expired, token_consumed)
          // Permanently remove from queue so it does not loop, and notify staff of refusal
          await removeQueuedCheckIn(item.id);
          failed++;
          onProgress?.({
            id: item.id,
            token: item.token,
            status: "refused",
            reason,
            detail,
            member,
          });
        } else {
          // Network failure or 5xx: keep in queue for next sync window
          onProgress?.({
            id: item.id,
            token: item.token,
            status: "network_error",
            detail: err instanceof Error ? err.message : "Network error",
          });
          // Abort further replay while offline
          break;
        }
      }
    }
  } finally {
    isReplaying = false;
  }

  return { processed, succeeded, failed };
}

/**
 * Setup listeners for online event, tab visibility, window focus, and 5-second interval.
 */
export function setupOfflineSyncListener(
  onProgress?: (event: ReplaySyncEvent) => void
): () => void {
  if (typeof window === "undefined") {
    return () => {};
  }

  const triggerReplay = () => {
    if (typeof navigator !== "undefined" && navigator.onLine) {
      replayOfflineQueue(onProgress).catch(() => {});
    }
  };

  const handleOnline = () => triggerReplay();
  const handleVisibility = () => {
    if (typeof document !== "undefined" && document.visibilityState === "visible") {
      triggerReplay();
    }
  };
  const handleFocus = () => triggerReplay();

  window.addEventListener("online", handleOnline);
  if (typeof document !== "undefined") {
    document.addEventListener("visibilitychange", handleVisibility);
  }
  window.addEventListener("focus", handleFocus);

  // Periodic 5-second sync check when items exist in queue
  const intervalId = setInterval(async () => {
    if (typeof navigator !== "undefined" && navigator.onLine) {
      const items = await getQueuedCheckIns();
      if (items.length > 0) {
        triggerReplay();
      }
    }
  }, 5000);

  return () => {
    window.removeEventListener("online", handleOnline);
    if (typeof document !== "undefined") {
      document.removeEventListener("visibilitychange", handleVisibility);
    }
    window.removeEventListener("focus", handleFocus);
    clearInterval(intervalId);
  };
}
