import { apiFetch } from "./client";
import type {
  Expense,
  ExpenseCreatePayload,
  ExpenseVoidPayload,
  FinancialReport,
  AttendanceReport,
} from "../types/expenses";

export async function listExpenses(params?: {
  category?: string;
  include_void?: boolean;
}): Promise<Expense[]> {
  const query = new URLSearchParams();
  if (params?.category) {
    query.set("category", params.category);
  }
  if (params?.include_void) {
    query.set("include_void", "true");
  }
  const qs = query.toString();
  return apiFetch<Expense[]>(`/api/gym/expenses/${qs ? `?${qs}` : ""}`);
}

export async function createExpense(payload: ExpenseCreatePayload): Promise<Expense> {
  return apiFetch<Expense>("/api/gym/expenses/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function voidExpense(id: string, reason: string): Promise<Expense> {
  const payload: ExpenseVoidPayload = { void_reason: reason };
  return apiFetch<Expense>(`/api/gym/expenses/${id}/void/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getFinancialReport(params?: {
  start_date?: string;
  end_date?: string;
}): Promise<FinancialReport> {
  const query = new URLSearchParams();
  if (params?.start_date) query.set("start_date", params.start_date);
  if (params?.end_date) query.set("end_date", params.end_date);
  const qs = query.toString();
  return apiFetch<FinancialReport>(`/api/gym/reports/financial/${qs ? `?${qs}` : ""}`);
}

export async function getAttendanceReport(params?: {
  start_date?: string;
  end_date?: string;
}): Promise<AttendanceReport> {
  const query = new URLSearchParams();
  if (params?.start_date) query.set("start_date", params.start_date);
  if (params?.end_date) query.set("end_date", params.end_date);
  const qs = query.toString();
  return apiFetch<AttendanceReport>(`/api/gym/reports/attendance/${qs ? `?${qs}` : ""}`);
}
