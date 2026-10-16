/**
 * Utility to extract gym tenant subdomain from current browser location.
 *
 * Matching logic:
 * - If host is 'localhost' or an IP: returns null (apex platform).
 * - Suffix matching: if host ends with '.localhost' or '.<domain>':
 *   extracts the subdomain portion.
 */
export function getTenantFromHostname(hostname?: string): string | null {
  const host = (
    hostname || (typeof window !== "undefined" ? window.location.hostname : "")
  )
    .trim()
    .toLowerCase();

  if (!host || host === "localhost" || host === "127.0.0.1") {
    return null;
  }

  // Handle *.localhost (standard local dev for multi-tenancy)
  if (host.endsWith(".localhost")) {
    const parts = host.slice(0, -".localhost".length);
    // Ignore nested dots or empty
    if (!parts || parts.includes(".")) return null;
    return parts;
  }

  // Handle production or custom domains (e.g., gym1.fitgate.org)
  const parts = host.split(".");
  if (parts.length >= 3) {
    // If not www
    if (parts[0] !== "www") {
      return parts[0];
    }
  }

  return null;
}
