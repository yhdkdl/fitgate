/**
 * Utility to extract gym tenant subdomain from current browser location
 * and helpers for dynamic subdomain navigation.
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

  // Check optional configured domain in env
  const metaEnv =
    typeof import.meta !== "undefined"
      ? (import.meta as unknown as { env?: Record<string, string> }).env
      : undefined;
  const configuredDomain = metaEnv?.VITE_DOMAIN || "";
  const cleanConfigured = configuredDomain.trim().toLowerCase();

  if (cleanConfigured) {
    if (host === cleanConfigured || host === `www.${cleanConfigured}`) {
      return null;
    }
    if (host.endsWith(`.${cleanConfigured}`)) {
      const sub = host.slice(0, -cleanConfigured.length - 1);
      if (sub && !sub.includes(".")) return sub;
      return null;
    }
  }

  // Platform apex domains
  if (
    host === "fitgate.tebebtech.com" ||
    host === "www.fitgate.tebebtech.com"
  ) {
    return null;
  }

  // Handle *.localhost (standard local dev for multi-tenancy)
  if (host.endsWith(".localhost")) {
    const parts = host.slice(0, -".localhost".length);
    if (!parts || parts.includes(".")) return null;
    return parts;
  }

  // Handle *.fitgate.tebebtech.com
  if (host.endsWith(".fitgate.tebebtech.com")) {
    const parts = host.slice(0, -".fitgate.tebebtech.com".length);
    if (!parts || parts.includes(".")) return null;
    return parts;
  }

  // Generic fallback for custom domains (e.g., gym1.example.org)
  const parts = host.split(".");
  if (parts.length >= 3) {
    if (parts[0] !== "www") {
      return parts[0];
    }
  }

  return null;
}

export const RESERVED_SUBDOMAINS = new Set([
  "api",
  "admin",
  "www",
  "app",
  "mail",
  "localhost",
]);

const SUBDOMAIN_REGEX = /^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$/;

/**
 * Validates a gym subdomain input string.
 * Returns valid status and user-facing error message if invalid.
 */
export function validateSubdomain(rawSubdomain: string): {
  valid: boolean;
  error?: string;
  subdomain?: string;
} {
  const clean = rawSubdomain.trim().toLowerCase();
  if (!clean) {
    return {
      valid: false,
      error:
        "Please enter a valid gym subdomain (letters, numbers, and hyphens only).",
    };
  }

  if (!SUBDOMAIN_REGEX.test(clean)) {
    return {
      valid: false,
      error:
        "Please enter a valid gym subdomain (letters, numbers, and hyphens only).",
    };
  }

  if (RESERVED_SUBDOMAINS.has(clean)) {
    return {
      valid: false,
      error: "This subdomain is reserved for platform services.",
    };
  }

  return { valid: true, subdomain: clean };
}

/**
 * Dynamically computes a gym tenant's URL based on current window location and the gym subdomain.
 * Never hardcodes any domain name.
 */
export function buildTenantUrl(
  subdomain: string,
  currentHost?: string,
  currentProtocol?: string,
  currentPort?: string
): string {
  const host = (
    currentHost ||
    (typeof window !== "undefined" ? window.location.hostname : "localhost")
  )
    .trim()
    .toLowerCase();

  const protocol =
    currentProtocol ||
    (typeof window !== "undefined" ? window.location.protocol : "http:");

  const port =
    currentPort !== undefined
      ? currentPort
      : typeof window !== "undefined"
        ? window.location.port
        : "";

  const portSuffix = port ? `:${port}` : "";
  const cleanSubdomain = subdomain.trim().toLowerCase();

  // If on local dev (localhost / 127.0.0.1 / *.localhost)
  if (
    host === "localhost" ||
    host === "127.0.0.1" ||
    host.endsWith(".localhost")
  ) {
    return `${protocol}//${cleanSubdomain}.localhost${portSuffix}/`;
  }

  // If on a domain, find the apex host by stripping current tenant if present or www
  const currentTenant = getTenantFromHostname(host);
  let apexHost = host;
  if (currentTenant && host.startsWith(`${currentTenant}.`)) {
    apexHost = host.slice(currentTenant.length + 1);
  } else if (host.startsWith("www.")) {
    apexHost = host.slice(4);
  }

  return `${protocol}//${cleanSubdomain}.${apexHost}${portSuffix}/`;
}
