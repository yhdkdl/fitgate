export const PAUSE_DURATION_MS = 3000;

/**
 * Pure cooldown helper to prevent multiple reads within PAUSE_DURATION_MS.
 * Exported so unit tests can directly verify the 3-second pause behavior.
 */
export function checkQrCooldown(
  now: number,
  lastScannedTime: number,
  isPaused: boolean,
  isProcessing: boolean
): boolean {
  if (isPaused) return false;
  if (isProcessing) return false;
  if (now - lastScannedTime < PAUSE_DURATION_MS) return false;
  return true;
}
