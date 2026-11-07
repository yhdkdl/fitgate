/**
 * Builds the front-desk contact line from the gym's CURRENT public phone and location/address.
 * Leaves out whichever is empty; never returns empty brackets or a generic placeholder.
 * Example: "(Phone: +251911223344 · Address: Bole, Addis Ababa)"
 */
export function formatGymContactLine(
  phone?: string | null,
  location?: string | null
): string {
  const parts: string[] = [];
  const cleanPhone = phone?.trim();
  const cleanLoc = location?.trim();
  if (cleanPhone) parts.push(`Phone: ${cleanPhone}`);
  if (cleanLoc) parts.push(`Address: ${cleanLoc}`);
  if (parts.length === 0) return "";
  return `(${parts.join(" · ")})`;
}
