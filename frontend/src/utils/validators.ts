/**
 * Shared frontend validation module for FitGate.
 * Mirrors backend rules defined in apps.core.validators and docs/DESIGN.md.
 * All validator functions return an error string on invalid input, or null on success.
 */

export const RESERVED_SUBDOMAINS = new Set([
  "api",
  "admin",
  "www",
  "app",
  "mail",
  "localhost",
]);

/**
 * Filter phone input characters as typed.
 * Blocks letters and special characters; allows only digits, an optional leading +, spaces, and hyphens.
 */
export function filterPhoneInput(value: string): string {
  if (!value) return "";
  const hasPlus = value.startsWith("+");
  const sanitized = value.replace(/[^\d\s-]/g, "");
  return hasPlus
    ? "+" + sanitized.replace(/\+/g, "")
    : sanitized.replace(/\+/g, "");
}

/**
 * Normalize Ethiopian and international phone numbers to standard format (+251XXXXXXXXX or +XXXXXXXXX).
 */
export function normalizePhone(value: string): string {
  if (!value) return "";
  const trimmed = value.trim();
  const digits = trimmed.replace(/\D/g, "");
  if (!digits) return "";

  if (digits.startsWith("251")) {
    return `+251${digits.slice(3)}`;
  }
  if (digits.startsWith("09") || digits.startsWith("07")) {
    return `+251${digits.slice(1)}`;
  }
  if (
    (digits.startsWith("9") || digits.startsWith("7")) &&
    digits.length === 9
  ) {
    return `+251${digits}`;
  }
  return `+${digits}`;
}

/**
 * Validate phone number.
 * Returns error string or null if valid.
 */
export function validatePhone(
  value: string,
  isRequired: boolean = true
): string | null {
  if (!value || !value.trim()) {
    if (isRequired) {
      return "Phone number is required.";
    }
    return null;
  }

  const trimmed = value.trim();

  // Check character validity: only digits, spaces, hyphens, optional single leading +
  if (!/^\+?[\d\s-]+$/.test(trimmed)) {
    return "Phone number can only contain digits, an optional leading +, spaces, and hyphens.";
  }

  const digits = trimmed.replace(/\D/g, "");
  if (digits.length < 9 || digits.length > 15) {
    return "Phone number must contain between 9 and 15 digits.";
  }

  // Ethiopian number formats
  if (digits.startsWith("251")) {
    const suffix = digits.slice(3);
    if (suffix.length !== 9) {
      return "Ethiopian phone numbers must be 9 digits after +251 (e.g. +251911223344 or 0911223344).";
    }
    if (!suffix.startsWith("9") && !suffix.startsWith("7")) {
      return "Ethiopian mobile numbers must start with 9 or 7 (e.g. +251911223344 or 0911223344).";
    }
    return null;
  }

  if (digits.startsWith("09") || digits.startsWith("07")) {
    if (digits.length !== 10) {
      return "Ethiopian phone numbers must be 10 digits when starting with 0 (e.g. 0911223344 or 0711223344).";
    }
    return null;
  }

  if (
    (digits.startsWith("9") || digits.startsWith("7")) &&
    digits.length === 9
  ) {
    return null;
  }

  return null;
}

/**
 * Validate names (full name, gym name, contact person).
 * Letters of any script (Amharic included), spaces, apostrophes, hyphens, dots.
 * No digits allowed. 2 to 100 characters. Trimmed, not only spaces.
 */
