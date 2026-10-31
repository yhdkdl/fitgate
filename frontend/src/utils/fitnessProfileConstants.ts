export interface SelectOption {
  code: string;
  label: string;
}

export const HEALTH_LIMITATION_OPTIONS: SelectOption[] = [
  { code: "none", label: "None" },
  { code: "lower_back", label: "Lower back" },
  { code: "knee", label: "Knee" },
  { code: "shoulder", label: "Shoulder" },
  { code: "neck", label: "Neck" },
  { code: "hip", label: "Hip" },
  { code: "ankle_foot", label: "Ankle or foot" },
  { code: "wrist_elbow", label: "Wrist or elbow" },
  { code: "high_blood_pressure", label: "High blood pressure" },
  { code: "heart_condition", label: "Heart condition" },
  { code: "diabetes", label: "Diabetes" },
  { code: "asthma", label: "Asthma" },
  { code: "pregnancy_postpartum", label: "Pregnancy or postpartum" },
  { code: "recent_surgery", label: "Recent surgery" },
  { code: "other", label: "Other" },
];

export const MEDICAL_CAUTION_CODES = new Set([
  "heart_condition",
  "high_blood_pressure",
  "diabetes",
  "asthma",
  "pregnancy_postpartum",
  "recent_surgery",
]);

export function hasMedicalCaution(codes: string[] = []): boolean {
  return codes.some((code) => MEDICAL_CAUTION_CODES.has(code));
}

export const EQUIPMENT_ACCESS_OPTIONS: SelectOption[] = [
  { code: "full_gym", label: "Full gym equipment" },
  { code: "free_weights", label: "Free weights (dumbbells and barbells)" },
  { code: "machines", label: "Machines" },
  { code: "cables", label: "Cables" },
  { code: "kettlebells", label: "Kettlebells" },
  { code: "resistance_bands", label: "Resistance bands" },
  { code: "cardio_machines", label: "Cardio machines" },
  { code: "bodyweight_only", label: "Bodyweight only" },
  { code: "other", label: "Other" },
];

export const DIETARY_NOTE_OPTIONS: SelectOption[] = [
  { code: "none", label: "No restrictions" },
  { code: "vegetarian", label: "Vegetarian" },
  { code: "vegan", label: "Vegan" },
  { code: "no_dairy", label: "No dairy" },
  { code: "no_eggs", label: "No eggs" },
  { code: "no_nuts", label: "No nuts" },
  { code: "no_fish", label: "No fish" },
  { code: "no_gluten", label: "No gluten" },
  { code: "halal", label: "Halal" },
  { code: "orthodox_fasting", label: "Orthodox fasting" },
  { code: "ramadan_fasting", label: "Ramadan fasting" },
  { code: "other", label: "Other" },
];

export const WEEKLY_FOCUS_OPTIONS: SelectOption[] = [
  { code: "no_focus", label: "No special focus" },
  { code: "legs", label: "Legs" },
  { code: "upper_body", label: "Upper body" },
  { code: "core", label: "Core" },
  { code: "cardio", label: "Cardio" },
  { code: "mobility", label: "Mobility" },
  { code: "other", label: "Other" },
];

export const PLAN_REJECTION_OPTIONS: SelectOption[] = [
  { code: "too_hard", label: "Too hard" },
  { code: "too_easy", label: "Too easy" },
  {
    code: "exercises_not_suitable",
    label: "Exercises not suitable for member limits",
  },
  { code: "equipment_not_available", label: "Equipment not available" },
  { code: "nutrition_not_suitable", label: "Nutrition not suitable" },
  { code: "other", label: "Other" },
];
