/**
 * FitGate API Client with in-memory access token and automatic single-flight refresh.
 *
 * TOKEN STORAGE ARCHITECTURE & RISK EXPLANATION:
 * - Access Token: Kept STRICTLY IN-MEMORY (JavaScript runtime variable).
 *   Never written to localStorage, sessionStorage, or cookies. It is short-lived (15 mins).
 * - Refresh Token: Stored in localStorage ('fitgate_refresh_token').
 *   Risk: localStorage is accessible to any script executing on the same origin (XSS vulnerability).
 *   Choice Rationale: The backend returns access and refresh tokens via JSON bodies (no httpOnly cookies).
 *   Without storing the refresh token in localStorage, users would be logged out on every page reload or tab switch.
 *   Mitigations: Short access token lifetime, immediate server-side revocation on logout/password change,
 *   and strict avoidance of unsafe eval or unvetted scripts.
 */

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

const REFRESH_TOKEN_KEY = "fitgate_refresh_token";

let inMemoryAccessToken: string | null = null;
let refreshPromise: Promise<string | null> | null = null;
let authFailureListeners: Array<() => void> = [];

export function getAccessToken(): string | null {
  return inMemoryAccessToken;
}

export function setAccessToken(token: string | null): void {
  inMemoryAccessToken = token;
}

export function getRefreshToken(): string | null {
  try {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setRefreshToken(token: string | null): void {
  try {
    if (token) {
      localStorage.setItem(REFRESH_TOKEN_KEY, token);
    } else {
      localStorage.removeItem(REFRESH_TOKEN_KEY);
    }
  } catch {
    // Ignore storage errors in restricted contexts
  }
}

export function clearTokens(): void {
  inMemoryAccessToken = null;
  try {
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  } catch {
    // Ignore
  }
}

export function onAuthFailure(callback: () => void): () => void {
  authFailureListeners.push(callback);
  return () => {
    authFailureListeners = authFailureListeners.filter((cb) => cb !== callback);
  };
}

function notifyAuthFailure(): void {
  clearTokens();
  authFailureListeners.forEach((cb) => {
    try {
      cb();
    } catch (e) {
      console.error("Auth failure listener error:", e);
    }
  });
}

/**
 * Execute token refresh with single-flight deduplication.
 * If multiple requests receive 401 simultaneously, only one refresh call is sent.
 */
export async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) {
    return refreshPromise;
  }

  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    notifyAuthFailure();
    return null;
  }

  refreshPromise = (async () => {
    try {
      const response = await fetch("/api/auth/refresh/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ refresh: refreshToken }),
      });

      if (!response.ok) {
        notifyAuthFailure();
        return null;
      }

      const data = (await response.json()) as { access: string };
      if (data && data.access) {
        setAccessToken(data.access);
        return data.access;
      } else {
        notifyAuthFailure();
        return null;
      }
    } catch {
      notifyAuthFailure();
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

/**
 * Core API request wrapper.
 * Automatically injects in-memory access token, intercepts 401s to refresh token, and retries.
 */
export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const currentToken = getAccessToken();
  if (currentToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${currentToken}`);
  }

  const response = await fetch(endpoint, {
    ...options,
    headers,
  });

  // Handle 401 Unauthorized for authenticated endpoints (except login & refresh itself)
  if (
    response.status === 401 &&
    endpoint !== "/api/auth/login/" &&
    endpoint !== "/api/auth/refresh/"
  ) {
    const newAccessToken = await refreshAccessToken();
    if (newAccessToken) {
      headers.set("Authorization", `Bearer ${newAccessToken}`);
      const retryResponse = await fetch(endpoint, {
        ...options,
        headers,
      });

      if (!retryResponse.ok) {
        let errData: unknown;
        try {
          errData = await retryResponse.json();
        } catch {
          errData = await retryResponse.text();
        }
        throw new ApiError(
          retryResponse.status,
          `HTTP ${retryResponse.status}`,
          errData
        );
      }

      if (retryResponse.status === 204) {
        return undefined as T;
      }
      return (await retryResponse.json()) as T;
    } else {
      throw new ApiError(401, "Session expired. Please log in again.");
    }
  }

  if (!response.ok) {
    let errData: unknown;
    try {
      errData = await response.json();
    } catch {
      errData = await response.text();
    }
    const message =
      typeof errData === "object" && errData !== null && "detail" in errData
        ? String((errData as { detail: unknown }).detail)
        : `HTTP ${response.status}`;
    throw new ApiError(response.status, message, errData);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
