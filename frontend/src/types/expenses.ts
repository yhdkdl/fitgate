export interface Expense {
  id: string;
  amount_etb: string | number;
  category:
    | "rent"
    | "salaries"
    | "utilities"
    | "equipment"
    | "maintenance"
    | "marketing"
    | "supplies"
    | "other";
  category_display: string;
  note: string;
  incurred_on: string;
  logged_by: string | null;
  logged_by_name: string;
  equipment: string | null;
  equipment_name: string;
  is_void: boolean;
  is_voided?: boolean;
  voided_at: string | null;
  voided_by: string | null;
  voided_by_name: string;
  void_reason: string;
  created_at: string;
  updated_at: string;
}

export interface ExpenseCreatePayload {
  amount_etb: number | string;
  category: string;
  note?: string;
  incurred_on?: string;
  equipment?: string | null;
}

export interface ExpenseVoidPayload {
  void_reason: string;
}

export interface FinancialReportCategoryItem {
  total_etb: string;
  count: number;
}

export interface FinancialReportPlanItem {
  plan_id: string;
  plan_name: string;
  total_etb: string;
  payment_count: number;
}

export interface FinancialReport {
  period: {
    start_date: string | null;
    end_date: string | null;
  };
  confirmed_gross_revenue_etb: string;
  reversed_payments_etb: string;
  net_revenue_etb: string;
  total_expenses_etb: string;
  net_income_etb: string;
  expenses_by_category: Record<string, FinancialReportCategoryItem>;
  revenue_by_plan: FinancialReportPlanItem[];
}

export interface AttendanceReportDailyItem {
  date: string;
  count: number;
}

export interface AttendanceReport {
  period: {
    start_date: string | null;
    end_date: string | null;
  };
  total_check_ins: number;
  unique_members: number;
  qr_check_ins: number;
  manual_override_check_ins: number;
  daily_counts: AttendanceReportDailyItem[];
}

export const EXPENSE_CATEGORIES: Array<{ code: string; label: string }> = [
  { code: "rent", label: "Rent & Facilities" },
  { code: "salaries", label: "Staff Salaries & Wages" },
  { code: "utilities", label: "Utilities (Water, Electricity, Internet)" },
  { code: "equipment", label: "Equipment Purchase & Upgrades" },
  { code: "maintenance", label: "Equipment Maintenance & Repairs" },
  { code: "marketing", label: "Marketing & Advertising" },
  { code: "supplies", label: "Cleaning & Operational Supplies" },
  { code: "other", label: "Other Expenses" },
];
