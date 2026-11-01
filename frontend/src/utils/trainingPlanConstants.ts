export interface PlanOptionItem {
  code: string;
  label: string;
}

export const WEEKLY_FOCUS_OPTIONS: PlanOptionItem[] = [
  { code: "no_focus", label: "No specific focus" },
  { code: "legs", label: "Legs & Lower Body" },
  { code: "upper_body", label: "Upper Body" },
  { code: "core_posture", label: "Core & Posture" },
  { code: "cardio_conditioning", label: "Cardio Conditioning" },
  { code: "recovery_mobility", label: "Recovery & Mobility" },
  { code: "other", label: "Other" },
];

export const REJECTION_REASONS_OPTIONS: PlanOptionItem[] = [
  { code: "wrong_phase", label: "Wrong Phase / Progression" },
  { code: "too_hard", label: "Too Hard / High Volume" },
  { code: "too_easy", label: "Too Easy / Low Intensity" },
  { code: "contravenes_limitation", label: "Contravenes Health Limitation" },
  { code: "missing_equipment", label: "Missing Required Gym Equipment" },
  { code: "inappropriate_food", label: "Inappropriate Food / Fasting Issue" },
  { code: "other", label: "Other reason" },
];
