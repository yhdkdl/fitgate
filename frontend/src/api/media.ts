/**
 * Authenticated Media and Download Helpers.
 *
 * Provides shared utilities to fetch protected files (e.g. member photos, future receipts)
 * using the application's authenticated API client (Authorization header, automatic token refresh),
 * in-page caching, and download handlers.
 */

import { apiFetchBlob } from "./client";

// In-memory cache of in-flight and resolved Blob promises to avoid repeated network requests within a page session
const blobCache = new Map<string, Promise<Blob>>();

/**
 * Clears the in-memory media cache.
 */
export function clearMediaCache(): void {
  blobCache.clear();
}

/**
 * Normalizes a URL by stripping any legacy ?token= query parameter.
 */
function cleanProtectedUrl(rawUrl: string): string {
  if (!rawUrl) return "";
  try {
    const parsed = new URL(rawUrl, window.location.origin);
    parsed.searchParams.delete("token");
    // If it's on the same origin or a relative path, use pathname + search
    if (parsed.origin === window.location.origin) {
      return parsed.pathname + (parsed.search ? parsed.search : "");
    }
    return parsed.toString();
  } catch {
    return rawUrl.split("?")[0];
  }
}

/**
 * Fetches a protected file with an authenticated API call (Authorization header + token refresh)
 * and returns a local object URL (blob:...).
 */
export async function fetchAuthenticatedBlobUrl(url: string): Promise<string> {
  if (!url) {
    throw new Error("No URL provided to fetchAuthenticatedBlobUrl.");
  }

  // If already a local blob URL or data URI, return immediately
  if (url.startsWith("blob:") || url.startsWith("data:")) {
    return url;
  }

  const cleanUrl = cleanProtectedUrl(url);

  let blobPromise = blobCache.get(cleanUrl);
  if (!blobPromise) {
    blobPromise = apiFetchBlob(cleanUrl);
    blobCache.set(cleanUrl, blobPromise);
  }

  try {
    const blob = await blobPromise;
    return URL.createObjectURL(blob);
  } catch (err) {
    // Evict failed requests so future attempts can retry
    blobCache.delete(cleanUrl);
    throw err;
  }
}

/**
 * Downloads a protected file (e.g. receipts in Sprint 12) using authenticated fetch.
 */
export async function downloadAuthenticatedFile(
  url: string,
  suggestedFilename?: string
): Promise<void> {
  const cleanUrl = cleanProtectedUrl(url);
  const blob = await apiFetchBlob(cleanUrl);
  const blobUrl = URL.createObjectURL(blob);

  const anchor = document.createElement("a");
  anchor.href = blobUrl;
  if (suggestedFilename) {
    anchor.download = suggestedFilename;
  }
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);

  // Revoke object URL after brief delay
  setTimeout(() => {
    URL.revokeObjectURL(blobUrl);
  }, 1000);
}
