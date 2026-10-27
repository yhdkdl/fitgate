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
      "Core multi-tenant platform & member management",
      "QR code attendance check-in & verification",
      "Manual cash recording & Chapa online payments",
      "Owner & manager operational dashboard",
      "Member self-service portal & profile",
    ],
    features: [
      { name: "Core membership management", included: true },
      { name: "QR code attendance check-in", included: true },
      { name: "Chapa online & cash payments", included: true },
      { name: "Operational dashboard & member directory", included: true },
      { name: "Trainer module & client assignment", included: false },
      { name: "AI personal training workout plans", included: false },
      { name: "Advanced analytics & revenue trends", included: false },
      { name: "Group fitness classes & schedules", included: false },
      { name: "Membership freeze workflow", included: false },
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
      "Advanced analytics: attendance heatmap & retention",
      "Group fitness classes & schedule management",
      "Member freeze request workflow",
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
