/**
 * Utilities and presets for gym tenant landing page customization.
 * Allows gym owners to customize the hero banner, motto, headline, cover photo,
 * operating hours, and aesthetic colors of their public gym portal.
 */

export interface GymLandingCustomization {
  heroMotto?: string;
  heroHeadline?: string;
  heroSubtitle?: string;
  heroImagePreset?: string;
  customHeroImage?: string;
  operatingHours?: string;
  announcement?: string;
}

export interface ImagePreset {
  id: string;
  name: string;
  url: string;
}

export const HERO_IMAGE_PRESETS: ImagePreset[] = [
  {
    id: "modern-iron",
    name: "Modern Strength & Machines",
    url: "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=1200&q=80",
  },
  {
    id: "power-lifting",
    name: "Powerlifting & Barbells",
    url: "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=1200&q=80",
  },
  {
    id: "functional-hiit",
    name: "Functional HIIT & Agility",
    url: "https://images.unsplash.com/photo-1581009146145-b5ef050c2e1e?auto=format&fit=crop&w=1200&q=80",
  },
  {
    id: "coaching-focus",
    name: "Personal Coaching & Dumbbells",
    url: "https://images.unsplash.com/photo-1583454110551-21f2fa2afe61?auto=format&fit=crop&w=1200&q=80",
  },
  {
    id: "discipline-athletic",
    name: "Athletic Conditioning",
    url: "https://images.unsplash.com/photo-1517836357463-d25dfeac3438?auto=format&fit=crop&w=1200&q=80",
  },
];

export interface ColorPreset {
  name: string;
  hex: string;
}

export const BRAND_COLOR_PRESETS: ColorPreset[] = [
  { name: "Electric Lime", hex: "#A3E635" },
  { name: "FitGate Blue", hex: "#2563EB" },
  { name: "Crimson Flame", hex: "#E11D48" },
  { name: "Blaze Orange", hex: "#F97316" },
  { name: "Emerald Energy", hex: "#10B981" },
  { name: "Cyber Violet", hex: "#8B5CF6" },
  { name: "Golden Power", hex: "#F59E0B" },
];

const STORAGE_PREFIX = "fitgate_gym_landing_customization_";

export function getGymLandingCustomization(
  subdomainOrId?: string | null
): GymLandingCustomization {
  if (typeof window === "undefined" || !window.localStorage) {
    return {};
  }
  const key = `${STORAGE_PREFIX}${subdomainOrId || "default"}`;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return {};
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

export function saveGymLandingCustomization(
  subdomainOrId: string | null | undefined,
  customization: GymLandingCustomization
): void {
  if (typeof window === "undefined" || !window.localStorage) {
    return;
  }
  const key = `${STORAGE_PREFIX}${subdomainOrId || "default"}`;
  try {
    window.localStorage.setItem(key, JSON.stringify(customization));
  } catch {
    // Ignore storage quota errors
  }
}

export function resolveHeroImage(
  customization: GymLandingCustomization,
  fallbackPresetId = "modern-iron"
): string {
  if (customization.customHeroImage && customization.customHeroImage.trim()) {
    return customization.customHeroImage.trim();
  }
  if (customization.heroImagePreset) {
    const matched = HERO_IMAGE_PRESETS.find(
      (p) => p.id === customization.heroImagePreset
    );
    if (matched) return matched.url;
  }
  const defaultPreset = HERO_IMAGE_PRESETS.find(
    (p) => p.id === fallbackPresetId
  );
  return defaultPreset?.url || HERO_IMAGE_PRESETS[0].url;
}
