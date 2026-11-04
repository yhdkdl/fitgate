export interface MaintenanceLog {
  id: string;
  equipment: string;
  reported_by: string | null;
  reported_by_name: string;
  issue_reason: string;
  other_details: string;
  reported_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
  resolved_by_name: string;
  resolution_notes: string;
}

export interface EquipmentItem {
  id: string;
  name: string;
  category: string;
  serial_number: string;
  quantity: number;
  min_qty_threshold: number | null;
  condition:
    "good" | "needs_maintenance" | "under_maintenance" | "out_of_service";
  purchase_date: string | null;
  unit_purchase_price_etb?: string | number | null;
  record_as_expense?: boolean;
  branch_id?: string | null;
  is_low_quantity: boolean;
  maintenance_logs?: MaintenanceLog[];
  created_at: string;
  updated_at: string;
}

export interface EquipmentCreatePayload {
  name: string;
  category: string;
  serial_number?: string;
  quantity: number;
  min_qty_threshold?: number | null;
  condition?: string;
  purchase_date?: string | null;
  unit_purchase_price_etb?: string | number | null;
  record_as_expense?: boolean;
}

export interface EquipmentUpdatePayload {
  name?: string;
  category?: string;
  serial_number?: string;
  quantity?: number;
  min_qty_threshold?: number | null;
  condition?: string;
  purchase_date?: string | null;
  unit_purchase_price_etb?: string | number | null;
  record_as_expense?: boolean;
}

export interface ReportIssuePayload {
  issue_reason: string;
  other_details?: string;
}

export interface UpdateConditionPayload {
  condition: string;
  resolution_notes?: string;
}

export const EQUIPMENT_CATEGORIES: Array<{ code: string; label: string }> = [
  { code: "barbell", label: "Barbell & Plates" },
  { code: "dumbbells", label: "Dumbbells" },
  { code: "cable_machine", label: "Cable Machine" },
  { code: "resistance_bands", label: "Resistance Bands" },
  { code: "kettlebells", label: "Kettlebells" },
  { code: "pull_up_bar", label: "Pull-up Bar" },
  { code: "bench", label: "Bench" },
  { code: "leg_press", label: "Leg Press" },
  { code: "squat_rack", label: "Squat Rack" },
  { code: "cardio_machines", label: "Cardio Machines" },
  { code: "bodyweight", label: "Bodyweight / Calisthenics" },
  { code: "other", label: "Other" },
];

export const CONDITION_LABELS: Record<
  string,
  { label: string; variant: "success" | "warning" | "danger" | "neutral" }
> = {
  good: { label: "Good", variant: "success" },
  needs_maintenance: { label: "Needs Maintenance", variant: "warning" },
  under_maintenance: { label: "Under Maintenance", variant: "neutral" },
  out_of_service: { label: "Out of Service", variant: "danger" },
};

export const ISSUE_REASONS: Array<{ code: string; label: string }> = [
  { code: "broken", label: "Broken" },
  { code: "worn_out", label: "Worn out" },
  { code: "noisy_unsafe", label: "Noisy or unsafe" },
  { code: "other", label: "Other" },
];
