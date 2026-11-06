import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ExpensesSection } from "../components/expenses/ExpensesSection";
import * as expensesApi from "../api/expenses";
import type {
  Expense,
  FinancialReport,
  AttendanceReport,
} from "../types/expenses";

const mockExpenses: Expense[] = [
  {
    id: "exp-1",
    amount_etb: "25000.00",
    category: "rent",
    category_display: "Rent & Facilities",
    note: "November gym space rent",
    incurred_on: "2026-11-01",
    logged_by: "user-1",
    logged_by_name: "Owner User",
    equipment: null,
    equipment_name: "",
    is_void: false,
    voided_at: null,
    voided_by: null,
    voided_by_name: "",
    void_reason: "",
    created_at: "2026-11-01T10:00:00Z",
    updated_at: "2026-11-01T10:00:00Z",
  },
  {
    id: "exp-2",
    amount_etb: "8000.00",
    category: "utilities",
    category_display: "Utilities (Water, Electricity, Internet)",
    note: "Water & electricity bill",
    incurred_on: "2026-11-02",
    logged_by: "user-1",
    logged_by_name: "Owner User",
    equipment: null,
    equipment_name: "",
    is_void: false,
    voided_at: null,
    voided_by: null,
    voided_by_name: "",
    void_reason: "",
    created_at: "2026-11-02T10:00:00Z",
    updated_at: "2026-11-02T10:00:00Z",
  },
  {
    id: "exp-3",
    amount_etb: "1500.00",
    category: "supplies",
    category_display: "Cleaning & Operational Supplies",
    note: "Mistaken cleaning supplies entry",
    incurred_on: "2026-11-02",
    logged_by: "user-1",
    logged_by_name: "Owner User",
    equipment: null,
    equipment_name: "",
    is_void: true,
    voided_at: "2026-11-02T12:00:00Z",
    voided_by: "user-1",
    voided_by_name: "Owner User",
    void_reason: "Entered wrong invoice amount",
    created_at: "2026-11-02T11:00:00Z",
    updated_at: "2026-11-02T12:00:00Z",
  },
];

const mockFinancialReport: FinancialReport = {
  period: { start_date: "2026-11-01", end_date: "2026-11-30" },
  confirmed_gross_revenue_etb: "100000.00",
  reversed_payments_etb: "0.00",
  net_revenue_etb: "100000.00",
  total_expenses_etb: "33000.00",
  net_income_etb: "67000.00",
  expenses_by_category: {
    rent: { total_etb: "25000.00", count: 1 },
    utilities: { total_etb: "8000.00", count: 1 },
  },
  revenue_by_plan: [
    {
      plan_id: "plan-1",
      plan_name: "Standard Monthly",
      total_etb: "60000.00",
      payment_count: 40,
    },
    {
      plan_id: "plan-2",
      plan_name: "Trainer Monthly",
      total_etb: "40000.00",
      payment_count: 20,
    },
  ],
};

const mockAttendanceReport: AttendanceReport = {
  period: { start_date: "2026-11-01", end_date: "2026-11-30" },
  total_check_ins: 150,
  unique_members: 65,
  qr_check_ins: 130,
  manual_override_check_ins: 20,
  daily_counts: [
    { date: "2026-11-01", count: 70 },
    { date: "2026-11-02", count: 80 },
  ],
};

describe("ExpensesSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(expensesApi, "listExpenses").mockResolvedValue(mockExpenses);
    vi.spyOn(expensesApi, "createExpense").mockResolvedValue(mockExpenses[0]);
    vi.spyOn(expensesApi, "voidExpense").mockResolvedValue({
      ...mockExpenses[1],
      is_void: true,
      void_reason: "Duplicate charge",
    });
    vi.spyOn(expensesApi, "getFinancialReport").mockResolvedValue(
      mockFinancialReport
    );
    vi.spyOn(expensesApi, "getAttendanceReport").mockResolvedValue(
      mockAttendanceReport
    );
  });

  it("denies access to non-managerial roles", () => {
    render(<ExpensesSection userRole="member" />);
    expect(screen.getByText(/Access Denied/i)).toBeInTheDocument();
  });

  it("renders active expenses and computes active total excluding voided", async () => {
    render(<ExpensesSection userRole="owner" />);

    // Active total: 25,000 + 8,000 = 33,000.00 ETB
    await waitFor(() => {
      expect(screen.getByTestId("total-active-expenses")).toHaveTextContent(
        "33,000.00 ETB"
      );
    });
    expect(screen.getByText("November gym space rent")).toBeInTheDocument();
    expect(screen.getByText("Water & electricity bill")).toBeInTheDocument();
  });

  it("opens modal and records a new expense", async () => {
    render(<ExpensesSection userRole="owner" />);

    await waitFor(() => {
      expect(screen.getByTestId("btn-open-log-expense")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("btn-open-log-expense"));

    const amountInput = screen.getByTestId("input-expense-amount");
    fireEvent.change(amountInput, { target: { value: "4500.00" } });

    const noteInput = screen.getByTestId("input-expense-note");
    fireEvent.change(noteInput, { target: { value: "Social media ad boost" } });

    fireEvent.click(screen.getByTestId("btn-save-expense"));

    await waitFor(() => {
      expect(expensesApi.createExpense).toHaveBeenCalledWith(
        expect.objectContaining({
          amount_etb: 4500,
          category: "other",
          note: "Social media ad boost",
        })
      );
    });
  });

  it("opens void modal and requires void reason", async () => {
    render(<ExpensesSection userRole="manager" />);

    await waitFor(() => {
      expect(screen.getByTestId("btn-void-exp-1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("btn-void-exp-1"));

    expect(screen.getByText("Void Expense Entry")).toBeInTheDocument();

    const reasonInput = screen.getByTestId("input-void-reason");
    fireEvent.change(reasonInput, {
      target: { value: "Incorrect account billed" },
    });

    fireEvent.click(screen.getByTestId("btn-confirm-void"));

    await waitFor(() => {
      expect(expensesApi.voidExpense).toHaveBeenCalledWith(
        "exp-1",
        "Incorrect account billed"
      );
    });
  });

  it("switches to financial report tab and displays net income metrics", async () => {
    render(<ExpensesSection userRole="owner" />);

    await waitFor(() => {
      expect(screen.getByTestId("tab-financial-report")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("tab-financial-report"));

    await waitFor(() => {
      expect(screen.getByTestId("stat-net-revenue")).toHaveTextContent(
        "100,000.00 ETB"
      );
      expect(screen.getByTestId("stat-total-expenses")).toHaveTextContent(
        "33,000.00 ETB"
      );
      expect(screen.getByTestId("stat-net-income")).toHaveTextContent(
        "67,000.00 ETB"
      );
    });
  });

  it("switches to attendance report tab and displays check-in summary", async () => {
    render(<ExpensesSection userRole="owner" />);

    await waitFor(() => {
      expect(screen.getByTestId("tab-attendance-report")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("tab-attendance-report"));

    await waitFor(() => {
      expect(screen.getByTestId("stat-total-checkins")).toHaveTextContent(
        "150"
      );
      expect(screen.getByTestId("stat-unique-members")).toHaveTextContent("65");
    });
  });
});