export function validateName(
  value: string,
  fieldName: string = "Name",
  isRequiredOrMin: boolean | number = true,
  maxLen: number = 100
): string | null {
  const isRequired =
    typeof isRequiredOrMin === "boolean" ? isRequiredOrMin : true;
  const minLen = typeof isRequiredOrMin === "number" ? isRequiredOrMin : 2;

  if (!value || !value.trim()) {
    if (isRequired) {
      return `${fieldName} is required.`;
    }
    return null;
  }

  const trimmed = value.trim();

  if (trimmed.length < minLen) {
    return `${fieldName} must be at least ${minLen} characters.`;
  }
  if (trimmed.length > maxLen) {
    return `${fieldName} cannot exceed ${maxLen} characters.`;
  }

  // Disallow any digits
  if (/\d/.test(trimmed)) {
    return `${fieldName} cannot contain digits.`;
  }

  // Unicode letters (including Amharic / Ethiopic), spaces, apostrophe, hyphen, dot
  const validCharsRegex = /^[\p{L}\s'\-.]+$/u;
  if (!validCharsRegex.test(trimmed)) {
    return `${fieldName} can only contain letters, spaces, apostrophes, hyphens, and dots.`;
  }

  // Ensure at least one letter character is present
  if (!/\p{L}/u.test(trimmed)) {
    return `${fieldName} must contain letters.`;
  }

  return null;
}

/**
 * Validate email address format and length.
 */
export function validateEmail(
  value: string,
  isRequired: boolean = true
): string | null {
  if (!value || !value.trim()) {
    if (isRequired) {
      return "Email address is required.";
    }
    return null;
  }

  const trimmed = value.trim().toLowerCase();
  if (trimmed.length > 254) {
    return "Email address cannot exceed 254 characters.";
  }

  // RFC 5322 standard email regex
  const emailRegex =
    /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$/;
  if (!emailRegex.test(trimmed)) {
    return "Enter a valid email address.";
  }

  return null;
}

/**
 * Password live checklist requirements.
 */
export interface PasswordRequirements {
  minLength: boolean;
  notNumeric: boolean;
  notCommon: boolean;
  matchesConfirm: boolean;
  allValid: boolean;
  isValid: boolean;
  hasMinLength: boolean;
  hasNotOnlyDigits: boolean;
  hasNoCommon: boolean;
}

const COMMON_PASSWORDS = new Set([
  "password",
  "password123",
  "1234567890",
  "qwertyuiop",
  "admin12345",
  "pass123456",
  "welcome123",
  "fitgate123",
]);

export function checkPasswordRequirements(
  password: string,
  confirmPassword?: string
): PasswordRequirements {
  const minLength = (password || "").length >= 10;
  const notNumeric = !/^\d+$/.test(password || "");
  const notCommon = !COMMON_PASSWORDS.has((password || "").toLowerCase());
  const matchesConfirm =
    confirmPassword !== undefined
      ? Boolean(password) && password === confirmPassword
      : true;

  const allValid = minLength && notNumeric && notCommon && matchesConfirm;

  return {
    minLength,
    notNumeric,
    notCommon,
    matchesConfirm,
    allValid,
    isValid: allValid,
    hasMinLength: minLength,
    hasNotOnlyDigits: notNumeric,
    hasNoCommon: notCommon,
  };
}

/**
 * Decimal validator helper.
 */
function checkDecimalPlaces(val: number | string): boolean {
  const str = String(val);
  const parts = str.split(".");
  return parts.length < 2 || parts[1].length <= 2;
}

/**
 * Validate weight (20 to 400 kg, max 2 decimals).
 */
export function validateWeight(value: number | string): string | null {
  if (value === "" || value === null || value === undefined) {
    return "Weight is required.";
  }
  const num = Number(value);
  if (isNaN(num)) {
    return "Weight must be a valid number.";
  }
  if (!checkDecimalPlaces(value)) {
    return "Weight cannot have more than 2 decimal places.";
  }
  if (num < 20 || num > 400) {
    return "Weight must be between 20 and 400 kg.";
  }
  return null;
}

/**
 * Validate height (50 to 260 cm, max 2 decimals).
 */
export function validateHeight(value: number | string): string | null {
  if (value === "" || value === null || value === undefined) {
    return "Height is required.";
  }
  const num = Number(value);
  if (isNaN(num)) {
    return "Height must be a valid number.";
  }
  if (!checkDecimalPlaces(value)) {
    return "Height cannot have more than 2 decimal places.";
  }
  if (num < 50 || num > 260) {
    return "Height must be between 50 and 260 cm.";
  }
  return null;
}

/**
 * Validate waist (40 to 200 cm, max 2 decimals).
 */
export function validateWaist(
  value: number | string | null | undefined
): string | null {
  if (value === "" || value === null || value === undefined) {
    return null;
  }
  const num = Number(value);
  if (isNaN(num)) {
    return "Waist must be a valid number.";
  }
  if (!checkDecimalPlaces(value)) {
    return "Waist cannot have more than 2 decimal places.";
  }
  if (num < 40 || num > 200) {
    return "Waist circumference must be between 40 and 200 cm.";
  }
  return null;
}

/**
 * Validate neck (20 to 80 cm, max 2 decimals).
 */
export function validateNeck(
  value: number | string | null | undefined
): string | null {
  if (value === "" || value === null || value === undefined) {
    return null;
  }
  const num = Number(value);
  if (isNaN(num)) {
    return "Neck must be a valid number.";
  }
  if (!checkDecimalPlaces(value)) {
    return "Neck cannot have more than 2 decimal places.";
  }
  if (num < 20 || num > 80) {
    return "Neck circumference must be between 20 and 80 cm.";
  }
  return null;
}

/**
 * Validate hip (40 to 220 cm, max 2 decimals).
 */
export function validateHip(
  value: number | string | null | undefined
): string | null {
  if (value === "" || value === null || value === undefined) {
    return null;
  }
  const num = Number(value);
  if (isNaN(num)) {
    return "Hip must be a valid number.";
  }
  if (!checkDecimalPlaces(value)) {
    return "Hip cannot have more than 2 decimal places.";
  }
  if (num < 40 || num > 220) {
    return "Hip circumference must be between 40 and 220 cm.";
  }
  return null;
}

/**
 * Validate payment amount (> 0, <= 10,000,000 ETB, max 2 decimals).
 */
export function validatePaymentAmount(value: number | string): string | null {
  if (value === "" || value === null || value === undefined) {
    return "Payment amount is required.";
  }
  const num = Number(value);
  if (isNaN(num)) {
    return "Payment amount must be a valid number.";
  }
  if (!checkDecimalPlaces(value)) {
    return "Payment amount cannot have more than 2 decimal places.";
  }
  if (num <= 0) {
    return "Payment amount must be greater than 0.";
  }
  if (num > 10000000) {
    return "Payment amount cannot exceed 10,000,000 ETB.";
  }
  return null;
}

/**
 * Validate date of birth (not in future, not older than 120 years).
 */
export function validateDateOfBirth(
  value: string,
  isRequired: boolean = false
): string | null {
  if (!value) {
    if (isRequired) {
      return "Date of birth is required.";
    }
    return null;
  }

  const date = new Date(value);
  if (isNaN(date.getTime())) {
    return "Date of birth must be a valid date (YYYY-MM-DD).";
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  if (date > today) {
    return "Date of birth cannot be in the future.";
  }

  const earliest = new Date(today);
  earliest.setFullYear(earliest.getFullYear() - 120);

  if (date < earliest) {
    return "Date of birth cannot be older than 120 years.";
  }

  return null;
}

/**
 * Validate date range (from <= to).
 */
export function validateDateRange(from: string, to: string): string | null {
  if (!from || !to) return null;

  const fromDate = new Date(from);
  const toDate = new Date(to);

  if (isNaN(fromDate.getTime()) || isNaN(toDate.getTime())) {
    return null;
  }

  if (fromDate > toDate) {
    return "From date cannot be after to date.";
  }

  return null;
}

/**
 * Validate text length. Flexible parameter order:
 * validateTextLength(value, fieldName, min, max) OR validateTextLength(value, min, max, fieldName)
 */
export function validateTextLength(
  value: string,
  arg2: string | number = "Text",
  arg3: number = 0,
  arg4: number | string = 500
): string | null {
  let fieldName = "Text";
  let minLen = 0;
  let maxLen = 500;

  if (typeof arg2 === "number") {
    minLen = arg2;
    maxLen = typeof arg3 === "number" ? arg3 : 500;
    fieldName = typeof arg4 === "string" ? arg4 : "Text";
  } else {
    fieldName = arg2;
    minLen = typeof arg3 === "number" ? arg3 : 0;
    maxLen = typeof arg4 === "number" ? arg4 : 500;
  }

  const trimmed = (value || "").trim();
  if (trimmed.length < minLen) {
    return `${fieldName} must be at least ${minLen} character${minLen !== 1 ? "s" : ""}.`;
  }
  if (trimmed.length > maxLen) {
    return `${fieldName} cannot exceed ${maxLen} characters.`;
  }
  return null;
}

/**
 * Validate subdomain (DNS label format).
 */
export function validateSubdomain(value: string): string | null {
  if (!value || !value.trim()) {
    return "Subdomain is required.";
  }
  const clean = value.trim().toLowerCase();
  const regex = /^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$/;
  if (!regex.test(clean)) {
    return "Subdomain must be a valid DNS label (lowercase alphanumeric and hyphens, 1–63 chars, no leading/trailing hyphens).";
  }
  if (RESERVED_SUBDOMAINS.has(clean)) {
    return `'${clean}' is a reserved subdomain.`;
  }
  return null;
}

/**
 * Validate hex color code.
 */
export function validateHexColor(
  value: string,
  fieldName: string = "Brand color"
): string | null {
  if (!value) return null;
  const clean = value.trim();
  if (!/^#[0-9a-fA-F]{6}$/.test(clean)) {
    return `${fieldName} must be a valid 6-character hex code (e.g. #2563EB).`;
  }
  return null;
}

/**
 * Helper to auto-focus the first field with an error on submit.
 */
export function focusFirstInvalidField(
  fieldIds: string[] | Record<string, unknown>
): void {
  if (!fieldIds) return;
  const ids = Array.isArray(fieldIds) ? fieldIds : Object.keys(fieldIds);
  for (const id of ids) {
    const el = document.getElementById(id);
    if (el) {
      el.focus();
      if (typeof el.scrollIntoView === "function") {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
      break;
    }
  }
}
