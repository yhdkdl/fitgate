/**
 * Single source of truth for FitGate subscription tiers and pricing.
 * Prices are yearly in Ethiopian Birr (ETB), matching SPEC §3.
 * Changing any price or tier attribute is a one-line edit.
 */

export interface PricingFeature {
  name: string;
  included: boolean;
}

export interface PricingTier {
  id: "starter" | "growth" | "pro";
  name: string;
  badge?: string;
  tagline: string;
  pricePerYearETB: number; // Single source of truth for yearly tier price
  popular?: boolean;
  highlights: string[];
  features: PricingFeature[];
}

export const PLATFORM_PRICING_TIERS: PricingTier[] = [
  {
    id: "starter",
    name: "Starter",
    tagline: "Essential digital operations for single-branch gyms.",
    pricePerYearETB: 12000,
    highlights: [
      "Core membership management, plans & payments (cash, bank, Chapa)",
      "QR code check-in & basic operational dashboard",
      "Equipment registry, unit prices & total investment",
      "CSV data exports & bank receipt verification",
      "Super Admin platform notices & member profile/password",
    ],
    features: [
      { name: "Core membership management & plans", included: true },
      { name: "QR code attendance check-in", included: true },
      { name: "Payments (Cash, Bank Transfer, Chapa)", included: true },
      { name: "Operational dashboard & audit log", included: true },
      { name: "Equipment registry, prices & total investment", included: true },
      { name: "CSV data exports & receipt verification", included: true },
      { name: "Platform notices & member self-service", included: true },
      { name: "Professional Trainer module & measurements", included: false },
      { name: "AI personal training workout plans", included: false },
      { name: "Membership freeze workflow", included: false },
      { name: "Premium analytics (revenue by plan)", included: false },
      { name: "Group fitness classes & schedules", included: false },
      { name: "Gym notice board & Telegram bridge", included: false },
      { name: "Expenses ledger & financial reports", included: false },
      { name: "Multi-branch gym management", included: false },
    ],
  },
  {
    id: "growth",
    name: "Growth",
    badge: "Most Popular",
    tagline:
      "For growing gyms delivering professional coaching and digital fitness services.",
    pricePerYearETB: 30000,
    popular: true,
    highlights: [
      "Everything in Starter, plus:",
      "Professional Trainer module & body measurements",
      "AI personal training plan generation & intake",
      "Membership freeze workflow & settings",
      "Group fitness classes & schedules",
      "Gym notice board, Telegram bridge & Expenses and Reports",
    ],
    features: [
      { name: "Core membership management & plans", included: true },
      { name: "QR code attendance check-in", included: true },
      { name: "Payments (Cash, Bank Transfer, Chapa)", included: true },
      { name: "Operational dashboard & audit log", included: true },
      { name: "Equipment registry, prices & total investment", included: true },
      { name: "CSV data exports & receipt verification", included: true },
      { name: "Platform notices & member self-service", included: true },
      { name: "Professional Trainer module & measurements", included: true },
      { name: "AI personal training workout plans", included: true },
      { name: "Membership freeze workflow", included: true },
      { name: "Premium analytics (revenue by plan)", included: true },
      { name: "Group fitness classes & schedules", included: true },
      { name: "Gym notice board & Telegram bridge", included: true },
      { name: "Expenses ledger & financial reports", included: true },
      { name: "Multi-branch gym management", included: false },
    ],
  },
  {
    id: "pro",
    name: "Pro",
    badge: "Multi-Branch",
    tagline: "Complete multi-branch gym networks with unified management.",
    pricePerYearETB: 60000,
    highlights: [
      "Everything in Growth, plus:",
      "Multi-branch management under one unified domain",
      "Branch-scoped staff & multi-branch member plans",
      "Network-wide attendance & revenue visibility",
      "Priority onboarding & setup assistance",
    ],
    features: [
      { name: "Core membership management", included: true },
      { name: "QR code attendance check-in", included: true },
      { name: "Chapa online & cash payments", included: true },
      { name: "Operational dashboard & member directory", included: true },
      { name: "Trainer module & client assignment", included: true },
      { name: "AI personal training workout plans", included: true },
      { name: "Advanced analytics & revenue trends", included: true },
      { name: "Group fitness classes & schedules", included: true },
      { name: "Membership freeze workflow", included: true },
      { name: "Multi-branch gym management", included: true },
    ],
  },
];

export function formatPriceETB(price: number): string {
  return `${price.toLocaleString()} ETB / year`;
}
