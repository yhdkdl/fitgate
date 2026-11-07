const STORAGE_KEY = "fitgate_seen_platform_notices";

export function getSeenPlatformNoticeIds(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function markPlatformNoticesSeen(ids: string[]): void {
  try {
    const existing = getSeenPlatformNoticeIds();
    const merged = Array.from(new Set([...existing, ...ids]));
    localStorage.setItem(STORAGE_KEY, JSON.stringify(merged));
  } catch {
    // Ignore localStorage errors in restricted environments
  }
}
